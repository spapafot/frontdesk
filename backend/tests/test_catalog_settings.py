from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import settings as settings_route
from app.schemas.settings import SettingsUpdate


def test_generic_catalog_update_selects_shopify_and_preserves_enabled_state():
    current = SimpleNamespace(
        provider="woocommerce",
        store_url="https://woo.example",
        enabled=True,
    )
    update = SettingsUpdate(
        catalog_provider="shopify",
        catalog_store_url="https://shop.example",
    )
    assert settings_route._resolve_catalog_update(update, current) == (
        "shopify",
        "https://shop.example",
        True,
    )


def test_legacy_catalog_update_maps_to_woocommerce():
    update = SettingsUpdate(
        woocommerce_store_url="https://woo.example",
        woocommerce_catalog_enabled=True,
    )
    assert settings_route._resolve_catalog_update(update, None) == (
        "woocommerce",
        "https://woo.example",
        True,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "catalog_provider": "shopify",
            "catalog_store_url": "https://shop.example",
            "woocommerce_store_url": "https://shop.example",
        },
        {
            "catalog_provider": "woocommerce",
            "catalog_store_url": "https://one.example",
            "woocommerce_store_url": "https://two.example",
        },
        {
            "catalog_provider": "woocommerce",
            "catalog_enabled": True,
            "woocommerce_catalog_enabled": False,
        },
    ],
)
def test_conflicting_generic_and_legacy_catalog_payloads_are_rejected(payload):
    with pytest.raises(HTTPException) as exc:
        settings_route._resolve_catalog_update(SettingsUpdate(**payload), None)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_generic_verification_uses_provider_adapter(monkeypatch):
    calls = []

    class FakeAdapter:
        store_url = "https://shop.example"

        async def verify_and_discover(self):
            return {
                "schema_version": 1,
                "product_count": None,
                "currency": {},
                "capabilities": ["search_catalog", "get_product"],
            }

    def fake_factory(provider, store_url):
        calls.append((provider, store_url))
        return FakeAdapter()

    monkeypatch.setattr(settings_route, "get_catalog_adapter", fake_factory)
    normalized, metadata, verified_at = await settings_route._verify_catalog(
        "shopify", "https://SHOP.example/"
    )
    assert normalized == "https://shop.example"
    assert metadata["capabilities"] == ["search_catalog", "get_product"]
    assert verified_at.tzinfo is not None
    assert calls == [("shopify", "https://SHOP.example/")]
