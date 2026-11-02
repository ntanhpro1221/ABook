// @vitest-environment happy-dom
// Trang sách chia hai cột theo bề rộng NỘI DUNG (không phải cửa sổ), cùng ngưỡng 840 với Qt (BookPage.qml: Theme.widthExpanded):
// từ 840 bìa + thông tin một bên, danh sách chương một bên (mỗi bên cuộn riêng); hẹp hơn thì một cột như cũ. happy-dom không có bố cục thật nên
// bài này kiểm LUẬT (cột nào, cuộn riêng, thứ tự, giữ nguyên bìa khi đổi bố cục); toạ độ thật đo ở trình duyệt (result.md của m1web).
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { Clock, ClockContext } from "./clock";
import type { ListenBook, ListenChapter } from "./model";

const state = vi.hoisted(() => ({ player: {} as Record<string, unknown>, book: undefined as unknown, width: 1630, entry: "/book/a" }));
vi.mock("./player", async (original) => ({
  ...(await original<typeof import("./player")>()),
  usePlayer: () => state.player,
  useNowPlaying: () => ({ expanded: false, setExpanded: vi.fn() }),
}));
vi.mock("./source", async (original) => ({
  ...(await original<typeof import("./source")>()),
  useSource: () => ({ kind: "desktop" }),
  useListenBook: () => ({ data: state.book, isLoading: false }),
  useListenLibrary: () => ({ data: [], isLoading: false }),
  useWarmVoice: () => undefined,
  useListenMutations: () => ({}),
  useCast: () => ({ data: undefined, isLoading: false }),
}));

import { BookScreen, bookLeftWidth, BOOK_SPLIT_WIDTH } from "./BookScreen";

type Watcher = { callback: (entries: unknown[]) => void; targets: Set<Element> };
const watchers: Watcher[] = [];
class FakeResizeObserver {
  watcher: Watcher;
  constructor(callback: (entries: unknown[]) => void) { this.watcher = { callback, targets: new Set() }; watchers.push(this.watcher); }
  observe(target: Element) { this.watcher.targets.add(target); }
  unobserve(target: Element) { this.watcher.targets.delete(target); }
  disconnect() { this.watcher.targets.clear(); }
}

let root: Root, host: HTMLDivElement, client: QueryClient, clock: Clock;
const chapter = (id: number) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 600, available: true }) as ListenChapter;
const listenBook = () => ({ id: "a", title: "Sách A", author: "Tác giả", narrator: "Ngọc Lan", duration: 3000, chaptersTotal: 5, chaptersAvailable: 5, complete: true, producing: false, updatedAt: null,
  state: { chapters: {} }, progress: { heardSeconds: 0, totalSeconds: 3000, fraction: 0, chaptersDone: 0, finished: false },
  chapters: [1, 2, 3, 4, 5].map(chapter) }) as unknown as ListenBook;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear();
  watchers.length = 0;
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get(this: HTMLElement) { return this.hasAttribute("data-book-frame") ? state.width : 0; } });
  state.width = 1630;
  state.entry = "/book/a";
  state.book = listenBook();
  state.player = {
    track: null, queue: [], playing: false, buffering: false, rate: 1, volume: 0.9, atEnd: null, purpose: "listen", sleep: { kind: "off" }, fading: false, error: "",
    toggle: vi.fn(), jumpTo: vi.fn(), resume: vi.fn(), pause: vi.fn(), play: vi.fn(), seek: vi.fn(), positionStamp: () => 0,
  };
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clock = new Clock();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
});
afterEach(async () => {
  await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  delete (HTMLElement.prototype as { clientWidth?: number }).clientWidth;
});

