// @vitest-environment happy-dom
// a139: mọi chỗ hiện / ẩn / đổi chữ của trình phát, đọc theo và thư viện đều có chuyển động (fade / trượt), không đổi cứng.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { TooltipProvider } from "@/shared/ui";
import { Clock, ClockContext } from "./clock";
import type { ListenBook, ListenChapter, Script } from "./model";

const state = vi.hoisted(() => ({
  player: {} as Record<string, unknown>,
  expanded: false,
  voices: [] as unknown[],
  books: [] as unknown[],
  book: undefined as unknown,
  script: undefined as unknown,
  bar: null as unknown,
}));
vi.mock("./player", async (original) => ({
  ...(await original<typeof import("./player")>()),
  usePlayer: () => state.player,
  useNowPlaying: () => ({ expanded: state.expanded, setExpanded: vi.fn() }),
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

import { ChapterPanel, MusicMenu, NowPlaying, PlayerBar, SpeedMenu, VoiceMenu } from "./PlayerViews";
import { ReadAlongText } from "./ReadAlongText";
import { LibraryScreen } from "./LibraryScreen";
import { ReaderScreen } from "./ReaderScreen";

let root: Root, host: HTMLDivElement, client: QueryClient, clock: Clock;
let animate: ReturnType<typeof vi.spyOn>;
const chapter = (id: number, extra: Partial<ListenChapter> = {}) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 600, available: true, ...extra }) as ListenChapter;
const listenBook = (id: string, title: string, extra: Partial<ListenBook> = {}) => ({ id, title, narrator: "", duration: 600, chaptersTotal: 2, chaptersAvailable: 2, complete: true, producing: false, updatedAt: null,
  state: { chapters: {} }, progress: { heardSeconds: 0, totalSeconds: 600, fraction: 0.2, chaptersDone: 0, finished: false }, chapters: [chapter(1), chapter(2)], ...extra }) as ListenBook;
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
const setTrack = (patch: Record<string, unknown>) => { state.player = { ...state.player, track: { ...(state.player.track as object), ...patch } }; };

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
const snapshots = () => [...document.querySelectorAll<HTMLElement>(".motion-snapshot")];
const snapshotWith = (text: string) => snapshots().find((image) => image.textContent?.includes(text));
/** Phần tử đã được Web Animations chạy (MotionRegion), lọc theo điều kiện. */
const animated = (match: (element: HTMLElement) => boolean) => (animate.mock.contexts as HTMLElement[]).filter(match);
const button = (label: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!;

it("C1 thanh phát: đổi chương mờ chéo tên chương, đổi cuốn mờ chéo cả bìa", async () => {
  for (const compact of [true, false]) {
    player();
    await render(<PlayerBar compact={compact} />);
    setTrack({ chapterId: 2, chapterTitle: "Chương 2" });
    await render(<PlayerBar compact={compact} />);
    expect(snapshotWith("Chương 1")?.hasAttribute("inert")).toBe(true);
    expect(host.textContent).toContain("Chương 2");
    animate.mockClear();
    setTrack({ bookId: "b", bookTitle: "Sách B" });
    await render(<PlayerBar compact={compact} />);
    // Bìa vẽ đổi màu theo tên: cả khung bìa (MotionRegion gốc của BookCover) có ảnh cũ và hiện dần.
    expect(animated((element) => element.getAttribute("data-np") === "cover").length).toBeGreaterThan(0);
    await act(() => root.unmount()); document.body.replaceChildren(); host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  }
});

it("C2 Nhạc nền: nút hiện dần khi dữ liệu nhạc về, đổi loại chương mờ chéo (một vỏ, không thay gốc)", async () => {
  player({ queue: [chapter(1), chapter(2, { state: "text" } as Partial<ListenChapter>)] });
  await render(<MusicMenu />);
  const shell = host.firstElementChild as HTMLElement;
  expect(host.querySelector("button")).toBeNull();
  await act(async () => { client.setQueryData(["listen", "edit-music", "a"], { package: true, hasMusic: true, enabled: true, levelDb: -20, defaultLevelDb: -20, cues: [] }); });
  await render(<MusicMenu />);
  const music = button("Nhạc nền");
  expect(music).not.toBeNull();
  expect(animated((element) => element.contains(music)).length).toBeGreaterThan(0);
  animate.mockClear();
  setTrack({ chapterId: 2, chapterTitle: "Chương 2" });
  await render(<MusicMenu />);
  expect(host.firstElementChild).toBe(shell); // cùng một vỏ qua hai loại chương
  expect(animated((element) => element === shell).length).toBe(1);
  expect(snapshots().length).toBeGreaterThan(0);
});

it("C2 Giọng đọc: có giọng thì nút hiện dần, không đổi gốc MotionRegion <-> MenuShell", async () => {
  player({ queue: [chapter(1, { state: "text" } as Partial<ListenChapter>)] });
  await render(<VoiceMenu />);
  const shell = host.firstElementChild as HTMLElement;
  state.voices = [{ id: "v1", name: "Giọng Một", provider: "vieneu", gender: "female" }];
  await render(<VoiceMenu />);
  expect(host.firstElementChild).toBe(shell);
  const voice = host.querySelector<HTMLButtonElement>("button")!;
  expect(voice.getAttribute("aria-label")).toContain("Giọng đọc");
  expect(animated((element) => element === shell).length).toBe(1);
});

it("C3 nút menu: đổi tốc độ mờ chéo chữ trên nút (số cũng là một lựa chọn)", async () => {
  await render(<SpeedMenu />);
  const speed = button("Tốc độ đọc: 1×");
  player({ rate: 1.5 });
  await render(<SpeedMenu />);
  expect(button("Tốc độ đọc: 1,5×")).toBe(speed);
  expect(snapshotWith("1×")).toBeTruthy();
  expect(animated((element) => speed.contains(element) && element !== speed).length).toBe(1);
});

it("V3 gợi ý cuộn của danh sách giọng: luôn dựng, đổi độ mờ có transition", async () => {
  player({ queue: [chapter(1, { state: "text" } as Partial<ListenChapter>)] });
  state.voices = Array.from({ length: 30 }, (_, i) => ({ id: `v${i}`, name: `Giọng ${i}`, provider: "vieneu", gender: "female" }));
  await render(<VoiceMenu />);
  await act(() => { host.querySelector<HTMLButtonElement>("button")!.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); host.querySelector<HTMLButtonElement>("button")!.click(); });
  const hint = [...document.querySelectorAll<HTMLElement>("[aria-hidden=true]")].find((element) => element.textContent === "Kéo xuống còn giọng khác");
  expect(hint).toBeTruthy();
  expect(hint!.className).toContain("transition-opacity");
  expect(hint!.className).toContain("opacity-0");
});

it("V1 / V2 / W1 màn Đang nghe: phát / dừng không mờ chéo cả màn; tiến độ cả cuốn và lời báo có chuyển cảnh riêng", async () => {
  state.expanded = true;
  player({ queue: [chapter(1, { available: false }), chapter(2, { available: false })] });
  await render(<NowPlaying mobile />);
  const screen = host.querySelector<HTMLElement>("section[role=main]")!;
  expect(screen).not.toBeNull();
  animate.mockClear();
  player({ queue: [chapter(1, { available: false }), chapter(2, { available: false })], playing: true });
  await render(<NowPlaying mobile />);
  expect(button("Tạm dừng (chạm bìa)")).not.toBeNull();
  expect(animated((element) => element === screen)).toHaveLength(0); // W1
  // V1: chương có audio -> dòng "Đã nghe …% cả cuốn" (đầu menu "…") hiện dần trong vùng riêng.
  const more = button("Thêm tuỳ chọn");
  await act(() => { more.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 })); more.click(); });
  animate.mockClear();
  player({ playing: true });
  await render(<NowPlaying mobile />);
  const line = [...document.querySelectorAll<HTMLElement>("[data-player-more] p")].find((element) => /cả cuốn|phần đã có/.test(element.textContent ?? ""))!;
  expect(line).toBeTruthy();
  expect(animated((element) => element === line)).toHaveLength(1);
  expect(animated((element) => element === screen)).toHaveLength(0);
  // V2: lỗi -> lời nhắn khi khối đang hiện: mờ chéo bên trong khối.
  player({ playing: true, error: "Không phát được chương này." });
  await render(<NowPlaying mobile />);
  animate.mockClear();
  player({ playing: true, notice: "Đang đọc bằng giọng của máy." });
  await render(<NowPlaying mobile />);
  expect(snapshotWith("Không phát được chương này.")?.hasAttribute("inert")).toBe(true);
  expect(animated((element) => element.textContent?.includes("Đang đọc bằng giọng của máy.") === true && element !== screen).length).toBeGreaterThan(0);
  expect(animated((element) => element === screen)).toHaveLength(0);
});

