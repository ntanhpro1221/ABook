// @vitest-environment happy-dom
import { act, type ReactNode, type ComponentProps } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterScrollLayout } from "@/shared/scrollMemory";
import { BookCover } from "@/shared/BookCover";
import { TooltipProvider } from "@/shared/ui";
import { CastList, ChapterGroups, ChapterRow, HistoryTab, SampleButton } from "./BookScreen";
import { SeriesShelves } from "./LibraryScreen";
import { QueueList } from "./AddBook";
import { VoiceCard, VoiceStep, SourceStep, QualityStep } from "@/studio/NewProjectScreen";
import { PreviewButton } from "@/studio/VoicePicker";
import { ChapterList, ProductionPanel } from "@/studio/ProjectScreen";
import { Producing, UpdateNotice } from "@/desktop/Shell";
import type { ListenBook, ListenChapter } from "./model";
import type { BookSummary, Chapter } from "@/studio/api";

const state = vi.hoisted(() => ({
  player: { track: null as { bookId: string; chapterId: number } | null, playing: false, toggle: vi.fn(), play: vi.fn() },
  clip: { current: "", loading: false, toggle: vi.fn() },
  cast: undefined as unknown,
  books: [] as BookSummary[],
  info: { dialogs: true } as { dialogs: boolean; update?: { version: string }; remote?: boolean },
}));
vi.mock("./player", async original => ({ ...await original<typeof import("./player")>(), usePlayer: () => state.player, useNowPlaying: () => ({ setExpanded: vi.fn() }) }));
vi.mock("./clip", async original => ({ ...await original<typeof import("./clip")>(), useClip: () => state.clip }));
vi.mock("./source", async original => ({ ...await original<typeof import("./source")>(), useSource: () => ({ kind: "desktop", voiceUrl: () => "/voice.wav" }), useReadAloudVoices: () => ({ data: [] }), useCast: () => ({ data: state.cast }) }));
vi.mock("@/studio/data", async original => ({ ...await original<typeof import("@/studio/data")>(), useAppInfo: () => ({ data: state.info }), useLibrary: () => ({ data: { books: state.books } }), usePreferences: () => ({ data: {} }), useStart: () => ({ mutate: vi.fn() }), useFirstPersonHint: () => ({}), useVoices: () => ({ data: Array.from({ length: 20 }, (_, i) => ({ name: `Giọng ${i}`, gender: "Nữ", region: "Bắc", style: "Tự nhiên" })) }) }));
vi.mock("@/studio/api", async original => ({ ...await original<typeof import("@/studio/api")>(), api: vi.fn(async () => ({ models: [], default: "v4" })) }));

let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear(); state.player.track = null; state.player.playing = false; state.clip.current = ""; state.clip.loading = false;
  state.books = []; state.info = { dialogs: true };
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });
const render = async (node: ReactNode) => { await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter></QueryClientProvider>)); };
const old = () => document.querySelector<HTMLElement>(".motion-snapshot");
const fold = (text: string) => [...host.querySelectorAll<HTMLButtonElement>("button[aria-controls]")].find(b => b.textContent?.startsWith(text))!;
const body = (button: HTMLButtonElement) => document.getElementById(button.getAttribute("aria-controls")!)!;
const chapter = (id: number) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 60, available: true }) as ListenChapter;
const book = (id = "book", title = "Truyện thử", count = 8) => ({ id, title, narrator: "Giọng thử", duration: 60 * count, chaptersTotal: count, chaptersAvailable: count, complete: true, producing: false, updatedAt: null,
  state: { chapters: {}, bookmarks: [] }, progress: { heardSeconds: 0, totalSeconds: 60 * count, fraction: 0, chaptersDone: 0, finished: false }, chapters: Array.from({ length: count }, (_, i) => chapter(i + 1)) }) as ListenBook;

for (const photo of [false, true]) it(`huy hiệu bìa vào/ra có ảnh cũ inert, ảnh thật=${photo}`, async () => {
  const cover = (playing: boolean) => <BookCover title="Sách" playing={playing} image={photo ? { url: "/cover.jpg", width: 100, height: 100 } : undefined} />;
  await render(cover(false)); await render(cover(true)); expect(host.querySelector(".vu")).not.toBeNull();
  await render(cover(false)); expect(old()?.querySelector(".vu")).not.toBeNull(); expect(old()?.hasAttribute("inert")).toBe(true);
});

