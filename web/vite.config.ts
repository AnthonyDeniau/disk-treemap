import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";
import { fileURLToPath } from "node:url";
import { readFile, rename, writeFile } from "node:fs/promises";

export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  plugins: [
    {
      name: "development-only-csp",
      apply: "serve",
      transformIndexHtml(html) {
        return html.replace(
          /content="default-src 'none';[^\"]+"/,
          `content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws:; img-src 'self' data:"`,
        );
      },
    },
    react(),
    viteSingleFile(),
    {
      name: "package-offline-viewer",
      async closeBundle() {
        await rename(
          new URL("../src/disk_treemap/assets/index.html", import.meta.url),
          new URL("../src/disk_treemap/assets/viewer.html", import.meta.url),
        );
        const viewer = new URL(
          "../src/disk_treemap/assets/viewer.html",
          import.meta.url,
        );
        const notices = await readFile(
          new URL("../THIRD_PARTY_NOTICES.md", import.meta.url),
          "utf8",
        );
        const html = await readFile(viewer, "utf8");
        await writeFile(
          viewer,
          html.replace("</head>", `<!--\n${notices}\n-->\n</head>`),
        );
      },
    },
  ],
  build: {
    outDir: fileURLToPath(
      new URL("../src/disk_treemap/assets", import.meta.url),
    ),
    emptyOutDir: true,
    rollupOptions: { output: { entryFileNames: "viewer.js" } },
  },
});
