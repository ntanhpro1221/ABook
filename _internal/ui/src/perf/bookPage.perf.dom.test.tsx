// @vitest-environment happy-dom
// Bài đo (docs/PERF_WEB.md mục 2): trang sách 2500 chương trên máy tính. Đo dựng, nhịp đồng hồ phát, phát / dừng, máy chủ trả tiến độ mới (lưu chỗ
// nghe mỗi 10 giây rồi hỏi lại cuốn), sang chương kế, và cuộn qua cả danh sách. Số in ra console; test giữ trần số lần vẽ hàng chương.
import "./renderCount";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Bench, FakeIntersections, installFakes, Store } from "./harness";
import { Clock, ClockContext } from "@/listen/clock";
import { TooltipProvider } from "@/shared/ui";
import type { ListenBook, ListenChapter } from "@/listen/model";

const CHAPTERS = 2500;
const CURRENT = 1250;

const fake = vi.hoisted(() => ({
  player: null as unknown as { use(): unknown; value: Record<string, unknown>; set(value: Record<string, unknown>): void },
  book: null as unknown as { use(): unknown; value: unknown; set(value: unknown): void },
}));
vi.mock("@/listen/player", async (original) => ({
  ...(await original<typeof import("@/listen/player")>()),
  usePlayer: () => fake.player.use(),
  useNowPlaying: () => ({ expanded: false, setExpanded: () => {} }),
}));
vi.mock("@/listen/clip", async (original) => ({ ...(await original<typeof import("@/listen/clip")>()), useClip: () => ({ current: "", loading: false, toggle() {} }) }));
vi.mock("@/listen/source", async (original) => ({
  ...(await original<typeof import("@/listen/source")>()),
  useSource: () => ({ kind: "desktop", voiceUrl: () => "/voice.wav" }),
  useListenBook: () => ({ data: fake.book.use(), isLoading: false, error: null }),
  useListenLibrary: () => ({ data: [], isLoading: false }),
  useListenMutations: () => new Proxy({}, { get: () => ({ mutate() {}, mutateAsync: async () => {}, isPending: false }) }),
  useCast: () => ({ data: undefined }),
  useWarmVoice: () => {},
  useReadAloudVoices: () => ({ data: [] }),
}));
vi.mock("@/studio/data", async (original) => ({
  ...(await original<typeof import("@/studio/data")>()),
  useAppInfo: () => ({ data: { dialogs: true } }),
  useLibrary: () => ({ data: { books: [] } }),
  usePreferences: () => ({ data: {} }),
}));

function chapter(id: number): ListenChapter {
  return { id, index: id - 1, title: `Chương ${id}`, subtitle: `Tên chương thứ ${id} của truyện`, fullTitle: `Chương ${id}: Tên chương thứ ${id} của truyện`, duration: 1500 + (id % 300), available: true };
}

function bookWith(chapters: ListenChapter[], heardNow: number): ListenBook {
  const states: ListenBook["state"]["chapters"] = {};
  for (let id = 1; id < CURRENT; id++) states[String(id)] = { heard: chapters[id - 1].duration, done: true };
  states[String(CURRENT)] = { heard: heardNow, done: false };
  const duration = chapters.reduce((sum, item) => sum + item.duration, 0);
  return {
    id: "big", title: "Truyện rất dài", narrator: "Giọng thử", duration, chaptersTotal: CHAPTERS, chaptersAvailable: CHAPTERS, complete: true, producing: false,
    updatedAt: 1, state: { chapters: states, last: { chapterId: CURRENT, seconds: heardNow, at: 1 } },
    progress: { heardSeconds: 0, totalSeconds: duration, fraction: 0.5, chaptersDone: CURRENT - 1, finished: false }, chapters,
  };
}

const playerValue = (chapterId: number, playing: boolean) => ({
  track: { bookId: "big", chapterId, chapterTitle: `Chương ${chapterId}`, recordId: "r" }, queue: [], playing, buffering: false, rate: 1,
  positionStamp: () => 0, toggle() {}, resume() {}, play() {}, jumpTo() {}, pause() {},
});

