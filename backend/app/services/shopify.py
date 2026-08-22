"""Safe, anonymous Shopify Storefront Catalog MCP access."""

from __future__ import annotations

import ipaddress
import json
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings
from app.services.woocommerce import (
    WooCommerceError,
    ensure_public_store_host,
    plain_text,
    safe_store_link,
)


class ShopifyError(RuntimeError):
    """A bounded, customer-safe Storefront Catalog MCP failure."""


class ShopifyOptionFilter(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    value: str = Field(..., min_length=1, max_length=100)

    @field_validator("name", "value")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ShopifySearchQuery(BaseModel):
    context_mode: Literal["new", "refine", "more"] = "new"
    query: str | None = Field(default=None, max_length=300)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    available: bool = True
    on_sale: bool | None = None
    options: list[ShopifyOptionFilter] = Field(default_factory=list, max_length=5)
    product_id: str | None = Field(default=None, max_length=255)
    page: int = Field(default=1, ge=1, le=100)
    per_page: int = Field(default=4, ge=1, le=4)

    @field_validator("query", "product_id")
    @classmethod
    def _trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value.isalpha():
            raise ValueError("currency must be an ISO 4217 code")
        return value

    @model_validator(mode="after")
    def _price_order(self) -> "ShopifySearchQuery":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot exceed max_price")
        return self


def normalize_shopify_store_url(value: str) -> str:
    """Return a customer-facing HTTPS origin accepted by Shopify MCP."""
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ShopifyError("Enter a valid HTTPS Shopify store URL.") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ShopifyError("The Shopify store URL must use HTTPS.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ShopifyError(
            "The store URL cannot contain credentials, a query string, or a fragment."
        )
    if port not in (None, 443):
        raise ShopifyError("The Shopify store URL must use the standard HTTPS port.")
    if parsed.path not in ("", "/"):
        raise ShopifyError("Enter only the Shopify store origin, without a path.")
    host = parsed.hostname.rstrip(".").lower()
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ShopifyError("The Shopify store must be publicly reachable.")
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ShopifyError("Enter a valid Shopify store hostname.") from exc
    netloc = f"[{ascii_host}]" if ":" in ascii_host else ascii_host
    return urlunsplit(("https", netloc, "", "", ""))


def _minor_unit(currency: str | None) -> int:
    # ISO 4217 currencies with a non-default number of minor-unit digits.
    zero = {
        "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG",
        "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF",
    }
    three = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}
    four = {"CLF", "UYW"}
    code = (currency or "").upper()
    return 0 if code in zero else 3 if code in three else 4 if code in four else 2


def _normalized(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def _amount(price: Any) -> int | None:
    if not isinstance(price, dict):
        return None
    raw = price.get("amount")
    if isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        return None
    return int(value)


def _currency(price: Any) -> str | None:
    if not isinstance(price, dict):
        return None
    value = price.get("currency")
    if isinstance(value, str) and len(value.strip()) == 3 and value.strip().isalpha():
        return value.strip().upper()
    return None


def _price_text(amount: int, currency: str) -> str:
    unit = _minor_unit(currency)
    value = Decimal(amount) / (Decimal(10) ** unit)
    return f"{value:.{unit}f}"


def _https_media_url(value: Any) -> str | None:
    try:
        parsed = urlsplit(str(value or ""))
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or port not in (None, 443)
    ):
        return None
    return parsed.geturl()


