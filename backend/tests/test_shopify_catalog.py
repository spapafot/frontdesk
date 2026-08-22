import json

import httpx
import pytest

from app.services.chat_service import _merge_shopify_product_query
from app.services.shopify import (
    ShopifyError,
    ShopifyOptionFilter,
    ShopifySearchQuery,
    ShopifyStoreClient,
    normalize_shopify_store_url,
)


def rpc_result(request: httpx.Request, result: dict, *, status: int = 200) -> httpx.Response:
    request_body = json.loads(request.content)
    return httpx.Response(
        status,
        request=request,
        json={"jsonrpc": "2.0", "id": request_body["id"], "result": result},
    )


def product(
    product_id: str,
    *,
    amount: int = 5000,
    color: str = "Black",
    available: bool = True,
    list_amount: int | None = None,
    url_host: str = "shop.example",
) -> dict:
    variant = {
        "id": f"gid://shopify/ProductVariant/{product_id.rsplit('/', 1)[-1]}",
        "title": color,
        "description": {"plain": color},
        "price": {"amount": amount, "currency": "EUR"},
        "availability": {"available": available},
        "options": [{"name": "Color", "label": color}],
    }
    if list_amount is not None:
        variant["list_price"] = {"amount": list_amount, "currency": "EUR"}
    return {
        "id": product_id,
        "handle": f"item-{product_id.rsplit('/', 1)[-1]}",
        "title": f"{color} Dress",
        "description": {"html": "<p>A useful description.</p>"},
        "url": f"https://{url_host}/products/item",
        "price_range": {
            "min": {"amount": amount, "currency": "EUR"},
            "max": {"amount": amount, "currency": "EUR"},
        },
        "list_price_range": (
            {
                "min": {"amount": list_amount, "currency": "EUR"},
                "max": {"amount": list_amount, "currency": "EUR"},
            }
            if list_amount is not None
            else None
        ),
        "media": [
            {
                "type": "image",
                "url": "https://cdn.shopify.com/item.jpg",
            }
        ],
        "options": [
            {
                "name": "Color",
                "values": [{"label": color, "available": available, "exists": True}],
            }
        ],
        "collections": [
            {
                "id": "gid://shopify/Collection/dresses",
                "title": "Dresses",
                "url": f"https://{url_host}/collections/dresses",
            }
        ],
        "variants": [variant],
    }


def search_result(products: list[dict], *, cursor: str | None = None, more: bool = False) -> dict:
    return {
        "structuredContent": {
            "ucp": {
                "version": "2026-04-08",
                "capabilities": {
                    "dev.ucp.shopping.catalog.search": [{"version": "2026-04-08"}]
                },
            },
            "products": products,
            "pagination": {
                "cursor": cursor,
                "has_next_page": more,
                "total_count": len(products),
            },
        }
    }


@pytest.mark.parametrize(
    "value",
    [
        "http://shop.example",
        "https://user:pass@shop.example",
        "https://shop.example:8443",
        "https://shop.example/products",
        "https://shop.example?x=1",
        "https://127.0.0.1",
    ],
)
def test_shopify_store_url_rejects_unsafe_origins(value):
    with pytest.raises(ShopifyError):
        normalize_shopify_store_url(value)


def test_shopify_store_url_normalizes_customer_origin():
    assert normalize_shopify_store_url(" HTTPS://SHOP.EXAMPLE/ ") == "https://shop.example"


