import type { APIRoute } from "astro";
import { SITE } from "../config";
import { LEGAL_ORDER } from "../data/legal";

// Hand-rolled sitemap: the marketing surface is small and fully known at build
// time, so we list its canonical URLs directly rather than depend on the
// sitemap integration.
const paths = ["/", ...LEGAL_ORDER.map((slug) => `/${slug}`)];

export const GET: APIRoute = () => {
  const urls = paths
    .map((path) => {
      const loc = new URL(path, SITE.url).href;
      return `  <url><loc>${loc}</loc></url>`;
    })
    .join("\n");

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;

  return new Response(body, {
    headers: { "Content-Type": "application/xml" },
  });
};
