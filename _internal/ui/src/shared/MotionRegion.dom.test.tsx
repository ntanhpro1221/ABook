// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MotionRegion } from "./MotionRegion";
import { Collapse } from "./Collapse";
import { MOTION } from "./motion";

let root: Root;
let mount: HTMLElement;
const rect = (left: number, top: number, width: number, height: number): DOMRect =>
  ({ x: left, y: top, left, top, width, height, right: left + width, bottom: top + height, toJSON() {} });
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  mount = document.createElement("div"); document.body.append(mount); root = createRoot(mount);
});
afterEach(async () => {
  await act(() => root.unmount());
  vi.runAllTimers(); document.body.replaceChildren(); vi.restoreAllMocks(); vi.useRealTimers();
});
const snapshots = () => [...document.querySelectorAll<HTMLElement>(".motion-snapshot")];

it.each([false, true])("a resizing dialog fades old text out before new text enters (reduced=%s)", async reduced => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: reduced } as MediaQueryList);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    return rect(40, 60, 240, this.textContent === "Old long preview" ? 400 : 100);
  });
  const render = (text: string) => act(() => root.render(<MotionRegion fadeThrough motionKey={text}>{text}</MotionRegion>));
  await render("Old long preview"); await render("Loading next");
  const box = mount.firstElementChild as HTMLElement;
  const call = vi.mocked(box.animate).mock.calls.at(-1)!;
  const duration = reduced ? MOTION.fast : MOTION.medium;
  const frames = call[0] as Keyframe[];
  expect(frames[0].opacity).toBe(0);
  expect(frames[1]).toMatchObject({ opacity: 0, offset: MOTION.fastOut / duration });
  expect(frames.at(-1)?.opacity).toBe(1);
  expect(call[1]).toMatchObject({ duration, easing: "linear" });
  expect(snapshots()[0].textContent).toBe("Old long preview");
});

it.each(["dialog", "sheet"])("%s: snapshot uses the host padding coordinates, including border, scale and scroll", async kind => {
  const render = (text: string) => act(() => root.render(
    <div data-host role={kind === "page" ? undefined : "dialog"} data-state="open"
      style={{ position: "relative", transform: "translate(100px, 200px) scale(.8)", border: "2px solid", overflow: "auto" }}>
      <MotionRegion motionKey={text} style={{ padding: 8, border: "1px solid" }}>{text}</MotionRegion>
    </div>));
  await render("Old book");
  const host = mount.querySelector<HTMLElement>("[data-host]")!;
  const region = host.querySelector<HTMLElement>("[data-motion-region]")!;
  vi.spyOn(host, "getBoundingClientRect").mockReturnValue(rect(100, 200, 400, 480));
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(140, 264, 240, 80));
  Object.defineProperties(host, {
    offsetWidth: { configurable: true, value: 500 }, offsetHeight: { configurable: true, value: 600 },
    clientLeft: { configurable: true, value: 2 }, clientTop: { configurable: true, value: 2 },
  });
  Object.defineProperty(region, "offsetParent", { configurable: true, value: host });
  host.scrollLeft = 12; host.scrollTop = 30;
  await render("Next book");
  const clone = snapshots()[0];
  expect(clone.parentElement).toBe(host);
  expect(clone.style.position).toBe("absolute");
  expect(parseFloat(clone.style.left)).toBeCloseTo((140 - 100) / .8 - 2 + 12);
  expect(parseFloat(clone.style.top)).toBeCloseTo((264 - 200) / .8 - 2 + 30);
  expect(parseFloat(clone.style.width)).toBeCloseTo(240 / .8);
  expect(parseFloat(clone.style.height)).toBeCloseTo(80 / .8);
  expect(clone.style.boxSizing).toBe("border-box");
  expect(clone.getAttribute("aria-hidden")).toBe("true");
  expect(clone.hasAttribute("inert")).toBe(true);
  expect(clone.style.pointerEvents).toBe("none");
  expect(region.animate).toHaveBeenCalledWith(expect.arrayContaining([{ opacity: .45 }, { opacity: 1 }]), expect.anything());
  await act(() => vi.advanceTimersByTime(MOTION.fastOut + 81));
  expect(snapshots()).toHaveLength(0);
});

