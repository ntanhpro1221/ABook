// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MarqueeLine } from "./MarqueeLine";
import { TIMING } from "./widthClass.generated";

let room = 100;
let base = 16;
let reduced = false;
let resized = () => {};
const cancel = vi.fn();
const animate = vi.fn(() => ({ cancel }));

beforeEach(() => {
  room = 100; base = 16; reduced = false;
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(window, "getComputedStyle").mockImplementation(() => ({ fontSize: `${base}px` }) as CSSStyleDeclaration);
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(() => room);
  vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockImplementation(function (this: HTMLElement) {
    const size = parseFloat(this.parentElement?.style.fontSize ?? "") || base;
    return (this.textContent ?? "").length * size / 2;
  });
  vi.spyOn(window, "matchMedia").mockImplementation(() => ({ matches: reduced }) as MediaQueryList);
  vi.stubGlobal("ResizeObserver", class {
    constructor(callback: () => void) { resized = callback; }
    observe() {} disconnect() {}
  });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(animate as unknown as typeof HTMLElement.prototype.animate);
  cancel.mockClear(); animate.mockClear();
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

async function mount(text: string) {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<MarqueeLine>{text}</MarqueeLine>));
  return { el: host.querySelector<HTMLElement>("[data-marquee-line]")!, async close() { await act(async () => root.unmount()); host.remove(); } };
}

it("scrolling text is announced once and cancels its animation when width grows", async () => {
  const view = await mount("A very long chapter title for a narrow player");
  try {
    expect(view.el.dataset.fit).toBe("scroll");
    expect(view.el.querySelectorAll('[aria-hidden]')).toHaveLength(1);
    expect(animate).toHaveBeenCalled();
    room = 1000;
    await act(async () => resized());
    expect(view.el.dataset.fit).toBe("one");
    expect(view.el.querySelector('[aria-hidden]')).toBeNull();
    expect(cancel).toHaveBeenCalled();
  } finally { await view.close(); }
});

it("text size changes remeasure even when the player width stays fixed", async () => {
  room = 100;
  const view = await mount("Short title");
  try {
    expect(view.el.dataset.fit).toBe("one");
    base = 32;
    await act(async () => resized());
    expect(view.el.dataset.fit).toBe("scroll");
  } finally { await view.close(); }
});

it("reduced motion advances by readable pages and clears its timer on unmount", async () => {
  reduced = true; vi.useFakeTimers();
  const view = await mount("A very long chapter title for a narrow player");
  try {
    expect(view.el.dataset.fit).toBe("scroll");
    expect(view.el.querySelector('[aria-hidden]')).toBeNull();
    expect(animate).not.toHaveBeenCalled();
    await act(async () => vi.advanceTimersByTime(TIMING.marqueeDelayMs));
    expect((view.el.firstElementChild as HTMLElement).style.transform).toBe("translateX(-52px)");
  } finally { await view.close(); }
  expect(vi.getTimerCount()).toBe(0);
});