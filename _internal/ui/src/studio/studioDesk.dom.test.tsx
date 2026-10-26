// @vitest-environment happy-dom
// Studio máy tính (DESIGN.md mục 7): đầu trang dự án đúng MỘT nút chính theo trạng thái, việc khác ở "…"; tối đa 5 tab hiện, phần
// còn lại trong "Thêm"; tạo sách nói từ danh sách Studio trong ≤ 3 lần bấm (L10).
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Tabs, TooltipProvider } from "@/shared/ui";
import type { BookSummary } from "./api";

const state = vi.hoisted(() => ({
  create: vi.fn(),
  pickFolder: vi.fn(async () => "D:/Truyện/Đồng hồ cát"),
  books: [] as unknown[],
}));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: null, close: vi.fn(), play: vi.fn() }) }));
vi.mock("@/listen/clip", async (original) => ({ ...await original<typeof import("@/listen/clip")>(), useClip: () => ({ current: "", loading: false, toggle: vi.fn() }) }));
vi.mock("@/listen/source", async (original) => ({ ...await original<typeof import("@/listen/source")>(), useSource: () => ({ kind: "desktop", voiceUrl: () => "/voice.wav" }), useCast: () => ({ data: undefined }) }));
vi.mock("@/studio/api", async (original) => ({ ...await original<typeof import("@/studio/api")>(), api: vi.fn(() => new Promise(() => {})) }));
vi.mock("@/studio/StudioSetup", () => ({ StudioSetupCard: () => null, StudioInstallNotice: () => null, NoStudioHere: () => null, useStudioFit: () => null, useStudioGpu: () => null }));
vi.mock("@/studio/TemplateBar", () => ({ TemplateBar: () => null }));
vi.mock("@/studio/AnalysisModelPicker", () => ({
  AnalysisModelPicker: () => null, analysisChoiceLabel: () => "Mặc định", modelLabel: (name: string) => name,
  useAnalysisModels: () => ({ data: { default: "v5" } }), useAvailableModelNames: () => ["v5"],
}));
vi.mock("@/studio/data", async (original) => {
  const file = (path: string) => ({ path, name: path, title: path, firstLine: "", words: 1800, chars: 6400, audioSeconds: 600, credits: [], tailCredits: [] });
  const scan = (paths: string[]) => ({ files: paths.map((path) => file(`${path}/${1}.txt`)), totals: { words: 1800, chapters: 1, audioSeconds: 600 }, skipped: [], missing: [], subfolders: [], suggestedTitle: "Đồng hồ cát" });
  return {
    ...await original<typeof import("@/studio/data")>(),
    useAppInfo: () => ({ data: { dialogs: true } }),
    useLibrary: () => ({ data: { root: "D:/Sách", books: state.books }, isLoading: false, isError: false }),
    useOpenBook: () => ({ mutateAsync: vi.fn() }),
    useReveal: () => ({ mutate: vi.fn() }),
    useStart: () => ({ mutate: vi.fn(), isPending: false }),
    usePause: () => ({ mutate: vi.fn(), isPending: false }),
    useStop: () => ({ mutate: vi.fn(), isPending: false }),
    useLeaveQueue: () => ({ mutate: vi.fn() }),
    useContinuation: () => ({}),
    useRedo: () => ({}),
    useStudioMissing: () => ({ missing: false }),
    usePreferences: () => ({ data: {} }),
    useVoices: () => ({ data: [{ name: "Giọng thử", gender: "Nữ", region: "Bắc", style: "Tự nhiên" }] }),
    useFirstPersonHint: () => ({}),
    useScan: () => ({ isPending: false, mutate: (args: { paths: string[] }, handlers: { onSuccess: (result: unknown) => void }) => handlers.onSuccess(scan(args.paths)) }),
    useCreateBook: () => ({ mutate: state.create, isPending: false }),
    pickFolder: state.pickFolder,
  };
});
import { Actions, MAIN_TABS, ProjectTabBar } from "./ProjectScreen";
import { ProjectsScreen } from "./ProjectsScreen";
import { NewProjectScreen } from "./NewProjectScreen";

