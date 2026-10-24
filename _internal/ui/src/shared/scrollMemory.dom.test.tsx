// @vitest-environment happy-dom
import { act, useRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { restoreScroll, saveScroll, useScrollMemory } from "./scrollMemory";

let root: Root, host: HTMLDivElement, scroller: HTMLDivElement;
let frame: FrameRequestCallback;
let finish: () => void;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear();
  scroller = document.createElement("div"); scroller.style.overflowY = "auto"; document.body.append(scroller);
  host = document.createElement("div"); scroller.append(host); root = createRoot(host);
  vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation(callback => { frame = callback; return 1; });
  vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => {});
  const finished = new Promise<void>(resolve => { finish = resolve; });
  vi.spyOn(scroller, "getAnimations").mockReturnValue([{ effect: { getComputedTiming: () => ({ endTime: 220 }) }, finished }] as unknown as Animation[]);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });
function Page() {
  const ref = useRef<HTMLDivElement>(null);
  useScrollMemory("book.test", ref);
  return <div ref={ref}>Danh sách chương</div>;
}

it.each(["trước RAF", "trước animation.finished"])("rời trang %s sau tự cuộn: quay lại chỗ mới", async when => {
  saveScroll("book.test", { scrollTop: 400 });
  await act(() => root.render(<Page />));
  expect(scroller.scrollTop).toBe(400);
  if (when === "trước animation.finished") frame(0);
  await act(() => { scroller.scrollTop = 750; scroller.dispatchEvent(new Event("scroll")); });
  await act(() => root.render(null));
  await act(async () => { finish(); await Promise.resolve(); });
  scroller.scrollTop = 0;
  await act(() => root.render(<Page />));
  expect(scroller.scrollTop).toBe(750);
});

it("cleanup flush chỗ tự cuộn khi sự kiện scroll chưa được phát", async () => {
  saveScroll("book.test", { scrollTop: 400 });
  await act(() => root.render(<Page />));
  scroller.scrollTop = 900;
  await act(() => root.render(null));
  const next = { scrollTop: 0 }; restoreScroll("book.test", next);
  expect(next.scrollTop).toBe(900);
});

it("tự cuộn rồi về vị trí ban đầu: không phục hồi lại chỗ cuộn giữa", async () => {
  saveScroll("book.test", { scrollTop: 400 });
  await act(() => root.render(<Page />));
  scroller.scrollTop = 750; scroller.dispatchEvent(new Event("scroll"));
  scroller.scrollTop = 400; scroller.dispatchEvent(new Event("scroll"));
  frame(0);
  await act(async () => { finish(); await Promise.resolve(); });
  expect(scroller.scrollTop).toBe(400);
  const next = { scrollTop: 0 }; restoreScroll("book.test", next);
  expect(next.scrollTop).toBe(400);
});

it("không ghi vị trí phục hồi bị clamp trong lúc Fold còn mở dở", async () => {
  let position = 0, limit = 200;
  Object.defineProperty(scroller, "scrollTop", { configurable: true, get: () => position, set: value => { position = Math.min(value, limit); } });
  saveScroll("book.test", { scrollTop: 1000 });
  await act(() => root.render(<Page />));
  expect(scroller.scrollTop).toBe(200);
  scroller.dispatchEvent(new Event("scroll")); // scroll do lần restore đầu, không phải người dùng.
  frame(0);
  limit = 1500;
  await act(async () => { finish(); await Promise.resolve(); });
  expect(scroller.scrollTop).toBe(1000);
  await act(() => root.render(null));
  const next = { scrollTop: 0 }; restoreScroll("book.test", next);
  expect(next.scrollTop).toBe(1000);
});

it("rời trang trong lúc restore bị clamp không ghi đè chỗ nhớ", async () => {
  Object.defineProperty(scroller, "scrollTop", { configurable: true, get: () => 200, set: () => {} });
  saveScroll("book.test", { scrollTop: 1000 });
  await act(() => root.render(<Page />));
  scroller.dispatchEvent(new Event("scroll"));
  await act(() => root.render(null));
  const next = { scrollTop: 0 }; restoreScroll("book.test", next);
  expect(next.scrollTop).toBe(1000);
});
