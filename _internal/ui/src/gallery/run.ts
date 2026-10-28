import { installPlatform, prepare } from "./boot";
import { mountApp } from "./mount";
import { galleryState } from "./state";
import type { Entry, Theme } from "./entries";

// Dựng một mục trưng bày: thế giới giả -> trang của app -> thao tác -> chờ trang đứng yên. Dùng chung cho khung trưng bày (frame) và test.

let watching = false;

/** Cảnh báo chỉ có ở bản dev mà app thật cũng in ra (không do dữ liệu giả): ghi riêng vào `galleryState.known`, không tính là lỗi của mục.
 *  - React Query "No queryFn": app đọc bộ đệm bằng `useQuery({ queryKey, enabled: false })` không kèm queryFn (listen/player.tsx
 *    ["listen","library"], ["listen","download",<mã>]) - React Query bản dev báo mỗi lần dựng. */
const KNOWN_DEV_WARNINGS = [
  /^\[\[.*\]\]: No queryFn was passed as an option/,
];

/** Lỗi trong lúc dựng (console.error, lỗi không bắt) vào `galleryState.errors` - test đòi rỗng, script chụp ghi ra. */
function watchErrors(): void {
  if (watching) return;
  watching = true;
  const original = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    const text = args.map((arg) => (arg instanceof Error ? arg.stack ?? arg.message : String(arg))).join(" ");
    if (KNOWN_DEV_WARNINGS.some((pattern) => pattern.test(text))) galleryState.known.add(text.slice(0, 160));
    else galleryState.errors.push(text);
    original(...args);
  };
  window.addEventListener("error", (event) => galleryState.errors.push(`error: ${event.message}`));
  window.addEventListener("unhandledrejection", (event) => galleryState.errors.push(`unhandledrejection: ${String((event.reason as Error)?.stack ?? event.reason)}`));
}

/** Chờ trang thôi đổi: không còn đổi DOM trong `quiet` ms và mọi chuyển động hữu hạn đã chạy xong (vòng quay "đang tải" lặp mãi thì bỏ qua). */
export async function waitStill(quiet = 400, timeout = 8000): Promise<void> {
  const started = performance.now();
  let last = performance.now();
  const observer = typeof MutationObserver === "function" ? new MutationObserver(() => (last = performance.now())) : null;
  observer?.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
  try {
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 50));
      const now = performance.now();
      if (now - started > timeout) return;
      const moving = typeof document.getAnimations === "function"
        ? document.getAnimations().some((animation) => animation.playState === "running" && animation.effect?.getComputedTiming().endTime !== Infinity)
        : false;
      if (!moving && now - last >= quiet) return;
    }
  } finally {
    observer?.disconnect();
  }
}

/** `quiet`: bao lâu không đổi DOM thì coi là đứng yên (test dùng số nhỏ cho nhanh). */
export async function runEntry(entry: Entry, theme: Theme, container: HTMLElement, { quiet = 400, settleTimeout = 8000 } = {}): Promise<() => void> {
  watchErrors();
  installPlatform(entry.platform, entry.clock);
  prepare(entry, theme);
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${entry.route}`);
  const unmount = await mountApp(entry.platform, container, entry.showcase);
  await waitStill(quiet, settleTimeout);
  if (entry.act) {
    try {
      await entry.act();
    } catch (error) {
      galleryState.errors.push(`act: ${(error as Error).message}`);
    }
    await waitStill(quiet, settleTimeout);
  }
  // Trang mới mở đưa tiêu điểm vào tiêu đề (shared/motion usePageFocus) - viền tiêu điểm ấy chỉ làm bẩn ảnh chụp.
  const focused = document.activeElement as HTMLElement | null;
  if (focused?.matches("h1, h2, [tabindex='-1']")) focused.blur();
  galleryState.ready = true;
  return unmount;
}
