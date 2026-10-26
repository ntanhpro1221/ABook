// @vitest-environment jsdom
import { expect, it } from "vitest";
import { ENTRIES } from "./entries";
import { attachHidingCss, installJsdomGallery } from "./jsdomShim";
import { galleryState } from "./state";
import { dialogOpener } from "@/shared/ui";

// Bàn phím trên máy tính, MỌI lớp nổi mà phòng trưng bày mở (hộp thoại, hộp xác nhận, menu, bảng nổi) trên cây desktop/App.tsx thật:
// - mở ra thì tiêu điểm nằm trong lớp trên cùng;
// - hộp thoại giữ tiêu điểm: Tab / Shift+Tab đi hết một vòng vẫn ở trong hộp (bảng nổi không chặn trang thì được phép để Tab đi ra);
// - Esc đóng ĐÚNG lớp trên cùng (lớp dưới còn mở), tiêu điểm về lớp ngay dưới, đóng hết thì về nút đã mở lớp đầu tiên
//   (mở từ mục menu thì là nút mở menu ấy).
// jsdom không tự chuyển tiêu điểm khi nhấn Tab: `tab()` làm như trình duyệt - gửi phím xuống phần tử đang giữ tiêu điểm, app / Radix không chặn
// thì sang phần tử nhận Tab kế theo thứ tự trong trang.

installJsdomGallery("desktop");

const LAYER = '[data-state="open"]:is([role="dialog"], [role="alertdialog"], [role="menu"])';
const TABBABLE = 'a[href], button, input, select, textarea, summary, [tabindex], [contenteditable="true"]';

const openLayers = () => [...document.querySelectorAll<HTMLElement>(LAYER)].filter((layer) => !layer.closest("[inert]") && !layer.hasAttribute("inert"));
const top = () => openLayers().at(-1) ?? null;
const active = () => document.activeElement as HTMLElement | null;

function shown(element: Element): boolean {
  for (let node: Element | null = element; node; node = node.parentElement) {
    if (node.hasAttribute("hidden") || getComputedStyle(node).display === "none") return false;
  }
  return true;
}

function tabbables(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>(TABBABLE)].filter((element) =>
    element.tabIndex >= 0 && !(element as HTMLButtonElement).disabled && !element.closest("[inert]") && !(element instanceof HTMLInputElement && element.type === "hidden") && shown(element));
}

async function press(key: string, shiftKey = false): Promise<boolean> {
  const target = active() ?? document.body;
  const event = new KeyboardEvent("keydown", { key, shiftKey, bubbles: true, cancelable: true });
  const allowed = target.dispatchEvent(event);
  target.dispatchEvent(new KeyboardEvent("keyup", { key, shiftKey, bubbles: true, cancelable: true }));
  return allowed;
}

async function tab(shiftKey = false): Promise<void> {
  const from = active();
  if (await press("Tab", shiftKey)) {
    const order = tabbables();
    const at = from ? order.indexOf(from) : -1;
    const next = order[(at + (shiftKey ? -1 : 1) + order.length) % order.length];
    next?.focus();
  }
  await new Promise((resolve) => setTimeout(resolve, 0));
}

const settle = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms));
const describe = (element: Element | null) => element ? `${element.tagName.toLowerCase()} "${element.getAttribute("aria-label") ?? element.textContent?.trim().slice(0, 40)}"` : "null";

/** Hộp chặn cả trang (Dialog của Radix): phải giữ tiêu điểm. Bảng nổi neo vào nút (Popover) thì không chặn trang. */
const traps = (layer: HTMLElement) => layer.matches('[role="dialog"], [role="alertdialog"]') && !layer.closest("[data-radix-popper-content-wrapper]");

const entries = ENTRIES.filter((entry) => entry.platform === "desktop" && entry.act);
const reached = new Set<string>();

