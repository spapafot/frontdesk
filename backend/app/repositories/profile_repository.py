import secrets

from sqlalchemy import select, text
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

    async def list_for_owner(self, owner_user_id: str) -> list[AssistantProfile]:
        result = await self.session.execute(
            select(AssistantProfile)
            .where(AssistantProfile.owner_user_id == owner_user_id)
            .order_by(AssistantProfile.id)
        )
        return list(result.scalars().all())

    async def get_owned(
        self, profile_id: int, owner_user_id: str
    ) -> AssistantProfile | None:
        """Fetch a profile only if it belongs to ``owner_user_id`` (the
        authorization primitive for selecting one of an owner's sites)."""
        result = await self.session.execute(
            select(AssistantProfile).where(
                AssistantProfile.id == profile_id,
                AssistantProfile.owner_user_id == owner_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _provision_installation(
        self, profile_id: int, allowed_origin: str | None = None
    ) -> None:
        """Create the single widget installation for a site, regenerating the
        public key once on the (astronomically unlikely) unique collision."""
        for attempt in range(2):
            self.session.add(
                WidgetInstallation(
                    profile_id=profile_id,
                    public_key=generate_public_key(),
                    monthly_limit=settings.widget_monthly_limit,
                    allowed_origin=allowed_origin,
                )
            )
            try:
                await self.session.flush()
                return
            except IntegrityError:
                await self.session.rollback()
                if attempt == 1:
                    raise

    async def create_site(
        self,
        owner_user_id: str,
        name: str,
        type: str = "general",
        assistant_name: str | None = None,
        allowed_origin: str | None = None,
    ) -> AssistantProfile:
        profile = AssistantProfile(
            owner_user_id=owner_user_id,
            name=name,
            type=type,
        )
        if assistant_name:
            profile.assistant_name = assistant_name
        self.session.add(profile)
        await self.session.flush()
        await self._provision_installation(profile.id, allowed_origin=allowed_origin)
        return profile

    async def get_or_create_default(
        self, owner_user_id: str, email: str | None = None
    ) -> AssistantProfile:
        """Return the owner's first site, creating one on first login. Serialized
        with an advisory lock because the owner-uniqueness DB constraint (which
        previously made this idempotent under concurrency) has been dropped."""
        existing = await self.list_for_owner(owner_user_id)
        if existing:
            return existing[0]
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": owner_user_id},
        )
        existing = await self.list_for_owner(owner_user_id)
        if existing:
            return existing[0]
        return await self.create_site(
            owner_user_id,
            name=email.split("@", 1)[0] if email else "My Business",
        )

    async def delete_site(self, profile: AssistantProfile) -> None:
        """Delete a site. FK ``ON DELETE CASCADE`` removes its installation,
        usage, knowledge documents/chunks, and conversations/messages."""
        await self.session.delete(profile)
        await self.session.flush()

    async def update_settings(self, profile: AssistantProfile, **fields) -> AssistantProfile:
        for key, value in fields.items():
            if value is not None:
                setattr(profile, key, value)
        await self.session.flush()
        return profile
