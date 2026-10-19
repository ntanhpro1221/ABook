import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import { createAppQueryClient } from "@/shared/queryClient";
import { setApiTransport } from "@/studio/api";
import { setNativeMusicImport } from "@/studio/musicImport";
import { initAndroidSource } from "./androidSource";
import { AndroidApp } from "./App";
import { localStudio } from "./localStudio";
import { nativeMusicImport } from "./musicImport";

// Sửa sách trên điện thoại: mọi `api()` đi vào lõi native (LocalStudio.kt), không có server để `fetch`.
setApiTransport(localStudio);
// "Nhập nhạc của tôi…": hộp chọn file của hệ thống + nhập ở lõi native (không có hộp chọn file của máy chủ).
setNativeMusicImport(nativeMusicImport);

const client = createAppQueryClient();

void initAndroidSource().finally(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <AndroidApp />
      </QueryClientProvider>
    </StrictMode>,
  );
});
