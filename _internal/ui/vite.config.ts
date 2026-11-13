/// <reference types="vitest/config" />
import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Bản build nằm trong package Python (abook/webui/static) để app chạy không cần Node.
// Không đặt tên "dist": .gitignore của repo bỏ qua mọi thư mục dist/.
// Máy chủ giao diện từ chối yêu cầu mang Origin của trang khác, kể cả khi chạy `--dev` không mã phiên (soát bảo mật 12-11). Trang Vite
// chính là giao diện, nên Origin của nó được đổi thành Origin của máy chủ; Origin khác (trang web lạ gửi vào cổng Vite) giữ nguyên để
// máy chủ từ chối. `changeOrigin` chỉ đổi Host.
const BACKEND = "http://127.0.0.1:8765";
const VITE_ORIGINS = new Set(["http://localhost:5173", "http://127.0.0.1:5173"]);
const devBackend: ProxyOptions = {
  target: BACKEND,
  changeOrigin: true,
  configure: (proxy) => {
    proxy.on("proxyReq", (proxyReq, req) => {
      const origin = req.headers.origin;
      if (origin && VITE_ORIGINS.has(origin)) proxyReq.setHeader("origin", BACKEND);
    });
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  // Test quét cả cây mã (máy dò) chạy riêng dưới 1 giây nhưng cạnh 300 file khác có lúc quá hạn mặc định 5 s; 30 s vẫn bắt được test treo.
  test: { testTimeout: 30_000, hookTimeout: 60_000 },
  build: {
    outDir: path.resolve(import.meta.dirname, "../abook/webui/static"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
  },
  server: {
    port: 5173,
    strictPort: true,
    // Danh sách thành phần bên thứ ba đọc thẳng docs/THIRD_PARTY.md (shared/thirdParty.ts), hằng số trộn nhạc đọc thẳng
    // abook/webui/assets/music_mix.json (listen/musicBed.ts) - nằm ngoài thư mục ui.
    fs: {
      allow: [import.meta.dirname, path.resolve(import.meta.dirname, "../docs/THIRD_PARTY.md"),
        path.resolve(import.meta.dirname, "../abook/webui/assets/music_mix.json")],
    },
    proxy: {
      "/api": devBackend,
      "/media": devBackend,
    },
  },
});
