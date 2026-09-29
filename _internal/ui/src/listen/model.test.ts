import { describe, expect, it } from "vitest";
import { foldVietnamese, resumePoint, seriesIndex, seriesOf, type ListenBook, type ListenChapter } from "./model";

describe("seriesOf", () => {
  it("reads the volume and the word the book uses for it", () => {
    expect(seriesOf("Throne of Magical Arcana · Tập 16")).toEqual({
      key: "title:Throne of Magical Arcana",
      series: "Throne of Magical Arcana",
      volume: 16,
      unit: "tập",
    });
    expect(seriesOf("Truyện - Quyển 4")).toEqual({ key: "title:Truyện", series: "Truyện", volume: 4, unit: "quyển" });
    expect(seriesOf("Nageki · Phần 2")).toEqual({ key: "title:Nageki", series: "Nageki", volume: 2, unit: "phần" });
    expect(seriesOf("Book: Vol. 3").volume).toBe(3);
  });

  it("leaves a title without a volume alone", () => {
    expect(seriesOf("Sách lẻ")).toEqual({ key: "title:Sách lẻ", series: "Sách lẻ", volume: null, unit: "tập" });
    expect(seriesOf("Truyện (phần 2)").volume, "hậu tố kiểu cũ không có dấu ngăn").toBeNull();
  });
});

describe("seriesIndex", () => {
  const books = [
    { id: "a", title: "Nageki" },
    { id: "b", title: "Nageki · Phần 2" },
    { id: "c", title: "Nageki · Phần 3" },
    { id: "d", title: "Sách lẻ" },
  ];

  it("counts the unnumbered first part of a continued book as part 1", () => {
    const places = seriesIndex(books);
    expect(places.get("a")).toEqual({ key: "title:Nageki", series: "Nageki", volume: 1, unit: "phần" });
    expect(places.get("c")?.volume).toBe(3);
  });

  it("does not number a book that has no numbered sibling", () => {
    expect(seriesIndex(books).get("d")?.volume).toBeNull();
    expect(seriesIndex([{ id: "x", title: "Nageki" }]).get("x")?.volume).toBeNull();
  });

  // Soát UX 29-09 (N10): các phần của "Làm tiếp cuốn này" đi theo chuỗi máy chủ biết (continues.json), không theo tên.
  it("keeps a renamed part with its book and leaves a look-alike title out", () => {
    const places = seriesIndex([
      { id: "p1", title: "lo18" }, // phần đầu: máy chủ không gắn gì, các phần sau trỏ về nó
      { id: "p2", title: "Ma pháp thần toạ", series: { root: "p1", part: 2 } },
      { id: "stray", title: "lo18 · Phần 2" },
    ]);
    expect(places.get("p2")).toEqual({ key: "chain:p1", series: "lo18", volume: 2, unit: "phần" });
    expect(places.get("p1")).toEqual({ key: "chain:p1", series: "lo18", volume: 1, unit: "phần" });
    expect(places.get("stray")?.key, "dự án lạ không nối gì: nhóm theo tên, tách khỏi chuỗi").toBe("title:lo18");
  });
});

describe("resumePoint", () => {
  const chapters = [
    { id: 1, available: true, duration: 600 },
    { id: 2, available: true, duration: 600 },
    { id: 3, available: false, duration: 0 },
  ] as unknown as ListenChapter[];
  const book = (last: { chapterId: number; seconds: number } | null, complete = true, done: number[] = []) =>
    ({
      complete,
      state: { last, chapters: Object.fromEntries(done.map((id) => [String(id), { done: true, heard: 600 }])) },
    }) as unknown as ListenBook;

  it("resumes where the listener stopped", () => {
    expect(resumePoint(book({ chapterId: 1, seconds: 120 }), chapters)).toEqual({ chapter: chapters[0], at: 120 });
  });

  it("moves on when the chapter was nearly finished", () => {
    expect(resumePoint(book({ chapterId: 1, seconds: 590 }), chapters)).toEqual({ chapter: chapters[1], at: 0 });
  });

  it("stays at the end of the last chapter made so far while the book is still being made", () => {
    expect(resumePoint(book({ chapterId: 2, seconds: 595 }, false), chapters)).toEqual({ chapter: chapters[1], at: 595 });
  });

  it("starts with the first chapter not heard to the end", () => {
    expect(resumePoint(book(null, true, [1]), chapters)).toEqual({ chapter: chapters[1], at: 0 });
  });
});

it("folds Vietnamese for searching without marks", () => {
  expect(foldVietnamese("Đức Trí · Tập 16")).toBe("duc tri · tap 16");
});
