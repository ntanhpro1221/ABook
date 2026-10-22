import { expect, it, vi } from "vitest";

const library = vi.hoisted(() => ({ addBookmark: vi.fn(), restoreBookmark: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: library, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("./readAloud", () => ({ phonePrepare: vi.fn() }));
vi.mock("./textImport", () => ({ phoneTextImport: vi.fn() }));
import { androidSource } from "./androidSource";

it("Hoàn tác gửi đúng ID, câu và lúc đặt dấu gốc xuống lõi Android", async () => {
  const mark = { id: "abcdef012345", chapterId: 2, seconds: 64, note: "Hay", at: 10, createdAt: 5, index: 7, quote: "Câu bảy." };
  await androidSource.restoreBookmark!("b", mark);
  expect(library.restoreBookmark).toHaveBeenCalledWith({ id: "b", mark });
  expect(library.addBookmark).not.toHaveBeenCalled();
});