for (const entry of entries) {
  it(`bàn phím: ${entry.id} - ${entry.title}`, async () => {
    const { runEntry } = await import("./run");
    attachHidingCss();
    // Nút đã mở lớp: cú bấm cuối cùng của thao tác nằm NGOÀI mọi lớp đang mở (bấm trong menu / hộp là chọn mục, không phải mở lớp mới từ trang).
    let opener: Element | null = null;
    const remember = (event: Event) => {
      if (event.target instanceof Element && !event.target.closest(LAYER)) opener = event.target.closest("button, a, [role=button], [role=tab]") ?? event.target;
    };
    document.addEventListener("click", remember, true);
    const container = document.createElement("div");
    document.body.append(container);
    // runEntry bỏ tiêu điểm khỏi phần tử tabindex=-1 cho ảnh chụp sạch viền - với menu / hộp đó là chính lớp nổi. Ở đây giữ nguyên.
    const blur = HTMLElement.prototype.blur;
    HTMLElement.prototype.blur = function (this: HTMLElement) { if (!this.closest(LAYER)) blur.call(this); };
    const unmount = await runEntry(entry, "light", container, { quiet: 120 }).finally(() => { HTMLElement.prototype.blur = blur; });
    document.removeEventListener("click", remember, true);
    try {
      expect(galleryState.errors, galleryState.errors.join("\n")).toEqual([]);
      const layers = openLayers();
      if (!layers.length) return;
      reached.add(entry.id);
      const first = top()!;
      // Menu con mở bằng chuột: tiêu điểm còn ở dòng mở nó trong menu cha - vẫn là trong lớp nổi.
      expect(layers.some((layer) => layer.contains(active())), `tiêu điểm phải ở trong lớp vừa mở, đang ở ${describe(active())}`).toBe(true);

      if (traps(first)) {
        const inside = tabbables().filter((element) => first.contains(element)).length;
        for (const shift of [false, true]) {
          for (let step = 0; step < inside + 2; step++) {
            await tab(shift);
            expect(first.contains(active()), `${shift ? "Shift+" : ""}Tab lần ${step + 1} ra khỏi hộp, tới ${describe(active())}`).toBe(true);
          }
        }
      }

      // Esc lùi đúng MỘT bước: đóng lớp trên cùng, hay lùi một bước trong cùng lớp (bảng con trong menu "…", bước Tìm ảnh bìa của hộp Sửa sách)
      // - không bao giờ đóng hết một lúc. Mỗi lần còn lớp thì tiêu điểm ở lớp trên cùng; đóng hết thì về nút đã mở.
      for (let step = 0; openLayers().length && step < 6; step++) {
        const before = openLayers().length;
        const closing = top()!;
        if (!closing.contains(active())) closing.focus();
        await press("Escape");
        await settle();
        expect(openLayers().length, `Esc đóng nhiều hơn một lớp (${describe(closing)})`).toBeGreaterThanOrEqual(before - 1);
        const below = top();
        if (below) expect(below.contains(active()), `sau Esc tiêu điểm phải ở lớp trên cùng ${describe(below)}, đang ở ${describe(active())}`).toBe(true);
      }
      expect(openLayers().map(describe), "Esc phải đóng được mọi lớp").toEqual([]);
      const expected = dialogOpener(opener);
      expect(active(), `tiêu điểm phải về nút đã mở (${describe(expected)}), đang ở ${describe(active())}`).toBe(expected);
    } finally {
      unmount();
      container.remove();
      document.body.replaceChildren();
    }
  }, 60_000);
}

it("đã thử đủ các hộp thoại và menu của máy tính", () => {
  for (const id of [
    "desktop/book-menu", "desktop/book-confirm-remove", "desktop/book-edit", "desktop/book-cover-search", "desktop/book-record-move",
    "desktop/book-music-menu", "desktop/player-more", "desktop/player-sleep", "desktop/player-speed", "desktop/player-voice",
    "desktop/player-music", "desktop/player-devices", "desktop/add-book-2", "desktop/studio-voice-picker", "desktop/studio-script-menu",
  ]) expect(reached, id).toContain(id);
});
