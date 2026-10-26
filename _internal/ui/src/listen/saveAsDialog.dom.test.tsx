// @vitest-environment happy-dom
// "Lưu thành": lưu hỏng hay bạn huỷ hộp chọn chỗ lưu thì hộp vẫn mở - loại file và thư mục đã chọn không mất; lưu xong mới đóng.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import type { ListenBook } from "./model";

const state = vi.hoisted(() => ({ saveBook: vi.fn() }));
vi.mock("./source", async (original) => ({ ...(await original<typeof import("./source")>()), useSource: () => ({ kind: "desktop", saveBook: state.saveBook }) }));
vi.mock("@/shared/toast", async (original) => ({ ...(await original<typeof import("@/shared/toast")>()), toastDone: vi.fn(), toast: Object.assign(vi.fn(), { error: vi.fn() }) }));
import { SaveAsDialog } from "./EditBook";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });

const book = { id: "b", title: "Sách" } as ListenBook;
const clickSave = async () => {
  const button = [...document.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.trim() === "Lưu")!;
  await act(async () => { button.click(); });
  await act(async () => { await Promise.resolve(); });
};

it.each([
  ["bạn huỷ hộp chọn chỗ lưu", () => state.saveBook.mockResolvedValue({ saved: false })],
  ["máy chủ báo lỗi", () => state.saveBook.mockRejectedValue(new Error("Ổ đĩa đầy"))],
])("%s: hộp Lưu thành vẫn mở", async (_case, arrange) => {
  arrange();
  const onOpenChange = vi.fn();
  await act(() => root.render(<TooltipProvider><SaveAsDialog book={book} open onOpenChange={onOpenChange} /></TooltipProvider>));
  await clickSave();
  expect(state.saveBook).toHaveBeenCalled();
  expect(onOpenChange).not.toHaveBeenCalledWith(false);
});

it("lưu xong thì đóng", async () => {
  state.saveBook.mockResolvedValue({ saved: true, edits: 1 });
  const onOpenChange = vi.fn();
  await act(() => root.render(<TooltipProvider><SaveAsDialog book={book} open onOpenChange={onOpenChange} /></TooltipProvider>));
  await clickSave();
  expect(onOpenChange).toHaveBeenCalledWith(false);
});
