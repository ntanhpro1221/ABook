import { afterEach, expect, it, vi } from "vitest";
import { workKeyHandler } from "./workKeys";
import { mergeRows } from "@/shared/motion";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
it("A đang exit: J/K rồi 1 bấm B/C theo key sống; không bấm A hay bản inert", () => {
  vi.useFakeTimers();
  vi.stubGlobal("Element", class {});
  vi.stubGlobal("CSS", { escape: (id: string) => id });
  const focus = vi.fn();
  vi.stubGlobal("window", { setTimeout });
  const a = vi.fn(), b = vi.fn(), c = vi.fn(), inert = vi.fn();
  const actions = { A: a, B: b, C: c };
  const query = vi.fn((selector: string) => {
    const key = /#work-(\w+)/.exec(selector)![1] as keyof typeof actions;
    return [{ closest: () => ({}), click: inert }, { closest: () => null, click: actions[key] }];
  });
  vi.stubGlobal("document", { querySelectorAll: query, getElementById: (id: string) => ({ focus: () => focus(id), scrollIntoView: vi.fn() }) });
  const all = [{ key: "A" }, { key: "B" }, { key: "C" }];
  const visible = mergeRows(mergeRows([], all, (item) => item.key, true), all.slice(1), (item) => item.key);
  expect(visible.map(({ key, state }) => [key, state])).toEqual([["A", "exit"], ["B", "idle"], ["C", "idle"]]);
  let items = all.slice(1), cursor: number | null = null;
  const handler = workKeyHandler(() => items, () => cursor, (next) => { cursor = next; }, { end: "end", lead: "lead" });
  const key = (value: string) => handler({ key: value, target: null, preventDefault: vi.fn() } as unknown as KeyboardEvent);
  key("j"); key("j"); key("k"); key("1");
  vi.runAllTimers();
  expect(focus.mock.calls.map(([id]) => id)).toEqual(["work-B", "work-C", "work-B"]);
  expect(b).toHaveBeenCalledOnce();
  // B cũng chuyển nhóm khi A chưa hết exit: cùng con trỏ 0 nay là C.
  items = all.slice(2);
  key("1");
  expect(c).toHaveBeenCalledOnce();
  expect(a).not.toHaveBeenCalled(); expect(inert).not.toHaveBeenCalled();
});
