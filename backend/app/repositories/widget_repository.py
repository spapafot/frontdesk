from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.widget import WidgetInstallation, WidgetUsage
from app.repositories.profile_repository import generate_public_key


class WidgetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_profile(self, profile_id: int) -> WidgetInstallation | None:
        result = await self.session.execute(
            select(WidgetInstallation).where(WidgetInstallation.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def get_by_key(self, public_key: str) -> WidgetInstallation | None:
        result = await self.session.execute(
            select(WidgetInstallation).where(WidgetInstallation.public_key == public_key)
        )
        return result.scalar_one_or_none()

    async def rotate(self, installation: WidgetInstallation) -> None:
        installation.public_key = generate_public_key()
        await self.session.flush()

    async def usage(self, installation_id: int, period: date) -> int:
        result = await self.session.execute(
            select(WidgetUsage.message_count).where(
                WidgetUsage.installation_id == installation_id,
                WidgetUsage.period == period,
            )
        )
        return int(result.scalar_one_or_none() or 0)

    async def increment_usage(self, installation: WidgetInstallation, period: date) -> None:
        """Bump a site's per-period message counter for analytics display.

        No ceiling guard - the monthly quota is enforced account-wide (pooled
        across all the owner's sites) by
        ``SubscriptionRepository.reserve_account_message``. This counter is kept
        only so per-site usage stays visible in Settings.
        """
        await self.session.execute(
            text(
                "INSERT INTO widget_usage (installation_id, period, message_count) "
                "VALUES (:installation_id, :period, 1) "
                "ON CONFLICT (installation_id, period) DO UPDATE "
                "SET message_count = widget_usage.message_count + 1"
            ),
            {"installation_id": installation.id, "period": period},
        )

    async def reserve_visitor_message(
        self, installation_id: int, ip_hash: str, day: date, limit: int
    ) -> bool:
        """Atomically reserve one message against a visitor IP's daily budget
        for this installation.

        Returns False (caller should 429) when the IP is at its ceiling for
        the day. Same guarded single-row UPSERT as
        ``SubscriptionRepository.reserve_account_message``, so concurrent
        turns from one IP serialize on one row.
        """
        result = await self.session.execute(
            text(
                "INSERT INTO visitor_usage (installation_id, ip_hash, day, message_count) "
                "VALUES (:installation_id, :ip_hash, :day, 1) "
                "ON CONFLICT (installation_id, ip_hash, day) DO UPDATE "
                "SET message_count = visitor_usage.message_count + 1 "
                "WHERE visitor_usage.message_count < :limit "
                "RETURNING message_count"
            ),
            {
                "installation_id": installation_id,
                "ip_hash": ip_hash,
                "day": day,
                "limit": limit,
            },
        )
        return result.scalar_one_or_none() is not None
