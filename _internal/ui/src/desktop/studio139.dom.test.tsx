// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { toast } from "@/shared/toast";
import { TooltipProvider } from "@/shared/ui";
import { SettingsList } from "@/shared/SettingsNav";
import { installBackOrder } from "@/shared/backOrder";
import { dismissTopLayer } from "@/android/backLayers";
import { ChapterError } from "@/studio/ChapterError";
import { PhoneSync } from "./PhoneSync";
import { AudiobookForm } from "./AudiobookDialog";
import { HandOffButton } from "./RemotePhone";
import { ExportJobHost, startExport } from "./ExportBookFileJob";

const h = vi.hoisted(() => ({ api: vi.fn(), track: null as null | { bookId: string; chapterId: number }, phones: [] as object[] }));
vi.mock("@/studio/api", async original => ({ ...await original<typeof import("@/studio/api")>(), api: h.api }));
vi.mock("@/studio/data", () => ({ useAppInfo: () => ({ data: { dialogs: false, remote: false } }), usePreferences: () => ({ data: {} }), pickFolder: vi.fn() }));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: h.track }) }));
vi.mock("@/listen/clock", () => ({ useClockReader: () => () => ({ time: 0 }) }));
vi.mock("@/listen/source", () => ({ useListenBook: () => ({}), useSource: () => ({}) }));
let root: Root, host: HTMLElement, client: QueryClient;
const draw = (node: ReactNode) => act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter></QueryClientProvider>));
const finish = () => act(() => {
  for (const call of vi.mocked(HTMLElement.prototype.animate).mock.results) (call.value as Animation).onfinish?.(new Event("finish") as AnimationPlaybackEvent);
});
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); localStorage.clear(); h.track = null; h.phones = [];
  h.api.mockReset(); h.api.mockResolvedValue({ jobs: [], phones: [] });
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ top: 0, left: 0, bottom: 200, right: 300, height: 200, width: 300, x: 0, y: 0, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
});
afterEach(async () => { await act(() => { toast.dismiss(); root.unmount(); }); client.clear(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); document.body.replaceChildren(); });

it.each(["RuntimeError: CUDA out of memory", "KeyError: 'speaker'"])("chi tiết lỗi chương nằm trên Back stack: %s", async raw => {
  const stop = installBackOrder();
  try {
    await draw(<ChapterError raw={raw} />);
    const trigger = host.querySelector<HTMLButtonElement>("button")!;
    expect(trigger.textContent).not.toContain(raw);
    await act(() => trigger.click());
    const popup = document.querySelector('[role="dialog"][data-state="open"]')!;
    expect(popup.textContent).toContain(raw);
    expect(popup.closest("details")).toBeNull();
    await act(() => { expect(dismissTopLayer()).toBe(true); });
    expect(document.querySelector('[role="dialog"][data-state="open"]')).toBeNull();
  } finally { stop(); }
});

it("mã ghép hết hạn fade cùng vùng và không chờ poll máy chủ", async () => {
  client.setQueryData(["sync"], { enabled: true, name: "Máy này", addresses: [], devices: [], fingerprint: "", remoteStudio: false, pairing: { code: "123456", expiresAt: Date.now() / 1000 + 1 }, pairingBlocked: false });
  await draw(<PhoneSync />);
  const code = host.querySelector('[aria-label="Mã ghép nối: 1 2 3 4 5 6"]')!;
  const region = code.closest("[data-motion-region]");
  expect(code).not.toBeNull();
  await act(() => vi.advanceTimersByTime(1000));
  expect(region?.isConnected).toBe(true);
  expect(region?.textContent).toContain("Ghép thiết bị mới");
  expect(vi.mocked(HTMLElement.prototype.animate).mock.contexts).toContain(region);
});

