// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import * as ui from "./ui";
import { useToastClearance } from "./toastClearance";

// Gate 24 gallery-inspect, desktop/toast at 400 px: while Now Playing was open the toaster sat 188 px up (off the player's control rows,
// data-toast-avoid). Closing it returned focus to the book row "Mở trình phát" (y 540-576) with preventScroll, the toaster was still at -188 px
// (558-616: its translate transition had not even started), and the focus-clear hook scrolled <main> by 576 - 558 + 8 = 26 px: every anchor of
// the page moved after the sheet closed. A toast may move; the page never scrolls or reflows because of a toast.
const VIEWPORT = 900, TOAST = { top: 746, height: 58 }, TRIGGER = { top: 540, bottom: 576 }, PLAYER_ROWS = { top: 632, bottom: 860 };
const overlaps = (a: { top: number; bottom: number }, b: { top: number; bottom: number }) => a.top < b.bottom && b.top < a.bottom;

afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); });

it("closing a sheet under a moved toast leaves the page scroll alone; the toast moves off the focused control instead", async () => {
  Object.defineProperty(window, "innerHeight", { value: VIEWPORT, configurable: true });
  const box = (top: number, bottom: number, left = 16, right = 396) => ({ top, bottom, left, right, width: right - left, height: bottom - top, x: left, y: top, toJSON() {} }) as DOMRect;
  document.body.innerHTML = '<main id="page" style="overflow-y:auto"><button id="trigger">Mở trình phát</button></main>'
    + '<section id="np" role="main" tabindex="-1"><div data-toast-avoid id="rows"><button id="pause">Tạm dừng</button></div></section>'
    + '<section><ol data-sonner-toaster><li data-sonner-toast data-mounted="true" data-visible="true">Đang nghe lại từ đầu</li></ol></section><div id="app"></div>';
  const page = document.getElementById("page")!, trigger = document.getElementById("trigger")!, np = document.getElementById("np")!;
  const rows = document.getElementById("rows")!, toaster = document.querySelector<HTMLElement>("[data-sonner-toaster]")!, toast = toaster.querySelector("li")!;
  Object.defineProperty(page, "scrollHeight", { value: 2000, configurable: true });
  Object.defineProperty(page, "clientHeight", { value: VIEWPORT, configurable: true });
  vi.spyOn(trigger, "getBoundingClientRect").mockReturnValue(box(TRIGGER.top, TRIGGER.bottom, 68, 310));
  Object.defineProperty(trigger, "offsetHeight", { value: TRIGGER.bottom - TRIGGER.top, configurable: true });
  vi.spyOn(rows, "getBoundingClientRect").mockReturnValue(box(PLAYER_ROWS.top, PLAYER_ROWS.bottom));
  Object.defineProperty(rows, "offsetHeight", { value: PLAYER_ROWS.bottom - PLAYER_ROWS.top, configurable: true });
  // The painted toaster lags the committed --toast-shift (CSS transition): `painted` is advanced by hand.
  let painted = 0;
  vi.spyOn(toast, "getBoundingClientRect").mockImplementation(() => box(TOAST.top + painted, TOAST.top + TOAST.height + painted));
  const real = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((el: Element) => {
    const style = real(el);
    return new Proxy(style, { get: (target, key) => key === "transform" ? "none" : key === "transformOrigin" ? "0px 0px"
      : key === "translate" ? (el === toaster ? `0px ${painted}px` : "none") : key === "display" ? "block" : key === "visibility" ? "visible"
      : key === "position" ? "static" : key === "overflowY" ? (el === page ? "auto" : "visible") : Reflect.get(target, key) }) as CSSStyleDeclaration;
  });
  const scrolled = vi.fn();
  for (const method of ["scrollBy", "scrollTo", "scrollIntoView"] as const) vi.spyOn(Element.prototype, method).mockImplementation(scrolled);
  const frames: FrameRequestCallback[] = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => frames.push(callback));
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
  const flush = async () => { await act(async () => { await Promise.resolve(); while (frames.length) frames.shift()!(0); }); };
  const committed = () => Number.parseFloat(toaster.style.getPropertyValue("--toast-shift")) || 0;
  // Every toast hook the app root mounts, whatever this revision calls them (07b381e6e also mounted a focus-clear hook that scrolled).
  const rootHooks = [useToastClearance, ...Object.entries(ui).filter(([name]) => /^use\w*Toast/.test(name)).map(([, hook]) => hook as () => void)];
  function Host() { for (const hook of rootHooks) hook(); return null; }
  const root = createRoot(document.getElementById("app")!);
  await act(async () => { root.render(<Host />); });

  // Now Playing open: focus inside it, the toaster moves off its control rows and lands on the book row behind it.
  document.getElementById("pause")!.focus();
  await flush();
  expect(committed()).toBe(-188);
  painted = committed();
  expect(overlaps({ top: TOAST.top + painted, bottom: TOAST.top + TOAST.height + painted }, TRIGGER)).toBe(true);

  // Escape: the surface goes inert at once and focus returns to the opener while the toaster is still painted 188 px up.
  np.setAttribute("inert", ""); np.setAttribute("aria-hidden", "true");
  trigger.focus({ preventScroll: true });
  await flush();
  expect(scrolled).not.toHaveBeenCalled();
  expect(page.scrollTop).toBe(0);
  painted = committed();
  await flush();
  expect(scrolled).not.toHaveBeenCalled();
  // The toast, not the page, gave way: it no longer covers the control that holds focus.
  expect(overlaps({ top: TOAST.top + committed(), bottom: TOAST.top + TOAST.height + committed() }, TRIGGER)).toBe(false);
  await act(async () => { root.unmount(); });
});