let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear(); sessionStorage.clear(); state.create.mockReset(); state.books = [];
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });
const render = async (node: ReactNode, path = "/") => {
  await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><TooltipProvider>{node}</TooltipProvider></MemoryRouter></QueryClientProvider>));
};
const text = (element: Element) => element.textContent?.trim() ?? "";
const primaries = () => [...host.querySelectorAll<HTMLButtonElement>("button")].filter((button) => button.classList.contains("bg-accent"));
const openMenu = (trigger: Element) => act(() => trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })));
const menuItems = () => [...document.querySelectorAll('[role="menu"] [role="menuitem"]')].map(text);

function book(extra: Partial<BookSummary> = {}): BookSummary {
  return {
    id: "b1", path: "D:/x/sach", title: "Sách thử", status: "analyzing", stage: "analysis", phase: "analysis", statusLabel: "Đang phân tích truyện",
    running: true, interrupted: false, starting: false, startError: "", createdAt: 1, updatedAt: 1, lastError: "", paused: null, canPause: true,
    settings: { profile: "high_quality", profileLabel: "Chất lượng cao", narrator: "" },
    chapters: { total: 10, completed: 0, failed: 0, working: 0 },
    segments: { total: 100, analyzed: 40, pending: 60, recorded: 0, finished: 0, failed: 0 },
    progress: { overall: 0.2, analysis: 0.4, synthesis: 0 }, audioSeconds: 0, eta: null, position: null,
    ...extra,
  } as BookSummary;
}

const stopped = { running: false, canPause: false };
const STATES: [string, Partial<BookSummary>, string][] = [
  ["chưa chạy", { ...stopped, phase: "idle", status: "idle", statusLabel: "Chưa bắt đầu" }, "Bắt đầu"],
  ["đang khởi động", { ...stopped, starting: true }, "Đang khởi động"],
  ["đang chạy", {}, "Tạm dừng"],
  ["tạm dừng", { paused: "listener" }, "Tiếp tục"],
  ["giữ chờ duyệt", { paused: "listener", precast: { held: true } as BookSummary["precast"] }, "Thu âm"],
  ["đang dừng", { stopping: true }, "Đang dừng"],
  ["dừng giữa lúc thu", { ...stopped, phase: "synthesis", chapters: { total: 10, completed: 3, failed: 0, working: 0 } }, "Tiếp tục"],
  ["phân tích bị ngắt", { ...stopped, analysisInterrupted: true }, "Phân tích lại"],
  ["xong", { ...stopped, phase: "done", chapters: { total: 10, completed: 10, failed: 0, working: 0 } }, "Nghe trong Thư viện"],
  ["xong, còn sửa chờ áp", { ...stopped, phase: "done", pendingChanges: 3, chapters: { total: 10, completed: 10, failed: 0, working: 0 } }, "Áp dụng 3 thay đổi"],
  ["xếp hàng, đã có chương", { ...stopped, phase: "synthesis", queuePosition: 2, chapters: { total: 10, completed: 4, failed: 0, working: 0 } }, "Nghe trong Thư viện"],
];

it.each(STATES)("đầu trang dự án %s: đúng một nút chính (%s)", async (_name, extra, label) => {
  await render(<Actions book={book(extra)} />);
  expect(primaries().map(text)).toEqual([label]);
});

it("xếp hàng mà chưa có chương nào: không có nút chính, trạng thái nói bằng chữ", async () => {
  await render(<Actions book={book({ ...stopped, phase: "analysis", queuePosition: 1 })} />);
  expect(primaries()).toHaveLength(0);
  expect(host.textContent).toContain("Chờ lượt 1");
});

it("đang chạy: Dừng, Xuất, Mở thư mục nằm trong \"…\", không phải nút riêng", async () => {
  await render(<Actions book={book({ chapters: { total: 10, completed: 2, failed: 0, working: 0 }, pendingChanges: 2 })} />);
  const buttons = [...host.querySelectorAll("button")].map(text);
  expect(buttons).not.toContain("Dừng");
  expect(buttons).not.toContain("Xuất");
  await openMenu(host.querySelector('[aria-label="Tuỳ chọn dự án Sách thử"]')!);
  expect(menuItems()).toEqual(expect.arrayContaining(["Nghe trong Thư viện", "Dừng", "2 thay đổi chờ áp", "Xuất", "Mở thư mục", "Đổi tên", "Xoá dự án"]));
});

