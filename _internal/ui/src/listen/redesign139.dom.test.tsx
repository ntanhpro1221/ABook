// @vitest-environment happy-dom
// a139 thiết kế lại ba màn (docs/DESIGN.md mục 7): trang sách một nút chính, trình phát 5 + 4 nút (còn lại trong "…"), màn đọc có thanh đầu
// không đè chữ và thanh dưới mờ đi khi cuộn đọc.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { Clock, ClockContext } from "./clock";
import type { ListenBook, ListenChapter, Script } from "./model";

const state = vi.hoisted(() => ({
  player: {} as Record<string, unknown>,
  expanded: false,
  book: undefined as unknown,
  script: undefined as unknown,
}));
vi.mock("./player", async (original) => ({
  ...(await original<typeof import("./player")>()),
  usePlayer: () => state.player,
  useNowPlaying: () => ({ expanded: state.expanded, setExpanded: vi.fn() }),
}));
vi.mock("./source", async (original) => ({
  ...(await original<typeof import("./source")>()),
  useSource: () => ({ kind: "desktop" }),
  useReadAloudVoices: () => ({ data: [] }),
  useChosenVoice: () => undefined,
  useListenBook: () => ({ data: state.book, isLoading: false }),
  useListenLibrary: () => ({ data: [], isLoading: false }),
  useBookVoice: () => "",
  useWarmVoice: () => undefined,
  useLastNight: () => ({ data: undefined }),
  useListenMutations: () => ({}),
  useCast: () => ({ data: undefined, isLoading: false }),
  useChapterScript: () => ({ data: state.script, isLoading: false }),
}));

vi.mock("./SentenceMenu", async (original) => ({
  ...(await original<typeof import("./SentenceMenu")>()),
  useSentenceMenu: () => ({ bar: null, dialogs: null, select: vi.fn(), selected: null, editable: false, wordMenu: undefined, waitingMark: undefined }),
}));

import { NowPlaying } from "./PlayerViews";
import { BookScreen } from "./BookScreen";
import { ReaderScreen } from "./ReaderScreen";

let root: Root, host: HTMLDivElement, client: QueryClient, clock: Clock;
const chapter = (id: number, extra: Partial<ListenChapter> = {}) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 600, available: true, ...extra }) as ListenChapter;
const listenBook = (extra: Partial<ListenBook> = {}) => ({ id: "a", title: "Sách A", author: "Tác giả", narrator: "Ngọc Lan", duration: 3000, chaptersTotal: 5, chaptersAvailable: 5, complete: true, producing: false, updatedAt: null,
  state: { chapters: {} }, progress: { heardSeconds: 0, totalSeconds: 3000, fraction: 0, chaptersDone: 0, finished: false },
  chapters: [1, 2, 3, 4, 5].map((id) => chapter(id)), ...extra }) as ListenBook;
const player = (patch: Record<string, unknown> = {}) => {
  state.player = {
    track: { bookId: "a", chapterId: 1, chapterTitle: "Chương 1", bookTitle: "Sách A", recordId: undefined },
    queue: [chapter(1), chapter(2)], playing: false, buffering: false, rate: 1.15, volume: 0.9, atEnd: null, purpose: "listen",
    sleep: { kind: "off" }, fading: false, options: { extendMinutes: 10, fadeSeconds: 10 }, error: "", errorRepeat: 0, notice: "", canGoBack: true, wantsPlay: false,
    musicBroken: false, musicOffline: false, musicLoading: false, toggle: vi.fn(), close: vi.fn(), skip: vi.fn(), next: vi.fn(), previous: vi.fn(),
    setRate: vi.fn(), setVolume: vi.fn(), jumpTo: vi.fn(), goBack: vi.fn(), resume: vi.fn(), retry: vi.fn(), dismissError: vi.fn(), setSleep: vi.fn(), extendSleep: vi.fn(),
    positionStamp: () => 0, switchRecord: vi.fn(), setContinues: vi.fn(), pause: vi.fn(), play: vi.fn(), seek: vi.fn(),
    sleepStoppedAt: null, lastSleepMinutes: 20,
    ...patch,
  };
};

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear();
  state.book = undefined; state.script = undefined; state.expanded = false;
  player();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clock = new Clock();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const render = async (node: ReactNode, at = "/") => {
  await act(() => root.render(<QueryClientProvider client={client}><ClockContext.Provider value={clock}><MemoryRouter initialEntries={[at]}><TooltipProvider>{node}</TooltipProvider></MemoryRouter></ClockContext.Provider></QueryClientProvider>));
};
const press = async (element: HTMLElement) => {
  await act(() => { element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); element.click(); });
};
const named = (label: string, within: ParentNode = document) => within.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
const primaries = () => [...host.querySelectorAll<HTMLButtonElement>("button")].filter((button) => button.className.includes("bg-accent") && !button.closest("[data-book-secondary]"));
const book = (at = "/book/a") => render(<Routes><Route path="/book/:id" element={<BookScreen />} /></Routes>, at);