it("a page snapshot keeps its viewport coordinates when the page scrolls during its fade", async () => {
  const render = (text: string) => act(() => root.render(<MotionRegion motionKey={text}>{text}</MotionRegion>));
  await render("Old book");
  const region = mount.firstElementChild as HTMLElement;
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(40, 60, 240, 80));
  vi.spyOn(window, "scrollX", "get").mockReturnValue(10);
  const scrollY = vi.spyOn(window, "scrollY", "get").mockReturnValue(100);
  await render("Next book");
  const clone = snapshots()[0];
  expect(clone.style.left).toBe("40px"); expect(clone.style.top).toBe("60px");
  scrollY.mockReturnValue(125);
  window.dispatchEvent(new Event("scroll"));
  expect(clone.style.top).toBe("60px");
});

it.each([false, true])("parent and child changing together keep one old image (child first=%s)", async childFirst => {
  // Both orders occur across React snapshot lifecycles and consecutive updates.
  const parent = document.createElement("div"), child = document.createElement("div");
  parent.append(child); mount.append(parent);
  for (const node of [parent, child]) vi.spyOn(node, "getBoundingClientRect").mockReturnValue(rect(40, 60, 240, 80));
  const { captureMotionSnapshot } = await import("./motion");
  if (childFirst) { captureMotionSnapshot(child); captureMotionSnapshot(parent); }
  else { captureMotionSnapshot(parent); captureMotionSnapshot(child); }
  expect(snapshots()).toHaveLength(1);
  expect(snapshots()[0].querySelector(".motion-snapshot")).toBeNull();
});

it("React nested regions keep one old tree even when the child image was inserted inside its parent", async () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(rect(40, 60, 240, 80));
  const render = (text: string) => act(() => root.render(
    <MotionRegion motionKey={text} style={{ position: "relative" }}>
      <p>{text}</p><MotionRegion motionKey={text}>{text}</MotionRegion>
    </MotionRegion>));
  await render("Old book");
  const parent = mount.firstElementChild as HTMLElement, child = parent.querySelector("[data-motion-region]")!;
  Object.defineProperty(child, "offsetParent", { configurable: true, value: parent });
  await render("Next book");
  expect(snapshots()).toHaveLength(1);
  expect(snapshots()[0].querySelector(".motion-snapshot")).toBeNull();
  expect(snapshots()[0].textContent).toBe("Old bookOld book");
});

it("discarding a speculative parent snapshot keeps the child's confirmed fade", async () => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(rect(40, 60, 240, 80));
  const Child = ({ text }: { text: string }) => <MotionRegion motionKey={text}>{text}</MotionRegion>;
  const render = (text: string) => act(() => root.render(<MotionRegion><Child text={text} /></MotionRegion>));
  await render("Old book"); await render("Next book");
  expect(snapshots()).toHaveLength(1);
  expect(snapshots()[0].textContent).toBe("Old book");
  expect(snapshots()[0].querySelector("[data-motion-region]")).toBeNull();
});

it("a static menu uses its actual transformed offsetParent and preserves inherited heading typography", async () => {
  const { captureMotionSnapshot } = await import("./motion");
  const popper = document.createElement("div"), menu = document.createElement("div"), heading = document.createElement("h2"), region = document.createElement("span");
  popper.append(menu); menu.append(heading); heading.append(region); mount.append(popper);
  heading.style.cssText = "font: 600 24px/32px serif; color: rgb(12, 34, 56)";
  vi.spyOn(popper, "getBoundingClientRect").mockReturnValue(rect(90, 130, 300, 400));
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(110, 160, 240, 32));
  const image = region.cloneNode(true) as HTMLElement;
  Object.defineProperty(image, "offsetParent", { configurable: true, value: popper });
  vi.spyOn(region, "cloneNode").mockReturnValue(image);
  const clone = captureMotionSnapshot(region, document, 51, menu)!;
  expect(clone.parentElement).toBe(menu);
  expect(clone.style.left).toBe("20px"); expect(clone.style.top).toBe("30px");
  expect(clone.style.fontSize).toBe("24px"); expect(clone.style.lineHeight).toBe("32px");
  expect(clone.style.color).toBe("rgb(12, 34, 56)");
});

