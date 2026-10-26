// @vitest-environment happy-dom
// "Tìm trong sách" với bộ gõ có khung soạn (IME: bàn phím điện thoại, Windows TSF): Enter chốt chữ đang soạn không phải là "mở kết quả đầu".
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import type { ListenBook } from "./model";

const source = vi.hoisted(() => ({ kind: "desktop" }));
vi.mock("./source", async (original) => ({ ...(await original<typeof import("./source")>()), useSource: () => source }));
vi.mock("./player", async (original) => ({ ...(await original<typeof import("./player")>()), usePlayer: () => ({ playing: false, track: null }) }));
vi.mock("./bookSearch", async (original) => ({
  ...(await original<typeof import("./bookSearch")>()),
  searchBook: async ({ onUpdate }: { onUpdate: (next: unknown) => void }) => {
    onUpdate({ done: true, scanned: 1, chapters: 1, total: 1, failed: 0, hits: [{ chapterId: 1, sentence: 3, snippet: { before: "", match: "Lan", after: "" } }] });
  },
}));
import { FindInBook } from "./FindInBook";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); vi.useRealTimers(); document.body.replaceChildren(); vi.restoreAllMocks(); });

const book = { id: "b", title: "Sách", chapters: [{ id: 1, index: 0, title: "Chương 1", fullTitle: "Chương 1", subtitle: "", duration: 60, available: true }] } as unknown as ListenBook;

it("Enter đang soạn chữ (isComposing) không mở kết quả; Enter thường thì mở", async () => {
  const onOpenChange = vi.fn();
  await act(() => root.render(
    <QueryClientProvider client={new QueryClient()}><MemoryRouter><TooltipProvider><FindInBook book={book} open onOpenChange={onOpenChange} /></TooltipProvider></MemoryRouter></QueryClientProvider>,
  ));
  const input = document.querySelector<HTMLInputElement>('input[type="search"]')!;
  await act(() => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    setter.call(input, "Lan");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(() => vi.advanceTimersByTimeAsync(300));
  // Vùng chuyển động giữ chữ cũ tới khi lần mờ xong: cho mọi lần mờ xong ngay.
  await act(() => { for (const call of vi.mocked(HTMLElement.prototype.animate).mock.results) (call.value as Animation).onfinish?.(new Event("finish") as AnimationPlaybackEvent); });
  await act(() => vi.advanceTimersByTimeAsync(500));
  expect(document.body.textContent).toContain("1 kết quả");
  await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, isComposing: true })); });
  expect(onOpenChange).not.toHaveBeenCalled();
  await act(() => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
  expect(onOpenChange).toHaveBeenCalledWith(false);
});
