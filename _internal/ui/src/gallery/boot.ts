import { installCapacitor } from "./capacitor";
import { installClock } from "./clock";
import { installDesktopApi } from "./desktopApi";
import { installFakeAudio } from "./fakeAudio";
import { capacitorApp, ebookLibrary, ebookPlayer, readAloud } from "./phoneNative";
import { resetData } from "./data";
import { DEFAULT_SCENARIO, galleryState } from "./state";
import type { Entry, Theme } from "./entries";

// Dựng thế giới giả cho một nền tảng: một lần mỗi trang (Capacitor phải có trước khi @capacitor/core nạp, và quyết định
// "đây là app Android" cố định suốt trang). `prepare` đặt lại dữ liệu + kịch bản cho từng mục.

let platformInstalled: "phone" | "desktop" | null = null;

export function installPlatform(platform: "phone" | "desktop", clock?: number): void {
  if (platformInstalled) {
    if (platformInstalled !== platform) throw new Error(`Trang đã dựng cho ${platformInstalled}, không đổi sang ${platform} được - tải lại trang.`);
    return;
  }
  platformInstalled = platform;
  installClock(clock);
  // Cả hai nền tảng: máy chủ giả (điện thoại dùng nó cho các lệnh sửa sách qua EbookLibrary.studio).
  installDesktopApi();
  if (platform === "phone") {
    installCapacitor({ EbookPlayer: ebookPlayer, EbookLibrary: ebookLibrary, ReadAloud: readAloud, App: capacitorApp });
    installTouchMedia();
  } else installFakeAudio();
}

export function prepare(entry: Entry, theme: Theme): void {
  window.dispatchEvent(new Event("online"));
  resetData();
  galleryState.scenario = { ...DEFAULT_SCENARIO, ...entry.scenario };
  galleryState.missing.clear();
  galleryState.errors.length = 0;
  galleryState.ready = false;
  try {
    localStorage.clear();
    sessionStorage.clear();
    // Điện thoại: giao diện sáng / tối nằm trong tuỳ chọn của trình phát (android/settings.ts); máy tính hỏi /api/preferences.
    localStorage.setItem("abook-player-settings", JSON.stringify({ theme, ...entry.phoneSettings }));
    for (const [key, value] of Object.entries(entry.storage ?? {})) localStorage.setItem(key, value);
  } catch {
    // Kho bị chặn: vẫn dựng được, chỉ mất chủ đề đã chọn.
  }
  document.documentElement.dataset.galleryTheme = theme;
  document.documentElement.dataset.theme = theme;
}

/** Điện thoại: màn cảm ứng, không có chuột - `matchMedia("(pointer: coarse)")` đúng, `(hover: hover)` sai (app ẩn gợi ý phím tắt, nới vùng chạm).
 *  Chỉ phần JS; CSS `@media (pointer: coarse)` cần trình duyệt giả lập cảm ứng (scripts/gallery_shots.mjs làm việc đó). */
function installTouchMedia(): void {
  const real = window.matchMedia?.bind(window);
  if (!real) return;
  const touch: Record<string, boolean> = { "(pointer: coarse)": true, "(any-pointer: coarse)": true, "(pointer: fine)": false, "(hover: hover)": false, "(hover: none)": true };
  window.matchMedia = (query: string) => {
    const answer = touch[query.trim()];
    if (answer === undefined) return real(query);
    const list = real(query);
    return {
      matches: answer,
      media: query,
      onchange: null,
      addEventListener: list.addEventListener.bind(list),
      removeEventListener: list.removeEventListener.bind(list),
      addListener: list.addListener.bind(list),
      removeListener: list.removeListener.bind(list),
      dispatchEvent: list.dispatchEvent.bind(list),
    } as MediaQueryList;
  };
}
