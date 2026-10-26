// @vitest-environment happy-dom
// Bài đo (docs/PERF_WEB.md mục 1): Thư viện 3000 cuốn trên máy tính. Đo dựng, nhịp đồng hồ, phát / dừng, thư viện được hỏi lại (30 giây một lần:
// mảng mới, cuốn không đổi giữ tham chiếu, một cuốn có tiến độ mới), đổi bộ lọc, đổi cách xếp, gõ tìm từng phím, và cuộn qua cả lưới.
import "./renderCount";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act } from "react";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Bench, FakeIntersections, installFakes, Store } from "./harness";
import { Clock, ClockContext } from "@/listen/clock";
import { TooltipProvider } from "@/shared/ui";
import type { ListenBook } from "@/listen/model";

const BOOKS = 3000;

const fake = vi.hoisted(() => ({
  player: null as unknown as { use(): unknown; set(value: unknown): void },
  library: null as unknown as { use(): unknown; set(value: unknown): void; value: unknown },
}));
vi.mock("@/listen/player", async (original) => ({
  ...(await original<typeof import("@/listen/player")>()),
  usePlayer: () => fake.player.use(),
  useNowPlaying: () => ({ expanded: false, setExpanded: () => {} }),
}));
vi.mock("@/listen/source", async (original) => ({
  ...(await original<typeof import("@/listen/source")>()),
  useSource: () => ({ kind: "desktop" }),
  useListenLibrary: () => ({ data: fake.library.use(), isLoading: false, error: null, refetch() {} }),
  useListenBook: () => ({ data: undefined }),
  useReadAloudVoices: () => ({ data: [] }),
}));

const SERIES = ["Tiên nghịch", "Phàm nhân tu tiên", "Đấu phá thương khung", "Ngạo thế đan thần"];

function book(index: number, heard = 0): ListenBook {
  const series = index % 10 === 0 ? SERIES[index % SERIES.length] : null;
  const duration = 36_000 + (index % 50) * 600;
  const listening = index % 7 === 0;
  return {
    id: `b${index}`,
    title: series ? `${series} - Tập ${Math.floor(index / 40) + 1}` : `Cuốn sách số ${index} về một chuyến đi dài`,
    author: `Tác giả ${index % 120}`, narrator: index % 2 ? "Ngọc Linh" : "Đức Trí", duration, chaptersTotal: 300, chaptersAvailable: 300,
    complete: true, producing: false, updatedAt: 1_700_000_000 + index, addedAt: 1_700_000_000 + index,
    state: { chapters: {}, ...(listening ? { last: { chapterId: 3, seconds: 12, at: 1_700_000_000 + index } } : {}) },
    progress: { heardSeconds: listening ? 1200 + heard : 0, totalSeconds: duration, fraction: listening ? (1200 + heard) / duration : 0, chaptersDone: 0, finished: index % 13 === 0 },
  };
}

const playerValue = (playing: boolean) => ({
  track: { bookId: "b7", chapterId: 3, chapterTitle: "Chương 3", recordId: "r" }, queue: [], playing, buffering: false, rate: 1, purpose: "listen",
  positionStamp: () => 0, toggle() {}, resume() {}, play() {}, prepare() {},
});

let bench: Bench;
beforeEach(() => {
  installFakes();
  sessionStorage.clear();
  localStorage.clear();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 1100, bottom: 300, width: 1100, height: 300, toJSON() {} });
});
afterEach(async () => {
  await bench?.unmount();
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

it("thư viện 3000 cuốn: phát / dừng, hỏi lại thư viện, lọc, tìm, cuộn", async () => {
  const books = Array.from({ length: BOOKS }, (_, i) => book(i));
  fake.library = new Store<unknown>(books);
  fake.player = new Store<unknown>(playerValue(true));
  const clock = new Clock();
  const { LibraryScreen } = await import("@/listen/LibraryScreen");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0, queryFn: async () => null } } });
  bench = new Bench("Thư viện 3000 cuốn", "BookTile");
  await bench.mount(
    <QueryClientProvider client={client}>
      <ClockContext.Provider value={clock}>
        <MemoryRouter>
          <TooltipProvider>
            <LibraryScreen header={<button type="button">Thêm sách</button>} />
          </TooltipProvider>
        </MemoryRouter>
      </ClockContext.Provider>
    </QueryClientProvider>,
  );
  const nodes = bench.nodes();
  const tiles = bench.host.querySelectorAll("[data-book-tile]").length;

  let time = 0;
  const tick = await bench.phase("nhịp đồng hồ (×20)", () => clock.set((time += 0.25), 1600), 20);
  const pause = await bench.phase("phát -> dừng", () => fake.player.set(playerValue(false)));
  await bench.phase("dừng -> phát", () => fake.player.set(playerValue(true)));
  // Hỏi lại thư viện: structural sharing giữ mọi cuốn không đổi, cuốn đang nghe có tiến độ mới.
  let heard = 0;
  const poll = await bench.phase("hỏi lại thư viện (×5)", () => {
    heard += 30;
    fake.library.set(books.map((item, index) => (index === 7 ? book(7, heard) : item)));
  }, 5);
  const button = (label: string) => [...bench.host.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.getAttribute("aria-label") === label)!;
  const filter = await bench.phase("lọc: Nghe dở", () => button("Nghe dở").click());
  await bench.phase("lọc: Tất cả", () => button("Tất cả").click());
  await act(async () => button("Tìm sách").click());
  const input = bench.host.querySelector<HTMLInputElement>('input[type="search"]')!;
  const typed = "tap 1";
  let at = 0;
  const search = await bench.phase(`gõ tìm "${typed}" (mỗi phím)`, () => {
    at++;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, typed.slice(0, at));
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, typed.length);
  await bench.phase("xoá ô tìm", () => button("Xoá ô tìm").click());
  const blocks = Math.ceil(bench.host.querySelectorAll("[data-block]").length);
  let step = 0;
  const scroll = await bench.phase(`cuộn qua ${blocks} khối (mỗi bước)`, () => {
    const now = step++;
    FakeIntersections.report((element) => Math.abs(Number((element as HTMLElement).dataset.block) - now) <= 1);
  }, blocks);
  bench.report({ "nút DOM sau khi dựng": nodes, "ô sách trong DOM": tiles });

  // Trần sau tối ưu (docs/PERF_WEB.md).
  expect(tick.watched).toBe(0);
  expect(pause.watched).toBeLessThanOrEqual(2);
  expect(poll.watched).toBeLessThanOrEqual(1);
  expect(filter.ms).toBeGreaterThan(0);
  expect(search.ms).toBeGreaterThan(0);
  expect(scroll.watched).toBeLessThanOrEqual(130);
}, 180_000);
