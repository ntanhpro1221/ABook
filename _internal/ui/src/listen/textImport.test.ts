import { describe, expect, it } from "vitest";
import {
  chapterPicks,
  defaultPicked,
  isDefaultPick,
  pickedSuggestions,
  pickedTotals,
  renameChapter,
  shownTitle,
  splitIsSure,
  splitLabel,
  type ImportPreviewChapter,
} from "./textImport";

// Chọn chương và đổi tên ở bước xem trước "Thêm sách từ file…": hàng 1 là trang đề tựa rất ngắn (chưa tích), hàng 3 có dòng ghi công.
const row = (index: number, title: string, words: number, extra: Partial<ImportPreviewChapter> = {}): ImportPreviewChapter => ({
  index,
  title,
  firstLine: title,
  words,
  chars: words * 5,
  ...extra,
});
const CHAPTERS = [
  row(1, "Chuyến phà cuối ngày", 3, { included: false, short: true }),
  row(2, "Chương 1", 100),
  row(3, "Chương 2", 80),
  row(4, "Chương 3", 60),
];

describe("default choice", () => {
  it("ticks everything except the very short items", () => {
    expect([...defaultPicked(CHAPTERS)]).toEqual([2, 3, 4]);
    expect(isDefaultPick(CHAPTERS, defaultPicked(CHAPTERS))).toBe(true);
    expect(isDefaultPick(CHAPTERS, new Set([1, 2, 3, 4]))).toBe(false);
    expect(isDefaultPick(CHAPTERS, new Set([2, 3]))).toBe(false);
    expect(isDefaultPick(CHAPTERS, new Set([1, 3, 4]))).toBe(false);
  });

  it("treats a row without the flag as ticked (a source that never says)", () => {
    expect([...defaultPicked([row(1, "A", 1), row(2, "B", 1)])]).toEqual([1, 2]);
  });

  it("sends nothing when the listener changed nothing, so the other side uses its own default", () => {
    expect(chapterPicks(CHAPTERS, defaultPicked(CHAPTERS), {})).toBeUndefined();
  });
});

describe("totals", () => {
  it("count only the ticked rows", () => {
    expect(pickedTotals(CHAPTERS, defaultPicked(CHAPTERS))).toEqual({ chapters: 3, words: 240 });
    expect(pickedTotals(CHAPTERS, new Set([1, 4]))).toEqual({ chapters: 2, words: 63 });
    expect(pickedTotals(CHAPTERS, new Set())).toEqual({ chapters: 0, words: 0 });
  });
});

describe("renaming", () => {
  it("keeps the new name, squeezing stray spaces", () => {
    const names = renameChapter({}, CHAPTERS[2], "  Người   khách  lạ ");
    expect(names).toEqual({ 3: "Người khách lạ" });
    expect(shownTitle(CHAPTERS[2], names)).toBe("Người khách lạ");
    expect(shownTitle(CHAPTERS[1], names)).toBe("Chương 1");
  });

  it("an empty name or the old name gives the old name back", () => {
    const names = { 3: "Người khách lạ", 4: "Mưa" };
    expect(renameChapter(names, CHAPTERS[2], "   ")).toEqual({ 4: "Mưa" });
    expect(renameChapter(names, CHAPTERS[3], "Chương 3")).toEqual({ 3: "Người khách lạ" });
  });

  it("does not change the names it was given", () => {
    const names = Object.freeze({ 3: "A" });
    renameChapter(names, CHAPTERS[2], "B");
    expect(names).toEqual({ 3: "A" });
  });
});

describe("what is sent when adding", () => {
  it("lists the ticked rows in file order, with a title only for the renamed ones", () => {
    expect(chapterPicks(CHAPTERS, new Set([4, 1, 3]), { 3: "Người khách", 4: "Chương 3" })).toEqual([
      { index: 1 },
      { index: 3, title: "Người khách" },
      { index: 4 },
    ]);
  });

  it("is sent for a rename alone, even when the ticks are the default", () => {
    expect(chapterPicks(CHAPTERS, defaultPicked(CHAPTERS), { 2: "Mở đầu" })).toEqual([{ index: 2, title: "Mở đầu" }, { index: 3 }, { index: 4 }]);
  });

  it("ignores the name of a row that is not ticked", () => {
    expect(chapterPicks(CHAPTERS, defaultPicked(CHAPTERS), { 1: "Trang đề tựa" })).toBeUndefined();
  });

  it("lets the listener leave out everything (the dialog refuses to add it)", () => {
    expect(chapterPicks(CHAPTERS, new Set(), {})).toEqual([]);
  });
});

describe("credit-line suggestions", () => {
  const suggestions = [{ chapter: 3, line: "Dịch: Nhóm Lục Bình" }];

  it("follow their chapter to its number in the book that will be added", () => {
    expect(pickedSuggestions(suggestions, CHAPTERS, defaultPicked(CHAPTERS))).toEqual([{ chapter: 2, line: "Dịch: Nhóm Lục Bình" }]);
    expect(pickedSuggestions(suggestions, CHAPTERS, new Set([1, 2, 3, 4]))).toEqual([{ chapter: 3, line: "Dịch: Nhóm Lục Bình" }]);
    expect(pickedSuggestions(suggestions, CHAPTERS, new Set([3]))).toEqual([{ chapter: 1, line: "Dịch: Nhóm Lục Bình" }]);
  });

  it("go away with an unticked chapter", () => {
    expect(pickedSuggestions(suggestions, CHAPTERS, new Set([2, 4]))).toEqual([]);
  });
});

describe("isBookFile", () => {
  it("nhận file sách / dự án ABook, không nhận sách để nhập chữ", async () => {
    const { isBookFile } = await import("./AddBook");
    expect(isBookFile("D:\Sách\Chuyến phà.abook")).toBe(true);
    expect(isBookFile(" C:/x/Du an.ABOOKPROJ ")).toBe(true);
    expect(isBookFile("D:\Truyện\Tên truyện.epub")).toBe(false);
    expect(isBookFile("D:\abook\chuong 1.txt")).toBe(false);
  });
});

describe("split is on by default only when the file is surely a whole story", () => {
  it("needs a split offer and at least three heading lines", () => {
    expect(splitIsSure({})).toBe(false);
    expect(splitIsSure({ splitOffer: 2, splitHeadings: 2 })).toBe(false);
    expect(splitIsSure({ splitOffer: 3, splitHeadings: 2 })).toBe(false);
    expect(splitIsSure({ splitOffer: 4, splitHeadings: 3 })).toBe(true);
    expect(splitIsSure({ splitOffer: 3, splitHeadings: 3 })).toBe(true);
  });
});

describe("split label", () => {
  // whole.txt của bộ ví dụ chung: chữ dẫn trước chương đầu + 3 dòng "Chương N" (importers.py / BookImport.kt: splitOffer 4, splitHeadings 3).
  it("counts the heading lines and names the preamble apart", () => {
    expect(splitLabel({ splitOffer: 4, splitHeadings: 3 })).toBe("Tách theo 3 dòng “Chương N” (thêm phần Mở đầu - 4 chương)");
  });
  it("says nothing extra when the file starts at its first heading", () => {
    expect(splitLabel({ splitOffer: 3, splitHeadings: 3 })).toBe("Tách theo 3 dòng “Chương N”");
  });
});
