// @vitest-environment happy-dom
// Đọc theo ở khổ điện thoại là CHẾ ĐỘ của màn Đang nghe (Android NowPlayingWindow.reading, Qt NowPlaying.page), không phải màn riêng:
// bấm "Đọc theo" thì thanh điều khiển vẫn ở trong cùng cửa sổ, đường dẫn không đổi, Back về "Nghe" rồi mới thu nhỏ màn.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { topBackLayer } from "@/shared/backStack";
import { Clock, ClockContext } from "./clock";
import type { ListenBook, ListenChapter, Script } from "./model";

const state = vi.hoisted(() => ({
  player: {} as Record<string, unknown>,
  expanded: true,
  collapsed: 0,
  book: undefined as unknown,
  script: undefined as unknown,
}));
vi.mock("./player", async (original) => ({
  ...(await original<typeof import("./player")>()),
  usePlayer: () => state.player,
  useNowPlaying: () => ({ expanded: state.expanded, setExpanded: (value: boolean) => { if (!value) state.collapsed += 1; } }),
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

let root: Root, host: HTMLDivElement, client: QueryClient, clock: Clock;
const chapter = (id: number) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 600, available: true }) as ListenChapter;
const script = { timed: true, segments: Array.from({ length: 12 }, (_, i) => ({ text: `Câu số ${i + 1}.`, start: i * 3, speaker: "", kind: "narration" })) } as unknown as Script;
const player = () => {
  state.player = {
    track: { bookId: "a", chapterId: 1, chapterTitle: "Chương 1", bookTitle: "Sách A", recordId: undefined },
    queue: [chapter(1), chapter(2)], playing: false, buffering: false, rate: 1, volume: 0.9, atEnd: null, purpose: "listen",
    sleep: { kind: "off" }, fading: false, options: { extendMinutes: 10, fadeSeconds: 10 }, error: "", errorRepeat: 0, notice: "", canGoBack: false, wantsPlay: false,
    musicBroken: false, musicOffline: false, musicLoading: false, toggle: vi.fn(), close: vi.fn(), skip: vi.fn(), next: vi.fn(), previous: vi.fn(),
    setRate: vi.fn(), setVolume: vi.fn(), jumpTo: vi.fn(), goBack: vi.fn(), resume: vi.fn(), retry: vi.fn(), dismissError: vi.fn(), setSleep: vi.fn(), extendSleep: vi.fn(),
    positionStamp: () => 0, switchRecord: vi.fn(), setContinues: vi.fn(), pause: vi.fn(), play: vi.fn(), seek: vi.fn(),
    sleepStoppedAt: null, lastSleepMinutes: 20,
  };
};

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear();
  state.expanded = true; state.collapsed = 0; state.script = script;
  state.book = { id: "a", title: "Sách A", chapters: [chapter(1), chapter(2)], state: { chapters: {} }, progress: { heardSeconds: 0, totalSeconds: 1200, fraction: 0, chaptersDone: 0, finished: false } } as unknown as ListenBook;
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

const Where = () => <output data-where>{useLocation().pathname}</output>;
const render = async (node: ReactNode) => {
  await act(() => root.render(<QueryClientProvider client={client}><ClockContext.Provider value={clock}><MemoryRouter initialEntries={["/book/a"]}><TooltipProvider>{node}<Where /></TooltipProvider></MemoryRouter></ClockContext.Provider></QueryClientProvider>));
};
const press = async (element: Element) => {
  await act(() => { element.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); (element as HTMLElement).click(); });
};
const screen = () => host.querySelector<HTMLElement>("section[role=main]")!;
const mode = (value: "listen" | "read") => screen().querySelector<HTMLButtonElement>(`[data-player-mode] [data-mode="${value}"]`)!;
const where = () => host.querySelector("[data-where]")!.textContent;
const sentences = () => screen().querySelectorAll("[data-read-along] [data-sentence]").length;

it("điện thoại: bấm Đọc theo thì chữ hiện TRONG Đang nghe, thanh điều khiển còn nguyên, đường dẫn không đổi", async () => {
  await render(<NowPlaying mobile />);
  expect(mode("listen").getAttribute("aria-selected")).toBe("true");
  expect(sentences()).toBe(0);
  const transport = screen().querySelector("[data-player-transport]")!;
  const secondary = screen().querySelector("[data-player-secondary]")!;
  await press(mode("read"));
  expect(mode("read").getAttribute("aria-selected")).toBe("true");
  expect(sentences()).toBeGreaterThan(0);
  // Vẫn cùng một cửa sổ: các nút điều khiển là CHÍNH những phần tử cũ (không dựng lại ở màn khác), URL đứng nguyên, màn không thu nhỏ.
  expect(screen().querySelector("[data-player-transport]")).toBe(transport);
  expect(screen().querySelector("[data-player-secondary]")).toBe(secondary);
  expect(transport.querySelectorAll("button")).toHaveLength(5);
  expect(where()).toBe("/book/a");
  expect(state.collapsed).toBe(0);
  // Không còn nút "Đọc theo" ở đáy cột - công tắc chế độ là nơi duy nhất.
  expect([...screen().querySelectorAll("button")].filter((button) => button.textContent === "Đọc theo")).toHaveLength(1);
});

it("Back từ Đọc theo về Nghe (cùng cửa sổ), Back lần nữa mới thu nhỏ màn", async () => {
  await render(<NowPlaying mobile />);
  await press(mode("read"));
  expect(sentences()).toBeGreaterThan(0);
  await act(() => { topBackLayer()!.close(); });
  expect(mode("listen").getAttribute("aria-selected")).toBe("true");
  expect(sentences()).toBe(0);
  expect(state.collapsed).toBe(0);
  expect(where()).toBe("/book/a");
  await act(() => { topBackLayer()!.close(); });
  expect(state.collapsed).toBe(1);
});

it("bìa thu nhỏ ('Về chế độ nghe') cũng đưa về Nghe", async () => {
  await render(<NowPlaying mobile />);
  await press(mode("read"));
  await press(screen().querySelector('button[aria-label="Về chế độ nghe"]')!);
  expect(mode("listen").getAttribute("aria-selected")).toBe("true");
  expect(sentences()).toBe(0);
});

it("máy tính: không có công tắc chế độ - Đọc theo vẫn là tab của bảng bên phải", async () => {
  await render(<NowPlaying />);
  expect(screen().querySelector("[data-player-mode]")).toBeNull();
  expect(screen().querySelector('[role="tab"][id="now-tab-text"]')).not.toBeNull();
});

it("chương chưa có chữ: nói thẳng, không để trống", async () => {
  state.script = undefined;
  await render(<NowPlaying mobile />);
  await press(mode("read"));
  expect(screen().textContent).toContain("Chương chưa có chữ. Bạn thử lại sau.");
});
