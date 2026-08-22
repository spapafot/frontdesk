from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import CatalogIntegration


class CatalogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, profile_id: int) -> CatalogIntegration | None:
        result = await self.session.execute(
            select(CatalogIntegration).where(
                CatalogIntegration.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        profile_id: int,
        *,
        store_url: str,
        enabled: bool,
        provider: str = "woocommerce",
        catalog_metadata: dict[str, Any] | None = None,
        verified_at: datetime | None = None,
    ) -> CatalogIntegration:
        integration = await self.get(profile_id)
        if integration is None:
            integration = CatalogIntegration(
                profile_id=profile_id,
                store_url=store_url,
                enabled=enabled,
                provider=provider,
            )
            self.session.add(integration)
        else:
            integration.store_url = store_url
            integration.enabled = enabled
            integration.provider = provider
        if catalog_metadata is not None:
            integration.catalog_metadata = catalog_metadata
            integration.metadata_refreshed_at = verified_at
        if verified_at is not None:
            integration.verified_at = verified_at
        await self.session.flush()
        return integration

    async def delete(self, integration: CatalogIntegration) -> None:
        await self.session.delete(integration)
        await self.session.flush()


# Compatibility alias for older backend modules and tests during rollout.
WooCommerceCatalogRepository = CatalogRepository