it("a focused control under the resting toast moves the toast, never the page (soát a67 without scrolling)", async () => {
  Object.defineProperty(window, "innerHeight", { value: 400, configurable: true });
  const box = (top: number, bottom: number, left: number, right: number) => ({ top, bottom, left, right, width: right - left, height: bottom - top, x: left, y: top, toJSON() {} }) as DOMRect;
  document.body.innerHTML = '<main id="page"><button id="tab">Lịch sử</button></main>'
    + '<section><ol data-sonner-toaster><li data-sonner-toast data-mounted="true" data-visible="true">Đang xuất</li></ol></section><div id="app"></div>';
  const tab = document.getElementById("tab")!, toaster = document.querySelector<HTMLElement>("[data-sonner-toaster]")!;
  vi.spyOn(tab, "getBoundingClientRect").mockReturnValue(box(40, 88, 300, 360));
  Object.defineProperty(tab, "offsetHeight", { value: 48, configurable: true });
  vi.spyOn(toaster.querySelector("li")!, "getBoundingClientRect").mockReturnValue(box(16, 100, 268, 624));
  const real = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((el: Element) => new Proxy(real(el), { get: (target, key) => key === "transform" ? "none"
    : key === "transformOrigin" ? "0px 0px" : key === "translate" ? "none" : key === "display" ? "block" : key === "visibility" ? "visible" : Reflect.get(target, key) }) as CSSStyleDeclaration);
  const scrolled = vi.fn();
  for (const method of ["scrollBy", "scrollTo", "scrollIntoView"] as const) vi.spyOn(Element.prototype, method).mockImplementation(scrolled);
  const frames: FrameRequestCallback[] = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => frames.push(callback));
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
  const flush = async () => { await act(async () => { await Promise.resolve(); while (frames.length) frames.shift()!(0); }); };
  function Host() { useToastClearance(); return null; }
  const root = createRoot(document.getElementById("app")!);
  await act(async () => { root.render(<Host />); });
  await flush();
  expect(toaster.style.getPropertyValue("--toast-shift")).toBe("0px");
  tab.focus();
  await flush();
  const shift = Number.parseFloat(toaster.style.getPropertyValue("--toast-shift"));
  expect(overlaps({ top: 16 + shift, bottom: 100 + shift }, { top: 40, bottom: 88 })).toBe(false);
  expect(scrolled).not.toHaveBeenCalled();
  // Focus leaves: the toast goes back to Sonner's own place.
  tab.blur();
  await flush();
  expect(toaster.style.getPropertyValue("--toast-shift")).toBe("0px");
  await act(async () => { root.unmount(); });
});
