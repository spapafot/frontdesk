import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import AssistantProfile
from app.models.widget import WidgetInstallation
from app.core.config import settings


def generate_public_key() -> str:
    return f"pk_live_{secrets.token_urlsafe(24)}"


class ProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, profile_id: int) -> AssistantProfile | None:
        return await self.session.get(AssistantProfile, profile_id)

    async def get_for_owner(self, owner_user_id: str) -> AssistantProfile | None:
        result = await self.session.execute(
            select(AssistantProfile).where(AssistantProfile.owner_user_id == owner_user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_for_owner(
        self, owner_user_id: str, email: str | None = None
    ) -> AssistantProfile:
        profile = await self.get_for_owner(owner_user_id)
        if profile is not None:
            return profile
        profile = AssistantProfile(
            owner_user_id=owner_user_id,
            name=email.split("@", 1)[0] if email else "My Business",
            type="general",
        )
        self.session.add(profile)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_for_owner(owner_user_id)
            if existing is None:
                raise
            return existing
        self.session.add(
            WidgetInstallation(
                profile_id=profile.id,
                public_key=generate_public_key(),
                monthly_limit=settings.widget_monthly_limit,
            )
        )
        await self.session.flush()
        return profile

    async def update_settings(self, profile: AssistantProfile, **fields) -> AssistantProfile:
        for key, value in fields.items():
            if value is not None:
                setattr(profile, key, value)
        await self.session.flush()
        return profile
