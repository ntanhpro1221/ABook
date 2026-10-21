import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ListenBook, ListenChapter } from "./model";
const h = vi.hoisted(() => ({ memory: vi.fn(), books: [] as unknown[], chapters: [] as unknown[] }));
vi.mock("@/shared/scrollMemory", async (original) => ({ ...await original<typeof import("@/shared/scrollMemory")>(), useScrollMemory: h.memory }));
vi.mock("./player", async (original) => ({ ...await original<typeof import("./player")>(), usePlayer: () => ({ track: { bookId: "book", chapterId: 2401 }, queue: h.chapters, playing: false }) }));
vi.mock("./source", async (original) => ({
  ...await original<typeof import("./source")>(),
  useListenLibrary: () => ({ data: h.books, isLoading: false }),
  useListenBook: () => ({ data: undefined }), useBookVoice: () => undefined,
  useReadAloudVoices: () => ({ data: [] }), useSource: () => ({ kind: "desktop" }),
}));
import { LibraryScreen } from "./LibraryScreen";
import { ChapterPanel } from "./PlayerViews";
import { BlockSizes } from "@/shared/Windowed";

beforeEach(() => {
  h.memory.mockClear();
  vi.stubGlobal("IntersectionObserver", class {});
  vi.stubGlobal("window", { location: { search: "" } });
});
afterEach(() => vi.unstubAllGlobals());

it("thư viện 226 cuốn nhớ chỗ cuộn và chiều cao khối khi quay lại", () => {
  h.books = Array.from({ length: 226 }, (_, i) => ({ id: `b${i}`, title: `Sách ${i}`, chaptersAvailable: 1, chaptersTotal: 1, complete: true, state: { chapters: {} }, progress: { fraction: 0, heardSeconds: 0 } }) as ListenBook);
  const sizes = new BlockSizes(226, 60);
  sizes.record([{ index: 0, width: 800, height: 4321, filled: true }]);
  const keys: string[] = [];
  vi.stubGlobal("sessionStorage", { getItem: (key: string) => { keys.push(key); return key.startsWith("abook.blocks.library.all.recent") ? JSON.stringify(sizes) : null; } });
  const html = renderToString(<MemoryRouter><LibraryScreen /></MemoryRouter>);
  expect(h.memory).toHaveBeenCalledWith("library.all.recent", expect.objectContaining({ current: null }));
  expect(keys.some((key) => key.startsWith("abook.blocks.library.all.recent"))).toBe(true);
  expect(html).toContain("height:4321px");
});

it("tab Chương 2500 chương dựng tối đa hai khối và giữ chương đang phát", () => {
  h.chapters = Array.from({ length: 2500 }, (_, i) => ({ id: i + 1, title: `Chương ${i + 1}`, fullTitle: `Chương ${i + 1}`, available: true, duration: 60 }) as ListenChapter);
  const html = renderToString(<ChapterPanel />);
  expect(html.match(/<button/g)).toHaveLength(80);
  expect(html).toContain('data-current="true"');
  expect(html).toContain("Chương 2401");
  expect(html).not.toContain("Chương 1201");
});
