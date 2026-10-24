// @vitest-environment happy-dom
// a139: lịch sử nghe đang tải không nói "chưa có"; chương thêm / bớt trong danh sách dài mở / khép tại chỗ (Windowed + useListPresence).
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { ChapterGroups, HistoryTab } from "./BookScreen";
import { ChapterList } from "@/studio/ProjectScreen";
import type { ListenBook, ListenChapter } from "./model";
import type { BookSummary, Chapter } from "@/studio/api";

const state = vi.hoisted(() => ({
  player: { track: null as { bookId: string; chapterId: number } | null, playing: false, toggle: vi.fn(), play: vi.fn() },
  clip: { current: "", loading: false, toggle: vi.fn() },
  cast: undefined as unknown,
  books: [] as BookSummary[],
  info: { dialogs: true } as { dialogs: boolean; update?: { version: string }; remote?: boolean },
  sessions: undefined as Promise<unknown[]> | undefined,
}));
vi.mock("./player", async original => ({ ...await original<typeof import("./player")>(), usePlayer: () => state.player, useNowPlaying: () => ({ setExpanded: vi.fn() }) }));
vi.mock("./clip", async original => ({ ...await original<typeof import("./clip")>(), useClip: () => state.clip }));
vi.mock("./source", async original => ({ ...await original<typeof import("./source")>(), useSource: () => ({ kind: "desktop", voiceUrl: () => "/voice.wav", ...(state.sessions ? { sessions: () => state.sessions! } : {}) }), useReadAloudVoices: () => ({ data: [] }), useCast: () => ({ data: state.cast }) }));
vi.mock("@/studio/data", async original => ({ ...await original<typeof import("@/studio/data")>(), useAppInfo: () => ({ data: state.info }), useLibrary: () => ({ data: { books: state.books } }), usePreferences: () => ({ data: {} }), useStart: () => ({ mutate: vi.fn() }), useFirstPersonHint: () => ({}), useVoices: () => ({ data: Array.from({ length: 20 }, (_, i) => ({ name: `Giọng ${i}`, gender: "Nữ", region: "Bắc", style: "Tự nhiên" })) }) }));
vi.mock("@/studio/api", async original => ({ ...await original<typeof import("@/studio/api")>(), api: vi.fn(async () => ({ models: [], default: "v4" })) }));

let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear(); state.player.track = null; state.player.playing = false; state.clip.current = ""; state.clip.loading = false;
  state.books = []; state.info = { dialogs: true }; state.sessions = undefined;
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });
const render = async (node: ReactNode) => { await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter></QueryClientProvider>)); };
const chapter = (id: number) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 60, available: true }) as ListenChapter;
const book = (id = "book", title = "Truyện thử", count = 8) => ({ id, title, narrator: "Giọng thử", duration: 60 * count, chaptersTotal: count, chaptersAvailable: count, complete: true, producing: false, updatedAt: null,
  state: { chapters: {}, bookmarks: [] }, progress: { heardSeconds: 0, totalSeconds: 60 * count, fraction: 0, chaptersDone: 0, finished: false }, chapters: Array.from({ length: count }, (_, i) => chapter(i + 1)) }) as ListenBook;

const wait = (ms: number) => act(() => new Promise<void>((done) => setTimeout(done, ms)));

it("V8 lịch sử: đang tải là khung chờ (không 'Chưa có lịch sử nghe'), tới nơi thì khung chờ mờ ra", async () => {
  const b = book();
  let answer: (sessions: unknown[]) => void = () => {};
  state.sessions = new Promise((done) => { answer = done; });
  await render(<HistoryTab book={b} />);
  expect(host.textContent).not.toContain("Chưa có lịch sử nghe");
  expect(host.querySelector(".motion-loading-placeholder")).not.toBeNull();
  const now = Date.now() / 1000;
  await act(async () => { answer([{ id: "1", startedAt: now - 60, endedAt: now, listened: 60, from: { chapterId: 1, seconds: 0 }, to: { chapterId: 1, seconds: 60 } }]); await Promise.resolve(); });
  await wait(10);
  expect(host.textContent).toContain("1 lượt nghe");
  expect(host.querySelector(".motion-loading-content.motion-reveal")).not.toBeNull();
  expect(host.querySelector('.motion-loading-placeholder[data-state="closed"]')?.hasAttribute("inert")).toBe(true);
});

it("V17 trang sách: chương mới về / bị gỡ mở ra / khép lại tại chỗ trong danh sách ảo hoá", async () => {
  const b = book("book", "Truyện thử", 3);
  const view = (chapters: ListenChapter[]) => <ChapterGroups book={{ ...b, chapters }} onDone={() => {}} />;
  await render(view(b.chapters!));
  await render(view([...b.chapters!, chapter(4)]));
  expect(host.querySelector('[data-chapter="4"]')?.getAttribute("data-state")).toBe("enter");
  expect(host.querySelector('[data-chapter="4"]')?.classList.contains("motion-row")).toBe(true);
  await render(view([chapter(1), chapter(3), chapter(4)]));
  const leaving = host.querySelector<HTMLElement>('[data-chapter="2"]')!;
  expect(leaving.getAttribute("data-state")).toBe("exit");
  expect(leaving.hasAttribute("inert")).toBe(true);
  expect(host.querySelector('[data-chapter="3"]')?.getAttribute("aria-posinset")).toBe("2");
});

it("V17 Studio: dòng chương thêm / bớt mở ra / khép lại tại chỗ", async () => {
  const b = { id: "p", title: "Sách", running: false } as BookSummary;
  const row = (id: number) => ({ id, index: id, displayTitle: `Chương ${id}`, status: "pending", statusLabel: "Chờ", segments: { total: 10, finished: 0, analyzed: 0, recorded: 0, failed: 0, warnings: 0 }, playable: false, seconds: 0 }) as Chapter;
  await render(<ChapterList book={b} chapters={[row(1), row(2)]} />);
  await render(<ChapterList book={b} chapters={[row(1), row(2), row(3)]} />);
  const added = [...host.querySelectorAll<HTMLElement>(".motion-row")].find((element) => element.textContent?.includes("Chương 3"))!;
  expect(added.getAttribute("data-state")).toBe("enter");
  expect(added.querySelector('[role="row"]')?.getAttribute("aria-rowindex")).toBe("4");
  await render(<ChapterList book={b} chapters={[row(1), row(3)]} />);
  const leaving = [...host.querySelectorAll<HTMLElement>(".motion-row")].find((element) => element.textContent?.includes("Chương 2"))!;
  expect(leaving.getAttribute("data-state")).toBe("exit");
  expect(leaving.hasAttribute("inert")).toBe(true);
});
