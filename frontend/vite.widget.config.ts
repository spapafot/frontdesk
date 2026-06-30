import { defineConfig } from "vite";

// Builds the iframe chat app (index.html + app.ts + widget.css) into
// dist-widget/app. Run AFTER the loader build so it doesn't wipe widget.js.
export default defineConfig({
  root: "widget",
  base: "./",
  build: {
    outDir: "../dist-widget/app",
    emptyOutDir: true,
  },
});
