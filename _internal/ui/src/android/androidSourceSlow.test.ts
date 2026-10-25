import { beforeEach, expect, it, vi } from "vitest";

// Thư viện của điện thoại khi máy tính trả lời chậm (soát a101 F2) và ô "Tìm trong sách" một lượt qua cầu (F6).
const mocks = vi.hoisted(() => ({ localBooks: vi.fn(), streamableBooks: vi.fn(), book: vi.fn(), readTexts: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: mocks, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("./readAloud", () => ({ phonePrepare: () => ({}) }));
vi.mock("./textImport", () => ({ phoneTextImport: {} }));

function native(id: string, title: string, at: number | null, extra = {}) {
  return {
    id, title, narrator: "Đức Trí", chaptersTotal: 1, chaptersAvailable: 1, complete: true,
    chapters: [{ id: 1, index: 1, title: "Chương 1", fullTitle: "Chương 1", duration: 100, available: true, file: "chapters/1.mp3" }],
    state: { ...(at === null ? {} : { last: { chapterId: 1, seconds: 10, at } }), chapters: {} },
    ...extra,
  };
}

/** Mỗi test một bản mô-đun mới: sách nghe thẳng đã biết nằm trong biến của mô-đun. */
async function fresh() {
  vi.resetModules();
  return (await import("./androidSource")).androidSource;
}

beforeEach(() => {
  vi.resetAllMocks();
});

it("máy tính chưa trả lời: sách đã tải hiện ngay, không chờ hết hạn của máy tính", async () => {
  const source = await fresh();
  mocks.localBooks.mockResolvedValue({ books: [native("a", "A", 10)] });
  mocks.streamableBooks.mockReturnValue(new Promise(() => undefined)); // máy tính treo
  const started = Date.now();
  const books = await source.library();
  expect(books.map((book) => book.id)).toEqual(["a"]);
  expect(Date.now() - started).toBeLessThan(1500);
});

it("máy tính trả lời sau: báo thư viện đổi, lần lấy kế có cả sách nghe thẳng; hỏi chồng thì không gọi máy tính hai lần", async () => {
  const source = await fresh();
  mocks.localBooks.mockResolvedValue({ books: [native("a", "A", 10)] });
  let answer!: (reply: { books: unknown[] }) => void;
  mocks.streamableBooks.mockReturnValue(new Promise((resolve) => (answer = resolve)));
  const changed = vi.fn();
  const stop = source.libraryChanged!(changed);
  expect((await source.library()).map((book) => book.id)).toEqual(["a"]);
  expect((await source.library()).map((book) => book.id)).toEqual(["a"]);
  expect(mocks.streamableBooks).toHaveBeenCalledTimes(1);
  answer({ books: [native("far", "Xa", 500, { streamed: true })] });
  await vi.waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  mocks.streamableBooks.mockResolvedValue({ books: [native("far", "Xa", 500, { streamed: true })] });
  expect((await source.library()).map((book) => book.id)).toEqual(["far", "a"]);
  expect(changed).toHaveBeenCalledTimes(1); // cùng danh sách: không báo lại, không vòng lặp lấy-báo-lấy
  stop();
});

it("máy tính ngắt kết nối: sách nghe thẳng rời danh sách và thư viện được báo", async () => {
  const source = await fresh();
  mocks.localBooks.mockResolvedValue({ books: [native("a", "A", 10)] });
  mocks.streamableBooks.mockResolvedValue({ books: [native("far", "Xa", 500, { streamed: true })] });
  expect((await source.library()).map((book) => book.id)).toEqual(["far", "a"]);
  const changed = vi.fn();
  source.libraryChanged!(changed);
  mocks.streamableBooks.mockRejectedValue(new Error("hết hạn"));
  expect((await source.library()).map((book) => book.id)).toEqual(["a"]);
  expect(changed).toHaveBeenCalled();
});

it("tìm trong sách: một lượt qua cầu cho cả lô, đúng đoạn và dấu ngăn cảnh; chương không đọc được báo failed", async () => {
  const source = await fresh();
  mocks.readTexts.mockResolvedValue({
    texts: [
      JSON.stringify({ segments: [{ text: "Trời đã sáng.", kind: "narration" }, { text: "***", sceneBreak: true }] }),
      "Chữ thô của chương chỉ có chữ",
      null,
      "không phải JSON",
    ],
  });
  const found = await source.searchTexts!("sach", [{ id: 1, text: false }, { id: 2, text: true }, { id: 3, text: false }, { id: 4, text: false }]);
  expect(mocks.readTexts).toHaveBeenCalledTimes(1);
  expect(mocks.readTexts).toHaveBeenCalledWith({ id: "sach", paths: ["scripts/1.json", "texts/2.txt", "scripts/3.json", "scripts/4.json"] });
  expect(found).toEqual([
    { id: 1, segments: [{ text: "Trời đã sáng." }, { text: "***", sceneBreak: true }] },
    { id: 2, text: "Chữ thô của chương chỉ có chữ" },
    { id: 3, failed: true },
    { id: 4, failed: true },
  ]);
});

it("chữ quá nhiều: lõi trả phần đầu, phần còn lại không có trong kết quả để bên tìm xin lại", async () => {
  const source = await fresh();
  mocks.readTexts.mockResolvedValue({ texts: [JSON.stringify({ segments: [{ text: "một" }] })] });
  const found = await source.searchTexts!("sach", [{ id: 1, text: false }, { id: 2, text: false }, { id: 3, text: false }]);
  expect(found.map((item) => item.id)).toEqual([1]);
});
