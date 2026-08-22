# E-commerce platform integration roadmap

Last reviewed: 22 August 2026

## Product decision

Natural-language product discovery is a core assistant capability, not a
premium-plan add-on. Every supported catalog provider is available on the
Trial, Starter, Pro, and Business plans. Normal per-plan website and message
limits still apply.

The integration remains read-only: visitors can search, refine, paginate, and
open products in the merchant's store. Carts, checkout, customers, orders,
returns, and other account-specific operations are out of scope.

## Current support

| Provider | Status | Connection | Catalog capabilities |
| --- | --- | --- | --- |
| WooCommerce | Shipped | Public HTTPS store URL | Search, filters, validated product cards, refinements, and pagination |
| Shopify | Shipped | Public HTTPS store URL and anonymous Storefront Catalog MCP | Search, filters, exact product details, validated product cards, refinements, and cursor pagination |

Only one catalog provider can be connected to an assistant site at a time.

## Market snapshot and priority

Wappalyzer's detected-store dataset currently places Wix eCommerce, Shopify,
and WooCommerce as the three most widely detected e-commerce technologies.
Because Shopify and WooCommerce are already supported, Wix is the missing
top-three provider and the next priority.

References:

- [Wappalyzer e-commerce usage](https://www.wappalyzer.com/technologies/ecommerce/)
- [Wix Catalog V3 product search](https://dev.wix.com/docs/api-reference/business-solutions/stores/catalog-v3/products-v3/search-products)
- [Wix app authentication](https://dev.wix.com/docs/build-apps/develop-your-app/access/authentication/about-authentication)
- [Squarespace Products API](https://developers.squarespace.com/commerce-apis/products)
- [Squarespace authentication](https://developers.squarespace.com/commerce-apis/authentication-and-permissions)
- [BigCommerce catalog API](https://docs.bigcommerce.com/developer/docs/admin/catalog-and-inventory/products-overview)

### Planned providers

1. **Wix eCommerce — next.** Add merchant OAuth installation and map Catalog
   V3 search, product details, variants, inventory, and cursor pagination onto
   the shared catalog-provider interface.
2. **Squarespace Commerce — planned.** Add OAuth and combine the Products and
   Inventory APIs. Account for the Products API's category limitations rather
   than inventing unsupported category filters.
3. **BigCommerce — planned.** Add OAuth/store identity and map its catalog
   filters, variants, images, inventory, and pagination onto the shared result
   contract.

PrestaShop and Adobe Commerce/Magento remain candidates, but are lower priority
because version fragmentation and self-hosted configuration make a dependable
generic integration more expensive. Ecwid is a lower-reach candidate worth
reconsidering if implementation speed becomes more important than merchant
coverage.

## Shared foundation required before Wix

- [ ] Register provider applications and callback URLs.
- [ ] Add a reusable OAuth authorization, callback, state-validation, refresh,
      revocation, and reconnect flow.
- [ ] Encrypt provider credentials at rest and prevent secrets from appearing
      in logs, API responses, analytics, or chat metadata.
- [ ] Persist provider-specific store identity separately from the public store
      URL.
- [ ] Extend the Product catalog settings card with provider-specific connect,
      connection-state, test, reconnect, disable, and delete actions.
- [ ] Preserve outbound-request protections, bounded requests, canonical
      same-store links, four validated cards, filter refinements, localization,
      and duplicate-free pagination for every adapter.
- [ ] Treat provider failures as catalog failures and never fabricate products
      or fall through to unrelated knowledge-base answers.

## Provider delivery checklist

Use this checklist for Wix, Squarespace, BigCommerce, and every later provider:

- [ ] Verify/connect a real store and an empty store.
- [ ] Search in Greek, Greeklish, and English.
- [ ] Enforce category, price, availability, sale, size, color, and other hard
      constraints supported by the provider.
- [ ] Return at most four validated product cards.
- [ ] Merge follow-up refinements into the previous effective search.
- [ ] Paginate without duplicates and reset pagination when filters change.
- [ ] Use exact-product lookup only for previously validated products.
- [ ] Return canonical same-store product and collection links; do not
      manufacture unsupported filtered storefront URLs.
- [ ] Cover OAuth failures, expired/revoked credentials, rate limits, timeouts,
      malformed responses, oversized responses, unsafe redirects, private DNS,
      and off-store product links.
- [ ] Pass backend, frontend, widget, migration, and production-build suites.
- [ ] Update README setup and architecture documentation.
- [ ] Update both pricing surfaces to name the newly shipped provider:
      `site/src/data/pricing.ts` and `frontend/src/pages/BillingPage.tsx`.
- [ ] Confirm the feature is present on Trial, Starter, Pro, and Business and
      that no provider-specific plan gate has been introduced.
- [ ] Update marketing feature copy and release notes only after the provider is
      production-ready.

## Plan-card wording policy

Pricing cards must describe what is available in production. Until Wix ships,
the shared feature text is:

> AI product catalog search (WooCommerce & Shopify)

After another provider ships, update the provider list everywhere in the same
release. Planned providers must not be presented as currently available.
