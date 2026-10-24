// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { captureMotionSnapshot, removeMotionSnapshot, settleMotionSnapshot } from "./motion";

const rect = (left: number, top: number, width: number, height: number): DOMRect =>
  ({ x: left, y: top, left, top, width, height, right: left + width, bottom: top + height, toJSON() {} });
beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
});
afterEach(() => { vi.runAllTimers(); document.body.replaceChildren(); vi.restoreAllMocks(); vi.useRealTimers(); });

/** Hộp thoại (host, toạ độ 20,20) có khung cuộn top 80; vùng chụp có dải 20px rồi tới header sticky top:0:
 *  header tự nhiên ở 100 - cuộn, ghim ở 80 (đỉnh khung cuộn). */
function setup(extra?: (region: HTMLElement) => void) {
  const host = document.createElement("div"), scroll = document.createElement("div"), region = document.createElement("div");
  host.style.position = "relative"; scroll.style.overflow = "auto";
  region.innerHTML = '<div data-lead style="height:20px"></div><div data-pin style="position:sticky;top:0px">Header</div><p data-body>Body</p>';
  extra?.(region);
  host.append(scroll); scroll.append(region); document.body.append(host);
  Object.defineProperties(scroll, { scrollHeight: { value: 1000 }, clientHeight: { value: 200 }, clientWidth: { value: 300 } });
  vi.spyOn(host, "getBoundingClientRect").mockReturnValue(rect(20, 20, 300, 500));
  vi.spyOn(scroll, "getBoundingClientRect").mockReturnValue(rect(20, 80, 300, 200));
  vi.spyOn(region, "getBoundingClientRect").mockImplementation(() => rect(20, 80 - scroll.scrollTop, 300, 600));
  const pin = region.querySelector<HTMLElement>("[data-pin]")!;
  vi.spyOn(pin, "getBoundingClientRect").mockImplementation(() => rect(20, Math.max(80, 100 - scroll.scrollTop), 300, 30));
  const image = region.cloneNode(true) as HTMLElement;
  vi.spyOn(region, "cloneNode").mockReturnValue(image);
  // Ảnh nằm trong host: toạ độ màn hình = toạ độ host + (20,20); copy header cách góc ảnh 20px + độ bù đã áp.
  vi.spyOn(image, "getBoundingClientRect").mockImplementation(() => rect(20 + parseFloat(image.style.left), 20 + parseFloat(image.style.top), 300, 600));
  const copy = image.querySelector<HTMLElement>("[data-pin]")!;
  vi.spyOn(copy, "getBoundingClientRect").mockImplementation(() =>
    rect(20, 20 + parseFloat(image.style.top) + 20 + (parseFloat(copy.style.top) || 0), 300, 30));
  const scrollTo = (value: number) => { scroll.scrollTop = value; scroll.dispatchEvent(new Event("scroll")); };
  return { host, scroll, region, pin, image, copy, scrollTo };
}

it("a sticky child in the snapshot follows the real pinned position, before and after the pin threshold", () => {
  const { host, region, pin, image, copy, scrollTo } = setup();
  const clone = captureMotionSnapshot(region, document, 51, host, true)!;
  expect(clone).toBe(image);
  settleMotionSnapshot(region, clone);
  expect(copy.getBoundingClientRect().top).toBe(100);
  for (const scrolled of [10, 20, 35, 50, 120]) {
    scrollTo(scrolled);
    // Phần sticky đứng đúng chỗ phần tử thật đang đứng (trước ngưỡng thì trượt theo, sau ngưỡng thì ghim ở 80).
    expect(copy.getBoundingClientRect().top).toBe(pin.getBoundingClientRect().top);
    // Phần còn lại vẫn trượt tuyến tính theo cuộn.
    expect(image.style.top).toBe(`${60 - scrolled}px`);
  }
  expect(pin.getBoundingClientRect().top).toBe(80);
  removeMotionSnapshot(clone);
});

it("sticky compensation stops after the snapshot is removed and the sticky copy stays out of the image's own pinning", () => {
  const { host, region, image, copy, scrollTo } = setup();
  const clone = captureMotionSnapshot(region, document, 51, host, true)!;
  settleMotionSnapshot(region, clone);
  expect(copy.style.position).toBe("relative"); // Ảnh không tự ghim theo khung cuộn riêng của nó.
  scrollTo(40);
  const placed = copy.style.top;
  removeMotionSnapshot(clone);
  scrollTo(90);
  expect(copy.style.top).toBe(placed);
  expect(image.isConnected).toBe(false);
});

it("a sticky child whose scroller is inside the captured region keeps its own pinning", () => {
  const { host, region, image } = setup(node => {
    node.innerHTML = '<div style="overflow:auto"><div data-pin style="position:sticky;top:0px">Inner</div></div>';
  });
  const clone = captureMotionSnapshot(region, document, 51, host, true)!;
  expect(clone).toBe(image);
  expect(image.querySelector<HTMLElement>("[data-pin]")!.style.position).toBe("sticky");
  removeMotionSnapshot(clone);
});