it("hàng chương thật: Play → VU → đã nghe; nút và focus giữ nguyên, tick ổn định không clone", async () => {
  const b = book(), c = b.chapters![0];
  const row = () => <ChapterRow book={b} chapter={c} onDone={() => {}} />;
  await render(row()); const button = host.querySelector("button")!; button.focus();
  state.player.track = { bookId: b.id, chapterId: c.id }; state.player.playing = true;
  await render(row()); expect(old()?.querySelector("svg")).not.toBeNull(); expect(host.querySelector(".vu")).not.toBeNull();
  const animate = vi.mocked(HTMLElement.prototype.animate); animate.mockClear(); await render(row()); expect(animate).not.toHaveBeenCalled();
  state.player.playing = false; b.state.chapters["1"] = { heard: 60, done: true };
  await render(row()); expect(host.querySelector('[aria-label="Đã nghe"]')).not.toBeNull();
  expect(host.querySelector("button")).toBe(button); expect(document.activeElement).toBe(button);
});

for (const studio of [false, true]) it(`nghe thử giữ icon cũ qua loading/VU, Studio=${studio}`, async () => {
  const view = () => studio ? <PreviewButton voice={{ name: "Giọng", key: "v", preview: true } as ComponentProps<typeof PreviewButton>["voice"]} /> : <SampleButton id="voice-Giọng" url="/v.wav" label="Nghe thử" />;
  await render(view()); state.clip.current = "voice-Giọng"; state.clip.loading = true;
  await render(view()); expect(old()?.querySelector("svg")).not.toBeNull(); expect(host.querySelector(".animate-spin")).not.toBeNull();
  state.clip.loading = false; await render(view()); expect(host.querySelector(".vu")).not.toBeNull();
});

it("hàng nhập sách: chờ → xong → lỗi fade cả icon và lời, không remount hàng", async () => {
  const view = (state: "waiting" | "added" | "error") => <QueueList items={[{ id: 1, name: "a.epub", state }]} currentId={1} />;
  await render(view("waiting")); const row = host.querySelector("li");
  await render(view("added")); expect(old()).not.toBeNull(); expect(host.textContent).toContain("Đã thêm");
  await render(view("error")); expect(document.querySelectorAll(".motion-snapshot").length).toBeGreaterThan(0); expect(host.querySelector("li")).toBe(row);
});

it("thẻ giọng thật fade chọn/bỏ chọn và nghe thử", async () => {
  const voice = { name: "Giọng", gender: "Nữ", region: "Bắc", style: "Tự nhiên" } as ComponentProps<typeof VoiceCard>["voice"];
  const view = (selected: boolean) => <VoiceCard voice={voice} selected={selected} focusable onSelect={() => {}} />;
  await render(view(false)); await render(view(true)); expect(old()).not.toBeNull();
  state.clip.current = "voice-Giọng"; await render(view(true)); expect(host.querySelector(".vu")).not.toBeNull();
  await render(view(false)); expect(old()).not.toBeNull();
});

it("thư viện nhiều bộ: luôn hiện một bìa mỗi bộ, chạm mở tập", async () => {
  const books = Array.from({ length: 8 }, (_, i) => book(String(i), `Bộ ${String.fromCharCode(65 + i)} · Tập 1`, 1)).flatMap((b, i) => [b, { ...b, id: `${i}-2`, title: b.title.replace("Tập 1", "Tập 2") }]);
  await render(<SeriesShelves books={books} twins={new Set()} />);
  const controls = [...host.querySelectorAll<HTMLButtonElement>('button[aria-haspopup="dialog"]')];
  expect(controls).toHaveLength(8);
  expect(host.querySelector('button[aria-expanded]')).toBeNull();
  await act(() => controls[0].click());
  expect(document.querySelector('[role="dialog"] [role="list"]')?.textContent).toContain("Tập 2");
});

/** Sách hai phần (8 + 4 chương): danh sách chương gom theo phần, mỗi phần một khối gấp được. */
const parted = () => {
  const b = book("book", "Truyện thử", 12);
  const part = (n: number, chapters: [number, number]) => ({ part: n, title: `Truyện thử · Phần ${n}`, chapters, duration: 60, narrator: "" });
  return { ...b, parts: [part(1, [1, 8]), part(2, [9, 12])] } as ListenBook;
};

it("trang sách một phần: danh sách chương phẳng, không gấp trong khối lặp tên tab", async () => {
  await render(<ChapterGroups book={book()} onDone={() => {}} />);
  expect(host.querySelector("button[aria-controls]")).toBeNull();
  expect(host.textContent).not.toContain("Danh sách chương");
  expect(host.querySelector('[data-chapter="1"]')?.closest("[inert]")).toBeNull();
});

