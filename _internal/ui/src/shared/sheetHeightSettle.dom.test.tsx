// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MOTION } from "./motion";
import { Sheet } from "./ui";

let root: Root;
let resized: (() => void) | null = null;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("max-width"), addEventListener() {}, removeEventListener() {} }));
  vi.stubGlobal("ResizeObserver", class { constructor(callback: () => void) { resized = callback; } observe() {} unobserve() {} disconnect() {} });
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.unstubAllGlobals(); vi.useRealTimers(); resized = null; });

// Soát điện thoại 26-10: danh sách con trong bảng mở ra làm bảng cao dần mỗi khung; báo mỗi khung thì màn Đang nghe đổi cỡ mỗi khung (tác vụ 111 ms).
it("bảng báo cao ngay lúc mở, rồi chỉ báo một lần khi đã đứng dù đổi cỡ liên tục", async () => {
  const heights: number[] = [];
  vi.useFakeTimers();
  await act(() => root.render(<Sheet open onOpenChange={() => {}} title="Giọng" onHeightChange={height => heights.push(height)}><p>Danh sách</p></Sheet>));
  expect(heights).toHaveLength(1);
  expect(resized).not.toBeNull();
  for (let frame = 0; frame < 12; frame++) { act(() => resized!()); act(() => { vi.advanceTimersByTime(16); }); }
  expect(heights).toHaveLength(1);
  act(() => { vi.advanceTimersByTime(MOTION.medium); });
  expect(heights).toHaveLength(2);
});