it("W1 hẹn giờ hết chương: dòng nhắc trượt vào trong lớp riêng, cả màn không mờ chéo", async () => {
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const screen = host.querySelector<HTMLElement>("section[role=main]")!;
  animate.mockClear();
  player({ sleep: { kind: "chapter" } });
  await render(<NowPlaying mobile />);
  const line = [...host.querySelectorAll("p")].find((element) => element.textContent === "Sẽ dừng khi hết chương này.")!;
  expect(line.closest(".motion-panel")?.getAttribute("data-state")).toBe("open");
  expect(animated((element) => element === screen)).toHaveLength(0);
});

it("W2 Đọc theo: thanh việc của câu hiện dần ngoài vùng của cả bài", async () => {
  state.expanded = true;
  state.script = { chapterId: 1, timed: true, segments: [{ text: "Câu một.", paragraph: 0, kind: "narration", start: 0 }, { text: "Câu hai.", paragraph: 1, kind: "narration", start: 5 }] } as unknown as Script;
  await render(<NowPlaying />);
  const article = host.querySelector<HTMLElement>("[data-sentence]")!.closest<HTMLElement>("[data-motion-region]")!;
  animate.mockClear();
  state.bar = <div className="pointer-events-auto test-bar">Thanh việc</div>;
  await render(<NowPlaying />);
  const bar = host.querySelector<HTMLElement>(".test-bar")!;
  expect(bar.textContent).toBe("Thanh việc");
  expect(bar.closest(".motion-panel")?.getAttribute("data-state")).toBe("open");
  expect(animated((element) => element === article)).toHaveLength(0);
  expect(snapshotWith("Câu một.")).toBeUndefined();
});

