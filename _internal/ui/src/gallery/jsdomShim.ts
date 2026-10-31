import { installPlatform } from "./boot";
import type { Platform } from "./entries";

// Phòng trưng bày trong jsdom (axe-core chạy chuẩn nhất trên jsdom; các bài thử khác của gallery dùng happy-dom). jsdom không có bố cục, không
// chuyển động, không canvas: vá đúng những API app gọi tới, rồi dựng thế giới giả TRƯỚC khi mã app nạp (runEntry nạp app bằng import động).

/** Phần CSS của Tailwind quyết định thứ gì bị ẩn: jsdom không nạp styles.css, mà thiếu nó thì "hidden md:flex" (thanh bên điện thoại / máy tính)
 *  hiện cả hai bản - axe sẽ báo trùng mốc trang, ô file ẩn thiếu nhãn... Khổ máy tính 1440 px: mọi mốc sm / md / lg / xl đều bật. */
const BREAKPOINTS = ["sm", "md", "lg", "xl"];
const DISPLAYS = ["flex", "grid", "block", "inline-flex", "contents"];
const HIDING_CSS = [
  ".hidden{display:none}",
  ...DISPLAYS.map((display) => `${BREAKPOINTS.map((bp) => `.${bp}\\:${display}`).join(",")}{display:${display}}`),
  `${BREAKPOINTS.map((bp) => `.${bp}\\:hidden`).join(",")}{display:none}`,
].join("");

export function installJsdomGallery(platform: Platform): void {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
  globals.IntersectionObserver ??= class { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } };
  globals.DOMMatrixReadOnly ??= class { a = 1; b = 0; c = 0; d = 1; e = 0; f = 0; m41 = 0; m42 = 0; };
  const css = (globals.CSS ??= {}) as Record<string, unknown>;
  css.escape ??= (value: string) => value.replace(/[^a-zA-Z0-9_-]/g, (char) => `\\${char}`);
  window.matchMedia ??= ((query: string) => ({
    matches: false, media: query, onchange: null, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
  })) as typeof window.matchMedia;
  // Bìa sách đo màu chủ đạo bằng canvas: không có canvas thì giữ nền thường (như bìa không có màu rõ).
  HTMLCanvasElement.prototype.getContext = (() => null) as never;
  Element.prototype.setPointerCapture ??= function () {};
  Element.prototype.releasePointerCapture ??= function () {};
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.scrollTo ??= function () {};
  Element.prototype.scrollIntoView ??= function () {};
  installPlatform(platform);
  document.documentElement.lang = "vi";
}

/** Gắn lại phần CSS ẩn / hiện vào <head> (mỗi mục dựng lại trang). */
export function attachHidingCss(): void {
  let sheet = document.head.querySelector<HTMLStyleElement>("style[data-jsdom-hiding]");
  if (!sheet) {
    sheet = document.createElement("style");
    sheet.setAttribute("data-jsdom-hiding", "");
    sheet.textContent = HIDING_CSS;
  }
  document.head.append(sheet);
}
