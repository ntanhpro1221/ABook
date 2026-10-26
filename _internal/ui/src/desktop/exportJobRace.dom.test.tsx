// @vitest-environment happy-dom
// Hỏi trạng thái việc xuất mỗi giây mà máy chủ trả chậm hơn một giây: câu trả lời cũ ("đang chạy") về SAU câu trả lời mới ("xong")
// không được dựng lại thông báo tiến độ có nút Huỷ quay mãi - khi ấy không còn ai hỏi tiếp để sửa nó.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { toast } from "@/shared/toast";
import { TooltipProvider } from "@/shared/ui";
import { ExportJobHost, startExport } from "./ExportBookFileJob";

const h = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("@/studio/api", async (original) => ({ ...(await original<typeof import("@/studio/api")>()), api: h.api }));
const appInfo = vi.hoisted(() => ({ data: { dialogs: false, remote: false } as object | undefined }));
vi.mock("@/studio/data", () => ({ useAppInfo: () => ({ data: appInfo.data }), usePreferences: () => ({ data: {} }), pickFolder: vi.fn() }));

let root: Root, host: HTMLElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  h.api.mockReset();
  appInfo.data = { dialogs: false, remote: false };
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
});
afterEach(async () => {
  await act(() => { toast.dismiss(); root.unmount(); });
  client.clear(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); document.body.replaceChildren();
});

it("câu trả lời 'đang chạy' về muộn sau câu 'xong' không đè thông báo xong", async () => {
  const running = { state: "running", chapter: 1, chapters: 3, phase: "chapters" };
  const done = { state: "done", result: { folder: "D:/Audio", files: 3 } };
  let slow: (job: object) => void = () => undefined;
  const answers: (() => Promise<object>)[] = [
    () => new Promise((resolve) => (slow = resolve)), // lần hỏi đầu: máy chủ trả chậm
    async () => done,
  ];
  h.api.mockImplementation(async (url: string, init?: { method?: string }) => {
    if (init?.method === "POST" || url === "/api/export-jobs") return { jobs: [] };
    return (answers.shift() ?? (async () => done))();
  });
  await act(() => root.render(
    <QueryClientProvider client={client}><MemoryRouter><TooltipProvider><ExportJobHost kind="mp3" /><Toaster /></TooltipProvider></MemoryRouter></QueryClientProvider>,
  ));
  await act(() => startExport("mp3", { id: "b", chapters: 3, target: "" }));
  await act(() => vi.advanceTimersByTime(1000)); // nhịp hỏi thứ hai
  await act(() => vi.advanceTimersByTime(50));
  await act(async () => slow(running)); // câu trả lời của lần hỏi đầu về muộn
  await act(() => vi.advanceTimersByTime(3000));
  await act(() => vi.advanceTimersByTime(50));
  const toastNode = document.querySelector<HTMLElement>("[data-sonner-toast]")!;
  expect(toastNode.textContent).toContain("Đã xuất MP3");
  expect(toastNode.textContent).not.toContain("Huỷ");
});

it("tải lại trang sách lúc đang xuất ở Studio từ xa: chờ biết máy này là máy nào rồi mới theo - thông báo xong không có 'Mở thư mục'", async () => {
  appInfo.data = undefined;
  let job: object = { state: "running", chapter: 1, chapters: 3, phase: "chapters" };
  h.api.mockImplementation(async (url: string) => (url === "/api/export-jobs" ? { mp3: [{ bookId: "b", state: "running" }] } : job));
  const draw = () => root.render(
    <QueryClientProvider client={client}><MemoryRouter initialEntries={["/book/b"]}><TooltipProvider><ExportJobHost kind="mp3" /><Toaster /></TooltipProvider></MemoryRouter></QueryClientProvider>,
  );
  await act(draw);
  await act(() => vi.advanceTimersByTimeAsync(50));
  appInfo.data = { dialogs: false, remote: true, remoteName: "Máy A" };
  await act(draw);
  await act(() => vi.advanceTimersByTimeAsync(1000));
  job = { state: "done", result: { folder: "D:/Audio", files: 3 } };
  await act(() => vi.advanceTimersByTimeAsync(2000));
  const toastNode = document.querySelector<HTMLElement>("[data-sonner-toast]")!;
  expect(toastNode).not.toBeNull();
  expect(toastNode.textContent).not.toContain("Mở thư mục");
});