it("trang sách: đúng một nút chính - 'Nghe' khi chưa nghe, 'Nghe tiếp · Chương N' khi đang nghe dở", async () => {
  player({ track: null });
  state.book = listenBook();
  await book();
  expect(primaries()).toHaveLength(1);
  expect(primaries()[0].textContent).toBe("Nghe");
  state.book = listenBook({ state: { chapters: { "3": { heard: 120, done: false } }, last: { chapterId: 3, seconds: 120, at: 1 } }, progress: { heardSeconds: 1320, totalSeconds: 3000, fraction: 0.44, chaptersDone: 2, finished: false } } as Partial<ListenBook>);
  await book();
  expect(primaries()).toHaveLength(1);
  expect(primaries()[0].textContent).toBe("Nghe tiếp · Chương 3");
  // Hàng phụ cùng một kiểu: Đọc · Tìm · Từ đầu · ⋯ (không nhãn) - không nút nào khác là nút chính.
  const secondary = host.querySelector("[data-book-secondary]")!;
  expect([...secondary.querySelectorAll("button")].map((button) => button.textContent)).toEqual(["Đọc", "Tìm", "Từ đầu", ""]);
});

it("trình phát: đúng 5 nút chính + 4 nút phụ có nhãn; việc khác nằm trong '…'", async () => {
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const screen = host.querySelector<HTMLElement>("section[role=main]")!;
  const transport = screen.querySelector("[data-player-transport]")!;
  expect(transport.querySelectorAll("button")).toHaveLength(5);
  expect(transport.querySelector<HTMLButtonElement>("[data-player-toggle]")!.className).toContain("size-[72px]");
  const secondary = screen.querySelector("[data-player-secondary]")!;
  const labels = [...secondary.querySelectorAll("button")].map((button) => button.textContent);
  expect(labels).toEqual(["1,15×Tốc độ", "Hẹn giờ", "Chương"]);
  // Màn chính không còn âm lượng, quay lại chỗ vừa nghe, nhạc / giọng: chỉ thấy trong "…".
  expect(named("Quay lại chỗ vừa nghe", screen)).toBeNull();
  expect(screen.textContent).not.toContain("Âm lượng");
  await press(named("Thêm tuỳ chọn", screen)!);
  const more = document.querySelector<HTMLElement>("[data-player-more]")!;
  expect(more.textContent).toContain("Âm lượng");
  expect(more.textContent).toContain("Về chỗ vừa nghe");
  // Đáy: một nút "Đọc theo" rộng cả hàng.
  expect([...screen.querySelectorAll("button")].filter((button) => button.textContent === "Đọc theo")).toHaveLength(1);
});

it("trình phát máy tính: 'Chương' và 'Đọc theo' chỉ là tab của bảng bên phải, cột trái không lặp lại (audit140 D11)", async () => {
  state.expanded = true;
  await render(<NowPlaying />);
  const screen = host.querySelector<HTMLElement>("section[role=main]")!;
  const secondary = screen.querySelector("[data-player-secondary]")!;
  expect([...secondary.querySelectorAll("button")].map((button) => button.textContent)).toEqual(["1,15×Tốc độ", "Hẹn giờ"]);
  for (const label of ["Chương", "Đọc theo"]) {
    const twins = [...screen.querySelectorAll("button")].filter((button) => button.textContent === label);
    expect(twins.map((button) => button.getAttribute("role"))).toEqual(["tab"]);
  }
});

