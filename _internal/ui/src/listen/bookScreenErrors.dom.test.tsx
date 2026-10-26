// @vitest-environment happy-dom
// Lỗi đúng / sai của trang sách (soát 26-10): lỗi mạng chớp, đổi cuốn khi hộp thoại còn mở.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { Clock, ClockContext } from "./clock";
import type { ListenBook, ListenChapter } from "./model";

const state = vi.hoisted(() => ({
  player: {} as Record<string, unknown>,
  expanded: false,
  book: undefined as unknown,
  error: null as unknown,
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
  useListenBook: () => ({ data: state.book, isLoading: false, error: state.error }),
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

import { BookScreen } from "./BookScreen";

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
  state.book = undefined; state.error = null; state.script = undefined; state.expanded = false;
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
const book = (at = "/book/a") => render(<Routes><Route path="/book/:id" element={<BookScreen />} /></Routes>, at);

it("hỏi lại sách hụt một lần (máy chủ khởi động lại, mạng chớp): trang vẫn giữ sách đã có, không nói 'Không tìm thấy sách này'", async () => {
  player({ track: null });
  state.book = listenBook();
  state.error = Object.assign(new Error("Failed to fetch"), { status: 0 });
  await book();
  expect(host.textContent).not.toContain("Không tìm thấy sách này");
  expect(host.querySelector("h1")?.textContent).toBe("Sách A");
});

it("sách thật sự không còn (404): nói không tìm thấy, kể cả khi còn bản cũ trong bộ nhớ", async () => {
  player({ track: null });
  state.book = listenBook();
  state.error = Object.assign(new Error("Not found"), { status: 404 });
  await book();
  expect(host.textContent).toContain("Không tìm thấy sách này");
});