it("V4 / V17 bảng Chương: tô sáng có transition, dòng phụ mờ chéo, chương mới vào / ra có hàng mở / khép", async () => {
  player({ queue: [chapter(1), chapter(2, { available: false, state: "text", speech: true } as Partial<ListenChapter>)] });
  await render(<ChapterPanel />);
  const current = host.querySelector<HTMLElement>("[data-current=true]")!;
  expect(current.className).toContain("transition-colors");
  expect(current.className).toContain("duration-motion-fast");
  player({ queue: [chapter(1), chapter(2)] });
  await render(<ChapterPanel />);
  expect(snapshots().length).toBeGreaterThan(0); // "Chương này đọc bằng giọng máy" -> độ dài
  player({ queue: [chapter(1), chapter(2), chapter(3)] });
  await render(<ChapterPanel />);
  expect(host.querySelector('.motion-row[data-state="enter"]')?.textContent).toContain("Chương 3");
  player({ queue: [chapter(1), chapter(3)] });
  await render(<ChapterPanel />);
  const leaving = host.querySelector<HTMLElement>('.motion-row[data-state="exit"]')!;
  expect(leaving.textContent).toContain("Chương 2");
  expect(leaving.hasAttribute("inert")).toBe(true);
});

const segments = (words: number) => [
  { text: "Câu đầu.", paragraph: 0, kind: "narration", start: 0 },
  { text: Array.from({ length: words }, (_, i) => `chữ${i}`).join(" "), paragraph: 1, kind: "narration", start: 1, words: Array.from({ length: words }, (_, i) => [1000 + i * 100, 1000 + i * 100 + 90]) },
  { text: "Câu cuối.", paragraph: 2, kind: "narration", start: 1 + words / 10 },
];
const readAlong = (script: Script, playing: number, selected: number | null = null) => (
  <ReadAlongText script={script} playingIndex={playing} focusIndex={0} selected={selected} onTap={() => {}} dimHeard headingClassName="" />
);

