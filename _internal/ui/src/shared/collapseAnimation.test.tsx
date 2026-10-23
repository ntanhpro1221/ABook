import { expect, it, vi } from "vitest";
import { Collapse } from "./Collapse";
const h = vi.hoisted(() => ({ slots: [] as { current: unknown }[], index: 0, effects: [] as (() => unknown)[] }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useRef: (initial: unknown) => h.slots[h.index++] ?? (h.slots[h.index - 1] = { current: initial }),
  useLayoutEffect: (effect: () => unknown) => h.effects.push(effect),
}));

it("giảm chuyển động: chỉ opacity; đóng giữ height đến cuối fade, đảo chiều không tween height", () => {
  const animation = { cancel: vi.fn(), onfinish: null as (() => void) | null };
  const box = { style: { height: "" }, getBoundingClientRect: () => ({ height: 900 }), firstElementChild: { getBoundingClientRect: () => ({ height: 900 }) }, animate: vi.fn((_frames: Keyframe[], _options: KeyframeAnimationOptions) => animation) };
  vi.stubGlobal("window", { matchMedia: () => ({ matches: true }) });
  const render = (open: boolean) => { h.index = 0; h.effects = []; return Collapse({ open, children: "body" }); };
  render(true); h.slots[0].current = box;
  render(false); h.effects[0]();
  expect(box.style.height).toBe("900px");
  expect(box.animate.mock.calls[0][0]).toEqual([{ opacity: 1 }, { opacity: 0 }]);
  animation.onfinish?.();
  expect(box.style.height).toBe("");
  render(true); h.effects[0]();
  expect(box.animate.mock.calls[1][0]).toEqual([{ opacity: 0 }, { opacity: 1 }]);
  vi.unstubAllGlobals();
});
