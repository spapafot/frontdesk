import { defineConfig } from "vite";

// Builds the embed loader as a single self-contained IIFE: dist-widget/widget.js
export default defineConfig({
  build: {
    outDir: "dist-widget",
    emptyOutDir: true,
    lib: {
      entry: "widget/loader.ts",
      name: "ChatWidget",
      formats: ["iife"],
      fileName: () => "widget.js",
    },
  },
});
