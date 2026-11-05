// @vitest-environment happy-dom
// Mở / đóng màn Đang nghe trên điện thoại (PlayerProvider plainOpen): hoạt ảnh CSS chạy đúng một lần, ruột dựng hoãn, không View Transition.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { TooltipProvider } from "@/shared/ui";
import { Clock, ClockContext } from "./clock";
import type { ListenChapter } from "./model";

const state = vi.hoisted(() => ({
  player: {} as Record<string, unknown>,
  expanded: false,
  plain: true,
  setExpanded: (() => undefined) as (value: boolean) => void,
  voices: [] as unknown[],
  books: [] as unknown[],
  book: undefined as unknown,
  script: undefined as unknown,
  bar: null as unknown,
}));
vi.mock("./player", async (original) => ({
  ...(await original<typeof import("./player")>()),
  usePlayer: () => state.player,
  useNowPlaying: () => ({ expanded: state.expanded, setExpanded: state.setExpanded, plain: state.plain }),
}));
vi.mock("./source", async (original) => ({
  ...(await original<typeof import("./source")>()),
  useSource: () => ({ kind: "desktop" }),
  useReadAloudVoices: () => ({ data: state.voices }),
  useChosenVoice: () => undefined,
  useListenBook: () => ({ data: state.book }),
  useListenLibrary: () => ({ data: state.books, isLoading: false }),
  useBookVoice: () => "",
  useWarmVoice: () => undefined,
  useLastNight: () => ({ data: undefined }),
  useListenMutations: () => ({}),
  useChapterScript: () => ({ data: state.script, isLoading: false }),
}));
vi.mock("./PlaylistChoice", async (original) => ({
  ...(await original<typeof import("./PlaylistChoice")>()),
  usePlaylistChoice: () => ({ options: [], chosen: null, label: "", playing: false, scene: false, error: "", loading: false, choose: vi.fn(), busy: false, levelDb: -20, setLevel: vi.fn(), levelBusy: false, canImport: false, addMusic: vi.fn() }),
}));
vi.mock("./SentenceMenu", async (original) => ({
  ...(await original<typeof import("./SentenceMenu")>()),
  useSentenceMenu: () => ({ bar: state.bar, dialogs: null, select: vi.fn(), selected: null, editable: false, wordMenu: undefined, waitingMark: undefined }),
}));

import { NowPlaying } from "./PlayerViews";
import { pushBackLayer, topBackLayer } from "@/shared/backStack";
import { dismissTopLayer } from "@/shared/backLayers";

let root: Root, host: HTMLDivElement, client: QueryClient, clock: Clock;
let animate: ReturnType<typeof vi.spyOn>;
const chapter = (id: number, extra: Partial<ListenChapter> = {}) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 600, available: true, ...extra }) as ListenChapter;
const player = (patch: Record<string, unknown> = {}) => {
  state.player = {
    track: { bookId: "a", chapterId: 1, chapterTitle: "Chương 1", bookTitle: "Sách A", recordId: undefined },
    queue: [chapter(1), chapter(2)], playing: false, buffering: false, rate: 1, volume: 0.9, atEnd: null, purpose: "listen",
    sleep: { kind: "off" }, fading: false, options: { extendMinutes: 10 }, error: "", errorRepeat: 0, notice: "", canGoBack: false, wantsPlay: false,
    musicBroken: false, musicOffline: false, musicLoading: false, toggle: vi.fn(), close: vi.fn(), skip: vi.fn(), next: vi.fn(), previous: vi.fn(),
    setRate: vi.fn(), setVolume: vi.fn(), jumpTo: vi.fn(), goBack: vi.fn(), resume: vi.fn(), retry: vi.fn(), dismissError: vi.fn(), setSleep: vi.fn(), extendSleep: vi.fn(),
    positionStamp: () => 0, switchRecord: vi.fn(), setContinues: vi.fn(), pause: vi.fn(), play: vi.fn(), seek: vi.fn(),
    ...patch,
  };
};

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear();
  state.voices = []; state.books = []; state.book = undefined; state.script = undefined; state.bar = null; state.expanded = false;
  player();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  animate = vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clock = new Clock();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); // không gọi máy chủ thật
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); document.head.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const render = async (node: ReactNode) => {
  await act(() => root.render(<QueryClientProvider client={client}><ClockContext.Provider value={clock}><MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter></ClockContext.Provider></QueryClientProvider>));
};
const screen = () => host.querySelector<HTMLElement>("section[role=main]");
const css = readFileSync(`${cwd()}/src/styles.css`, "utf8");