it("trang sách dài: nhóm chương gập, mở lại giữ thao tác đúng chương", async () => {
  const b = parted(), done = vi.fn();
  await render(<ChapterGroups book={b} onDone={done} />);
  const control = fold("Phần 1"); expect(body(control).hasAttribute("inert")).toBe(true);
  await act(() => control.click()); expect(body(control).hasAttribute("inert")).toBe(false);
  await act(() => host.querySelector<HTMLButtonElement>('[aria-label="Nghe Chương 1"]')!.click());
  expect(state.player.play).toHaveBeenCalledWith(b, b.chapters, 1, 0, undefined);
  await act(() => control.click()); expect(body(control).hasAttribute("inert")).toBe(true);
});

it("nhân vật dài: chia ba Fold và không lộ người ở chương sau", async () => {
  const people = Array.from({ length: 8 }, (_, i) => ({ name: `P${i}`, displayName: `Người ${i}`, lines: 3, seconds: 0, firstChapter: i > 3 ? "later" : "now" }));
  state.cast = { narrator: { voice: "", lines: 1, seconds: 0 }, characters: people, extras: people.slice(0, 2), carried: people.slice(0, 2) };
  await render(<CastList bookId="b" reached={new Set(["now"])} onPickVoice={() => {}} />);
  for (const label of ["Vai chính", "Vai phụ", "Từ phần trước"]) expect(body(fold(label)).hasAttribute("inert")).toBe(true);
  await act(() => fold("Vai chính").click());
  const content = body(fold("Vai chính")); expect(content.textContent).not.toContain("Người 7");
  const later = [...content.querySelectorAll("button")].find(b => b.textContent?.includes("Hiện chương sau"))!;
  await act(() => later.click()); expect(content.textContent).toContain("Người 7");
});

it("kệ sách đổi Play/Pause trong component con vẫn giữ ảnh cũ", async () => {
  const books = [book()]; const view = () => <SeriesShelves books={books} twins={new Set()} grouped={false} />;
  await render(view()); state.player.track = { bookId: books[0].id, chapterId: 1 }; state.player.playing = true;
  await render(view()); expect(old()).not.toBeNull();
  expect(host.querySelector('[aria-label="Tạm dừng Truyện thử"]')).not.toBeNull();
});

it("tạo sách nhiều giọng: tên đã chọn còn hiện, danh sách gập và mở để đổi", async () => {
  const select = vi.fn();
  await render(<VoiceStep narrator="Giọng 0" setNarrator={select} paths={[]} firstPerson="" setFirstPerson={() => {}} setFirstPersonGender={() => {}} setTellerMode={() => {}} narratorAuto={false} povOff={[]} setPovOff={() => {}} />);
  const control = fold("Đổi giọng"); expect(control.textContent).toContain("Giọng 0"); expect(body(control).hasAttribute("inert")).toBe(true);
  await act(() => control.click());
  await act(() => host.querySelector<HTMLButtonElement>('[data-voice="Giọng 1"]')!.click()); expect(select).toHaveBeenCalledWith("Giọng 1");
});

it("lịch sử hơn sáu ngày gập theo ngày, giữ đúng chỗ nghe tiếp", async () => {
  const b = book(); const now = Date.now() / 1000;
  const sessions = Array.from({ length: 8 }, (_, i) => ({ id: String(i), startedAt: now - i * 86400, endedAt: now - i * 86400 + 30, listened: 30, from: { chapterId: 1, seconds: 0 }, to: { chapterId: 1, seconds: 30 } }));
  client.setQueryData(["listen", "sessions", b.id], sessions);
  await render(<HistoryTab book={b} />); const controls = [...host.querySelectorAll<HTMLButtonElement>("button[aria-expanded]")];
  expect(controls).toHaveLength(8); expect(controls[0].textContent).toContain("lượt nghe");
  expect(controls.every(c => body(c).hasAttribute("inert"))).toBe(true);
  await act(() => controls[0].click()); await act(() => body(controls[0]).querySelector("button")!.click());
  expect(state.player.play).toHaveBeenCalledWith(b, b.chapters, 1, 30, undefined);
});

it("sidebar chỉ fade icon/số khi đổi, poll yên không clone", async () => {
  const b = { id: "p", title: "Sách", running: true, phase: "synthesis", progress: { overall: .2 } } as BookSummary;
  state.books = [b]; const view = () => <Producing />;
  await render(view()); vi.mocked(HTMLElement.prototype.animate).mockClear(); await render(view()); expect(HTMLElement.prototype.animate).not.toHaveBeenCalled();
  state.books = [{ ...b, paused: "listener", progress: { ...b.progress, overall: .3 } }]; await render(view());
  expect(host.querySelector('[aria-label="Đang tạm dừng"]')).not.toBeNull(); expect(old()).not.toBeNull();
  expect(host.textContent).toContain("30%"); expect(document.querySelector(".motion-snapshot")?.hasAttribute("inert")).toBe(true);
});

