// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import { dismissTopLayer } from "@/android/backLayers";
import type { ListenBook } from "./model";
import { ClipProvider } from "./clip";

// audit140 V9: "Tìm bìa…" trong hộp Sửa sách từng mở hộp thứ hai đè lên. Giờ là một bước của chính hộp ấy: một hộp, đổi tên, Quay lại / Back về.
vi.mock("@/studio/api", async (original) => ({
  ...(await original<typeof import("@/studio/api")>()),
  api: vi.fn(() => new Promise(() => undefined)),
}));
vi.mock("./source", async (original) => ({
  ...(await original<typeof import("./source")>()),
  useSource: () => new Proxy({}, { get: () => () => new Promise(() => undefined) }),
  useReadAloudVoices: () => ({ data: [] }),
}));
let root: ReturnType<typeof createRoot>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, finished: Promise.resolve() }) as unknown as Animation);
});
afterEach(() => { act(() => root.unmount()); document.body.innerHTML = ""; vi.restoreAllMocks(); });

const titleText = () => document.querySelector('[role="dialog"] h2')?.textContent;

it("tìm bìa là một bước trong hộp Sửa sách, không phải hộp thứ hai", async () => {
  const { EditBookDialog } = await import("./EditBook");
  const book = { id: "sach", title: "Tiệm Sách Trên Gác Xép", author: "", stage: "text", chapters: [], capabilities: {} } as unknown as ListenBook;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await act(async () => root.render(<QueryClientProvider client={client}><TooltipProvider><ClipProvider><EditBookDialog book={book} open onOpenChange={() => undefined} /></ClipProvider></TooltipProvider></QueryClientProvider>));
  expect(titleText()).toBe("Sửa sách");
  const find = [...document.querySelectorAll("button")].find((button) => button.textContent?.includes("Tìm bìa"))!;
  await act(async () => find.click());
  expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1);
  expect(titleText()).toBe("Tìm ảnh bìa");
  expect(document.querySelector<HTMLInputElement>("#cover-search-query")?.value).toBe("Tiệm Sách Trên Gác Xép");
  await act(async () => { expect(dismissTopLayer()).toBe(true); });
  expect(titleText()).toBe("Sửa sách");
  expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1);
  await act(async () => [...document.querySelectorAll("button")].find((button) => button.textContent?.includes("Tìm bìa"))!.click());
  await act(async () => [...document.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Sửa sách")!.click());
  expect(titleText()).toBe("Sửa sách");
});