it("opening Now Playing focuses Play without scrolling the underlying document", async () => {
  const focus = vi.spyOn(HTMLElement.prototype, "focus");
  state.expanded = true;
  await render(<NowPlaying />);
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 60)); });
  const calls = focus.mock.calls.filter((_call, index) => {
    const target = focus.mock.contexts[index];
    return target instanceof HTMLElement && target.matches("[data-player-toggle]");
  });
  expect(calls).toEqual([[{ preventScroll: true }]]);
});

it("desktop Now Playing closes before an underlying page layer on Escape", async () => {
  const underlying = vi.fn();
  const remove = pushBackLayer(underlying);
  const expanded = vi.fn();
  state.setExpanded = expanded;
  state.expanded = true;
  try {
    await render(<NowPlaying />);
    expect(topBackLayer()?.element()).toBe(screen());
    await act(() => { expect(dismissTopLayer()).toBe(true); });
    expect(expanded).toHaveBeenCalledWith(false);
    expect(underlying).not.toHaveBeenCalled();
  } finally { remove(); }
});

const sheetCases = [
  { button: "Tốc độ", title: "Tốc độ đọc" },
  { button: "Hẹn giờ", title: "Hẹn giờ ngủ" },
  { button: "Chương", title: "Chương" },
];
async function openSheet(button: string) {
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
    matches: query === "(max-width: 640px)", media: query,
    addEventListener() {}, removeEventListener() {},
  }) as unknown as MediaQueryList);
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const scroller = screen()!.querySelector<HTMLElement>(".player-controls-scroll")!;
  expect(scroller).not.toBeNull();
  const trigger = [...scroller.querySelectorAll<HTMLButtonElement>("[data-player-secondary] button")]
    .find((node) => node.textContent?.includes(button))!;
  expect(trigger).toBeDefined();
  return { scroller, trigger };
}

it.each(sheetCases)("$title: tấm qua Portal và fixed, nằm ngoài cây bố cục Đang nghe", async ({ button, title }) => {
  const { trigger } = await openSheet(button);
  await act(() => trigger.click());
  const sheet = document.querySelector<HTMLElement>('[role="dialog"][data-state="open"]')!;
  expect(sheet).not.toBeNull();
  expect(document.getElementById(sheet.getAttribute("aria-labelledby")!)?.textContent).toBe(title);
  expect(host.contains(sheet)).toBe(false); // Radix Portal phải thoát khỏi root React của màn nghe.
  expect(document.body.contains(sheet)).toBe(true);
  expect(sheet.classList.contains("fixed")).toBe(true);
  expect(sheet.classList.contains("sheet-surface")).toBe(true);
});

