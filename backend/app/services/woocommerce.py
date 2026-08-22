"""Safe, read-only WooCommerce Store API access for public product catalogs."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings


class WooCommerceError(RuntimeError):
    """A bounded, customer-safe Store API failure."""


class ProductAttributeFilter(BaseModel):
    taxonomy: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=200)

    @field_validator("taxonomy", "slug")
    @classmethod
    def _safe_slug(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in value):
            raise ValueError("must be a lowercase taxonomy slug")
        return value


class ProductSearchQuery(BaseModel):
    search: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=200)
    attributes: list[ProductAttributeFilter] = Field(default_factory=list, max_length=5)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    on_sale: bool | None = None
    stock_status: list[Literal["instock", "outofstock", "onbackorder"]] = Field(
        default_factory=lambda: ["instock"], max_length=3
    )
    orderby: Literal[
        "date", "modified", "id", "title", "slug", "price", "popularity", "rating", "menu_order"
    ] = "menu_order"
    order: Literal["asc", "desc"] = "asc"
    page: int = Field(default=1, ge=1, le=100)
    per_page: int = Field(default=8, ge=1, le=24)

    @field_validator("search", "slug", "sku", "category")
    @classmethod
    def _trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def _price_order(self) -> "ProductSearchQuery":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot exceed max_price")
        return self


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def plain_text(value: Any, *, limit: int = 500) -> str:
    parser = _PlainText()
    try:
        parser.feed(str(value or ""))
    except Exception:  # malformed merchant-authored HTML is non-fatal
        return ""
    return " ".join(parser.parts)[:limit]


def normalize_store_url(value: str) -> str:
    """Return a canonical HTTPS store base URL, without query or fragment."""
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise WooCommerceError("Enter a valid HTTPS WooCommerce store URL.") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise WooCommerceError("The WooCommerce store URL must use HTTPS.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WooCommerceError(
            "The store URL cannot contain credentials, a query string, or a fragment."
        )
    if port not in (None, 443):
        raise WooCommerceError("The WooCommerce store URL must use the standard HTTPS port.")
    host = parsed.hostname.rstrip(".").lower()
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise WooCommerceError("The WooCommerce store must be publicly reachable.")
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise WooCommerceError("Enter a valid WooCommerce store hostname.") from exc
    netloc = f"[{ascii_host}]" if ":" in ascii_host else ascii_host
    path = parsed.path.rstrip("/")
    return urlunsplit(("https", netloc, path, "", ""))


async def _ensure_public_host(store_url: str) -> None:
    parsed = urlsplit(store_url)
    host = parsed.hostname
    if not host:
        raise WooCommerceError("The WooCommerce store URL has no hostname.")
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host, 443, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        raise WooCommerceError("The WooCommerce store hostname could not be resolved.") from exc
    if not addresses:
        raise WooCommerceError("The WooCommerce store hostname could not be resolved.")
    for address in addresses:
        try:
            resolved = ipaddress.ip_address(address[4][0])
        except ValueError as exc:
            raise WooCommerceError("The WooCommerce store resolved unexpectedly.") from exc
        if not resolved.is_global:
            raise WooCommerceError("The WooCommerce store must resolve only to public addresses.")


def _safe_https_url(value: Any, *, same_origin: str | None = None) -> str | None:
    try:
        parsed = urlsplit(str(value or ""))
        parsed_port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if same_origin:
        expected = urlsplit(same_origin)
        if (parsed.hostname.lower(), parsed_port or 443) != (
            (expected.hostname or "").lower(),
            expected.port or 443,
        ):
            return None
    return parsed.geturl()


def _format_price(raw: Any, minor_unit: int) -> str | None:
    try:
        amount = Decimal(str(raw)) / (Decimal(10) ** minor_unit)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return f"{amount:.{minor_unit}f}"


class WooCommerceStoreClient:
    def __init__(
        self,
        store_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        validate_dns: bool = True,
    ) -> None:
        self.store_url = normalize_store_url(store_url)
        self.api_base = f"{self.store_url}/wp-json/wc/store/v1"
        self.transport = transport
        self.validate_dns = validate_dns

    async def _get_json(
        self, path: str, params: list[tuple[str, str]] | None = None
    ) -> tuple[Any, httpx.Headers]:
        if self.validate_dns:
            await _ensure_public_host(self.store_url)
        url = f"{self.api_base}/{path.lstrip('/')}"
        timeout = httpx.Timeout(settings.woocommerce_timeout)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                transport=self.transport,
                headers={"Accept": "application/json", "User-Agent": "SECR-Catalog/1.0"},
            ) as client:
                async with client.stream("GET", url, params=params) as response:
                    if response.is_redirect:
                        raise WooCommerceError(
                            "The store redirected the API request. Use its final canonical HTTPS URL."
                        )
                    if response.status_code == 404:
                        raise WooCommerceError(
                            "WooCommerce's public Store API was not found on this site."
                        )
                    if response.status_code >= 400:
                        raise WooCommerceError(
                            f"The WooCommerce Store API returned HTTP {response.status_code}."
                        )
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > settings.woocommerce_max_response_bytes:
                        raise WooCommerceError("The WooCommerce response was too large.")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > settings.woocommerce_max_response_bytes:
                            raise WooCommerceError("The WooCommerce response was too large.")
                        chunks.append(chunk)
                    headers = response.headers
        except WooCommerceError:
            raise
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise WooCommerceError("The WooCommerce Store API could not be reached.") from exc
        try:
            return json.loads(b"".join(chunks)), headers
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WooCommerceError("The WooCommerce Store API returned invalid JSON.") from exc

    async def verify_and_discover(self) -> dict[str, Any]:
        products, product_headers = await self._get_json(
            "products", [("per_page", "1"), ("catalog_visibility", "visible")]
        )
        if not isinstance(products, list):
            raise WooCommerceError("The site did not return a WooCommerce product catalog.")

        categories_raw, _ = await self._get_json(
            "products/categories", [("per_page", "100"), ("hide_empty", "false")]
        )
        attributes_raw, _ = await self._get_json(
            "products/attributes", [("per_page", "100")]
        )
        categories = [
            {"id": item.get("id"), "name": plain_text(item.get("name"), limit=100), "slug": item.get("slug")}
            for item in (categories_raw if isinstance(categories_raw, list) else [])[:200]
            if isinstance(item, dict) and item.get("slug")
        ]

        async def attribute_with_terms(item: dict[str, Any]) -> dict[str, Any] | None:
            attribute_id = item.get("id")
            taxonomy = item.get("taxonomy") or item.get("slug")
            if not isinstance(attribute_id, int) or not isinstance(taxonomy, str):
                return None
            terms_raw, _ = await self._get_json(
                f"products/attributes/{attribute_id}/terms", [("per_page", "100")]
            )
            terms = [
                {"id": term.get("id"), "name": plain_text(term.get("name"), limit=100), "slug": term.get("slug")}
                for term in (terms_raw if isinstance(terms_raw, list) else [])[:100]
                if isinstance(term, dict) and term.get("slug")
            ]
            return {
                "id": attribute_id,
                "name": plain_text(item.get("name"), limit=100),
                "taxonomy": taxonomy,
                "terms": terms,
            }

        raw_attributes = [
            item for item in (attributes_raw if isinstance(attributes_raw, list) else [])[:20]
            if isinstance(item, dict)
        ]
        discovered = await asyncio.gather(
            *(attribute_with_terms(item) for item in raw_attributes)
        )
        attributes = [item for item in discovered if item is not None]

        currency: dict[str, Any] = {}
        if products and isinstance(products[0], dict):
            prices = products[0].get("prices")
            if isinstance(prices, dict):
                currency = {
                    "code": prices.get("currency_code"),
                    "minor_unit": prices.get("currency_minor_unit", 2),
                    "symbol": plain_text(prices.get("currency_symbol"), limit=8),
                }
        try:
            product_count = int(product_headers.get("x-wp-total", len(products)))
        except ValueError:
            product_count = len(products)
        return {
            "product_count": max(product_count, 0),
            "currency": currency,
            "categories": categories,
            "attributes": attributes,
        }

    async def search_products(self, query: ProductSearchQuery) -> dict[str, Any]:
        params: list[tuple[str, str]] = [
            ("page", str(query.page)),
            ("per_page", str(min(query.per_page, settings.woocommerce_max_products))),
            ("catalog_visibility", "visible"),
            ("orderby", query.orderby),
            ("order", query.order),
        ]
        for key in ("search", "slug", "sku", "category"):
            value = getattr(query, key)
            if value:
                params.append((key, value))
        if query.min_price is not None:
            params.append(("min_price", str(query.min_price)))
        if query.max_price is not None:
            params.append(("max_price", str(query.max_price)))
        if query.on_sale is not None:
            params.append(("on_sale", str(query.on_sale).lower()))
        for status in query.stock_status:
            params.append(("stock_status[]", status))
        for index, attribute in enumerate(query.attributes):
            params.extend(
                [
                    (f"attributes[{index}][attribute]", attribute.taxonomy),
                    (f"attributes[{index}][slug]", attribute.slug),
                ]
            )
        if len(query.attributes) > 1:
            params.append(("attribute_relation", "and"))

        raw, headers = await self._get_json("products", params)
        if not isinstance(raw, list):
            raise WooCommerceError("The store returned an invalid product list.")
        products = [self._normalize_product(item) for item in raw if isinstance(item, dict)]
        products = [item for item in products if item is not None]
        try:
            total_pages = int(headers.get("x-wp-totalpages", query.page))
        except ValueError:
            total_pages = query.page
        return {
            "products": products,
            "page": query.page,
            "has_more": query.page < total_pages,
            "query": query.model_dump(mode="json"),
        }

    def _normalize_product(self, item: dict[str, Any]) -> dict[str, Any] | None:
        product_id = item.get("id")
        name = plain_text(item.get("name"), limit=200)
        product_url = _safe_https_url(item.get("permalink"), same_origin=self.store_url)
        if not isinstance(product_id, int) or not name or not product_url:
            return None
        prices = item.get("prices") if isinstance(item.get("prices"), dict) else {}
        try:
            minor_unit = int(prices.get("currency_minor_unit", 2))
        except (TypeError, ValueError):
            minor_unit = 2
        minor_unit = min(max(minor_unit, 0), 6)
        images = item.get("images") if isinstance(item.get("images"), list) else []
        image_url = None
        if images and isinstance(images[0], dict):
            image_url = _safe_https_url(images[0].get("thumbnail") or images[0].get("src"))
        attributes: list[dict[str, Any]] = []
        for attribute in item.get("attributes") or []:
            if not isinstance(attribute, dict):
                continue
            terms = attribute.get("terms") if isinstance(attribute.get("terms"), list) else []
            attributes.append(
                {
                    "name": plain_text(attribute.get("name"), limit=100),
                    "taxonomy": attribute.get("taxonomy"),
                    "terms": [
                        {
                            "name": plain_text(term.get("name"), limit=100),
                            "slug": term.get("slug"),
                        }
                        for term in terms[:20]
                        if isinstance(term, dict) and term.get("slug")
                    ],
                }
            )
        return {
            "id": product_id,
            "name": name,
            "slug": item.get("slug"),
            "summary": plain_text(
                item.get("summary") or item.get("short_description"), limit=500
            ),
            "price": _format_price(prices.get("price"), minor_unit),
            "regular_price": _format_price(prices.get("regular_price"), minor_unit),
            "sale_price": _format_price(prices.get("sale_price"), minor_unit),
            "currency_code": prices.get("currency_code"),
            "currency_symbol": plain_text(prices.get("currency_symbol"), limit=8),
            "on_sale": bool(item.get("on_sale")),
            "is_in_stock": bool(item.get("is_in_stock")),
            "has_options": bool(item.get("has_options")),
            "image_url": image_url,
            "product_url": product_url,
            "attributes": attributes[:10],
        }


def product_tool_schema() -> dict[str, Any]:
    """DeepSeek/OpenAI-compatible function schema for the bounded catalog tool."""
    schema = ProductSearchQuery.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search the connected store's public product catalog. Use this when the "
                "customer asks to find, list, browse, filter, compare, or see a product."
            ),
            "parameters": schema,
        },
    }
