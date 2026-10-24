// @vitest-environment happy-dom
import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useMotionState } from "./motion";

let root: Root, host: HTMLDivElement;
let state: ReturnType<typeof useMotionState<number>>;
let start: ReturnType<typeof vi.fn>;
function State() { state = useMotionState(0); return <p>{state[0]}</p>; }
beforeEach(async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  start = vi.fn((update: () => void) => { update(); return {}; });
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: start });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(() => root.render(<StrictMode><State /></StrictMode>));
});
afterEach(async () => {
  await act(() => root.unmount()); host.remove(); Reflect.deleteProperty(document, "startViewTransition");
  delete document.documentElement.dataset.vt; delete document.documentElement.dataset.nav;
});

it("same values and identity updaters never start a View Transition", async () => {
  await act(() => { state[1](0); state[1](previous => previous); });
  expect(start).not.toHaveBeenCalled();
});
it("real changes start one transition even in StrictMode", async () => {
  await act(() => state[1](previous => previous + 1));
  expect(start).toHaveBeenCalledTimes(1); expect(host.textContent).toBe("1");
});
it("Object.is treats NaN as unchanged and distinguishes signed zero", async () => {
  await act(() => state[2](NaN));
  await act(() => state[1](NaN));
  expect(start).not.toHaveBeenCalled();
  await act(() => state[2](0));
  await act(() => state[1](-0));
  expect(start).toHaveBeenCalledTimes(1);
  expect(Object.is(state[0], -0)).toBe(true);
});
it("cleanup updates without a transition and supports queued functional changes", async () => {
  await act(() => { state[2](1); state[2](previous => previous + 1); });
  expect(start).not.toHaveBeenCalled(); expect(host.textContent).toBe("2");
});
it("a delayed transition cannot undo newer cleanup", async () => {
  let update!: () => void;
  start.mockImplementation(callback => { update = callback; return { finished: new Promise(() => {}) }; });
  await act(() => state[1](1));
  await act(() => state[2](2));
  await act(() => update());
  expect(host.textContent).toBe("2");
  delete document.documentElement.dataset.vt; delete document.documentElement.dataset.nav;
});

it.each([
  ["VT rồi noVT, cùng giá trị", 1, 2, 1],
  ["VT rồi noVT, khác giá trị", 1, 2, 2],
  ["noVT rồi VT, cùng giá trị", 2, 1, 1],
  ["noVT rồi VT, khác giá trị", 2, 1, 2],
] as const)("%s: callback trì hoãn không đảo ý định mới", async (_label, first, second, last) => {
  const updates: (() => void)[] = [];
  start.mockImplementation(callback => { updates.push(callback); return { finished: new Promise(() => {}) }; });
  await act(() => state[first](1));
  expect(host.textContent).toBe(first === 1 ? "0" : "1");
  await act(() => state[second](last));
  // Setter noVT phải commit ngay, kể cả khi trùng giá trị đang chờ callback VT.
  expect(host.textContent).toBe(second === 2 ? String(last) : "1");
  await act(() => updates.forEach(update => update()));
  expect(host.textContent).toBe(String(last));
  expect(start).toHaveBeenCalledTimes(first === 2 && last === 1 ? 0 : 1);
});

it("identity noVT commits a pending value immediately and invalidates its callback", async () => {
  let update!: () => void;
  start.mockImplementation(callback => { update = callback; return { finished: new Promise(() => {}) }; });
  await act(() => state[1](1));
  await act(() => state[2](previous => previous));
  expect(host.textContent).toBe("1");
  await act(() => state[2](2));
  await act(() => update());
  expect(host.textContent).toBe("2");
});