it.each(sheetCases)("$title: mở rồi đóng tấm giữ nguyên padding/margin và lớp bố cục của vùng cuộn", async ({ button }) => {
  const { scroller, trigger } = await openSheet(button);
  const page = screen()!;
  const ancestors: HTMLElement[] = [];
  for (let node: HTMLElement | null = scroller; node; node = node.parentElement) {
    ancestors.push(node);
    if (node === page) break;
  }
  const spacing = () => ancestors.map((node) => ({
    classes: node.className,
    inline: node.getAttribute("style"),
    spacing: ["paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "marginTop", "marginRight", "marginBottom", "marginLeft"]
      .map((key) => getComputedStyle(node)[key as keyof CSSStyleDeclaration]),
  }));
  const before = spacing();
  await act(() => trigger.click());
  expect(document.querySelector('[role="dialog"][data-state="open"]')).not.toBeNull();
  expect(spacing()).toEqual(before);
  // Luật CSS theo trạng thái tấm cũng không được lén bù khoảng trống cho màn/vùng cuộn.
  // DOM giả không tính layout hay chạy Tailwind, nên so thêm nguồn CSS của các luật điều kiện.
  for (const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (/now-playing|player-controls-scroll/.test(rule[1]) && /:has\(|data-state|data-sheet/.test(rule[1]))
      expect(rule[2]).not.toMatch(/(?:^|;)\s*(?:padding|margin)(?:-[\w-]+)?\s*:/);
  }
  const close = document.querySelector<HTMLButtonElement>('[role="dialog"][data-state="open"] [data-sheet-handle]')!;
  await act(() => close.click());
  expect(document.querySelector('[role="dialog"][data-state="open"]')).toBeNull();
  expect(screen()).toBe(page);
  expect(spacing()).toEqual(before);
});

it("điện thoại: mở màn Đang nghe dựng đủ ruột (sau lượt render hoãn), đóng thì xuống trạng thái closed rồi gỡ", async () => {
  state.expanded = false;
  await render(<NowPlaying mobile />);
  expect(screen()).toBeNull(); // chưa mở thì không dựng gì (việc dựng thử chạy lúc rảnh, không ở đây)
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const open = screen()!;
  expect(open.getAttribute("data-state")).toBe("open");
  expect(open.hasAttribute("data-plain")).toBe(true);
  expect(open.querySelector("aside")).not.toBeNull();
  expect(host.querySelector('button[aria-label="Phát (chạm bìa)"]')).not.toBeNull();
  state.expanded = false;
  await render(<NowPlaying mobile />);
  expect(screen()!.getAttribute("data-state")).toBe("closed");
  expect(screen()!.querySelector("aside")).not.toBeNull(); // ruột ở lại tới khi trượt xuống xong
});

it("hoạt ảnh vào chạy đúng một lần: View Transition của việc khác (đổi bảng, đổi trang) bật / tắt html[data-vt] không đổi gì trên màn", async () => {
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const open = screen()!;
  const before = [open.className, open.getAttribute("data-state"), open.getAttribute("style")].join("|");
  const root = document.documentElement;
  root.dataset.vt = "1"; root.dataset.nav = "forward";
  await render(<NowPlaying mobile />);
  delete root.dataset.vt; delete root.dataset.nav;
  await render(<NowPlaying mobile />);
  expect(screen()).toBe(open); // cùng một phần tử, không dựng lại
  expect([open.className, open.getAttribute("data-state"), open.getAttribute("style")].join("|")).toBe(before);
  expect(open.className).not.toContain("now-playing-vt"); // điện thoại không mang tên chuyển cảnh
});

it("styles.css: hoạt ảnh vào gắn với data-state=open, không còn luật html[data-vt] .now-playing tắt / bật hoạt ảnh vào", () => {
  expect(css).not.toMatch(/html\[data-vt\]\s+\.now-playing\s*\{/);
  expect(css).toMatch(/\.now-playing\[data-plain\]\[data-state="open"\]\s*\{[^}]*animation: motion-enter/);
  const base = css.match(/\n\.now-playing \{([^}]*)\}/)![1];
  expect(base).not.toContain("animation");
  expect(css).toMatch(/\.now-playing\[data-state="warm"\][^}]*animation: none/);
  expect(css).toMatch(/\.now-playing\[data-state="closed"\]\s*\{[^}]*animation: motion-exit/);
});

it("ruột dựng sau vỏ: đổi trạng thái phát (sleep) không làm cả màn mờ chéo; chỉ đổi cuốn mới mờ chéo cả màn", async () => {
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const open = screen()!;
  animate.mockClear();
  player({ sleep: { kind: "chapter" } });
  await render(<NowPlaying mobile />);
  expect((animate.mock.contexts as HTMLElement[]).filter((element) => element === open)).toHaveLength(0);
});
