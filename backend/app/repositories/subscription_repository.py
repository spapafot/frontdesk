from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import TRIAL_DAYS
from app.models.billing import AccountUsage, Subscription


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, owner_user_id: str) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.owner_user_id == owner_user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_trial(self, owner_user_id: str) -> Subscription:
        """Return the account's subscription, lazily creating a 7-day trial.

        Mirrors ``ProfileRepository.get_or_create_default``: a brand-new owner
        gets a ``trialing`` row so entitlements resolve without a Stripe object.
        """
        existing = await self.get(owner_user_id)
        if existing is not None:
            return existing
        subscription = Subscription(
            owner_user_id=owner_user_id,
            plan="trial",
            status="trialing",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS),
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def usage(self, owner_user_id: str, period: date) -> tuple[int, int]:
        """Return ``(message_count, bonus_messages)`` for the account's period."""
        result = await self.session.execute(
            select(AccountUsage.message_count, AccountUsage.bonus_messages).where(
                AccountUsage.owner_user_id == owner_user_id,
                AccountUsage.period == period,
            )
        )
        row = result.first()
        return (int(row[0]), int(row[1])) if row is not None else (0, 0)

    async def reserve_account_message(
        self, owner_user_id: str, period: date, base_limit: int
    ) -> bool:
        """Atomically reserve one pooled message against the account's monthly
        allowance (``base_limit`` + any current-period top-up ``bonus_messages``).

        Returns False (caller should 429) when the account is at its ceiling.
        Same single-row UPSERT-with-guard shape as
        ``WidgetRepository.reserve_message``, keyed by account instead of site.
        """
        result = await self.session.execute(
            text(
                "INSERT INTO account_usage (owner_user_id, period, message_count, bonus_messages) "
                "VALUES (:owner_user_id, :period, 1, 0) "
                "ON CONFLICT (owner_user_id, period) DO UPDATE "
                "SET message_count = account_usage.message_count + 1 "
                "WHERE account_usage.message_count < :base_limit + account_usage.bonus_messages "
                "RETURNING message_count"
            ),
            {
                "owner_user_id": owner_user_id,
                "period": period,
                "base_limit": base_limit,
            },
        )
        return result.scalar_one_or_none() is not None

    async def add_bonus(self, owner_user_id: str, period: date, quantity: int) -> None:
        """Add top-up messages to the account's current period (Phase 2)."""
        await self.session.execute(
            text(
                "INSERT INTO account_usage (owner_user_id, period, message_count, bonus_messages) "
                "VALUES (:owner_user_id, :period, 0, :quantity) "
                "ON CONFLICT (owner_user_id, period) DO UPDATE "
                "SET bonus_messages = account_usage.bonus_messages + :quantity"
            ),
            {"owner_user_id": owner_user_id, "period": period, "quantity": quantity},
        )

    async def apply_stripe_state(
        self,
        owner_user_id: str,
        *,
        plan: str | None = None,
        status: str | None = None,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        billing_interval: str | None = None,
        current_period_end: datetime | None = None,
    ) -> Subscription:
        """Mirror Stripe payment state onto the account's subscription row.

        Only the fields provided are overwritten, so a ``subscription.updated``
        event that changes just the status/period leaves the plan intact.
        """
        subscription = await self.get_or_create_trial(owner_user_id)
        if plan is not None:
            subscription.plan = plan
        if status is not None:
            subscription.status = status
        if stripe_customer_id is not None:
            subscription.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            subscription.stripe_subscription_id = stripe_subscription_id
        if billing_interval is not None:
            subscription.billing_interval = billing_interval
        if current_period_end is not None:
            subscription.current_period_end = current_period_end
        await self.session.flush()
        return subscription

    async def find_by_customer(self, stripe_customer_id: str) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.stripe_customer_id == stripe_customer_id
            )
        )
        return result.scalar_one_or_none()

    async def mark_event_processed(self, stripe_event_id: str) -> bool:
        """Record a webhook event id. Returns False if it was already processed
        (unique-constraint conflict), so the caller can skip duplicate delivery."""
        result = await self.session.execute(
            text(
                "INSERT INTO billing_events (stripe_event_id) VALUES (:event_id) "
                "ON CONFLICT (stripe_event_id) DO NOTHING RETURNING id"
            ),
            {"event_id": stripe_event_id},
        )
        return result.scalar_one_or_none() is not None