@pytest.mark.asyncio
async def test_verify_discovers_required_tools_and_currency(settings):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") is None
        body = json.loads(request.content)
        calls.append(body)
        meta = body["params"]["arguments"]["meta"]["ucp-agent"]
        assert meta["profile"] == settings.shopify_ucp_agent_profile_url
        if body["method"] == "tools/list":
            return rpc_result(
                request,
                {
                    "tools": [
                        {"name": "get_product"},
                        {"name": "search_catalog"},
                        {"name": "lookup_catalog"},
                    ]
                },
            )
        assert body["params"]["name"] == "search_catalog"
        assert body["params"]["arguments"]["catalog"]["pagination"]["limit"] == 1
        return rpc_result(request, search_result([product("gid://shopify/Product/1")]))

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    metadata = await client.verify_and_discover()
    assert metadata["schema_version"] == 1
    assert metadata["currency"] == {"code": "EUR", "minor_unit": 2, "symbol": ""}
    assert set(metadata["capabilities"]) >= {"search_catalog", "get_product"}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_verify_rejects_missing_tools():
    def handler(request: httpx.Request) -> httpx.Response:
        return rpc_result(request, {"tools": [{"name": "search_catalog"}]})

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    with pytest.raises(ShopifyError, match="required catalog"):
        await client.verify_and_discover()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 429, 500])
async def test_mcp_rejects_redirects_rate_limits_and_server_errors(status):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, request=request, headers={"location": "https://other.example"})

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    with pytest.raises(ShopifyError):
        await client.verify_and_discover()


@pytest.mark.asyncio
async def test_mcp_rejects_malformed_json_rpc():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"jsonrpc": "2.0", "id": 999, "result": {}})

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    with pytest.raises(ShopifyError, match="JSON-RPC"):
        await client.verify_and_discover()


@pytest.mark.asyncio
async def test_mcp_surfaces_json_rpc_errors_as_catalog_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        request_body = json.loads(request.content)
        return httpx.Response(
            200,
            request=request,
            json={
                "jsonrpc": "2.0",
                "id": request_body["id"],
                "error": {"code": -32000, "message": "temporary"},
            },
        )

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    with pytest.raises(ShopifyError, match="MCP error"):
        await client.verify_and_discover()


@pytest.mark.asyncio
async def test_mcp_timeout_is_a_catalog_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow store", request=request)

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    with pytest.raises(ShopifyError, match="could not be reached"):
        await client.verify_and_discover()


@pytest.mark.asyncio
async def test_mcp_rejects_oversized_body(monkeypatch, settings):
    monkeypatch.setattr(settings, "shopify_max_response_bytes", 20)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=b"{" + b"x" * 100 + b"}")

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    with pytest.raises(ShopifyError, match="too large"):
        await client.verify_and_discover()


@pytest.mark.asyncio
async def test_search_scans_pages_and_enforces_hard_filters():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        catalog = body["params"]["arguments"]["catalog"]
        assert catalog["query"] == "black dresses"
        assert catalog["context"]["language"] == "el"
        assert catalog["context"]["currency"] == "EUR"
        assert catalog["filters"] == {
            "available": True,
            "price": {"max": 7000},
        }
        cursor = catalog["pagination"].get("cursor")
        if cursor is None:
            items = [
                product("gid://shopify/Product/red", color="Red"),
                product("gid://shopify/Product/expensive", amount=9000),
                product("gid://shopify/Product/1", amount=5000, list_amount=7000),
            ]
            return rpc_result(request, search_result(items, cursor="next-1", more=True))
        if cursor == "next-1":
            items = [
                product("gid://shopify/Product/1", amount=5000, list_amount=7000),
                product("gid://shopify/Product/2", amount=5500, list_amount=7000),
                product("gid://shopify/Product/3", amount=6000, list_amount=7000),
            ]
            return rpc_result(request, search_result(items, cursor="next-2", more=True))
        assert cursor == "next-2"
        return rpc_result(
            request,
            search_result(
                [product("gid://shopify/Product/4", amount=6500, list_amount=7000)],
                cursor="next-3",
                more=True,
            ),
        )

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    result = await client.search_products(
        ShopifySearchQuery(
            query="black dresses",
            max_price=7000,
            currency="EUR",
            on_sale=True,
            options=[ShopifyOptionFilter(name="Color", value="Black")],
        ),
        language="el",
    )
    assert [item["id"] for item in result["products"]] == [
        "gid://shopify/Product/1",
        "gid://shopify/Product/2",
        "gid://shopify/Product/3",
        "gid://shopify/Product/4",
    ]
    assert result["products"][0]["price"] == "50.00"
    assert result["products"][0]["sale_price"] == "50.00"
    assert result["products"][0]["collection_url"] == "https://shop.example/collections/dresses"
    assert result["has_more"] is True
    assert result["cursor"]["cursor"] == "next-3"
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_search_rejects_off_store_product_links():
    def handler(request: httpx.Request) -> httpx.Response:
        return rpc_result(
            request,
            search_result([product("gid://shopify/Product/1", url_host="evil.example")]),
        )

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    result = await client.search_products(ShopifySearchQuery(query="dress"))
    assert result["products"] == []