it("C4 câu đang đọc / đã nghe / được chọn: nền, màu, gạch chân có transition (styles.css)", async () => {
  const style = document.createElement("style");
  // Lấy đúng các luật thường (không phải @utility của Tailwind) của styles.css cho câu đọc theo.
  const css = readFileSync(`${cwd()}/src/styles.css`, "utf8");
  style.textContent = [...css.matchAll(/(^\[data-sentence\]|^\.read-along-[\w.-]+)\s*\{[^}]*\}/gm)].map((match) => match[0]).join("\n");
  document.head.append(style);
  const script = { chapterId: 1, timed: true, segments: segments(3) } as unknown as Script;
  await render(readAlong(script, 0));
  const second = host.querySelector<HTMLElement>('[data-index="1"]')!;
  const computed = getComputedStyle(second);
  expect(computed.transitionProperty || computed.transition).toMatch(/background-color/);
  expect(computed.transitionProperty || computed.transition).toMatch(/text-decoration-color/);
  expect(computed.transitionProperty || computed.transition).toMatch(/(^|[ ,])color/);
  // Gạch chân luôn có, trong suốt khi không chọn: chọn chỉ đổi màu gạch chân (chuyển tiếp được), không bật thuộc tính underline.
  expect(second.className).toContain("decoration-transparent");
  expect(second.className).toContain("underline");
  await render(readAlong(script, 0, 1));
  expect(second.className).toContain("decoration-accent");
  expect(second.className).not.toContain("decoration-transparent");
});

it("C5 chữ đang đọc: mọi chữ của câu đang nghe có sẵn span, sang chữ kế chỉ đổi lớp is-lit (cùng nút DOM)", async () => {
  const script = { chapterId: 1, timed: true, segments: segments(4) } as unknown as Script;
  await act(() => clock.set(1.05));
  await render(readAlong(script, 1));
  const words = [...host.querySelectorAll<HTMLElement>('[data-index="1"] .read-along-word')];
  expect(words).toHaveLength(4);
  expect(words.map((word) => word.classList.contains("is-lit"))).toEqual([true, false, false, false]);
  await act(() => clock.set(1.15));
  const after = [...host.querySelectorAll<HTMLElement>('[data-index="1"] .read-along-word')];
  expect(after[0]).toBe(words[0]);
  expect(after.map((word) => word.classList.contains("is-lit"))).toEqual([false, true, false, false]);
});

it("C5 hiệu năng: câu 5.000 chữ - dựng và 50 nhịp sang chữ kế trong ngân sách", async () => {
  const script = { chapterId: 1, timed: true, segments: segments(5000) } as unknown as Script;
  await act(() => clock.set(1.0));
  const start = performance.now();
  await render(readAlong(script, 1));
  const mounted = performance.now() - start;
  expect(host.querySelectorAll('[data-index="1"] .read-along-word')).toHaveLength(5000);
  // Đếm thay đổi DOM chứ không đo giờ: giờ đồng hồ chập chờn theo tải máy (cả bộ test chạy song song thì đỏ, chạy riêng thì xanh).
  // Hồi quy cỡ bậc (dựng lại cả 5.000 span mỗi nhịp) làm số này lên hàng nghìn; một nhịp đúng chỉ đổi lớp vài chữ.
  let touched = 0;
  const watch = new MutationObserver((records) => { touched += records.length; });
  watch.observe(host, { subtree: true, childList: true, attributes: true, characterData: true });
  const ticks = performance.now();
  for (let step = 1; step <= 50; step++) await act(() => clock.set(1.0 + step * 0.1));
  const perTick = (performance.now() - ticks) / 50;
  watch.disconnect();
  expect(host.querySelector('[data-index="1"] .is-lit')?.textContent).toBe("chữ50");
  console.info(`[C5] 5.000 chữ: dựng ${mounted.toFixed(0)} ms, mỗi nhịp sang chữ ${perTick.toFixed(1)} ms, ${(touched / 50).toFixed(1)} thay đổi DOM (happy-dom)`);
  expect(touched / 50).toBeLessThan(50);
}, 30000); // dựng 5.000 chữ trong happy-dom ~1 giây, cả bộ test chạy song song thì lâu hơn hạn mặc định 5 giây

