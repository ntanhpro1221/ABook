// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MotionRegion } from "./MotionRegion";
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

it.each(["dialog", "sheet", "page"])("%s: snapshot uses the host padding coordinates, including border, scale and scroll", async kind => {
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

it("a viewport snapshot stays aligned when the page scrolls during its fade", async () => {
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
  expect(clone.style.top).toBe("35px");
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
