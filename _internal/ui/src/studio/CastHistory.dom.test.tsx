// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import fixture from "../../../tests/fixtures/cast_history.json";
import type { CastHistoryView } from "@/listen/model";
import { CastHistory } from "./CastHistory";

const request = vi.hoisted(() => vi.fn(async () => ({ state: "pending" })));
vi.mock("./api", () => ({ api: request }));
vi.mock("./decisions", () => ({ refreshAfterDecision: vi.fn() }));
let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  request.mockReset(); request.mockResolvedValue({ state: "pending" });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  localStorage.clear();
  container = document.createElement("div"); document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks(); });
async function show(history: CastHistoryView | undefined, editable = true) {
  await act(async () => root.render(<QueryClientProvider client={new QueryClient()}><CastHistory bookId="book1" history={history} editable={editable} /></QueryClientProvider>));
}
function button(text: string) { return [...container.querySelectorAll("button")].find(item => item.textContent?.includes(text))!; }

it("opens history and queues the exact operation in two clicks", async () => {
  await show(fixture.history as CastHistoryView);
  expect(request).not.toHaveBeenCalled();
  await act(async () => button("Lịch sử").click());
  await act(async () => button("Hoàn tác").click());
  expect(request).toHaveBeenCalledExactlyOnceWith("/api/books/book1/cast-history/undo", { method: "POST", body: { operationId: fixture.original } });
  expect(container.textContent).toContain("Chờ áp dụng");
  expect(container.textContent).toContain("Giọng đọc chưa đổi; chờ thu lại.");
});

it("keeps conflicts visible after reopen and disables completed operations", async () => {
  await show({ items: [{ ...fixture.history.items[0], state: "undone", conflicts: 1 }], manualOnly: false });
  expect(container.textContent).toContain("1 câu xung đột");
  expect(container.textContent).toContain("Đã hoàn tác");
  expect(container.querySelectorAll("button")).toHaveLength(1);
});

it("explains manual splitting without before-state", async () => {
  await show(undefined);
  expect(container.textContent).toContain("Không có trạng thái trước; hãy tách thủ công.");
  expect(request).not.toHaveBeenCalled();
});

it("keeps the history read-only when editing is unavailable", async () => {
  await show(fixture.history as CastHistoryView, false);
  expect(container.querySelectorAll("button")).toHaveLength(1);
  expect(request).not.toHaveBeenCalled();
});

it("keeps an uncertain request retryable with the same operation ID", async () => {
  request.mockRejectedValueOnce(new Error("offline"));
  await show(fixture.history as CastHistoryView);
  await act(async () => button("Lịch sử").click());
  await act(async () => button("Hoàn tác").click());
  expect(container.textContent).toContain("offline");
  await act(async () => button("Hoàn tác").click());
  expect(request.mock.calls[0]).toEqual(request.mock.calls[1]);
});