it("tab dự án: tối đa 5 tab hiện, phần còn lại mở được trong \"Thêm\"", async () => {
  const onTab = vi.fn();
  const view = (tab: string) => (
    <Tabs value={tab}>
      <ProjectTabBar tab={tab} onTab={onTab} precast counts={{ chapters: 12, precast: 4, work: 3 }} />
    </Tabs>
  );
  await render(view("chapters"));
  // Nút "Thêm" cũng là một tab của hàng (tablist chỉ chứa tab - axe aria-required-children) nhưng mở menu: không tính vào số tab hiện.
  const tabs = [...host.querySelectorAll('[role="tab"]:not([aria-haspopup])')].map(text);
  expect(tabs.length).toBeLessThanOrEqual(5);
  expect(tabs).toHaveLength(MAIN_TABS.length);
  expect(tabs.map((label) => label.replace(/[\d,\s]*(mục)?$/, ""))).toEqual(["Chương", "Việc cần duyệt", "Cần nghe lại", "Nhân vật", "Nhạc nền"]);
  const more = [...host.querySelectorAll("button")].find((button) => text(button).startsWith("Thêm"))!;
  expect(more.getAttribute("role")).toBe("tab");
  expect(more.getAttribute("aria-haspopup")).toBe("menu");
  expect(more.getAttribute("aria-selected")).toBe("false");
  expect(text(more)).toContain("4"); // số của "Duyệt trước khi thu" không mất khi tab nằm trong "Thêm"
  await openMenu(more);
  expect(menuItems().map((label) => label.replace(/\d+$/, ""))).toEqual(["Duyệt trước khi thu", "Kịch bản", "Nhật ký"]);
  const script = [...document.querySelectorAll('[role="menuitem"]')].find((item) => text(item) === "Kịch bản")!;
  await act(() => { (script as HTMLElement).click(); });
  expect(onTab).toHaveBeenCalledWith("script");
  // Tab đang chọn nằm trong "Thêm": nút mang tên tab ấy và gạch chân như tab thường.
  await render(view("script"));
  const active = [...host.querySelectorAll("button[data-active]")];
  expect(active.map(text)).toEqual(["Kịch bản"]);
  expect(active[0].getAttribute("aria-selected")).toBe("true");
});

it("tạo sách nói từ danh sách Studio: ≤ 3 lần bấm tới khi chạy (L10)", async () => {
  state.books = [book({ id: "a", title: "Sách cũ", ...stopped, phase: "done", chapters: { total: 10, completed: 10, failed: 0, working: 0 } })];
  await render(
    <Routes>
      <Route path="/studio" element={<ProjectsScreen />} />
      <Route path="/studio/new" element={<NewProjectScreen />} />
    </Routes>,
    "/studio",
  );
  let taps = 0;
  const tap = async (label: string) => {
    const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find((item) => text(item) === label);
    expect(button, label).toBeDefined();
    taps++;
    await act(async () => { button!.click(); await Promise.resolve(); });
  };
  await tap("Dự án mới");
  await tap("Chọn thư mục");
  await act(() => new Promise<void>((done) => setTimeout(done, 0)));
  // Tuỳ chọn gập sẵn, có một dòng tóm tắt - không bắt chỉnh.
  const options = [...host.querySelectorAll<HTMLButtonElement>("button[aria-expanded]")].find((button) => text(button).startsWith("Tuỳ chọn"))!;
  expect(options.getAttribute("aria-expanded")).toBe("false");
  expect(document.getElementById(options.getAttribute("aria-controls")!)?.getAttribute("data-state")).toBe("closed");
  await tap("Bắt đầu");
  expect(taps).toBeLessThanOrEqual(3);
  expect(state.create).toHaveBeenCalledOnce();
  expect(state.create.mock.calls[0][0]).toMatchObject({ title: "Đồng hồ cát", start: true, paths: ["D:/Truyện/Đồng hồ cát/1.txt"] });
});
