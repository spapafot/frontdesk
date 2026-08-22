from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.services import chat_service
from app.services.chat_service import (
    _catalog_more_prompt,
    _catalog_reply,
    _select_product_search,
    run_turn,
)
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
            "per_page": 1,
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


async def test_search_rejects_prices_outside_bounds_when_store_lookup_is_stale():
    def product(product_id: int, name: str, price: object) -> dict:
        return {
            "id": product_id,
            "name": name,
            "permalink": f"https://shop.example/product/{product_id}/",
            "prices": {
                "price": price,
                "regular_price": price,
                "sale_price": price,
                "currency_code": "EUR",
                "currency_minor_unit": 2,
            },
            "is_in_stock": True,
        }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["min_price"] == "1000"
        assert request.url.params["max_price"] == "7000"
        return httpx.Response(
            200,
            headers={"x-wp-totalpages": "1"},
            json=[
                product(1, "Within range", "6320"),
                product(2, "Over stale maximum", "17680"),
                product(3, "Under minimum", "900"),
                product(4, "Malformed price", "not-a-price"),
                product(5, "Missing price", None),
            ],
        )

    client = WooCommerceStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )

    result = await client.search_products(
        ProductSearchQuery(min_price=1000, max_price=7000)
    )

    assert [item["name"] for item in result["products"]] == ["Within range"]
    assert result["products"][0]["price"] == "63.20"
    assert result["has_more"] is False


async def test_search_keeps_products_without_prices_when_no_price_filter_is_used():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "Contact for price",
                    "permalink": "https://shop.example/product/1/",
                    "prices": {"price": None, "currency_minor_unit": 2},
                }
            ],
        )

    client = WooCommerceStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )

    result = await client.search_products(ProductSearchQuery())

    assert [item["name"] for item in result["products"]] == ["Contact for price"]
    assert result["products"][0]["price"] is None


async def test_price_hardening_backfills_pages_and_cursor_avoids_repeats():
    def product(product_id: int, price: str) -> dict:
        return {
            "id": product_id,
            "name": f"Product {product_id}",
            "permalink": f"https://shop.example/product/{product_id}/",
            "prices": {
                "price": price,
                "regular_price": price,
                "sale_price": price,
                "currency_code": "EUR",
                "currency_minor_unit": 2,
            },
        }

    pages = {
        1: [product(1, "5000"), product(99, "17000")],
        2: [product(2, "6000"), product(3, "6500")],
        3: [product(4, "6900")],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        assert request.url.params["per_page"] == "2"
        return httpx.Response(
            200,
            headers={"x-wp-totalpages": "3"},
            json=pages[page],
        )

    client = WooCommerceStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    query = ProductSearchQuery(max_price=7000, per_page=2)

    first = await client.search_products(query)

    assert [item["id"] for item in first["products"]] == [1, 2]
    assert first["cursor"] == {"store_page": 2, "offset": 1}
    assert first["has_more"] is True

    second = await client.search_products(
        query.model_copy(update={"context_mode": "more", "page": 2}),
        cursor=first["cursor"],
    )

    assert [item["id"] for item in second["products"]] == [3, 4]
    assert second["cursor"] is None
    assert second["has_more"] is False


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


def _tool_response(arguments: str):
    return SimpleNamespace(
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


class _FakeCompletions:
    def __init__(self, arguments: str):
        self.response = _tool_response(arguments)

    async def create(self, **kwargs):
        return self.response


def _fake_tool_client(arguments: str):
    return SimpleNamespace(
        chat=SimpleNamespace(completions=_FakeCompletions(arguments))
    )


def _shoe_state():
    return {
        "catalog_search": ProductSearchQuery(
            search="παπούτσι",
            attributes=[
                {"taxonomy": "pa_size", "slug": "38"},
                {"taxonomy": "pa_color", "slug": "black"},
            ],
        ).model_dump(mode="json")
    }


def _shoe_metadata():
    return {
        "currency": {"code": "EUR", "minor_unit": 2},
        "categories": [],
        "attributes": [
            {
                "name": "Μέγεθος",
                "taxonomy": "pa_size",
                "terms": [{"name": "38", "slug": "38"}],
            },
            {
                "name": "Χρώμα",
                "taxonomy": "pa_color",
                "terms": [{"name": "Μαύρο", "slug": "black"}],
            },
        ],
    }


async def test_sale_refinement_inherits_previous_product_filters():
    query = await _select_product_search(
        _fake_tool_client('{"context_mode":"refine","on_sale":true}'),
        "σε έκπτωση",
        catalog_metadata=_shoe_metadata(),
        previous_state=_shoe_state(),
    )

    assert query is not None
    assert query.search == "παπούτσι"
    assert query.on_sale is True
    assert {(item.taxonomy, item.slug) for item in query.attributes} == {
        ("pa_size", "38"),
        ("pa_color", "black"),
    }
    assert query.page == 1


async def test_sale_only_search_is_refined_even_when_model_calls_it_new():
    query = await _select_product_search(
        _fake_tool_client('{"search":"με έκπτωση"}'),
        "σε έκπτωση",
        catalog_metadata=_shoe_metadata(),
        previous_state=_shoe_state(),
    )

    assert query is not None
    assert query.context_mode == "refine"
    assert query.search == "παπούτσι"
    assert query.on_sale is True
    assert len(query.attributes) == 2


async def test_show_more_preserves_filters_and_advances_page():
    state = _shoe_state()
    state["catalog_search"]["page"] = 2
    query = await _select_product_search(
        _fake_tool_client('{"context_mode":"more"}'),
        "δείξε μου περισσότερα",
        catalog_metadata=_shoe_metadata(),
        previous_state=state,
    )

    assert query is not None
    assert query.page == 3
    assert query.search == "παπούτσι"
    assert len(query.attributes) == 2


def test_catalog_reply_states_effective_filters_in_greek():
    query = ProductSearchQuery.model_validate(
        {
            **_shoe_state()["catalog_search"],
            "on_sale": True,
            "max_price": 6000,
        }
    )

    reply = _catalog_reply("σε έκπτωση", 3, query, _shoe_metadata())

    assert reply.startswith("Βρήκα 3 προϊόντα")
    assert "αναζήτηση «παπούτσι»" in reply
    assert "Μέγεθος: 38" in reply
    assert "Χρώμα: Μαύρο" in reply
    assert "έως 60 EUR" in reply
    assert "σε έκπτωση" in reply
    assert "σε απόθεμα" in reply


def test_catalog_more_prompt_matches_the_customer_language():
    assert _catalog_more_prompt("Έχεις φορέματα κάτω από 70 ευρώ;") == (
        "Πείτε «δείξε μου περισσότερα» για να δείτε κι άλλα προϊόντα."
    )
    assert _catalog_more_prompt("Show me dresses under 70 euros") == (
        "Ask “show me more” for the next page."
    )


def test_tool_schema_exposes_only_read_only_product_search():
    schema = product_tool_schema()
    assert schema["function"]["name"] == "search_products"
    assert "store_url" not in str(schema)
    assert "order" not in schema["function"]["name"]
    assert schema["function"]["parameters"]["properties"]["per_page"] == {
        "default": 4,
        "maximum": 4,
        "minimum": 1,
        "title": "Per Page",
        "type": "integer",
    }


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

        async def search_products(self, query, *, cursor=None):
            assert query.category == "dresses"
            assert cursor is None
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
                "cursor": None,
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
    assert "Filters: category dresses, in stock." in events[2]["content"]
    assert [message["role"] for message in stored_messages] == ["user", "assistant"]
    assert stored_messages[1]["meta"]["catalog_search"]["category"] == "dresses"
