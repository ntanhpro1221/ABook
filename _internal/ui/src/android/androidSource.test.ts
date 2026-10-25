import { beforeEach, expect, it, vi } from "vitest";

// Thư viện của điện thoại (androidSource.library): thứ tự "Nghe gần đây" và liên kết bộ truyện giữ qua bộ chuyển (soát a97 T1, V2).
const mocks = vi.hoisted(() => ({ localBooks: vi.fn(), streamableBooks: vi.fn(), book: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: mocks, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("./readAloud", () => ({ phonePrepare: () => ({}) }));
vi.mock("./textImport", () => ({ phoneTextImport: {} }));

import { seriesIndex } from "@/listen/model";
import { sortBooks } from "@/listen/librarySort";
import { androidSource } from "./androidSource";

function native(id: string, title: string, at: number | null, extra = {}) {
  return {
    id, title, narrator: "Đức Trí", chaptersTotal: 1, chaptersAvailable: 1, complete: true,
    chapters: [{ id: 1, index: 1, title: "Chương 1", fullTitle: "Chương 1", duration: 100, available: true, file: "chapters/1.mp3" }],
    state: { ...(at === null ? {} : { last: { chapterId: 1, seconds: 10, at } }), chapters: {} },
    ...extra,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.streamableBooks.mockResolvedValue({ books: [] });
});

it("Nghe gần đây: cuốn nghe sau đứng trước, dù tải sau hay nghe thẳng từ máy tính", async () => {
  mocks.localBooks.mockResolvedValue({ books: [native("old", "A", 10), native("recent", "B", 999), native("never", "C", null)] });
  mocks.streamableBooks.mockResolvedValue({ books: [native("streamed", "D", 500, { streamed: true })] });
  const result = sortBooks(await androidSource.library(), "recent");
  expect(result.map((book) => book.id)).toEqual(["recent", "streamed", "old", "never"]);
});

it("Cùng mốc nghe (hay chưa nghe) thì giữ thứ tự nhận vào", async () => {
  mocks.localBooks.mockResolvedValue({ books: [native("a", "A", null), native("b", "B", null)] });
  expect((await androidSource.library()).map((book) => book.id)).toEqual(["a", "b"]);
});

it("liên kết bộ truyện trong gói sách đi qua bộ chuyển: đổi tên phần 2 không làm mất nhóm", async () => {
  mocks.localBooks.mockResolvedValue({ books: [native("first", "Bộ truyện", 10), native("second", "Ngày trở về", 20, { series: { root: "first", part: 2 } })] });
  const result = await androidSource.library();
  const second = result.find((book) => book.id === "second")!;
  expect(second.series).toEqual({ root: "first", part: 2 });
  const places = seriesIndex(result);
  expect(places.get("first")!.key).toBe(places.get("second")!.key);
  expect(places.get("second")!.volume).toBe(2);
});

it("sách chi tiết cũng mang liên kết bộ", async () => {
  mocks.book.mockResolvedValue(native("second", "Ngày trở về", 20, { series: { root: "first", part: 2 } }));
  expect((await androidSource.book("second")).series).toEqual({ root: "first", part: 2 });
});
