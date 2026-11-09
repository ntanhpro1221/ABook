// @vitest-environment happy-dom
// Route commits immediately; old/new content move together outside fixed shell chrome.
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { Collapse } from "./Collapse";
import { enterPage, leavePage, pageEntering, type NavMotion } from "./motion";

type Call = { frames: Keyframe[]; options: KeyframeAnimationOptions };

function fakePage() {
  const calls: Call[] = [];
  const finishers: (() => void)[] = [];
  const cancelled: number[] = [];
  const page = {
    getBoundingClientRect: () => ({ width: 360, height: 640 }),
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

it("commits immediately and uses the latest direction without an exit-only interval", async () => {
  const { calls, doc } = fakePage();
  await leavePage("forward", doc);
  expect(pageEntering()).toBe(true);
  await leavePage("back", doc);
  expect(calls).toHaveLength(0);
  enterPage(doc);
  expect(pageEntering()).toBe(false);
  expect(calls).toHaveLength(1);
  expect(calls[0].frames[0]).toMatchObject({ transform: "translateX(-360px)" });
  expect(calls[0].frames.at(-1)).toMatchObject({ opacity: 1, transform: "none" });
});

it("peer navigation uses translation without scaling the contents", async () => {
  const { calls, doc } = fakePage();
  await leavePage("none", doc);
  enterPage(doc);
  expect(calls).toHaveLength(0);
  await leavePage("through", doc); enterPage(doc);
  expect(calls[0].frames[0]).toMatchObject({ transform: "translateX(360px)" });
});

it.each<NavMotion>(["forward", "back", "tab-forward", "tab-back", "through"])("%s: incoming content has fixed geometry and an explicit reduced-motion alternative", async nav => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: false } as MediaQueryList);
  const { calls, doc } = fakePage();
  await leavePage(nav, doc); enterPage(doc);
  expect(calls).toHaveLength(1);
  expect(calls[0].frames[0].transform).toBe(`translateX(${nav.endsWith("back") ? -360 : 360}px)`);
  expect(calls[0].frames.at(-1)?.transform).toBe("none");
  for (const frame of calls[0].frames) expect(frame).not.toHaveProperty("height");
});

it("nội dung có sẵn lúc trang vào không mọc từ 0; nội dung tới sau vẫn mở ra", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const animate = vi.fn(() => ({ cancel() {}, onfinish: null }) as unknown as Animation);
  Object.defineProperty(HTMLElement.prototype, "animate", { configurable: true, value: animate });
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  const { doc } = fakePage();
  const left = leavePage("through", doc);
  await act(() => root.render(<Collapse open appear><p>Tất cả</p></Collapse>));
  expect(animate).not.toHaveBeenCalled();
  await left; enterPage(doc);
  // Tới ngay lúc trang đang hiện vào: cũng hiện tại chỗ.
  await act(() => root.render(<><Collapse open appear><p>Tất cả</p></Collapse><Collapse key="soon" open appear><p>Kèm trang</p></Collapse></>));
  expect(animate).not.toHaveBeenCalled();
  // Tới sau khi trang đã đứng yên: mở ra.
  const later = performance.now() + 1000;
  vi.spyOn(performance, "now").mockReturnValue(later);
  await act(() => root.render(<><Collapse open appear><p>Tất cả</p></Collapse><Collapse key="soon" open appear><p>Kèm trang</p></Collapse><Collapse key="late" open appear><p>Mới</p></Collapse></>));
  expect(animate).toHaveBeenCalledTimes(1);
  await act(() => root.unmount()); host.remove();
  Reflect.deleteProperty(HTMLElement.prototype, "animate");
});

it("thứ dựng cùng trang mới (hiện dần, dòng nhô lên) đi theo chuyển cảnh trang; vòng lặp, việc dài, việc đã chạy và việc trễ có chủ ý giữ nguyên", async () => {
  const { doc } = fakePage();
  const finished: string[] = [];
  const child = (name: string, iterations: number, endTime: number, currentTime: number, delay = 0) =>
    ({ effect: { getComputedTiming: () => ({ iterations, endTime }), getTiming: () => ({ delay }) }, currentTime, cancel() {}, finish: () => finished.push(name) });
  const children = [child("hiện dần", 1, 220, 0), child("dòng nhô", 1, 300, 0), child("nhấp nháy", Infinity, 1200, 0), child("đếm ngược", 1, 60000, 0), child("đang chạy", 1, 220, 150),
    child("khung chờ trễ", 1, 420, 0, 200)];
  const page = (doc as unknown as { querySelector: () => { getAnimations: (options?: { subtree?: boolean }) => unknown[] } }).querySelector();
  const own = page.getAnimations;
  page.getAnimations = (options) => (options?.subtree ? children : own());
  const left = leavePage("through", doc);
  await left;
  enterPage(doc);
  expect(finished).toEqual(["hiện dần", "dòng nhô"]);
});
