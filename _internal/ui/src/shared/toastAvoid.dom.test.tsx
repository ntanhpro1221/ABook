// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { toastPlacement, useToastClearance } from "./toastClearance";

// Gate 23 tap-audit "Player mobile - Speed" (412x915): the Speed trigger of the phone's full player sat at y 731-787 and the bottom toast at
// 761-819 (96 px offset). The toast covered the lower half of the button; a second toast growing the stack covered its centre during a tap,
// and the tap's click went to the toast (trace: pointerdown/up on the trigger's SPAN, focusin/click on the toast LI). Page controls marked
// data-toast-avoid are obstacles exactly like open layers.
const TRIGGER_ROW = { top: 731, bottom: 787 };
const overlaps = (a: { top: number; bottom: number }, b: { top: number; bottom: number }) => a.top < b.bottom && b.top < a.bottom;

it("moves a bottom toast off the player's control rows to the nearest free space", () => {
  const rows = [{ top: 560, bottom: 600 }, { top: 612, bottom: 692 }, TRIGGER_ROW, { top: 795, bottom: 851 }];
  const { wanted, hidden } = toastPlacement(761, 58, rows, 915);
  expect(hidden).toBe(false);
  const moved = { top: 761 + wanted, bottom: 819 + wanted };
  for (const row of rows) expect(overlaps(moved, row)).toBe(false);
  // Without obstacles the toast stays where Sonner put it.
  expect(toastPlacement(761, 58, [], 915)).toEqual({ wanted: 0, hidden: false });
});

it("fades the toast when no free space is left, as for a full-screen layer", () => {
  expect(toastPlacement(761, 58, [{ top: 0, bottom: 915 }], 915).hidden).toBe(true);
});

afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); });

it("the shared clearance treats a data-toast-avoid region as an obstacle and shifts the toaster", async () => {
  Object.defineProperty(window, "innerHeight", { value: 915, configurable: true });
  const box = (top: number, bottom: number) => ({ top, bottom, left: 16, right: 396, width: 380, height: bottom - top, x: 16, y: top, toJSON() {} }) as DOMRect;
  document.body.innerHTML = '<div data-toast-avoid id="row"><button>Tốc độ</button></div>'
    + '<section><ol data-sonner-toaster><li data-sonner-toast data-mounted="true" data-visible="true">Chưa tải được bản mới</li></ol></section><div id="app"></div>';
  const row = document.getElementById("row")!, toaster = document.querySelector<HTMLElement>("[data-sonner-toaster]")!;
  const toast = toaster.querySelector("li")!;
  vi.spyOn(row, "getBoundingClientRect").mockReturnValue(box(TRIGGER_ROW.top, TRIGGER_ROW.bottom));
  Object.defineProperty(row, "offsetHeight", { value: TRIGGER_ROW.bottom - TRIGGER_ROW.top, configurable: true });
  vi.spyOn(toast, "getBoundingClientRect").mockReturnValue(box(761, 819));
  const real = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((el: Element) => {
    const style = real(el);
    return new Proxy(style, { get: (target, key) => key === "transform" ? "none" : key === "transformOrigin" ? "0px 0px" : key === "translate" ? "none"
      : key === "display" ? "block" : key === "visibility" ? "visible" : Reflect.get(target, key) }) as CSSStyleDeclaration;
  });
  // Frames are driven by hand: the clearance measures on requestAnimationFrame, so each step is deterministic (no wall clock).
  const frames: FrameRequestCallback[] = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => frames.push(callback));
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
  const flush = async () => { await act(async () => { await Promise.resolve(); while (frames.length) frames.shift()!(0); }); };
  function Host() { useToastClearance(); return null; }
  const root = createRoot(document.getElementById("app")!);
  await act(async () => { root.render(<Host />); });
  await flush();
  const shift = Number.parseFloat(toaster.style.getPropertyValue("--toast-shift"));
  expect(shift).not.toBe(0);
  expect(overlaps({ top: 761 + shift, bottom: 819 + shift }, TRIGGER_ROW)).toBe(false);
  // The same region hidden (e.g. the player behind a modal) is no obstacle any more.
  row.setAttribute("aria-hidden", "true");
  await flush();
  expect(toaster.style.getPropertyValue("--toast-shift")).toBe("0px");
  await act(async () => { root.unmount(); });
});
