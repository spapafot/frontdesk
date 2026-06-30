import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business


def generate_public_key() -> str:
    """Non-secret, URL-safe site key the widget embeds (e.g. pk_live_xxx)."""
    return f"pk_live_{secrets.token_urlsafe(24)}"


class BusinessRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, business_id: int) -> Business | None:
        return await self.session.get(Business, business_id)

    async def get_by_public_key(self, public_key: str) -> Business | None:
        result = await self.session.execute(
            select(Business).where(Business.public_key == public_key)
        )
        return result.scalar_one_or_none()

    async def get_default(self) -> Business | None:
        result = await self.session.execute(select(Business).order_by(Business.id).limit(1))
        return result.scalar_one_or_none()

    async def get_or_create_default(self) -> Business:
        """Return the single tenant business, creating a neutral one if none exists."""
        business = await self.get_default()
        if business is None:
            business = await self.create(name="Default Business", type="general")
        elif not business.public_key:
            business.public_key = generate_public_key()
            await self.session.flush()
        return business

    async def create(self, **kwargs) -> Business:
        kwargs.setdefault("public_key", generate_public_key())
        business = Business(**kwargs)
        self.session.add(business)
        await self.session.flush()
        return business

    async def update_settings(self, business: Business, **fields) -> Business:
        for key, value in fields.items():
            if value is not None:
                setattr(business, key, value)
        await self.session.flush()
        return business
