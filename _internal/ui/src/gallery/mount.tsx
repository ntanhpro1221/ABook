import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { installDetailsMotion } from "@/shared/motion";
import { createAppQueryClient } from "@/shared/queryClient";
import type { StateStory } from "./StateStories";

// Dựng ĐÚNG cây của app như lối vào thật (src/main.tsx) - chỉ khác: trả hàm gỡ, để test dựng lần lượt từng
// mục trong cùng một trang. Mã app nạp bằng import động: fetch giả, đồng hồ giả phải có trước khi mô-đun app đầu tiên chạy.

let motionInstalled = false;

export async function mountApp(container: HTMLElement, showcase?: StateStory): Promise<() => void> {
  if (!motionInstalled) {
    motionInstalled = true;
    installDetailsMotion();
  }
  const client = createAppQueryClient();
  // Kịch bản lỗi chụp sau đủ lượt thử, không đứng ở khoảng nghỉ trước lần thử kế.
  const defaults = client.getDefaultOptions();
  client.setDefaultOptions({ ...defaults, queries: { ...defaults.queries, retryDelay: 0 } });
  const root = createRoot(container);
  if (showcase) {
    const { StateStories } = await import("./StateStories");
    root.render(<StrictMode><StateStories state={showcase} /></StrictMode>);
    return () => { root.unmount(); client.clear(); };
  }
  const { App, preloadScreens } = await import("@/desktop/App");
  await preloadScreens();
  root.render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
  return () => {
    root.unmount();
    client.clear();
  };
}