let clock: Clock;
let bench: Bench;
beforeEach(() => {
  installFakes();
  sessionStorage.clear();
  localStorage.clear();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 800, bottom: 54, width: 800, height: 54, toJSON() {} });
});
afterEach(async () => {
  await bench?.unmount();
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

it("trang sách 2500 chương: nhịp đồng hồ / phát-dừng / tiến độ mới không vẽ lại cả danh sách", async () => {
  const chapters = Array.from({ length: CHAPTERS }, (_, i) => chapter(i + 1));
  fake.book = new Store<unknown>(bookWith(chapters, 100));
  fake.player = new Store<Record<string, unknown>>(playerValue(CURRENT, true));
  clock = new Clock();
  const { BookScreen } = await import("@/listen/BookScreen");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0, queryFn: async () => null } } });
  bench = new Bench("Trang sách 2500 chương", "ChapterLine");
  await bench.mount(
    <QueryClientProvider client={client}>
      <ClockContext.Provider value={clock}>
        <MemoryRouter initialEntries={["/book/big"]}>
          <TooltipProvider>
            <Routes><Route path="/book/:id" element={<BookScreen />} /></Routes>
          </TooltipProvider>
        </MemoryRouter>
      </ClockContext.Provider>
    </QueryClientProvider>,
  );
  const nodes = bench.nodes();
  const rowsInDom = bench.host.querySelectorAll("[data-chapter]").length;

  let time = 100;
  const tick = await bench.phase("nhịp đồng hồ (×20, 4 lần/giây)", () => clock.set((time += 0.25), 1600), 20);
  const pause = await bench.phase("phát -> dừng", () => fake.player.set(playerValue(CURRENT, false)));
  await bench.phase("dừng -> phát", () => fake.player.set(playerValue(CURRENT, true)));
  // Lưu chỗ nghe xong, cuốn được hỏi lại: chương giữ nguyên tham chiếu (structural sharing của react-query), state + progress mới.
  const progress = await bench.phase("tiến độ mới từ máy chủ (×5)", () => fake.book.set(bookWith(chapters, (time += 10))), 5);
  const next = await bench.phase("sang chương kế", () => fake.player.set(playerValue(CURRENT + 1, true)));
  // Cuộn từ đầu tới cuối: mỗi bước một khối 40 hàng vào khung (và khối cách xa thôi dựng).
  const blocks = Math.ceil(CHAPTERS / 40);
  let step = 0;
  const scroll = await bench.phase(`cuộn qua ${blocks} khối (mỗi bước)`, () => {
    const at = step++;
    FakeIntersections.report((element) => Math.abs(Number((element as HTMLElement).dataset.block) - at) <= 1);
  }, blocks);
  bench.report({ "nút DOM sau khi dựng": nodes, "hàng chương trong DOM": rowsInDom });

  // Trần (sau tối ưu, docs/PERF_WEB.md): nhịp đồng hồ không vẽ hàng nào; phát / dừng, tiến độ mới, sang chương chỉ vẽ hàng có đổi.
  expect(tick.watched).toBe(0);
  expect(pause.watched).toBeLessThanOrEqual(2);
  expect(progress.watched).toBeLessThanOrEqual(2);
  expect(next.watched).toBeLessThanOrEqual(3);
  expect(scroll.watched).toBeLessThanOrEqual(80);
  expect(rowsInDom).toBeLessThanOrEqual(160);
  await act(async () => {});
}, 120_000);

it("Đang nghe › Chương, 2500 chương: phát / dừng, sang chương kế, tiến độ mới", async () => {
  const chapters = Array.from({ length: CHAPTERS }, (_, i) => chapter(i + 1));
  fake.book = new Store<unknown>(bookWith(chapters, 100));
  const value = (chapterId: number, playing: boolean) => ({ ...playerValue(chapterId, playing), queue: chapters });
  fake.player = new Store<Record<string, unknown>>(value(CURRENT, true));
  clock = new Clock();
  const { ChapterPanel } = await import("@/listen/PlayerViews");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0, queryFn: async () => null } } });
  bench = new Bench("Đang nghe › Chương, 2500 chương", "PanelChapterRow");
  await bench.mount(
    <QueryClientProvider client={client}>
      <ClockContext.Provider value={clock}>
        <MemoryRouter><TooltipProvider><ChapterPanel /></TooltipProvider></MemoryRouter>
      </ClockContext.Provider>
    </QueryClientProvider>,
  );
  const pause = await bench.phase("phát -> dừng", () => fake.player.set(value(CURRENT, false)));
  await bench.phase("dừng -> phát", () => fake.player.set(value(CURRENT, true)));
  const progress = await bench.phase("tiến độ mới từ máy chủ (×5)", () => fake.book.set(bookWith(chapters, 200)), 5);
  const next = await bench.phase("sang chương kế", () => fake.player.set(value(CURRENT + 1, true)));
  bench.report({ "nút DOM sau khi dựng": bench.nodes() });
  expect(pause.watched).toBeLessThanOrEqual(1);
  expect(progress.watched).toBeLessThanOrEqual(1);
  expect(next.watched).toBeLessThanOrEqual(3);
}, 120_000);
