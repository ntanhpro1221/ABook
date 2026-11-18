// Trang đo chữ tự đo (src/testing/fitFixture) cho các test Chromium thật: dựng bằng vite (cùng Tailwind + phông app) và mở ở bề ngang điện thoại.
import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { build } from "vite";
import { openPage, waitUntil } from "./gallery_browser.mjs";

const ui = path.resolve(import.meta.dirname, "..");
const fixture = path.join(ui, "src/testing/fitFixture");

/** Dựng trang đo (gallery.html: tên mà serve() của gallery_browser cần). */
export async function buildFitFixture(outDir) {
  await build({
    configFile: false,
    logLevel: "silent",
    root: fixture,
    base: "./",
    cacheDir: path.join(ui, ".vite"),
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": path.join(ui, "src") } },
    build: { outDir, emptyOutDir: true, minify: false, chunkSizeWarningLimit: 4000, rollupOptions: { input: path.join(fixture, "gallery.html") } },
  });
}

/** Mở trang đo ở bề ngang điện thoại, chờ phông + hai khung. */
export async function openFixture(cdp, base, hash = "") {
  const page = await openPage(cdp, { width: 360, height: 2000, scale: 1, mobile: true, theme: "light" });
  await cdp.send("Page.navigate", { url: base + hash }, page.sessionId);
  await waitUntil(cdp, page.sessionId, "window.__ready === true", 60000, "trang đo sẵn sàng");
  return page;
}