@pytest.mark.asyncio
async def test_get_product_validates_id_and_selected_available_option():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        catalog = body["params"]["arguments"]["catalog"]
        assert catalog["id"] == "gid://shopify/Product/1"
        assert catalog["selected"] == [{"name": "Color", "label": "Black"}]
        return rpc_result(
            request,
            {
                "structuredContent": {
                    "ucp": {"version": "2026-04-08", "capabilities": {}},
                    "product": product("gid://shopify/Product/1"),
                }
            },
        )

    client = ShopifyStoreClient(
        "https://shop.example",
        transport=httpx.MockTransport(handler),
        validate_dns=False,
    )
    result = await client.get_product(
        "gid://shopify/Product/1",
        selected=[ShopifyOptionFilter(name="Color", value="Black")],
        currency="EUR",
    )
    assert result["id"] == "gid://shopify/Product/1"


def test_shopify_refinement_merges_previous_effective_search_and_resets_cursor():
    previous = ShopifySearchQuery(
        query="μαύρα φορέματα",
        currency="EUR",
        options=[ShopifyOptionFilter(name="Size", value="M")],
        page=3,
    )
    state = {
        "catalog_provider": "shopify",
        "catalog_search": previous.model_dump(mode="json"),
    }
    refined = _merge_shopify_product_query(
        ShopifySearchQuery(
            context_mode="refine",
            max_price=7000,
            on_sale=True,
            options=[ShopifyOptionFilter(name="Color", value="Black")],
        ),
        state,
    )
    assert refined.query == "μαύρα φορέματα"
    assert refined.currency == "EUR"
    assert refined.max_price == 7000
    assert refined.on_sale is True
    assert {(item.name, item.value) for item in refined.options} == {
        ("Size", "M"),
        ("Color", "Black"),
    }
    assert refined.page == 1


def test_shopify_more_reuses_exact_search_and_advances_logical_page():
    previous = ShopifySearchQuery(query="dresses", max_price=5000, page=1)
    state = {
        "catalog_provider": "shopify",
        "catalog_search": previous.model_dump(mode="json"),
    }
    more = _merge_shopify_product_query(
        ShopifySearchQuery(context_mode="more"), state
    )
    assert more.query == "dresses"
    assert more.max_price == 5000
    assert more.page == 2


def test_shopify_modifier_only_sale_follow_up_keeps_previous_search():
    previous = ShopifySearchQuery(query="foremata", currency="EUR")
    state = {
        "catalog_provider": "shopify",
        "catalog_search": previous.model_dump(mode="json"),
    }
    refined = _merge_shopify_product_query(
        ShopifySearchQuery(query="se ekptosi"), state
    )
    assert refined.context_mode == "refine"
    assert refined.query == "foremata"
    assert refined.on_sale is True


def test_shopify_text_refinement_accumulates_with_previous_query():
    previous = ShopifySearchQuery(query="foremata", currency="EUR")
    state = {
        "catalog_provider": "shopify",
        "catalog_search": previous.model_dump(mode="json"),
    }
    refined = _merge_shopify_product_query(
        ShopifySearchQuery(context_mode="refine", query="mavra"), state
    )
    assert refined.query == "foremata mavra"
