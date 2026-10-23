import { afterEach, expect, it, vi } from "vitest";
import { backLayerCount, topBackLayer, useBackLayer } from "./backStack";

const h = vi.hoisted(() => ({ refs: [] as { current: unknown }[], cursor: 0, effect: undefined as (() => void | (() => void)) | undefined }));
vi.mock("react", async (original) => ({ ...await original<typeof import("react")>(), useRef: (initial: unknown) => h.refs[h.cursor++] ??= { current: initial }, useEffect: (run: () => void) => { h.effect = run; } }));
afterEach(() => { h.refs = []; h.cursor = 0; });
it("Back bước con trả focus sau commit, chỉ gỡ lớp đó; cleanup unmount không focus nhầm", () => {
  const close = vi.fn();
  const focus = vi.fn();
  const panel = { current: {} as Element };
  const trigger = { current: { focus } as unknown as HTMLElement };
  const render = (open: boolean) => {
    h.cursor = 0;
    useBackLayer(open, close, panel, trigger);
    return h.effect!();
  };
  const cleanup = render(true);
  expect(backLayerCount()).toBe(1);
  topBackLayer()!.close();
  expect(close).toHaveBeenCalledOnce(); expect(focus).not.toHaveBeenCalled();
  // React đã commit nút mở mới trước effect đóng.
  if (typeof cleanup === "function") cleanup();
  render(false);
  expect(backLayerCount()).toBe(0);
  expect(focus).toHaveBeenCalledOnce();
  const unmount = render(true);
  if (typeof unmount === "function") unmount();
  expect(focus).toHaveBeenCalledOnce();
});