it("nút chuyển máy giữ một vùng khi chưa phát, hiện menu hoặc còn một đích", async () => {
  client.setQueryData(["remote"], { phones: [] });
  await draw(<HandOffButton />); const region = host.firstElementChild;
  h.track = { bookId: "b", chapterId: 1 }; await draw(<HandOffButton />);
  expect(host.firstElementChild).toBe(region);
  expect(host.querySelector('[aria-label="Phát trên máy khác"]')).not.toBeNull();
  await finish();
  await act(() => client.setQueryData(["remote"], { phones: [{ device: "p", name: "Loa", via: "cast", kind: "cast" }] }));
  await act(() => vi.advanceTimersByTime(1));
  expect(host.firstElementChild).toBe(region);
  expect(host.querySelector('[aria-label="Phát trên Loa"]')).not.toBeNull();
  expect(vi.mocked(HTMLElement.prototype.animate).mock.contexts).toContain(region);
});

it("kết quả tính xuất sách đến muộn fade trong thân hộp", async () => {
  const props = { voice: undefined, plan: undefined, planError: "", ffmpeg: undefined, format: "mp3" as const, onFormat: vi.fn(), onDownload: vi.fn(), onStopDownload: vi.fn() };
  await draw(<AudiobookForm {...props} />); const region = host.firstElementChild;
  await draw(<AudiobookForm {...props} ffmpeg={{ ready: false, bytes: 1000, downloading: false, done: 0, total: 1000, error: "", blocked: "" }} />);
  expect(host.firstElementChild).toBe(region);
  expect(host.textContent).toContain("Thiếu công cụ ghép");
  expect(vi.mocked(HTMLElement.prototype.animate).mock.contexts).toContain(region);
});

it("tóm tắt cài đặt fade theo chữ và giữ mục Studio inert trong lúc rời", async () => {
  await draw(<SettingsList rows={[{ id: "listen", summary: "Tự lùi" }, { id: "studio" }]} />);
  const summary = host.querySelector('a[href="/settings/listen"] [data-motion-region]');
  await draw(<SettingsList rows={[{ id: "listen", summary: "Không tự lùi" }]} />);
  expect(vi.mocked(HTMLElement.prototype.animate).mock.contexts).toContain(summary);
  expect(host.querySelector('a[href="/settings/studio"]')?.closest("[inert]")).not.toBeNull();
});

it("toast xuất giữ node khi tiến độ, huỷ, kết quả đổi và Back đóng được", async () => {
  let job: object = { state: "running", chapter: 1, chapters: 3, phase: "chapters" };
  h.api.mockImplementation(async (url: string) => url.includes("running") || url.includes("exports") ? { jobs: [] } : job);
  const stop = installBackOrder();
  try {
    await draw(<><ExportJobHost kind="mp3" /><Toaster /></>);
    await act(() => startExport("mp3", { id: "b", chapters: 3, target: "" }));
    await act(() => vi.advanceTimersByTime(50));
    const toastNode = document.querySelector<HTMLElement>("[data-sonner-toast]")!;
    expect(toastNode).not.toBeNull(); expect(toastNode.textContent).toContain("Chi tiết"); await finish();
    await act(() => [...toastNode.querySelectorAll("button")].find(button => button.textContent === "Chi tiết")!.click());
    expect(toastNode.textContent).toContain("Huỷ");
    await act(() => [...toastNode.querySelectorAll("button")].find(button => button.textContent === "Huỷ")!.click());
    await act(() => vi.advanceTimersByTime(50));
    expect(toastNode.textContent).toContain("Đang dừng");
    expect(document.querySelector("[data-sonner-toast]")).toBe(toastNode); await finish();
    job = { state: "done", result: { folder: "D:/Audio", files: 3 } };
    await act(() => vi.advanceTimersByTime(1000));
    await act(() => vi.advanceTimersByTime(50));
    expect(toastNode.textContent).toContain("Đã xuất MP3");
    expect(toastNode.textContent).toContain("Mở thư mục");
    expect(document.querySelector("[data-sonner-toast]")).toBe(toastNode);
    expect(document.querySelector(".motion-snapshot")).not.toBeNull();
    await act(() => { expect(dismissTopLayer()).toBe(true); });
    expect(toastNode.dataset.removed).toBe("true");
  } finally { stop(); }
});
