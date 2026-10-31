"""Billing: Stripe Checkout, Billing Portal, current-plan status, and the
Stripe webhook.

Billing is per **account** (the owner's Supabase ``sub``). The webhook is public
(Stripe authenticates itself with a signed ``Stripe-Signature`` header); the
customer-facing endpoints are admin-gated at the router level in ``main.py`` and
additionally require the caller to be an account **owner** (team members see the
plan read-only). Super-admins are comped: unlimited entitlements on their own
account, never billed.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, is_superadmin, require_admin
from app.core.db import get_session
from app.core.config import settings
from app.core.plans import (
    PLANS,
    SUPERADMIN_LIMITS,
    plan_price_id,
    price_id_to_plan,
)
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.team_repository import TeamRepository
from app.schemas.billing import (
    BillingOut,
    CheckoutRequest,
    CheckoutResponse,
    Entitlements,
    KnowledgeUsageOut,
    PortalResponse,
    TopupRequest,
    UsageOut,
)
from app.services import billing, stripe_service
from app.services.stripe_service import BillingError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


async def _resolve_account(session: AsyncSession, user: AdminUser) -> tuple[str, bool]:
    """Return ``(account_owner_id, manageable)`` for the caller.

    An owner (any user with their own sites, or a brand-new user) manages their
    own account. A pure team member's billing account is their team owner's, and
    is read-only for them.
    """
    profile_repo = ProfileRepository(session)
    owned = await profile_repo.list_for_owner(user.id)
    if owned:
        return user.id, True
    teams = await TeamRepository(session).list_teams_for_user(user.id, user.email)
    if teams:
        return teams[0].owner_user_id, False
    return user.id, True


def _reset_at() -> str:
    """ISO timestamp for the first of next month (UTC) - when usage resets."""
    now = datetime.now(timezone.utc)
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
    return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc).isoformat()


@router.get("", response_model=BillingOut)
async def get_billing(
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> BillingOut:
    account_owner, manageable = await _resolve_account(session, user)
    repo = SubscriptionRepository(session)
    period = billing.current_period()

    knowledge_repo = KnowledgeRepository(session)

    if is_superadmin(user):
        used, bonus = await repo.usage(user.id, period)
        chunks_used = await knowledge_repo.count_chunks_for_owner(user.id)
        await session.commit()
        limits = SUPERADMIN_LIMITS
        return BillingOut(
            plan="superadmin",
            status="active",
            manageable=False,
            has_stripe_customer=False,
            entitlements=Entitlements(**limits.__dict__),
            usage=UsageOut(
                messages_used=used,
                messages_limit=None,
                bonus_messages=bonus,
                resets_at=_reset_at(),
            ),
            knowledge=KnowledgeUsageOut(chunks_used=chunks_used, chunks_limit=None),
        )

    subscription = await repo.get_or_create_trial(account_owner)
    used, bonus = await repo.usage(account_owner, period)
    chunks_used = await knowledge_repo.count_chunks_for_owner(account_owner)
    limits = billing.limits_for(subscription)
    status = billing.effective_status(subscription)
    await session.commit()
    return BillingOut(
        plan=subscription.plan,
        status=status,
        manageable=manageable,
        has_stripe_customer=bool(subscription.stripe_customer_id),
        billing_interval=subscription.billing_interval,
        trial_ends_at=(
            subscription.trial_ends_at.isoformat()
            if subscription.trial_ends_at
            else None
        ),
        current_period_end=(
            subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None
        ),
        entitlements=Entitlements(**limits.__dict__),
        usage=UsageOut(
            messages_used=used,
            messages_limit=limits.messages,
            bonus_messages=bonus,
            resets_at=_reset_at(),
        ),
        knowledge=KnowledgeUsageOut(
            chunks_used=chunks_used, chunks_limit=limits.knowledge_chunks
        ),
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> CheckoutResponse:
    if is_superadmin(user):
        raise HTTPException(status_code=400, detail="This account is not billed.")
    account_owner, manageable = await _resolve_account(session, user)
    if not manageable:
        raise HTTPException(
            status_code=403, detail="Billing is managed by your account owner."
        )
    if not settings.app_base_url:
        raise HTTPException(status_code=503, detail="Billing is not configured.")
    price_id = plan_price_id(body.plan, body.interval)
    if not price_id:
        raise HTTPException(status_code=400, detail="That plan is not available.")

    subscription = await SubscriptionRepository(session).get_or_create_trial(account_owner)
    base = settings.app_base_url.rstrip("/")
    try:
        url: str | None = None
        if (
            subscription.stripe_subscription_id
            and subscription.stripe_customer_id
            and billing.effective_status(subscription) in ("active", "past_due")
        ):
            # Already subscribed: a plan change must UPDATE the existing
            # subscription (portal confirm flow, prorated per the portal
            # configuration). A second Checkout subscription would not replace
            # the first - the account would be billed for both.
            url = await stripe_service.create_plan_change_session(
                customer_id=subscription.stripe_customer_id,
                subscription_id=subscription.stripe_subscription_id,
                price_id=price_id,
                return_url=f"{base}/billing",
                confirm_url=f"{base}/billing?checkout=updated",
            )
        if url is None:
            # First subscription, or the tracked one is gone on Stripe's side.
            url = await stripe_service.create_checkout_session(
                owner_user_id=account_owner,
                price_id=price_id,
                mode="subscription",
                success_url=f"{base}/billing?checkout=success",
                cancel_url=f"{base}/billing?checkout=cancel",
                customer_id=subscription.stripe_customer_id,
                customer_email=user.email,
                metadata={"plan": body.plan, "interval": body.interval},
            )
    except BillingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await session.commit()
    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> PortalResponse:
    if is_superadmin(user):
        raise HTTPException(status_code=400, detail="This account is not billed.")
    account_owner, manageable = await _resolve_account(session, user)
    if not manageable:
        raise HTTPException(
            status_code=403, detail="Billing is managed by your account owner."
        )
    if not settings.app_base_url:
        raise HTTPException(status_code=503, detail="Billing is not configured.")
    subscription = await SubscriptionRepository(session).get_or_create_trial(account_owner)
    await session.commit()
    if not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=400, detail="Choose a plan before managing billing."
        )
    base = settings.app_base_url.rstrip("/")
    try:
        url = await stripe_service.create_portal_session(
            customer_id=subscription.stripe_customer_id,
            return_url=f"{base}/billing",
        )
    except BillingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PortalResponse(url=url)


# Every paid plan can buy extra messages without changing subscription tier.
TOPUP_PLANS = ("starter", "pro", "business")
TOPUP_PACK_SIZE = 1_000  # messages per pack (kept in sync with the webhook)


@router.post("/topup", response_model=CheckoutResponse)
async def create_topup(
    body: TopupRequest,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(require_admin),
) -> CheckoutResponse:
    """Buy one or more 1,000-message packs for the current billing month.

    A one-time Checkout (``payment`` mode); the webhook credits
    ``account_usage.bonus_messages`` for the current period, which resets with
    the monthly quota. Gated to active paid accounts.
    """
    if is_superadmin(user):
        raise HTTPException(status_code=400, detail="This account is not billed.")
    account_owner, manageable = await _resolve_account(session, user)
    if not manageable:
        raise HTTPException(
            status_code=403, detail="Billing is managed by your account owner."
        )
    if not settings.app_base_url or not settings.stripe_price_topup:
        raise HTTPException(status_code=503, detail="Top-ups are not available.")

    subscription = await SubscriptionRepository(session).get_or_create_trial(account_owner)
    if (
        subscription.plan not in TOPUP_PLANS
        or billing.effective_status(subscription) != "active"
    ):
        raise HTTPException(
            status_code=402,
            detail="Message top-ups are available on active paid plans.",
        )

    base = settings.app_base_url.rstrip("/")
    try:
        url = await stripe_service.create_checkout_session(
            owner_user_id=account_owner,
            price_id=settings.stripe_price_topup,
            mode="payment",
            quantity=body.packs,
            success_url=f"{base}/billing?topup=success",
            cancel_url=f"{base}/billing?topup=cancel",
            customer_id=subscription.stripe_customer_id,
            customer_email=user.email,
            metadata={"kind": "topup", "packs": str(body.packs)},
        )
    except BillingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await session.commit()
    return CheckoutResponse(url=url)


def _map_status(stripe_status: str | None) -> str:
    if stripe_status in ("past_due", "unpaid"):
        return "past_due"
    if stripe_status in ("canceled", "incomplete_expired", "incomplete"):
        return "canceled"
    return "active"


async def _handle_event(session: AsyncSession, event: dict) -> None:
    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    repo = SubscriptionRepository(session)

    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata") or {}
        owner = obj.get("client_reference_id") or metadata.get("owner_user_id")
        if not owner:
            return
        if metadata.get("kind") == "topup":
            packs = int(metadata.get("packs", "1") or 1)
            await repo.add_bonus(
                owner, billing.current_period(), packs * TOPUP_PACK_SIZE
            )
            return
        plan = metadata.get("plan")
        if plan and plan not in PLANS:
            # Never store an unrecognized plan (it would resolve to LOCKED and
            # silently dark the account). Surface it instead.
            logger.warning(
                "Stripe checkout completed with unknown plan %r for owner %s",
                plan,
                owner,
            )
            return
        if plan:
            await repo.apply_stripe_state(
                owner,
                plan=plan,
                status="active",
                stripe_customer_id=obj.get("customer"),
                stripe_subscription_id=obj.get("subscription"),
                billing_interval=metadata.get("interval"),
            )
        return

    if event_type in ("customer.subscription.updated", "customer.subscription.created"):
        metadata = obj.get("metadata") or {}
        owner = metadata.get("owner_user_id")
        customer = obj.get("customer")
        if not owner and customer:
            existing = await repo.find_by_customer(customer)
            owner = existing.owner_user_id if existing else None
        if not owner:
            return
        sub_id = obj.get("id")
        current = await repo.get(owner)
        if (
            current is not None
            and current.stripe_subscription_id
            and current.stripe_subscription_id != sub_id
            and current.status in ("active", "past_due")
        ):
            # Not the subscription this account is tracked on. While the
            # tracked one is live, a stale or duplicate subscription's events
            # must never overwrite the account's plan/status.
            logger.warning(
                "Ignoring %s for subscription %s: account %s is on %s",
                event_type,
                sub_id,
                owner,
                current.stripe_subscription_id,
            )
            return
        items = (obj.get("items") or {}).get("data") or []
        price_id = (
            items[0].get("price", {}).get("id")
            if items and isinstance(items[0], dict)
            else None
        )
        mapped = price_id_to_plan(price_id) if price_id else None
        plan, interval = mapped if mapped else (None, None)
        cpe = obj.get("current_period_end")
        if cpe is None and items and isinstance(items[0], dict):
            # Stripe API 2025-03-31+ moved current_period_end off the
            # subscription object onto its items.
            cpe = items[0].get("current_period_end")
        await repo.apply_stripe_state(
            owner,
            plan=plan,
            status=_map_status(obj.get("status")),
            stripe_customer_id=customer,
            stripe_subscription_id=sub_id,
            billing_interval=interval,
            current_period_end=(
                datetime.fromtimestamp(cpe, tz=timezone.utc) if cpe else None
            ),
        )
        return

    if event_type == "customer.subscription.deleted":
        metadata = obj.get("metadata") or {}
        owner = metadata.get("owner_user_id")
        customer = obj.get("customer")
        if not owner and customer:
            existing = await repo.find_by_customer(customer)
            owner = existing.owner_user_id if existing else None
        if not owner:
            return
        current = await repo.get(owner)
        if current is None or current.stripe_subscription_id != obj.get("id"):
            # Only the subscription the account is tracked on may cancel it.
            # Deleting any other (e.g. the old one after a re-subscribe, or a
            # stray duplicate) must not dark a paying account.
            logger.warning(
                "Ignoring %s for subscription %s: account %s is on %s",
                event_type,
                obj.get("id"),
                owner,
                current.stripe_subscription_id if current else None,
            )
            return
        await repo.apply_stripe_state(owner, status="canceled")
        return


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Public Stripe webhook. Verifies the signature, dedupes by event id, then
    mirrors payment state onto the account. Returns 400 on a bad signature so
    Stripe retries only genuine failures."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.verify_event(payload, signature)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    event_id = event.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Malformed event.")

    repo = SubscriptionRepository(session)
    if not await repo.mark_event_processed(event_id):
        # Duplicate delivery - already handled on a prior receipt.
        await session.rollback()
        return {"received": True, "duplicate": True}

    await _handle_event(session, dict(event) if not isinstance(event, dict) else event)
    await session.commit()
    return {"received": True}
