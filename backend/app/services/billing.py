"""Billing orchestration: super-admin detection, plan/status resolution, and
turning a subscription row into concrete entitlements.

Plan *limits* come from ``app.core.plans``; this module decides which limit set
applies to a given caller/account right now (super-admin bypass, expired-trial
lockout, etc.). It is the single source of truth the API routes consult before
enforcing a gate.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import is_superadmin
from app.core.plans import (
    LOCKED_LIMITS,
    PLANS,
    SUPERADMIN_LIMITS,
    PlanLimits,
)
from app.models.billing import Subscription
from app.repositories.subscription_repository import SubscriptionRepository

if TYPE_CHECKING:
    from app.core.auth import AdminUser

__all__ = [
    "current_period",
    "effective_status",
    "is_superadmin",
    "limits_for",
    "resolve_entitlements",
]


def current_period(now: datetime | None = None) -> date:
    """First day of the current UTC month - the pooled-usage period key."""
    moment = now or datetime.now(timezone.utc)
    return date(moment.year, moment.month, 1)


def effective_status(subscription: Subscription, now: datetime | None = None) -> str:
    """Resolve the account's *effective* status.

    A trial whose window has elapsed is treated as ``locked`` even though the
    stored status is still ``trialing`` (the webhook never fires for a no-card
    trial that simply expires).
    """
    moment = now or datetime.now(timezone.utc)
    if subscription.status == "trialing":
        ends = subscription.trial_ends_at
        if ends is not None and ends < moment:
            return "locked"
    return subscription.status


def limits_for(subscription: Subscription, now: datetime | None = None) -> PlanLimits:
    """Concrete entitlements for a subscription, honoring effective status."""
    status = effective_status(subscription, now)
    if status in ("locked", "canceled"):
        return LOCKED_LIMITS
    return PLANS.get(subscription.plan, LOCKED_LIMITS)


async def resolve_entitlements(
    session: AsyncSession, user: "AdminUser", owner_user_id: str
) -> PlanLimits:
    """Entitlements to enforce for ``owner_user_id``'s account.

    Super-admins bypass everything. Otherwise the owning account's subscription
    (lazily created as a trial) decides the limits.
    """
    if is_superadmin(user):
        return SUPERADMIN_LIMITS
    subscription = await SubscriptionRepository(session).get_or_create_trial(
        owner_user_id
    )
    return limits_for(subscription)
