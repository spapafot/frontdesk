"""Provider-neutral runtime contract for read-only product catalogs."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from app.core.config import settings
from app.services.shopify import ShopifySearchQuery, ShopifyStoreClient
from app.services.woocommerce import ProductSearchQuery, WooCommerceStoreClient

CatalogProviderName = Literal["woocommerce", "shopify"]
CatalogQuery = ProductSearchQuery | ShopifySearchQuery


class CatalogAdapter(Protocol):
    provider: CatalogProviderName
    metadata_schema_version: int
    metadata_ttl_seconds: int
    store_url: str

    async def verify_and_discover(self) -> dict[str, Any]: ...

    async def execute(
        self,
        query: CatalogQuery,
        *,
        cursor: dict[str, Any] | str | None,
        language: str,
    ) -> dict[str, Any]: ...


class WooCommerceCatalogAdapter:
    provider: CatalogProviderName = "woocommerce"
    metadata_schema_version = 2

    def __init__(self, store_url: str) -> None:
        self.client = WooCommerceStoreClient(store_url)
        self.store_url = self.client.store_url
        self.metadata_ttl_seconds = settings.woocommerce_metadata_ttl_seconds

    async def verify_and_discover(self) -> dict[str, Any]:
        return await self.client.verify_and_discover()

    async def execute(
        self,
        query: CatalogQuery,
        *,
        cursor: dict[str, Any] | str | None,
        language: str,
    ) -> dict[str, Any]:
        del language
        woo_query = ProductSearchQuery.model_validate(query)
        woo_cursor = cursor if isinstance(cursor, dict) else None
        return await self.client.search_products(woo_query, cursor=woo_cursor)


class ShopifyCatalogAdapter:
    provider: CatalogProviderName = "shopify"
    metadata_schema_version = 1

    def __init__(self, store_url: str) -> None:
        self.client = ShopifyStoreClient(store_url)
        self.store_url = self.client.store_url
        self.metadata_ttl_seconds = settings.shopify_metadata_ttl_seconds

    async def verify_and_discover(self) -> dict[str, Any]:
        return await self.client.verify_and_discover()

    async def execute(
        self,
        query: CatalogQuery,
        *,
        cursor: dict[str, Any] | str | None,
        language: str,
    ) -> dict[str, Any]:
        shopify_query = ShopifySearchQuery.model_validate(query)
        if shopify_query.product_id:
            product = await self.client.get_product(
                shopify_query.product_id,
                selected=shopify_query.options,
                currency=shopify_query.currency,
                language=language,
            )
            return {
                "products": [product],
                "query": shopify_query.model_dump(mode="json"),
                "page": 1,
                "has_more": False,
                "cursor": None,
            }
        return await self.client.search_products(
            shopify_query, cursor=cursor, language=language
        )


def get_catalog_adapter(
    provider: CatalogProviderName, store_url: str
) -> CatalogAdapter:
    if provider == "shopify":
        return ShopifyCatalogAdapter(store_url)
    return WooCommerceCatalogAdapter(store_url)
