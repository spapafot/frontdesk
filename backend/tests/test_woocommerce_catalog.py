from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.services import chat_service
from app.services.chat_service import _select_product_search, run_turn
from app.services.woocommerce import (
    ProductSearchQuery,
    WooCommerceError,
    WooCommerceStoreClient,
    normalize_store_url,
    product_tool_schema,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://shop.example",
        "https://127.0.0.1",
        "https://[::1]",
        "https://user:pass@shop.example",
        "https://shop.example:8443",
        "https://shop.example?next=https://evil.example",
    ],
)
def test_store_url_rejects_unsafe_destinations(url):
    with pytest.raises(WooCommerceError):
        normalize_store_url(url)


def test_store_url_keeps_subdirectory_and_canonicalizes_host():
    assert normalize_store_url(" HTTPS://Shop.Example/store/ ") == (
        "https://shop.example/store"
    )


async def test_discovers_public_catalog_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/products"):
            return httpx.Response(
                200,
                headers={"x-wp-total": "42"},
                json=[
                    {
                        "prices": {
                            "currency_code": "EUR",
                            "currency_minor_unit": 2,
                            "currency_symbol": "€",
                        }
                    }
                ],
            )
        if path.endswith("/products/categories"):
            return httpx.Response(
                200, json=[{"id": 7, "name": "Dresses", "slug": "dresses"}]
            )
        if path.endswith("/products/attributes"):
            return httpx.Response(
                200,
                json=[{"id": 3, "name": "Size", "taxonomy": "pa_size"}],
            )
        if path.endswith("/products/attributes/3/terms"):
            return httpx.Response(
                200, json=[{"id": 9, "name": "Medium", "slug": "medium"}]
            )
        raise AssertionError(f"Unexpected Store API path: {path}")

    client = WooCommerceStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )

    metadata = await client.verify_and_discover()

    assert metadata["product_count"] == 42
    assert metadata["currency"]["code"] == "EUR"
    assert metadata["categories"][0]["slug"] == "dresses"
    assert metadata["attributes"][0]["terms"][0]["slug"] == "medium"


async def test_search_maps_filters_and_normalizes_untrusted_product_html():
    seen_query = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_query
        seen_query = request.url.params
        return httpx.Response(
            200,
            headers={"x-wp-totalpages": "2"},
            json=[
                {
                    "id": 21,
                    "name": "<b>Blue</b> Dress<script>alert(1)</script>",
                    "slug": "blue-dress",
                    "permalink": "https://shop.example/product/blue-dress/",
                    "summary": "<p>Lightweight <em>summer</em> dress.</p>",
                    "prices": {
                        "price": "2599",
                        "regular_price": "2999",
                        "sale_price": "2599",
                        "currency_code": "EUR",
                        "currency_minor_unit": 2,
                        "currency_symbol": "€",
                    },
                    "images": [{"thumbnail": "https://cdn.example/blue.jpg"}],
                    "attributes": [
                        {
                            "name": "Size",
                            "taxonomy": "pa_size",
                            "terms": [{"name": "Medium", "slug": "medium"}],
                        }
                    ],
                    "on_sale": True,
                    "is_in_stock": True,
                },
                {
                    "id": 22,
                    "name": "Bad redirect",
                    "permalink": "https://evil.example/phishing",
                },
            ],
        )

    client = WooCommerceStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    query = ProductSearchQuery.model_validate(
        {
            "category": "dresses",
            "attributes": [{"taxonomy": "pa_size", "slug": "medium"}],
            "max_price": 5000,
            "page": 1,
        }
    )

    result = await client.search_products(query)

    assert seen_query is not None
    assert seen_query["category"] == "dresses"
    assert seen_query["attributes[0][attribute]"] == "pa_size"
    assert seen_query["attributes[0][slug]"] == "medium"
    assert seen_query["max_price"] == "5000"
    assert seen_query["stock_status[]"] == "instock"
    assert result["has_more"] is True
    assert len(result["products"]) == 1
    product = result["products"][0]
    assert product["name"] == "Blue Dress alert(1)"
    assert product["summary"] == "Lightweight summer dress."
    assert product["price"] == "25.99"
    assert product["product_url"].startswith("https://shop.example/")