it("a snapshot portaled to the surface follows inner scroll and clips at the original scrollport", async () => {
  const { captureMotionSnapshot, removeMotionSnapshot, settleMotionSnapshot } = await import("./motion");
  const surface = document.createElement("div"), scroller = document.createElement("div"), region = document.createElement("div");
  surface.append(scroller); scroller.append(region); mount.append(surface);
  scroller.style.overflow = "auto";
  vi.spyOn(surface, "getBoundingClientRect").mockReturnValue(rect(100, 200, 400, 600));
  const scrollport = vi.spyOn(scroller, "getBoundingClientRect").mockReturnValue(rect(120, 240, 300, 200));
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(130, 260, 240, 300));
  Object.defineProperties(scroller, { clientWidth: { value: 300 }, clientHeight: { configurable: true, value: 200 } });
  // happy-dom has no layout: supply the old image rectangle independently of style calculations.
  const bounds = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(rect(130, 260, 240, 300));
  const clone = captureMotionSnapshot(region, document, 51, surface, true)!;
  expect(clone.style.top).toBe("60px");
  expect(clone.style.clipPath).toBe("inset(0px 0px 120px 0px)");
  // Loading the next file shrinks the scrollport during React commit, before the fade paints.
  scrollport.mockReturnValue(rect(120, 240, 300, 140));
  Object.defineProperty(scroller, "clientHeight", { value: 140 });
  settleMotionSnapshot(region, clone);
  expect(clone.style.clipPath).toBe("inset(0px 0px 180px 0px)");
  bounds.mockReturnValue(rect(130, 210, 240, 300));
  scroller.scrollTop = 50; scroller.dispatchEvent(new Event("scroll"));
  expect(clone.style.top).toBe("10px");
  expect(clone.style.clipPath).toBe("inset(30px 0px 130px 0px)");
  removeMotionSnapshot(clone);
  scroller.scrollTop = 100; scroller.dispatchEvent(new Event("scroll"));
  expect(clone.style.top).toBe("10px"); // Detached images no longer subscribe to scroll.
});

it("page regions use fixed viewport coordinates and keep the ancestor clip during scroll", async () => {
  const render = (text: string) => act(() => root.render(
    <div style={{ position: "relative", overflow: "auto", height: 70 }}>
      <MotionRegion motionKey={text} style={{ position: "sticky", top: 0 }}>{text}</MotionRegion>
    </div>));
  await render("Old header");
  const host = mount.firstElementChild as HTMLElement, region = host.firstElementChild as HTMLElement;
  Object.defineProperty(region, "offsetParent", { value: host });
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(40, 48, 240, 80));
  const documentAdd = vi.spyOn(document, "addEventListener"), windowAdd = vi.spyOn(window, "addEventListener");
  await render("New header");
  const clone = snapshots()[0];
  expect(clone.parentElement).toBe(document.body);
  expect(clone.style.position).toBe("fixed");
  expect(clone.style.clipPath).toBe("inset(0px 0px 0px 0px)");
  host.scrollTop = 20; host.dispatchEvent(new Event("scroll"));
  expect(clone.style.top).toBe("48px");
  expect(documentAdd.mock.calls.filter(([type]) => type === "scroll")).toHaveLength(1);
  expect(windowAdd.mock.calls.filter(([type]) => type === "scroll")).toHaveLength(1);
});

it.each([false, true])("menu scroll is compensated only when its containing block does not already scroll with it (positioned=%s)", async positioned => {
  const { captureMotionSnapshot, removeMotionSnapshot } = await import("./motion");
  const popper = document.createElement("div"), menu = document.createElement("div"), region = document.createElement("div");
  popper.append(menu); menu.append(region); mount.append(popper);
  menu.style.overflow = "auto"; menu.scrollTop = 40;
  vi.spyOn(popper, "getBoundingClientRect").mockReturnValue(rect(180, 110, 300, 400));
  vi.spyOn(menu, "getBoundingClientRect").mockReturnValue(rect(180, 110, 300, 210));
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(187, 127, 240, 300));
  const image = region.cloneNode(true) as HTMLElement;
  Object.defineProperty(image, "offsetParent", { value: positioned ? menu : popper });
  vi.spyOn(region, "cloneNode").mockReturnValue(image);
  const clone = captureMotionSnapshot(region, document, 51, menu)!;
  const initial = parseFloat(clone.style.top);
  menu.scrollTop = 60; menu.dispatchEvent(new Event("scroll"));
  expect(parseFloat(clone.style.top)).toBe(initial - (positioned ? 0 : 20));
  removeMotionSnapshot(clone);
});

it("copies inherited font longhands even when the browser font shorthand is empty", async () => {
  const { captureMotionSnapshot, removeMotionSnapshot } = await import("./motion");
  const region = document.createElement("span"); mount.append(region);
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(40, 60, 240, 32));
  const values: Record<string, string> = { "font-size": "18px", "font-family": "serif", "font-weight": "600", "font-style": "italic",
    "font-stretch": "condensed", "font-variant": "small-caps", "font-feature-settings": '"ss01"', "font-variation-settings": '"wght" 600', "line-height": "28px" };
  const native = getComputedStyle;
  vi.spyOn(globalThis, "getComputedStyle").mockImplementation(node => {
    const computed = native(node);
    if (node === region) vi.spyOn(computed, "getPropertyValue").mockImplementation(name => values[name] ?? "");
    return computed;
  });
  const clone = captureMotionSnapshot(region)!;
  for (const [name, value] of Object.entries(values)) expect(clone.style.getPropertyValue(name), name).toBe(value);
  removeMotionSnapshot(clone);
});

