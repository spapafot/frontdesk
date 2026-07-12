import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

// The public marketing site is served at the apex domain. `site` is required
// for correct canonical URLs, absolute Open Graph tags, and the sitemap
// generated at src/pages/sitemap.xml.ts.
export default defineConfig({
  site: "https://plugandplay.gr",
  integrations: [tailwind()],
});