it("nhắc cập nhật sidebar vào/đổi phiên bản/ra đều có presence", async () => {
  await render(<UpdateNotice />); state.info = { dialogs: true, update: { version: "1" } }; await render(<UpdateNotice />);
  expect(host.textContent).toContain("ABook 1"); state.info = { dialogs: true, update: { version: "2" } }; await render(<UpdateNotice />);
  expect(old()?.textContent).toContain("ABook 1"); state.info = { dialogs: true }; await render(<UpdateNotice />);
  expect(host.querySelector('[data-state="closed"][inert]')).not.toBeNull();
});

it("Studio gập các bước; tiến độ và lỗi khởi động ở ngoài phần gập", async () => {
  const b = { id: "p", phase: "analysis", statusLabel: "Đang phân tích", running: true, castLocked: true, progress: { overall: .2, analysis: .4, synthesis: 0 }, eta: null, startError: "Hết chỗ trống", settings: {} } as BookSummary;
  await render(<ProductionPanel book={b} />); const control = fold("Các bước");
  expect(body(control).hasAttribute("inert")).toBe(true); expect(host.textContent).not.toContain("20% tổng"); // phần trăm tổng đã lên đầu trang (HeaderProgress)
  const alert = host.querySelector('[role="alert"]')!; expect(alert.closest("[inert]")).toBeNull();
  await act(() => control.click()); expect(body(control).hasAttribute("inert")).toBe(false);
});

it("bảng chương Studio phẳng dưới tab (không khung gập lặp tên tab), giữ hàng/cột ARIA", async () => {
  const b = { id: "p", title: "Sách", running: false } as BookSummary;
  const chapters = Array.from({ length: 9 }, (_, i) => ({ id: i + 1, index: i + 1, displayTitle: `Chương ${i + 1}`, status: "pending", statusLabel: "Chờ", segments: { total: 10, finished: 0, analyzed: 0, recorded: 0, failed: 0, warnings: 0 }, playable: false, seconds: 0 })) as Chapter[];
  await render(<ChapterList book={b} chapters={chapters} />);
  expect([...host.querySelectorAll("button[aria-expanded]")].some((button) => button.textContent?.includes("Danh sách chương"))).toBe(false);
  expect(host.querySelector('[role="table"]')?.closest("[inert]")).toBeNull();
  expect(host.querySelector('[role="table"]')?.getAttribute("aria-rowcount")).toBe("10");
  expect(host.querySelector('[role="row"][aria-rowindex="2"]')).not.toBeNull();
});

it("tạo sách: danh sách dài và trợ giúp định dạng gập, tên sách ở ngoài", async () => {
  const files = Array.from({ length: 9 }, (_, i) => ({ path: `${i}.txt`, name: `${i}.txt`, title: `Chương ${i + 1}`, firstLine: "", words: 50, chars: 200, audioSeconds: 20, credits: [], tailCredits: [] }));
  const props = { scan: { files, totals: { words: 450, chapters: 9, audioSeconds: 180 }, skipped: [], missing: [] }, title: "Sách", total: 9, limit: null, later: 0, scanning: false, problem: null, dropCredits: { head: false, tail: false }, matter: { files: [], keep: [] }, onKeepMatter: vi.fn(), onTitle: vi.fn(), onPaths: vi.fn(), onAddFiles: vi.fn(), onRemove: vi.fn(), onLimit: vi.fn(), onDropCredits: vi.fn(), onSplit: vi.fn() } as unknown as ComponentProps<typeof SourceStep>;
  await render(<SourceStep {...props} />);
  for (const label of ["Định dạng", "Danh sách chương"]) expect(body(fold(label)).hasAttribute("inert")).toBe(true);
  expect(host.querySelector('input[value="Sách"]')?.closest("[inert]")).toBeNull();
  await act(() => fold("Danh sách chương").click()); expect(host.querySelector('[role="list"][aria-label="Các chương sẽ làm"]')?.closest("[inert]")).toBeNull();
});