it.each(["remove", "animationend", "timeout"])("surface snapshots share a finite frame scheduler, refresh after layout effects and resize, and clean up on %s", async finish => {
  const { captureMotionSnapshot, removeMotionSnapshot, settleMotionSnapshot } = await import("./motion");
  const frames = new Map<number, FrameRequestCallback>(); let nextId = 0;
  vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation(callback => { frames.set(++nextId, callback); return nextId; });
  vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(id => { frames.delete(id); });
  const frame = () => { const work = [...frames.values()]; frames.clear(); work.forEach(callback => callback(16)); };
  const surface = document.createElement("div"), scroller = document.createElement("div");
  surface.append(scroller); mount.append(surface); scroller.style.overflow = "hidden";
  vi.spyOn(surface, "getBoundingClientRect").mockReturnValue(rect(100, 200, 400, 600));
  vi.spyOn(scroller, "getBoundingClientRect").mockReturnValue(rect(120, 240, 300, 200));
  let height = 0;
  Object.defineProperties(scroller, { clientWidth: { value: 300 }, clientHeight: { get: () => height } });
  const clones = Array.from({ length: 2 }, () => {
    const region = document.createElement("div"); scroller.append(region);
    vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(130, 260, 240, 300));
    const image = region.cloneNode(true) as HTMLElement;
    vi.spyOn(image, "getBoundingClientRect").mockReturnValue(rect(130, 260, 240, 300));
    vi.spyOn(region, "cloneNode").mockReturnValue(image);
    const clone = captureMotionSnapshot(region, document, 51, surface, true)!;
    settleMotionSnapshot(region, clone); return clone;
  });
  // Collapse's parent layout effect starts its 200px -> 0px animation after child componentDidUpdate.
  height = 200; frame();
  expect(clones[0].style.clipPath).toBe("inset(0px 0px 120px 0px)");
  expect(frames.size).toBe(1); // One frame for both images, including the resize below without scroll.
  height = 70; frame();
  expect(clones[0].style.clipPath).toBe("inset(0px 0px 250px 0px)");
  if (finish === "timeout") vi.advanceTimersByTime(MOTION.fastOut + 81);
  else clones.forEach(clone => finish === "remove" ? removeMotionSnapshot(clone) : clone.dispatchEvent(new Event("animationend")));
  expect(frames.size).toBe(0);
  expect(snapshots()).toHaveLength(0);
});

it("refreshes the image after a real Collapse layout effect starts the closing animation", async () => {
  const frames = new Map<number, FrameRequestCallback>(); let nextId = 0, animatedHeight: number | undefined;
  vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation(callback => { frames.set(++nextId, callback); return nextId; });
  vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(id => { frames.delete(id); });
  const height = (node: HTMLElement) => node.classList.contains("motion-collapse") && node.dataset.state === "closed" ? animatedHeight ?? 0 : 80;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    return this.hasAttribute("data-surface") ? rect(100, 200, 400, 600) : rect(120, 240, 240, height(this));
  });
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(240);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function (this: HTMLElement) { return height(this); });
  vi.mocked(HTMLElement.prototype.animate).mockImplementation(function (this: HTMLElement) {
    if (this.classList.contains("motion-collapse")) animatedHeight = 80;
    return { cancel: vi.fn(), onfinish: null } as unknown as Animation;
  });
  const render = (next: boolean) => act(() => root.render(
    <div data-surface role="dialog" data-state="open"><Collapse open={!next}>
      <MotionRegion motionKey={next}>{next ? "New content" : "Old content"}</MotionRegion>
    </Collapse></div>));
  await render(false);
  (mount.querySelector(".motion-collapse") as HTMLElement).style.overflow = "hidden";
  await render(true);
  const clone = snapshots()[0];
  expect(clone.style.clipPath).toBe("inset(0px 0px 80px 0px)"); // Child settled before parent effect.
  const work = [...frames.values()]; frames.clear(); work.forEach(callback => callback(16));
  expect(clone.style.clipPath).toBe("inset(0px 0px 0px 0px)");
  await act(() => root.render(null));
  expect(frames.size).toBe(0); // Unmount also releases the shared scheduler.
});