const render = async (node: ReactNode) => {
  await act(() => root.render(<QueryClientProvider client={client}><ClockContext.Provider value={clock}><MemoryRouter initialEntries={[state.entry]}><TooltipProvider>{node}</TooltipProvider></MemoryRouter></ClockContext.Provider></QueryClientProvider>));
};
const open = (width: number) => { state.width = width; return render(<Routes><Route path="/book/:id" element={<BookScreen />} /></Routes>); };
/** Đổi bề rộng khung nội dung như ResizeObserver báo. */
const resize = async (width: number) => {
  state.width = width;
  const frame = host.querySelector("[data-book-frame]")!;
  await act(() => { for (const watcher of watchers) if (watcher.targets.has(frame)) watcher.callback([{ target: frame, contentRect: { width } }]); });
};
const layout = () => host.querySelector<HTMLElement>("[data-book-layout]")!;
const info = () => layout().querySelector<HTMLElement>(":scope > div > header")!;
const tabs = () => layout().querySelector<HTMLElement>('[data-orientation]:not([role])')!; // gốc của Tabs (hàng tab và các bảng nằm trong nó)
const list = () => layout().querySelector<HTMLElement>("[data-book-list]")!; // phần cuộn của cột phải (hàng tab nằm ngoài nó)
const scrolls = (element: Element) => element.className.split(/\s+/).includes("overflow-y-auto");

it("cột trái của trang sách theo đúng công thức của Qt: 320 ở 840, rộng thêm 6 % phần dư, tối đa 380", () => {
  expect(BOOK_SPLIT_WIDTH).toBe(840);
  expect(bookLeftWidth(840)).toBe(320);
  expect(bookLeftWidth(700)).toBe(320);
  expect(bookLeftWidth(1630)).toBeCloseTo(367.4, 5);
  expect(bookLeftWidth(3000)).toBe(380);
});

it("nội dung 1630: hai cột - bìa + thông tin bên trái, tab Chương bên phải, mỗi bên cuộn riêng", async () => {
  await open(1630);
  expect(layout().dataset.bookLayout).toBe("split");
  expect(layout().style.getPropertyValue("--book-left")).toBe("367.4px");
  const body = layout().firstElementChild!.nextElementSibling as HTMLElement;
  expect(body.className).toContain("grid-cols-[var(--book-left)_minmax(0,1fr)]");
  // Bìa (trong khối thông tin) đứng TRƯỚC danh sách chương trong cây, thuộc hai ô lưới khác nhau: trái, phải.
  const cover = info().querySelector("img, [data-cover]") ?? info().firstElementChild!;
  expect(body.children[0]).toBe(info());
  expect(body.children[1]).toBe(tabs());
  expect(info().contains(cover)).toBe(true);
  expect(tabs().querySelector('[role="list"]')).not.toBeNull();
  expect(info().querySelector('[role="list"]')).toBeNull();
  expect(scrolls(info())).toBe(true);
  expect(scrolls(list())).toBe(true);
  expect(scrolls(tabs())).toBe(false);
  // Cùng đáy trang: khung bao cao đúng vùng nội dung; hàng tab đứng yên ở đầu cột phải (nằm ngoài phần cuộn).
  expect(host.querySelector("[data-book-frame]")!.className).toContain("h-full");
  expect(list().contains(tabs().querySelector('[role="tablist"]'))).toBe(false);
});

it("ngưỡng 840: 841 là hai cột", async () => {
  await open(841);
  expect(layout().dataset.bookLayout).toBe("split");
  expect(layout().style.getPropertyValue("--book-left")).toBe("320.06px");
});