it("C6 / V9 thư viện: thẻ Đang nghe mờ chéo chữ, icon và cụm nút; lỗi / trống / có sách mờ hẳn qua", async () => {
  const book = listenBook("a", "Sách A", { state: { chapters: {}, last: { chapterId: 1, seconds: 30, at: Date.now() / 1000 } } as unknown as ListenBook["state"] });
  state.books = [book];
  player({ track: null });
  await render(<LibraryScreen />);
  const card = [...host.querySelectorAll("section")].find((element) => element.textContent?.includes("Đang nghe"))!;
  expect(card).toBeTruthy();
  player({ track: { bookId: "a", chapterId: 1, chapterTitle: "Chương 1", bookTitle: "Sách A" }, playing: true });
  animate.mockClear();
  await render(<LibraryScreen />);
  expect(card.textContent).toContain("đang phát");
  expect(snapshotWith("nghe lần cuối")).toBeTruthy();
  const pause = card.querySelector<HTMLButtonElement>('button[aria-label="Tạm dừng Sách A"]')!;
  expect(animated((element) => pause.contains(element) && element !== pause).length).toBe(1); // icon Play -> Pause
  animate.mockClear();
  player({ track: { bookId: "a", chapterId: 1, chapterTitle: "Chương 1", bookTitle: "Sách A" }, playing: false });
  await render(<LibraryScreen />);
  expect(card.textContent).toContain("tạm dừng");
  expect(animated((element) => card.contains(element) && element.tagName === "P").length).toBeGreaterThan(0);
  // Nghe hết phần đã có: nút phát -> chip "Chờ chương mới" mờ chéo trong một vỏ.
  state.books = [{ ...book, progress: { ...book.progress, caughtUp: true } }];
  player({ track: null });
  animate.mockClear();
  await render(<LibraryScreen />);
  expect(card.textContent).toContain("Chờ chương mới");
  expect(snapshots().some((image) => image.querySelector('button[aria-label^="Nghe tiếp Sách A"]'))).toBe(true);
  // V9: sách cuối rời thư viện -> lời mời trống mờ hẳn qua, không thay tức thì.
  state.books = [];
  await render(<LibraryScreen />);
  await act(() => new Promise((done) => setTimeout(done, 400))); // hàng cuối khép xong (useListPresence)
  animate.mockClear();
  await render(<LibraryScreen />);
  expect(host.textContent).toContain("Chưa có sách nào");
  expect(snapshotWith("Đang nghe")?.hasAttribute("inert")).toBe(true);
});

it("W2 màn đọc: thanh chọn câu hiện dần ngoài vùng của cả chương", async () => {
  state.book = listenBook("a", "Sách A");
  state.script = { chapterId: 1, timed: true, segments: [{ text: "Câu một.", paragraph: 0, kind: "narration", start: 0 }, { text: "Câu hai.", paragraph: 1, kind: "narration", start: 5 }] } as unknown as Script;
  player({ track: null });
  const reader = () => (
    <QueryClientProvider client={client}><ClockContext.Provider value={clock}><MemoryRouter initialEntries={["/book/a/read/1"]}><TooltipProvider>
      <Routes><Route path="/book/:id/read/:chapterId?" element={<ReaderScreen />} /></Routes>
    </TooltipProvider></MemoryRouter></ClockContext.Provider></QueryClientProvider>
  );
  await act(() => root.render(reader()));
  const page = host.querySelector<HTMLElement>("[data-sentence]")!.closest<HTMLElement>(".motion-loading-content > [data-motion-region]")!;
  expect(page).not.toBeNull();
  animate.mockClear();
  state.bar = <div className="pointer-events-auto test-bar">Thanh chọn câu</div>;
  await act(() => root.render(reader()));
  const bar = host.querySelector<HTMLElement>(".test-bar")!;
  expect(bar.textContent).toBe("Thanh chọn câu");
  expect(bar.closest(".motion-panel")?.getAttribute("data-state")).toBe("open");
  expect(animated((element) => element === page)).toHaveLength(0);
  expect(snapshotWith("Câu một.")).toBeUndefined();
});

it("fix139 1.2 nút phát / dừng lớn: glyph (cả vòng chờ đệm) mờ chéo trong vùng riêng của nút, không nảy (icon-pop) và không mờ cả hàng nút", async () => {
  state.expanded = true;
  await render(<NowPlaying mobile />);
  const toggle = host.querySelector<HTMLButtonElement>("[data-player-toggle]")!;
  const transport = host.querySelector<HTMLElement>("[data-player-transport]")!;
  const glyph = toggle.querySelector<HTMLElement>("[data-motion-region]");
  expect(glyph).not.toBeNull();
  expect(host.querySelector(".icon-pop")).toBeNull();
  for (const patch of [{ playing: true }, { playing: true, buffering: true }, { playing: false }]) {
    animate.mockClear();
    player(patch);
    await render(<NowPlaying mobile />);
    expect(toggle.querySelector("[data-motion-region]")).toBe(glyph);
    expect(animated((element) => element === glyph)).toHaveLength(1);
    expect(animated((element) => element === transport)).toHaveLength(0);
  }
  expect(readFileSync(`${cwd()}/src/styles.css`, "utf8")).not.toContain("icon-pop");
});
