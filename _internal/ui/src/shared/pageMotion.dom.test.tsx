// @vitest-environment happy-dom
// Đổi trang không qua View Transition (video 25-10 "mở tab thư viện bị giật"): khung trang mờ ra trước, trang mới dựng khi đã khuất rồi
// hiện vào theo hướng; nội dung có sẵn của trang mới (Collapse appear trong MotionPresence) không mọc từ 0 làm trang cao dần.
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { Collapse } from "./Collapse";
import { enterPage, leavePage, pageEntering } from "./motion";

type Call = { frames: Keyframe[]; options: KeyframeAnimationOptions };

function fakePage() {
  const calls: Call[] = [];
  const finishers: (() => void)[] = [];
  const cancelled: number[] = [];
  const page = {
    animate: (frames: Keyframe[], options: KeyframeAnimationOptions) => {
      const index = calls.push({ frames, options }) - 1;
      return { finished: new Promise<void>((resolve) => finishers.push(resolve)), cancel: () => cancelled.push(index) };
    },
    getAnimations: () => calls.map((_, index) => ({ cancel: () => cancelled.push(index) })),
  };
  const doc = { documentElement: { dataset: {} }, querySelector: () => page } as unknown as Parameters<typeof leavePage>[1];
  return { calls, finishers, cancelled, doc };
}

afterEach(() => { vi.restoreAllMocks(); enterPage({ documentElement: { dataset: {} }, querySelector: () => null } as never); });

it("mờ ra ngay khi bấm, bấm liên tiếp dùng chung một lần mờ, trang mới vào theo hướng của lần cuối", async () => {
  const { calls, finishers, cancelled, doc } = fakePage();
  const left = leavePage("forward", doc);
  expect(pageEntering()).toBe(true);
  expect(leavePage("back", doc)).toBe(left);
  expect(calls).toHaveLength(1);
  expect(calls[0].frames.at(-1)).toMatchObject({ opacity: 0, transform: "translateX(-12px)" });
  expect(calls[0].options).toMatchObject({ duration: 90, fill: "forwards" });
  finishers[0](); await left;
  enterPage(doc);
  expect(pageEntering()).toBe(false);
  expect(cancelled).toContain(0);
  expect(calls[1].frames[0]).toMatchObject({ opacity: 0, transform: "translateX(-32px)" });
  expect(calls[1].frames.at(-1)).toMatchObject({ opacity: 1, transform: "none" });
});

it("ngang hàng (tab dưới) mờ qua và phóng nhẹ; không đổi trang thì không đụng khung", async () => {
  const { calls, finishers, doc } = fakePage();
  await leavePage("none", doc);
  expect(calls).toHaveLength(0);
  const left = leavePage("through", doc);
  expect(calls[0].frames.at(-1)).toMatchObject({ opacity: 0, transform: "none" });
  finishers[0](); await left; enterPage(doc);
  expect(calls[1].frames[0]).toMatchObject({ opacity: 0, transform: "scale(0.97)" });
});

it("nội dung có sẵn lúc trang vào không mọc từ 0; nội dung tới sau vẫn mở ra", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const animate = vi.fn(() => ({ cancel() {}, onfinish: null }) as unknown as Animation);
  Object.defineProperty(HTMLElement.prototype, "animate", { configurable: true, value: animate });
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  const { finishers, doc } = fakePage();
  const left = leavePage("through", doc);
  await act(() => root.render(<Collapse open appear><p>Tất cả</p></Collapse>));
  expect(animate).not.toHaveBeenCalled();
  finishers[0](); await left; enterPage(doc);
  await act(() => root.render(<><Collapse open appear><p>Tất cả</p></Collapse><Collapse key="late" open appear><p>Mới</p></Collapse></>));
  expect(animate).toHaveBeenCalledTimes(1);
  await act(() => root.unmount()); host.remove();
  Reflect.deleteProperty(HTMLElement.prototype, "animate");
});

it("thứ dựng cùng trang mới (hiện dần, dòng nhô lên) đi theo chuyển cảnh trang; vòng lặp, việc dài và việc đã chạy giữ nguyên", async () => {
  const { finishers, doc } = fakePage();
  const finished: string[] = [];
  const child = (name: string, iterations: number, endTime: number, currentTime: number) =>
    ({ effect: { getComputedTiming: () => ({ iterations, endTime }) }, currentTime, cancel() {}, finish: () => finished.push(name) });
  const children = [child("hiện dần", 1, 220, 0), child("dòng nhô", 1, 300, 0), child("nhấp nháy", Infinity, 1200, 0), child("đếm ngược", 1, 60000, 0), child("đang chạy", 1, 220, 150)];
  const page = (doc as unknown as { querySelector: () => { getAnimations: (options?: { subtree?: boolean }) => unknown[] } }).querySelector();
  const own = page.getAnimations;
  page.getAnimations = (options) => (options?.subtree ? children : own());
  const left = leavePage("through", doc);
  finishers[0](); await left;
  enterPage(doc);
  expect(finished).toEqual(["hiện dần", "dòng nhô"]);
});