async def test_router_constrains_invented_taxonomy_values():
    arguments = (
        '{"category":"evening","attributes":['
        '{"taxonomy":"pa_size","slug":"medium"},'
        '{"taxonomy":"pa_color","slug":"invisible"}]}'
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="search_products", arguments=arguments
                            )
                        )
                    ]
                )
            )
        ]
    )

    class Completions:
        async def create(self, **kwargs):
            assert kwargs["tool_choice"] == "auto"
            return response

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    metadata = {
        "categories": [{"slug": "dresses"}],
        "attributes": [
            {"taxonomy": "pa_size", "terms": [{"slug": "medium"}]},
            {"taxonomy": "pa_color", "terms": [{"slug": "blue"}]},
        ],
    }

    query = await _select_product_search(
        client,
        "medium dresses",
        catalog_metadata=metadata,
        previous_state=None,
    )

    assert query is not None
    assert query.category is None
    assert [item.model_dump() for item in query.attributes] == [
        {"taxonomy": "pa_size", "slug": "medium"}
    ]
    assert query.search == "medium dresses"


def test_tool_schema_exposes_only_read_only_product_search():
    schema = product_tool_schema()
    assert schema["function"]["name"] == "search_products"
    assert "store_url" not in str(schema)
    assert "order" not in schema["function"]["name"]


async def test_catalog_turn_streams_products_and_skips_rag(monkeypatch, settings):
    stored_messages = []
    profile = SimpleNamespace(
        id=7,
        name="Acme",
        assistant_name="Aria",
        timezone="Europe/Athens",
        custom_instructions=None,
        moderation_enabled=False,
    )
    conversation = SimpleNamespace(id=42, profile_id=7, mode="ai", title=None)
    catalog = SimpleNamespace(
        store_url="https://shop.example",
        enabled=True,
        catalog_metadata={"categories": [], "attributes": []},
        metadata_refreshed_at=datetime.now(timezone.utc),
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def commit(self):
            return None

        async def refresh(self, obj, attribute_names=None):
            return None

    class FakeProfileRepo:
        def __init__(self, session):
            pass

        async def get(self, profile_id):
            return profile

    class FakeConversationRepo:
        def __init__(self, session):
            pass

        async def get(self, conversation_id):
            return conversation

        async def get_messages(self, conversation_id):
            return []

        async def latest_catalog_state(self, conversation_id):
            return None

        async def add_message(self, conversation_id, role, content="", **kwargs):
            stored_messages.append(
                {"role": role, "content": content, "meta": kwargs.get("meta")}
            )

    class FakeCatalogRepo:
        def __init__(self, session):
            pass

        async def get(self, profile_id):
            return catalog

    class FakeStoreClient:
        def __init__(self, store_url):
            assert store_url == "https://shop.example"

        async def search_products(self, query):
            assert query.category == "dresses"
            return {
                "products": [
                    {
                        "id": 21,
                        "name": "Blue Dress",
                        "slug": "blue-dress",
                        "product_url": "https://shop.example/product/blue-dress/",
                    }
                ],
                "page": 1,
                "has_more": False,
                "query": query.model_dump(mode="json"),
            }

    async def fake_select(*args, **kwargs):
        return ProductSearchQuery(category="dresses")

    async def trap_search(*args, **kwargs):
        raise AssertionError("A product turn must not reach RAG")

    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(chat_service, "SessionLocal", FakeSession)
    monkeypatch.setattr(chat_service, "ProfileRepository", FakeProfileRepo)
    monkeypatch.setattr(chat_service, "ConversationRepository", FakeConversationRepo)
    monkeypatch.setattr(chat_service, "WooCommerceCatalogRepository", FakeCatalogRepo)
    monkeypatch.setattr(chat_service, "WooCommerceStoreClient", FakeStoreClient)
    monkeypatch.setattr(chat_service, "_select_product_search", fake_select)
    monkeypatch.setattr(chat_service, "search_knowledge", trap_search)
    monkeypatch.setattr(chat_service, "get_client", lambda: object())

    events = [event async for event in run_turn("medium dresses", 7, 42)]

    assert [event["type"] for event in events] == [
        "conversation",
        "product_results",
        "token",
        "done",
    ]
    assert events[1]["products"][0]["name"] == "Blue Dress"
    assert [message["role"] for message in stored_messages] == ["user", "assistant"]
    assert stored_messages[1]["meta"]["catalog_search"]["category"] == "dresses"