def _description(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("plain") or value.get("html") or ""
    return plain_text(value, limit=500)


def _variant_matches(variant: dict[str, Any], query: ShopifySearchQuery) -> bool:
    availability = variant.get("availability")
    if query.available and (
        not isinstance(availability, dict) or availability.get("available") is not True
    ):
        return False
    price = variant.get("price")
    current = _amount(price)
    if current is None:
        return False
    if query.currency and _currency(price) != query.currency:
        return False
    if query.min_price is not None and current < query.min_price:
        return False
    if query.max_price is not None and current > query.max_price:
        return False
    list_amount = _amount(variant.get("list_price"))
    is_sale = list_amount is not None and list_amount > current
    if query.on_sale is not None and is_sale is not query.on_sale:
        return False
    selected = variant.get("options")
    selected_options = selected if isinstance(selected, list) else []
    for requested in query.options:
        found = False
        for option in selected_options:
            if not isinstance(option, dict):
                continue
            same_value = _normalized(option.get("label")) == _normalized(requested.value)
            same_name = requested.name is None or _normalized(option.get("name")) == _normalized(
                requested.name
            )
            if same_value and same_name:
                found = True
                break
        if not found:
            return False
    return True


class ShopifyStoreClient:
    def __init__(
        self,
        store_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        validate_dns: bool = True,
    ) -> None:
        self.store_url = normalize_shopify_store_url(store_url)
        self.endpoint = f"{self.store_url}/api/ucp/mcp"
        self.transport = transport
        self.validate_dns = validate_dns
        self._request_id = 0

    def _agent_meta(self) -> dict[str, Any]:
        return {
            "ucp-agent": {"profile": settings.shopify_ucp_agent_profile_url}
        }

    async def _post_json_rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.validate_dns:
            try:
                await ensure_public_store_host(self.store_url)
            except WooCommerceError as exc:
                raise ShopifyError(str(exc).replace("WooCommerce", "Shopify")) from exc
        self._request_id += 1
        request_id = self._request_id
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.shopify_timeout),
                follow_redirects=False,
                transport=self.transport,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "SECR-Catalog/1.0",
                },
            ) as client:
                async with client.stream("POST", self.endpoint, json=payload) as response:
                    if response.is_redirect:
                        raise ShopifyError(
                            "The store redirected the catalog request. Use its final customer-facing URL."
                        )
                    if response.status_code == 404:
                        raise ShopifyError("Shopify Storefront Catalog MCP was not found on this site.")
                    if response.status_code >= 400:
                        raise ShopifyError(
                            f"Shopify Storefront Catalog MCP returned HTTP {response.status_code}."
                        )
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > settings.shopify_max_response_bytes:
                        raise ShopifyError("The Shopify catalog response was too large.")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > settings.shopify_max_response_bytes:
                            raise ShopifyError("The Shopify catalog response was too large.")
                        chunks.append(chunk)
        except ShopifyError:
            raise
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise ShopifyError("Shopify Storefront Catalog MCP could not be reached.") from exc
        try:
            response_payload = json.loads(b"".join(chunks))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ShopifyError("Shopify Storefront Catalog MCP returned invalid JSON.") from exc
        if (
            not isinstance(response_payload, dict)
            or response_payload.get("jsonrpc") != "2.0"
            or response_payload.get("id") != request_id
        ):
            raise ShopifyError("Shopify Storefront Catalog MCP returned invalid JSON-RPC.")
        if response_payload.get("error") is not None:
            raise ShopifyError("Shopify Storefront Catalog MCP returned an MCP error.")
        result = response_payload.get("result")
        if not isinstance(result, dict) or result.get("isError") is True:
            raise ShopifyError("Shopify Storefront Catalog MCP returned an invalid result.")
        return result

    async def _call_tool(self, name: str, catalog: dict[str, Any]) -> dict[str, Any]:
        result = await self._post_json_rpc(
            "tools/call",
            {
                "name": name,
                "arguments": {"meta": self._agent_meta(), "catalog": catalog},
            },
        )
        structured = result.get("structuredContent")
        if not isinstance(structured, dict):
            raise ShopifyError("Shopify Storefront Catalog MCP returned malformed content.")
        ucp = structured.get("ucp")
        if not isinstance(ucp, dict) or ucp.get("version") != "2026-04-08":
            raise ShopifyError("The store returned an unsupported UCP catalog response.")
        return structured

    async def verify_and_discover(self) -> dict[str, Any]:
        listed = await self._post_json_rpc(
            "tools/list", {"arguments": {"meta": self._agent_meta()}}
        )
        tools = listed.get("tools")
        if not isinstance(tools, list):
            raise ShopifyError("The store returned an invalid MCP tool list.")
        capabilities = sorted(
            {
                str(tool.get("name"))
                for tool in tools
                if isinstance(tool, dict) and isinstance(tool.get("name"), str)
            }
        )
        required = {"search_catalog", "get_product"}
        if not required.issubset(capabilities):
            raise ShopifyError(
                "This Shopify store does not expose the required catalog search and product tools."
            )
        browse = await self._call_tool(
            "search_catalog", {"filters": {"available": True}, "pagination": {"limit": 1}}
        )
        products = browse.get("products")
        if not isinstance(products, list):
            raise ShopifyError("The store returned an invalid Shopify product catalog.")
        currency: dict[str, Any] = {}
        if products and isinstance(products[0], dict):
            price_range = products[0].get("price_range")
            minimum = price_range.get("min") if isinstance(price_range, dict) else None
            code = _currency(minimum)
            if code:
                currency = {"code": code, "minor_unit": _minor_unit(code), "symbol": ""}
        pagination = browse.get("pagination")
        total_count = pagination.get("total_count") if isinstance(pagination, dict) else None
        return {
            "schema_version": 1,
            "product_count": total_count if isinstance(total_count, int) and total_count >= 0 else None,
            "currency": currency,
            "capabilities": capabilities,
        }

    def _catalog_request(
        self,
        query: ShopifySearchQuery,
        *,
        language: str,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        catalog: dict[str, Any] = {
            "context": {
                "language": language,
                "intent": query.query or "Browse the product catalog",
            },
            "filters": {"available": query.available},
            "pagination": {"limit": min(max(limit, 1), 4)},
        }
        if query.query:
            catalog["query"] = query.query
        if query.currency:
            catalog["context"]["currency"] = query.currency
        if query.min_price is not None or query.max_price is not None:
            price: dict[str, int] = {}
            if query.min_price is not None:
                price["min"] = query.min_price
            if query.max_price is not None:
                price["max"] = query.max_price
            catalog["filters"]["price"] = price
        if cursor:
            catalog["pagination"]["cursor"] = cursor
        return catalog

    async def search_products(
        self,
        query: ShopifySearchQuery,
        *,
        cursor: dict[str, Any] | str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        if query.page > settings.shopify_max_pagination_pages:
            raise ShopifyError("The Shopify catalog pagination limit was reached.")
        mcp_cursor: str | None = None
        seen: set[str] = set()
        if isinstance(cursor, str):
            mcp_cursor = cursor
        elif isinstance(cursor, dict):
            value = cursor.get("cursor")
            if isinstance(value, str) and value:
                mcp_cursor = value
            seen_raw = cursor.get("seen_ids")
            if isinstance(seen_raw, list):
                seen = {item for item in seen_raw[:100] if isinstance(item, str)}

        products: list[dict[str, Any]] = []
        next_mcp_cursor = mcp_cursor
        has_next = False
        scan_limit = max(settings.shopify_max_scan_pages, 1)
        for _ in range(scan_limit):
            structured = await self._call_tool(
                "search_catalog",
                self._catalog_request(
                    query,
                    language=language,
                    cursor=next_mcp_cursor,
                    limit=query.per_page - len(products),
                ),
            )
            raw_products = structured.get("products")
            if not isinstance(raw_products, list):
                raise ShopifyError("The store returned an invalid Shopify product list.")
            for item in raw_products:
                if not isinstance(item, dict):
                    continue
                product_id = item.get("id")
                if not isinstance(product_id, str) or product_id in seen:
                    continue
                normalized = self._normalize_product(item, query)
                if normalized is None:
                    continue
                seen.add(product_id)
                products.append(normalized)
                if len(products) >= query.per_page:
                    break
            pagination = structured.get("pagination")
            if not isinstance(pagination, dict):
                pagination = {}
            candidate_cursor = pagination.get("cursor")
            has_next = pagination.get("has_next_page") is True and isinstance(candidate_cursor, str)
            next_mcp_cursor = candidate_cursor if has_next else None
            if len(products) >= query.per_page or not has_next:
                break

        next_cursor = None
        if has_next and next_mcp_cursor:
            next_cursor = {"cursor": next_mcp_cursor, "seen_ids": sorted(seen)[-100:]}
        return {
            "products": products,
            "page": query.page,
            "has_more": next_cursor is not None,
            "cursor": next_cursor,
            "query": query.model_dump(mode="json"),
        }

    async def get_product(
        self,
        product_id: str,
        *,
        selected: list[ShopifyOptionFilter] | None = None,
        currency: str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        catalog: dict[str, Any] = {
            "id": product_id,
            "context": {"language": language},
        }
        if currency:
            catalog["context"]["currency"] = currency
        if selected:
            catalog["selected"] = [
                {"name": option.name, "label": option.value}
                for option in selected
                if option.name
            ]
        structured = await self._call_tool("get_product", catalog)
        item = structured.get("product")
        if not isinstance(item, dict) or item.get("id") != product_id:
            raise ShopifyError("The store did not return the requested Shopify product.")
        query = ShopifySearchQuery(
            options=selected or [], currency=currency, available=True, product_id=product_id
        )
        product = self._normalize_product(item, query)
        if product is None:
            raise ShopifyError("The requested Shopify product or option is unavailable.")
        return product

    def _normalize_product(
        self, item: dict[str, Any], query: ShopifySearchQuery
    ) -> dict[str, Any] | None:
        product_id = item.get("id")
        name = plain_text(item.get("title"), limit=200)
        product_url = safe_store_link(item.get("url"), self.store_url)
        if not isinstance(product_id, str) or not product_id or not name or not product_url:
            return None
        raw_variants = item.get("variants")
        variants = [
            variant
            for variant in (raw_variants if isinstance(raw_variants, list) else [])
            if isinstance(variant, dict) and _variant_matches(variant, query)
        ]
        if not variants:
            return None
        featured = variants[0]
        amount = _amount(featured.get("price"))
        currency = _currency(featured.get("price"))
        if amount is None or currency is None:
            return None
        list_amount = _amount(featured.get("list_price"))
        on_sale = list_amount is not None and list_amount > amount

        media = featured.get("media")
        if not isinstance(media, list) or not media:
            media = item.get("media") if isinstance(item.get("media"), list) else []
        image_url = next(
            (
                safe
                for medium in media
                if isinstance(medium, dict) and medium.get("type") == "image"
                and (safe := _https_media_url(medium.get("url")))
            ),
            None,
        )
        attributes: list[dict[str, Any]] = []
        raw_options = item.get("options")
        for option in raw_options if isinstance(raw_options, list) else []:
            if not isinstance(option, dict):
                continue
            values = option.get("values") if isinstance(option.get("values"), list) else []
            attributes.append(
                {
                    "name": plain_text(option.get("name"), limit=100),
                    "taxonomy": None,
                    "terms": [
                        {
                            "name": plain_text(value.get("label"), limit=100),
                            "slug": None,
                            "available": value.get("available"),
                        }
                        for value in values
                        if isinstance(value, dict) and value.get("label")
                    ][:50],
                }
            )
        collection_url = None
        collection_name = None
        raw_collections = item.get("collections")
        for collection in raw_collections if isinstance(raw_collections, list) else []:
            if not isinstance(collection, dict):
                continue
            candidate = safe_store_link(collection.get("url"), self.store_url)
            if candidate:
                collection_url = candidate
                collection_name = plain_text(collection.get("title"), limit=100)
                break
        price = _price_text(amount, currency)
        regular = _price_text(list_amount, currency) if list_amount is not None else price
        return {
            "id": product_id,
            "name": name,
            "slug": item.get("handle") if isinstance(item.get("handle"), str) else None,
            "summary": _description(item.get("description")),
            "price": price,
            "regular_price": regular,
            "sale_price": price if on_sale else None,
            "currency_code": currency,
            "currency_symbol": "",
            "on_sale": on_sale,
            "is_in_stock": True,
            "has_options": bool(attributes),
            "image_url": image_url,
            "product_url": product_url,
            "attributes": attributes[:10],
            "collection_url": collection_url,
            "collection_name": collection_name,
        }


def shopify_product_tool_schema() -> dict[str, Any]:
    schema = ShopifySearchQuery.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search the connected Shopify product catalog, refine the previous "
                "search, request its next page, or inspect an exact prior result."
            ),
            "parameters": schema,
        },
    }
