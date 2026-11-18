// @vitest-environment happy-dom
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, expect, it, vi } from "vitest";
import { SAVED_THEME_KEY, saveTheme, savedTheme } from "./savedTheme";

// Soát tapthru5 S4 (18-11): trang lúc tải tô nền theo giao diện chọn TRONG app, không theo máy - máy để Tối, app chọn Sáng thì khung đầu sáng.
const html = readFileSync(join(import.meta.dirname, "../../index.html"), "utf8");
const boot = html.match(/<script>([\s\S]*?)<\/script>/)![1];

function runBoot(systemDark: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: systemDark && query.includes("dark") }));
  delete document.documentElement.dataset.theme;
  new Function(boot)();
  return document.documentElement.dataset.theme;
}

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); delete (window as { __ABOOK_BOOT_THEME__?: string }).__ABOOK_BOOT_THEME__; });

it("the loading page reads the saved in-app choice before the OS", () => {
  expect(boot).toContain(`'${SAVED_THEME_KEY}'`);
  expect(runBoot(true)).toBe("dark");                 // chưa lưu gì: theo máy
  saveTheme("light");
  expect(runBoot(true)).toBe("light");                // máy Tối, app Sáng: khung đầu sáng
  saveTheme("dark");
  expect(runBoot(false)).toBe("dark");
  saveTheme("system");
  expect(runBoot(true)).toBe("dark");
  expect(runBoot(false)).toBe("light");
  saveTheme("light");
  (window as { __ABOOK_BOOT_THEME__?: string }).__ABOOK_BOOT_THEME__ = "dark";
  expect(runBoot(false)).toBe("dark");                // vỏ máy tính đã đọc preferences.json: thắng
});

it("only real choices are saved, and a blocked storage falls back to the OS", () => {
  saveTheme("sepia");
  expect(localStorage.getItem(SAVED_THEME_KEY)).toBeNull();
  saveTheme("dark");
  expect(savedTheme()).toBe("dark");
  saveTheme("system");
  expect(savedTheme()).toBeNull();
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  expect(savedTheme()).toBeNull();
  expect(runBoot(true)).toBe("dark");
});

it("the app saves the theme it applies from preferences", () => {
  const app = readFileSync(join(import.meta.dirname, "../desktop/App.tsx"), "utf8");
  expect(app).toMatch(/if \(theme !== undefined\) saveTheme\(theme\);/);
  expect(app).toMatch(/window\.__ABOOK_BOOT_THEME__ \?\? savedTheme\(\)/);
});
