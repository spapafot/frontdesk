# Plug & Play- marketing site

The public site at **plugandplay.gr**: the landing page and legal pages. It is a
static [Astro](https://astro.build) project so every page ships real SEO
metadata (title, description, canonical, Open Graph) and JSON-LD schema, with no
client-side JavaScript.

## Structure

```
src/
  config.ts               Brand name, URLs, app link (PUBLIC_APP_URL)
  data/legal.ts           Legal page content + order
  components/             Header, Footer, SEO, and the static feature showcases
  layouts/BaseLayout.astro
  pages/
    index.astro           Landing (hero + feature sections + CTA)
    [slug].astro          Legal pages (/privacy-policy, /terms-of-service, …)
    sitemap.xml.ts        Generated sitemap
public/                   robots.txt, PNG logo assets, favicons, og.png
```

The feature showcases are static reimplementations of the admin app's UI
(chat bubbles, knowledge base, install snippet, analytics), styled with the same
Tailwind palette so they mirror the real product without shipping React.

## Develop

```bash
npm install
npm run dev      # http://localhost:4321
```

## Build & check

```bash
npm run check    # astro type-check
npm run build    # static output to dist/
```

## Configuration

- `PUBLIC_APP_URL`- where "Log in" / "Register" / CTAs point. Defaults to
  `https://app.plugandplay.gr`.
- The apex origin lives in `astro.config.mjs` (`site`) and `src/config.ts`.

## Deploy

Deploy to Cloudflare Pages (project `plugandplay-site`) with
`deploy/cloudflare/deploy-site.sh`.

## Notes

- `public/og.png` is the 1200×630 social-share image referenced by
  `SITE.ogImage` in `src/config.ts`.
