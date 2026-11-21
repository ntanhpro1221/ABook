import { createElement, Suspense, use, type ComponentType, type ReactNode } from "react";

// Màn ít dùng (Studio, Cài đặt, hộp sửa câu) nằm ở chunk riêng: gói đầu của app chỉ còn Thư viện, trang sách, trình phát (docs/PERF_WEB.md).
// Không phải React.lazy: chunk đã về (nạp sẵn lúc rảnh - preloadWhenIdle) thì dựng thẳng, không treo một nhịp Suspense - mở Studio lần đầu
// không chớp khung chờ. Chưa về thì khung chờ `fallback` đúng hình nội dung (DESIGN mục 2: đang tải = khung xám), không xoay vòng.

export type LazyComponent<P> = ComponentType<P> & { preload: () => Promise<unknown> };

export function lazyComponent<P extends object>(load: () => Promise<ComponentType<P>>, fallback: ReactNode = null): LazyComponent<P> {
  let loaded: ComponentType<P> | null = null;
  let loading: Promise<ComponentType<P>> | null = null;
  const preload = () => {
    loading ??= load().then(
      (component) => (loaded = component),
      (error: unknown) => {
        // Mạng / file hỏng: lần sau thử nạp lại, không giữ lời hứa hỏng mãi.
        loading = null;
        throw error;
      },
    );
    return loading;
  };
  function Loaded(props: P) {
    return createElement(loaded ?? use(preload()), props);
  }
  // Luôn cùng một hình cây Suspense > Loaded: chunk đã về thì Loaded dựng thẳng, không treo, không chớp khung chờ. Trả thẳng
  // `loaded` khi đã về (như trước 19-11) làm lần vẽ lại đầu tiên sau khi chunk về ĐỔI hình cây - React gỡ và dựng lại cả màn:
  // menu "…" vừa mở biến mất dưới tay, hộp thoại / ô đang gõ mất (gateflake: Studio "Thêm tuỳ chọn" mở rồi tự đóng).
  function Lazy(props: P) {
    return <Suspense fallback={fallback}><Loaded {...props} /></Suspense>;
  }
  return Object.assign(Lazy, { preload });
}

/** Nạp sẵn các chunk khi trình duyệt rảnh (sau khi màn đầu đã vẽ): bấm sang Studio / Cài đặt không phải chờ tải. */
export function preloadWhenIdle(components: readonly { preload: () => Promise<unknown> }[], delay = 1500): () => void {
  let cancelled = false;
  const run = () => {
    if (cancelled) return;
    for (const component of components) component.preload().catch(() => undefined);
  };
  const idle = (globalThis as { requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number }).requestIdleCallback;
  const timer = window.setTimeout(() => (idle ? idle(run, { timeout: 4000 }) : run()), delay);
  return () => {
    cancelled = true;
    window.clearTimeout(timer);
  };
}
