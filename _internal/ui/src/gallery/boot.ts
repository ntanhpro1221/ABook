import { installClock } from "./clock";
import { installDesktopApi } from "./desktopApi";
import { installFakeAudio } from "./fakeAudio";
import { resetData } from "./data";
import { DEFAULT_SCENARIO, galleryState } from "./state";
import type { Entry, Platform, Theme } from "./entries";
import { chromeStateEvent, type WindowChrome } from "@/desktop/windowChrome";

// Dựng thế giới giả cho một nền tảng: một lần mỗi trang (đồng hồ, máy chủ giả và Audio giả phải có trước khi app nạp). `prepare` đặt lại dữ liệu + kịch bản cho từng mục.

let platformInstalled: Platform | null = null;
let galleryChrome: WindowChrome | undefined;

export function installPlatform(platform: Platform, clock?: number): void {
  if (platformInstalled) {
    if (platformInstalled !== platform) throw new Error(`Trang đã dựng cho ${platformInstalled}, không đổi sang ${platform} được - tải lại trang.`);
    return;
  }
  platformInstalled = platform;
  installClock(clock);
  installDesktopApi();
  installFakeAudio();
}

export function prepare(entry: Entry, theme: Theme): void {
  if (window.__ABOOK_CHROME__ === galleryChrome) delete window.__ABOOK_CHROME__;
  if (entry.chrome && !window.__ABOOK_CHROME__) {
    const state = { maximized: false, focused: true, snapHovered: false, snapPressed: false };
    galleryChrome = { state, action: action => {
      if (action === "toggleMaximize") state.maximized = !state.maximized;
      window.dispatchEvent(new Event(chromeStateEvent));
    } };
    window.__ABOOK_CHROME__ = galleryChrome;
  }
  window.dispatchEvent(new Event("online"));
  resetData();
  galleryState.scenario = { ...DEFAULT_SCENARIO, ...entry.scenario };
  galleryState.missing.clear();
  galleryState.errors.length = 0;
  galleryState.ready = false;
  try {
    localStorage.clear();
    sessionStorage.clear();
    for (const [key, value] of Object.entries(entry.storage ?? {})) localStorage.setItem(key, value);
  } catch {
    // Kho bị chặn: vẫn dựng được, chỉ mất chủ đề đã chọn.
  }
  document.documentElement.dataset.galleryTheme = theme;
  document.documentElement.dataset.theme = theme;
}