it("chất lượng: ba lựa chọn ngắn; chi tiết chọn hiện trong một Fold, không lồng nút", async () => {
  const change = vi.fn();
  const view = (profile: ComponentProps<typeof QualityStep>["profile"]) => <QualityStep profile={profile} setProfile={change} words={1000} chapters={2} analysisModel="v4" setAnalysisModel={() => {}} noStudio />;
  await render(view("high_quality")); expect(host.querySelectorAll('[role="radio"]').length).toBe(3);
  const control = fold("Chi tiết"); expect(body(control).hasAttribute("inert")).toBe(true);
  expect(host.querySelector('button button')).toBeNull();
  await act(() => control.click()); expect(body(control).hasAttribute("inert")).toBe(false);
  const radios = host.querySelectorAll<HTMLButtonElement>('[role="radio"]'); await act(() => radios[1].click()); expect(change).toHaveBeenCalled();
  await render(view("balanced")); expect(old()).not.toBeNull();
});


it("V1: chương giữa nhóm dài mở mặc định và không inert; quay lại vẫn mở", async () => {
  const b = parted();
  const view = () => <ChapterGroups book={b} currentChapter={5} onDone={() => {}} />;
  await render(view());
  expect(fold("Phần 1").getAttribute("aria-expanded")).toBe("true");
  expect(host.querySelector('[data-chapter="5"]')?.closest("[inert]")).toBeNull();
  await render(<div>Màn đọc</div>); await render(view());
  expect(fold("Phần 1").getAttribute("aria-expanded")).toBe("true");
  expect(host.querySelector('[data-chapter="5"]')).not.toBeNull();
});

it("V1: giữ lựa chọn gấp, đầu nhóm chỉ Đang nghe; mở xong hoạt ảnh mới cuộn", async () => {
  localStorage.setItem("abook.fold.book.book.chapters.0", "0");
  await render(<ChapterGroups book={parted()} currentChapter={5} onDone={() => {}} />);
  const control = fold("Phần 1");
  expect(control.textContent).toContain("Đang nghe");
  expect(body(control).hasAttribute("inert")).toBe(true);
  const row = host.querySelector<HTMLElement>('[data-chapter="5"]')!;
  const measure = vi.spyOn(row, "getBoundingClientRect");
  measure.mockReturnValue({ x: 0, y: 5000, top: 5000, left: 0, right: 100, bottom: 5024, width: 100, height: 24, toJSON() {} });
  document.documentElement.scrollTop = 0;
  measure.mockClear();
  await act(() => control.click());
  expect(row.closest("[inert]")).toBeNull(); expect(document.documentElement.scrollTop).toBe(0);
  const animation = vi.mocked(HTMLElement.prototype.animate).mock.results.at(-1)!.value as Animation;
  await act(() => animation.onfinish?.call(animation, {} as AnimationPlaybackEvent));
  expect(document.documentElement.scrollTop).toBeGreaterThan(0);
});

it("V1: khôi phục chỗ cuộn sau layout và hoạt ảnh, huỷ khi rời trang", async () => {
  let finish!: () => void;
  const animation = { finished: new Promise<void>(resolve => { finish = resolve; }) } as unknown as Animation;
  const frame = vi.spyOn(window, "requestAnimationFrame").mockImplementation(callback => { queueMicrotask(() => callback(0)); return 1; });
  const animations = vi.fn(() => [animation]);
  Object.defineProperty(host, "getAnimations", { configurable: true, value: animations });
  const done = vi.fn(); afterScrollLayout(host, done);
  await act(async () => {}); expect(done).not.toHaveBeenCalled();
  await act(async () => finish()); expect(done).toHaveBeenCalledOnce();
  const cancel = afterScrollLayout(host, done); cancel();
  await act(async () => {}); expect(done).toHaveBeenCalledOnce();
  frame.mockRestore();
});

it("V2: giọng khác phần trước vẫn cảnh báo và dùng lại khi Fold đã lưu đóng", async () => {
  localStorage.setItem("abook.fold.new-project.voices", "0");
  const select = vi.fn();
  await render(<VoiceStep narrator="Giọng 1" previousNarrator="Giọng 0" setNarrator={select} paths={[]} firstPerson="" setFirstPerson={() => {}} setFirstPersonGender={() => {}} setTellerMode={() => {}} narratorAuto={false} povOff={[]} setPovOff={() => {}} />);
  expect(body(fold("Đổi giọng")).hasAttribute("inert")).toBe(true);
  const reuse = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Dùng lại Giọng 0")!;
  expect(reuse).toBeDefined(); expect(reuse.closest(".motion-collapse")).toBeNull();
  expect(reuse.parentElement?.textContent).toContain("hai phần sẽ đọc lời dẫn khác nhau");
  await act(() => reuse.click()); expect(select).toHaveBeenCalledWith("Giọng 0");
});
