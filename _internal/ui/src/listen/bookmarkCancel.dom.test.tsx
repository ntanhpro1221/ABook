// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BookmarkList } from "./PlayerViews";
import { MotionHashRouter } from "@/shared/MotionRouter";
import { Dialog, TooltipProvider } from "@/shared/ui";
import { dismissTopLayer } from "@/android/backLayers";

const h = vi.hoisted(() => ({ update: vi.fn() }));
vi.mock("./source", () => ({ useSource: () => ({}), useListenMutations: () => ({ updateBookmark: { mutate: h.update } }) }));
let root: ReturnType<typeof createRoot>;
let client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {} }) as Animation);
});

it("M16 chỉ hiện empty sau khi dấu trang cuối đã hết exit", async () => {
  vi.useFakeTimers();
  const mark = { id: "m", chapterId: 1, seconds: 3, at: 1, note: "Đã lưu", quote: "Câu văn" };
  const render = (marks: typeof mark[]) => act(() => root.render(<QueryClientProvider client={client}><TooltipProvider><BookmarkList bookId="b" chapters={[]} marks={marks} onJump={() => {}} empty={<p>Hết dấu trang</p>} /></TooltipProvider></QueryClientProvider>));
  try {
    await render([mark]); await render([]);
    expect(document.body.textContent).not.toContain("Hết dấu trang");
    await act(() => vi.advanceTimersByTime(500));
    expect(document.body.textContent).toContain("Hết dấu trang");
  } finally { vi.useRealTimers(); }
});

it("V8 empty dấu trang fade ra khi thêm và fade vào sau khi hàng cuối exit", async () => {
  vi.useFakeTimers();
  const mark = { id: "m", chapterId: 1, seconds: 3, at: 1, note: "Đã lưu", quote: "Câu văn" };
  const render = (marks: typeof mark[], empty = true) => act(() => root.render(<QueryClientProvider client={client}><TooltipProvider><BookmarkList bookId="b" chapters={[]} marks={marks} onJump={() => {}} empty={empty ? <p>Hết dấu trang</p> : null} /></TooltipProvider></QueryClientProvider>));
  try {
    await render([]);
    expect(document.querySelector(".motion-panel[data-state=open]")?.textContent).toBe("Hết dấu trang");
    await render([mark], false);
    const exiting = document.querySelector(".motion-panel[data-state=closed]");
    expect(exiting?.textContent).toBe("Hết dấu trang"); expect(exiting?.hasAttribute("inert")).toBe(true);
    await act(() => vi.advanceTimersByTime(500)); expect(exiting?.isConnected).toBe(false);
    await render([]);
    expect(document.querySelector(".motion-panel[data-state=open]")).toBeNull();
    await act(() => vi.advanceTimersByTime(500));
    expect(document.querySelector(".motion-panel[data-state=open]")?.textContent).toBe("Hết dấu trang");
  } finally { vi.useRealTimers(); }
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); h.update.mockClear(); });

it.each(["Escape", "Back", "Huỷ"])("V6 %s huỷ draft, mở lại là bản lưu, trả focus và giữ Dialog ngoài", async (method) => {
  const close = vi.fn();
  const mark = { id: "m", chapterId: 1, seconds: 3, at: 1, note: "Đã lưu", quote: "Câu văn" };
  await act(() => root.render(<QueryClientProvider client={client}><TooltipProvider><MotionHashRouter><Dialog open onOpenChange={close} title="Dấu trang" description="Ghi chú"><BookmarkList bookId="b" chapters={[]} marks={[mark]} onJump={() => {}} /></Dialog></MotionHashRouter></TooltipProvider></QueryClientProvider>));
  const edit = document.querySelector<HTMLButtonElement>('[aria-label="Sửa ghi chú"]')!;
  await act(() => edit.click());
  const input = document.querySelector<HTMLInputElement>('[aria-label="Ghi chú"]')!;
  await act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "Draft chưa lưu");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(input.value).toBe("Draft chưa lưu");
  await act(() => {
    if (method === "Escape") input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    else if (method === "Back") expect(dismissTopLayer()).toBe(true);
    else Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((el) => el.textContent === "Huỷ")!.click();
  });
  expect(document.querySelector('[aria-label="Ghi chú"]')).toBeNull();
  expect(document.activeElement).toBe(edit);
  expect(close).not.toHaveBeenCalled();
  expect(h.update).not.toHaveBeenCalled();
  await act(() => edit.click());
  expect(document.querySelector<HTMLInputElement>('[aria-label="Ghi chú"]')!.value).toBe("Đã lưu");
});