it("ngưỡng 840: 839 là một cột (chương nằm dưới bìa, trang cuộn nguyên khối)", async () => {
  await open(839);
  expect(layout().dataset.bookLayout).toBe("stacked");
  expect(layout().style.getPropertyValue("--book-left")).toBe("");
  expect(layout().className).toContain("max-w-[1180px]");
  expect(layout().className).not.toContain("h-full");
  // Một cột: khối bao là `contents` (không tạo ô lưới), không khối nào tự cuộn.
  const wrapper = layout().firstElementChild!.nextElementSibling as HTMLElement;
  expect(wrapper.className).toBe("contents");
  expect(scrolls(info())).toBe(false);
  expect(scrolls(list())).toBe(false);
  expect(host.querySelector("[data-book-frame]")!.className).not.toContain("h-full");
  // Thứ tự đọc vẫn là bìa rồi tới chương.
  expect(info().compareDocumentPosition(tabs()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("đổi cỡ cửa sổ qua ngưỡng: đổi bố cục tại chỗ, khối thông tin (bìa) không bị dựng lại", async () => {
  await open(1630);
  const before = info();
  await resize(839);
  expect(layout().dataset.bookLayout).toBe("stacked");
  expect(info()).toBe(before);
  await resize(1200);
  expect(layout().dataset.bookLayout).toBe("split");
  expect(info()).toBe(before);
  expect(layout().style.getPropertyValue("--book-left")).toBe("341.6px");
});

// Giữ chỗ cuộn khi đổi khổ (DESIGN.md 5.5). happy-dom không có bố cục: dựng hình học giả - mỗi hàng chương cao 54, danh sách bắt đầu ở 400 trong
// trang một cột (khung cuộn = host) và ở 0 trong cột phải (khung cuộn = [data-book-list], mép trên màn hình ở 100).
const ROW = 54;
const fakeGeometry = () => {
  const rect = (top: number, height = ROW) => ({ x: 0, y: top, top, left: 0, right: 100, bottom: top + height, width: 100, height, toJSON() {} });
  const frame = () => (layout().dataset.bookLayout === "split" ? { scroller: list(), base: 100 } : { scroller: host, base: 400 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    if (this === host) return rect(0, 800);
    if (this.hasAttribute("data-book-list")) return rect(100, 700);
    if (!layout()) return rect(0, 24);
    const { scroller, base } = frame();
    if (this.dataset.chapter) return rect(base + (Number(this.dataset.chapter) - 1) * ROW - scroller.scrollTop);
    if (this.dataset.state && this.getAttribute("role") === "tabpanel" && this.contains(host.querySelector("[data-chapter]"))) return rect(base - scroller.scrollTop, 40 * ROW);
    return rect(0, 24);
  });
  host.style.overflowY = "auto";
  const style = document.createElement("style");
  style.textContent = ".overflow-y-auto { overflow-y: auto; }";
  document.head.append(style);
};
const manyChapters = (count: number) => { (state.book as ListenBook).chapters = Array.from({ length: count }, (_, index) => chapter(index + 1)); };
const firstRowTop = (scroller: HTMLElement, rows: NodeListOf<HTMLElement>) => {
  const view = scroller === host ? 0 : 100;
  for (const row of rows) if (row.getBoundingClientRect().bottom > view) return { id: row.dataset.chapter, top: row.getBoundingClientRect().top - view };
  return null;
};

it("đổi khổ qua 840 giữ NGUYÊN chỗ đang xem trong danh sách chương (một cột -> hai cột -> một cột), không nhảy về chương đang nghe", async () => {
  manyChapters(40);
  fakeGeometry();
  await open(839);
  expect(layout().dataset.bookLayout).toBe("stacked");
  const rows = () => host.querySelectorAll<HTMLElement>("[data-chapter]");
  const row3 = host.querySelector('[data-chapter="3"]');
  host.scrollTop = 10 * ROW + 20; // trang một cột cuộn tới giữa danh sách
  const seen = firstRowTop(host, rows());
  expect(seen).toEqual({ id: "3", top: -52 });

  await resize(1630);
  expect(layout().dataset.bookLayout).toBe("split");
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  // Cùng hàng ở cùng chỗ trên màn hình; cột phải cuộn bù đúng khoảng chênh gốc (400 -> 100 trong hình học giả).
  expect(firstRowTop(list(), rows())).toEqual(seen);
  expect(list().scrollTop).toBe(160);
  // Danh sách không bị dựng lại (hàng cũ vẫn là nút DOM cũ).
  expect(host.querySelector('[data-chapter="3"]')).toBe(row3);

  list().scrollTop = 20 * ROW + 10;
  const seenSplit = firstRowTop(list(), rows());
  await resize(700);
  expect(layout().dataset.bookLayout).toBe("stacked");
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(firstRowTop(host, rows())).toEqual(seenSplit);
  expect(host.querySelector('[data-chapter="3"]')).toBe(row3);
});

it("đổi khổ qua 840 giữ tab đang chọn và nội dung tab ấy", async () => {
  state.entry = "/book/a?tab=history";
  await open(1630);
  const selected = () => [...host.querySelectorAll('[role="tab"][aria-selected="true"]')].map((tab) => tab.textContent);
  const before = selected();
  expect(before).toHaveLength(1);
  expect(before[0]).not.toContain("Chương");
  await resize(700);
  expect(layout().dataset.bookLayout).toBe("stacked");
  expect(selected()).toEqual(before);
  await resize(1630);
  expect(selected()).toEqual(before);
});
