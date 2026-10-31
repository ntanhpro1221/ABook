// @vitest-environment happy-dom
// Dòng tình trạng dưới tên sách và mục "Huỷ tải" trong menu đang mở cùng theo một lần tải: tải xong thì báo MỘT lần, không hai thông báo giống hệt.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import type { ListenBook } from "@/listen/model";
import { RemoteDownloadStatus } from "./RemoteDownload";

const toasts = vi.hoisted(() => ({ success: [] as unknown[][] }));
vi.mock("@/shared/toast", () => ({ toast: Object.assign(() => "", { success: (...args: unknown[]) => { toasts.success.push(args); return ""; }, error: () => "", dismiss: () => undefined }) }));
vi.mock("@/studio/api", async (original) => ({ ...(await original<typeof import("@/studio/api")>()), api: vi.fn(() => new Promise(() => {})) }));

let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, refetchInterval: false } } });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); vi.useRealTimers(); document.body.replaceChildren(); vi.restoreAllMocks(); });

it("hai chỗ cùng theo một lần tải: tải xong chỉ một thông báo", async () => {
  const book = { id: "r1", title: "Sách xa", remote: { computer: "Máy A" } } as unknown as ListenBook;
  const key = ["listen", "download", book.id];
  client.setQueryData(key, { state: "running", files: 2, filesDone: 1, bytes: 10, bytesDone: 5, error: "" });
  await act(() => root.render(
    <QueryClientProvider client={client}><TooltipProvider><RemoteDownloadStatus book={book} /><RemoteDownloadStatus book={book} /></TooltipProvider></QueryClientProvider>,
  ));
  toasts.success = [];
  await act(() => { client.setQueryData(key, { state: "done", files: 2, filesDone: 2, bytes: 10, bytesDone: 10, error: "" }); });
  await act(() => vi.advanceTimersByTime(10)); // React Query báo đổi qua một nhịp hẹn giờ
  // Cùng một mã thông báo: lần báo thứ hai thay đúng thông báo ấy (Sonner), không chồng thêm một cái.
  const ids = new Set(toasts.success.map(([, options]) => (options as { id?: unknown } | undefined)?.id));
  expect(toasts.success.length).toBeGreaterThan(0);
  expect(ids.size).toBe(1);
  expect([...ids][0]).toBeDefined();
});
