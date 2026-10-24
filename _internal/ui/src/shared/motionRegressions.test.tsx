import { expect, it, vi } from "vitest";
import { cloneElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AnimatedRows } from "./MotionPresence";
import { mergeRows, fallbackSnapshot } from "./motion";
import { WorkCards, type WorkItem } from "@/studio/WorkInbox";
import type { BookSummary } from "@/studio/api";

const h = vi.hoisted(() => ({ rows: [] as unknown[], navigate: vi.fn(), state: {} }));
vi.mock("./motion", async (original) => ({ ...await original<typeof import("./motion")>(), useListPresence: () => h.rows }));
vi.mock("react-router", () => ({ useNavigate: () => h.navigate, useLocation: () => ({ state: h.state }), NavLink: "a" }));
vi.mock("@/studio/liveRefresh", () => ({ useProducingRefetch: () => false }));
import { useLeaveSettingsGroup } from "./SettingsNav";

it("hàng exit không chiếm chỉ số dữ liệu: B vẫn 0 khi A đang ra", () => {
  const all = [{ id: "A" }, { id: "B" }, { id: "C" }];
  h.rows = mergeRows(mergeRows([], all, (row) => row.id, true), all.slice(1), (row) => row.id);
  const render = vi.fn((item: { id: string }, index: number) => `${item.id}:${index}`);
  renderToStaticMarkup(<AnimatedRows items={all.slice(1)} keyOf={(row) => row.id}>{render}</AnimatedRows>);
  expect(render.mock.calls.map(([item, index]) => [item.id, index])).toEqual([["A", -1], ["B", 0], ["C", 1]]);
});

it("thẻ chuyển nhóm: bản exit bỏ ID và ARIA định danh, bản sống giữ ID duy nhất", () => {
  const tree = WorkCards({ book: { id: "b" } as BookSummary, items: [{ key: "A", kind: "audio", title: "A", examples: [], affected: 1, current: "" } as unknown as WorkItem], onOpenReview: vi.fn() });
  const list = tree.props.children;
  const card = list.props.children[0] as ReactElement<{ exiting?: boolean }>;
  const html = renderToStaticMarkup(<>{cloneElement(card, { exiting: true })}{card}</>);
  expect(html.match(/id="work-A"/g)).toHaveLength(1);
  expect(html.match(/id="work-A-title"/g)).toHaveLength(1);
  expect(html.match(/aria-labelledby="work-A-title"/g)).toHaveLength(1);
});

it("rộng → chọn nhóm bằng replace → hẹp → Về Cài đặt luôn về route cha", () => {
  h.state = { settingsList: false };
  vi.stubGlobal("window", { history: { state: { idx: 3 } } });
  useLeaveSettingsGroup()();
  expect(h.navigate).toHaveBeenLastCalledWith("/settings", { replace: true });
  h.state = {};
  useLeaveSettingsGroup()();
  expect(h.navigate).toHaveBeenLastCalledWith(-1); // Lối tắt player trở về nguồn.
  vi.unstubAllGlobals();
});

it("fallback của bước Dialog nằm trên surface 50, inert, nội dung mới cũng fade", () => {
  vi.useFakeTimers();
  const remove = vi.fn();
  const clone = { style: { setProperty: vi.fn(), zIndex: "" }, classList: { add: vi.fn() }, removeAttribute: vi.fn(), setAttribute: vi.fn(), querySelectorAll: () => [], addEventListener: vi.fn(), remove };
  const target = { cloneNode: () => clone, getBoundingClientRect: () => ({ top: 1, left: 2, width: 300, height: 500 }), querySelectorAll: () => [], animate: vi.fn() };
  vi.stubGlobal("window", { setTimeout, clearTimeout });
  vi.stubGlobal("requestAnimationFrame", (run: () => void) => run());
  vi.stubGlobal("getComputedStyle", () => Object.assign([], { zIndex: "50", getPropertyValue: () => "#fff" }));
  const doc = { body: { append: vi.fn() }, querySelector: () => null, querySelectorAll: () => [target], documentElement: { dataset: {} } };
  fallbackSnapshot(doc as unknown as Parameters<typeof fallbackSnapshot>[0], "none");
  expect(clone.style.zIndex).toBe("51");
  expect(clone.setAttribute).toHaveBeenCalledWith("inert", "");
  expect(target.animate).toHaveBeenCalled();
  vi.runAllTimers();
  expect(remove).toHaveBeenCalled();
  vi.unstubAllGlobals(); vi.useRealTimers();
});
