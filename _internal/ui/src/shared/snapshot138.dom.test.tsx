// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { captureMotionSnapshot, removeMotionSnapshot, settleMotionSnapshot } from "./motion";

const rect = (top: number, height: number): DOMRect => ({ x: 20, y: top, top, left: 20, right: 320, bottom: top + height, width: 300, height, toJSON() {} });
beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
});
afterEach(() => { vi.runAllTimers(); document.body.replaceChildren(); vi.restoreAllMocks(); vi.useRealTimers(); });

it("copies the live selection, including multiple selected options, into inert snapshots", () => {
  const node = document.createElement("div");
  node.innerHTML = '<select><option value="recent">Recent</option><option value="author">Author</option></select><select multiple><option>A</option><option>B</option><option>C</option></select>';
  document.body.append(node);
  node.querySelector("select")!.value = "author";
  node.querySelectorAll("select")[1].options[1].selected = true;
  node.querySelectorAll("select")[1].options[2].selected = true;
  vi.spyOn(node, "getBoundingClientRect").mockReturnValue(rect(20, 80));
  const image = captureMotionSnapshot(node)!;
  expect(image.querySelector("select")!.value).toBe("author");
  expect([...image.querySelectorAll("select")[1].selectedOptions].map(o => o.textContent)).toEqual(["B", "C"]);
  expect(image.hasAttribute("inert")).toBe(true);
  expect(image.getAttribute("aria-hidden")).toBe("true");
  expect(image.style.pointerEvents).toBe("none");
});

it("content shrink clamps scroll without moving the old visible chapters; real scrolling still moves them", () => {
  const host = document.createElement("div"), scroll = document.createElement("div"), region = document.createElement("div");
  host.style.position = "relative"; scroll.style.overflow = "auto";
  host.append(scroll); scroll.append(region); document.body.append(host);
  vi.spyOn(host, "getBoundingClientRect").mockReturnValue(rect(20, 500));
  vi.spyOn(scroll, "getBoundingClientRect").mockReturnValue(rect(60, 200));
  vi.spyOn(region, "getBoundingClientRect").mockReturnValue(rect(-740, 1100));
  let extent = 1100;
  Object.defineProperties(scroll, { scrollHeight: { get: () => extent }, clientHeight: { value: 200 }, clientWidth: { value: 300 } });
  scroll.scrollTop = 800;
  const image = region.cloneNode(true) as HTMLElement;
  vi.spyOn(region, "cloneNode").mockReturnValue(image);
  vi.spyOn(image, "getBoundingClientRect").mockReturnValue(rect(-740, 1100));
  captureMotionSnapshot(region, document, 51, host, true);
  const top = image.style.top;
  extent = 300; scroll.scrollTop = 100; // Browser clamp during the React commit.
  settleMotionSnapshot(region, image);
  expect(image.style.top).toBe(top);
  scroll.dispatchEvent(new Event("scroll"));
  expect(image.style.top).toBe(top); // Delayed clamp event does not count twice.
  scroll.scrollTop = 60; scroll.dispatchEvent(new Event("scroll"));
  expect(parseFloat(image.style.top)).toBe(parseFloat(top) + 40);
  removeMotionSnapshot(image);
});

it("page images retain the main scrollport clip above player and navigation", () => {
  const main = document.createElement("main"), node = document.createElement("div");
  main.style.overflowY = "auto"; main.append(node); document.body.append(main);
  Object.defineProperties(main, { clientWidth: { value: 300 }, clientHeight: { value: 500 } });
  vi.spyOn(main, "getBoundingClientRect").mockReturnValue(rect(50, 500));
  vi.spyOn(node, "getBoundingClientRect").mockReturnValue(rect(-150, 1000));
  const image = node.cloneNode(true) as HTMLElement;
  vi.spyOn(node, "cloneNode").mockReturnValue(image);
  vi.spyOn(image, "getBoundingClientRect").mockReturnValue(rect(-150, 1000));
  captureMotionSnapshot(node);
  expect(image.style.clipPath).toBe("inset(200px 0px 300px 0px)");
});

it("results follow the scroller's restored coordinates before paint while ordinary page images stay fixed", () => {
  let frame: FrameRequestCallback = () => {};
  vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation(callback => { frame = callback; return 1; });
  const main = document.createElement("main"), node = document.createElement("div");
  main.style.overflowY = "auto"; main.append(node); document.body.append(main);
  vi.spyOn(main, "getBoundingClientRect").mockReturnValue(rect(50, 500));
  Object.defineProperties(main, { clientHeight: { value: 500 }, clientWidth: { value: 300 } });
  vi.spyOn(node, "getBoundingClientRect").mockReturnValue(rect(-150, 1000));
  main.scrollTop = 400;
  const image = captureMotionSnapshot(node, document, 39, undefined, true, true)!;
  settleMotionSnapshot(node, image);
  expect(image.style.top).toBe("-150px");
  main.scrollTop = 100; // useScrollMemory's layout microtask; no scroll event yet.
  frame(16);
  expect(image.style.top).toBe("150px");
  main.scrollTop = 160; main.dispatchEvent(new Event("scroll"));
  expect(image.style.top).toBe("90px");
});

it("lazy rows keep their CSS height under a scaled surface instead of reusing intrinsic estimates", () => {
  const node = document.createElement("div"), row = document.createElement("div");
  row.className = "[content-visibility:auto]";
  row.style.cssText = "content-visibility:auto; height:48px; box-sizing:border-box";
  node.append(row); document.body.append(node);
  vi.spyOn(node, "getBoundingClientRect").mockReturnValue(rect(20, 80));
  vi.spyOn(row, "getBoundingClientRect").mockReturnValue(rect(20, 38.4));
  const image = captureMotionSnapshot(node)!;
  expect((image.firstElementChild as HTMLElement).style.contentVisibility).toBe("visible");
  expect((image.firstElementChild as HTMLElement).style.height).toBe("48px");
});

it("collapsed margins through plain wrappers do not reappear inside an absolute snapshot", () => {
  const node = document.createElement("div");
  node.style.cssText = "display:block;overflow:visible";
  node.innerHTML = '<div style="display:block;overflow:visible;float:none"><ul style="margin-top:12px;float:none"><li>Queue</li></ul></div>';
  document.body.append(node);
  for (const item of [node, node.firstElementChild!, node.querySelector("ul")!]) {
    vi.spyOn(item, "getBoundingClientRect").mockReturnValue(rect(20, 80));
  }
  const image = captureMotionSnapshot(node)!;
  expect(image.querySelector("ul")!.style.marginTop).toBe("0px");
});