it("trình phát điện thoại: lớp phủ inset-0 tự chừa biên an toàn - nút đầu không nằm dưới thanh trạng thái (soát máy ảo C1)", async () => {
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const screen = host.querySelector<HTMLElement>("section[role=main]")!;
  for (const edge of ["pt-[env(safe-area-inset-top)]", "pl-[env(safe-area-inset-left)]", "pr-[env(safe-area-inset-right)]", "pb-[env(safe-area-inset-bottom)]"]) {
    expect(screen.classList).toContain(edge);
  }
});

const script = { timed: true, segments: Array.from({ length: 30 }, (_, i) => ({ text: `Câu số ${i + 1}.`, start: i * 3, speaker: "", kind: "narration" })) } as unknown as Script;
const reader = () => render(<Routes><Route path="/book/:id/read/:chapterId?" element={<ReaderScreen />} /></Routes>, "/book/a/read/1");

it("màn đọc: cỡ chữ và giãn dòng giữ lựa chọn, gạch chân và áp ngay vào bài", async () => {
  player({ track: null }); state.book = listenBook(); state.script = script;
  await reader(); await press(named("Cỡ chữ và giãn dòng")!);
  const sizes = document.querySelector('[role="group"][aria-label="Cỡ chữ"]')!;
  expect([...sizes.querySelectorAll("button")].map(button => button.textContent)).toEqual(["16", "18", "20", "22", "24"]);
  expect(sizes.querySelector('[data-sliding-indicator="line"]')).not.toBeNull();
  await press(named("Cỡ chữ 24")!);
  expect(host.querySelector("article")!.style.fontSize).toBe("24px");
  expect(named("Cỡ chữ 24")!.getAttribute("aria-pressed")).toBe("true");
  await press([...document.querySelectorAll<HTMLButtonElement>('button[aria-pressed]')].find(button => button.textContent === "1,9")!);
  expect(host.querySelector("article")!.style.lineHeight).toBe("1.9");
});

it("màn đọc: thanh đầu chỉ có nút về + tên chương, nền đặc, đứng ngoài khung cuộn chữ", async () => {
  player({ track: null });
  state.book = listenBook(); state.script = script;
  await reader();
  const header = host.querySelector<HTMLElement>("[data-reader-header]")!;
  const scroller = host.querySelector<HTMLElement>("[data-reader-scroll]")!;
  expect(header.querySelectorAll("button")).toHaveLength(1);
  expect(header.textContent).toBe("Chương 1");
  // Không đè lên chữ: thanh đầu không nằm trong khung cuộn, chữ không nằm dưới nó; nền đặc (không trong suốt, không làm mờ phía sau).
  expect(scroller.contains(header)).toBe(false);
  expect(header.contains(scroller)).toBe(false);
  expect(header.compareDocumentPosition(scroller) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(scroller.querySelector("article [data-sentence]")).not.toBeNull();
  expect(header.className).toMatch(/(^|\s)bg-bg(\s|$)/);
  expect(header.className).not.toMatch(/bg-bg\/|backdrop-blur/);
});

it("màn đọc: thanh dưới mờ đi khi người đọc tự cuộn, chạm vào trang thì hiện lại", async () => {
  player({ track: null });
  state.book = listenBook(); state.script = script;
  await reader();
  const scroller = host.querySelector<HTMLElement>("[data-reader-scroll]")!;
  const panel = () => host.querySelector<HTMLElement>("[data-reader-controls]")?.closest<HTMLElement>(".motion-panel");
  expect(panel()?.getAttribute("data-state")).toBe("open");
  expect(host.querySelector("[data-reader-controls]")!.textContent).toContain("Nghe từ đây");
  await act(() => { scroller.dispatchEvent(new WheelEvent("wheel", { bubbles: true, deltaY: 120 })); });
  // Mờ ra (không biến mất cứng): lớp còn đó với data-state="closed", đã ra khỏi Tab / chạm.
  expect(panel()?.getAttribute("data-state")).toBe("closed");
  expect(panel()?.hasAttribute("inert")).toBe(true);
  await act(() => { scroller.querySelector<HTMLElement>("article")!.click(); });
  expect(panel()?.getAttribute("data-state")).toBe("open");
  expect(panel()?.hasAttribute("inert")).toBe(false);
});
