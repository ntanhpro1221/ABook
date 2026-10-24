import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { installDetailsMotion } from "@/shared/motion";
import { createAppQueryClient } from "@/shared/queryClient";

// Dựng ĐÚNG cây của app như hai lối vào thật (src/main.tsx, src/android/main.tsx) - chỉ khác: trả hàm gỡ, để test dựng lần lượt từng
// mục trong cùng một trang. Mã app nạp bằng import động: Capacitor giả, fetch giả, đồng hồ giả phải có trước khi mô-đun app đầu tiên chạy.

let motionInstalled = false;

export async function mountApp(platform: "phone" | "desktop", container: HTMLElement): Promise<() => void> {
  if (!motionInstalled) {
    motionInstalled = true;
    installDetailsMotion();
  }
  const client = createAppQueryClient();
  const root = createRoot(container);
  if (platform === "phone") {
    const [{ setApiTransport }, { setNativeMusicImport }, { initAndroidSource }, { AndroidApp }, { localStudio }, { nativeMusicImport }] = await Promise.all([
      import("@/studio/api"),
      import("@/studio/musicImport"),
      import("@/android/androidSource"),
      import("@/android/App"),
      import("@/android/localStudio"),
      import("@/android/musicImport"),
    ]);
    setApiTransport(localStudio);
    setNativeMusicImport(nativeMusicImport);
    await initAndroidSource();
    root.render(
      <StrictMode>
        <QueryClientProvider client={client}>
          <AndroidApp />
        </QueryClientProvider>
      </StrictMode>,
    );
  } else {
    const { App } = await import("@/desktop/App");
    root.render(
      <StrictMode>
        <QueryClientProvider client={client}>
          <App />
        </QueryClientProvider>
      </StrictMode>,
    );
  }
  return () => {
    root.unmount();
    client.clear();
  };
}
