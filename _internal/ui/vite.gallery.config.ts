import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Phòng trưng bày màn hình (src/gallery/README.md) - CHỈ khi phát triển: lối vào riêng gallery.html, dựng ra dist/gallery (thư mục dist/
// bị .gitignore bỏ qua), không đụng tới bản dựng phát hành (vite.config.ts -> abook/webui/static, vite.android.config.ts -> mobile/www).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  // Bìa sách giả (SVG tự vẽ); thư mục public/ của app (biểu tượng, manifest) không cần ở đây.
  publicDir: path.resolve(import.meta.dirname, "src/gallery/public"),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/gallery"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 4000,
    rollupOptions: { input: path.resolve(import.meta.dirname, "gallery.html") },
  },
  server: {
    port: 5174,
    strictPort: false,
    fs: {
      allow: [import.meta.dirname, path.resolve(import.meta.dirname, "../docs/THIRD_PARTY.md"),
        path.resolve(import.meta.dirname, "../abook/webui/assets/music_mix.json")],
    },
  },
  preview: { port: 5174, strictPort: false },
});
