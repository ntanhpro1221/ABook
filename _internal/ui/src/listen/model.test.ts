import { describe, expect, it } from "vitest";
import { chaptersByPart, foldVietnamese, partHeading, resumePoint, seriesIndex, seriesOf, type BookPart, type ListenBook, type ListenChapter } from "./model";

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

describe("chaptersByPart", () => {
  const chapter = (id: number, part?: number): ListenChapter => ({
    id,
    index: id % 100000,
    title: `Chương ${id % 100000}`,
    subtitle: "",
    fullTitle: `Chương ${id % 100000}`,
    duration: 60,
    available: true,
    ...(part === undefined ? {} : { part }),
  });
  const parts: BookPart[] = [
    { part: 1, title: "Truyện X · Phần 1", chapters: [100001, 100002], duration: 120, narrator: "Đức Trí" },
    { part: 2, title: "Truyện X · Phần 2", chapters: [200001, 200002], duration: 120, narrator: "Đức Trí" },
  ];

  it("names a part after the book, not after its own suffix", () => {
    expect(partHeading(parts[1])).toBe("Phần 2 · Truyện X");
    expect(partHeading({ ...parts[0], title: "" })).toBe("Phần 1");
  });

  it("groups the chapter list under a heading per part when the file holds several", () => {
    const list = [chapter(100001, 1), chapter(100002, 1), chapter(200001, 2), chapter(200002, 2)];
    expect(chaptersByPart(list, parts).map((group) => [group.heading, group.chapters.map((item) => item.id)])).toEqual([
      ["Phần 1 · Truyện X", [100001, 100002]],
      ["Phần 2 · Truyện X", [200001, 200002]],
    ]);
  });

  it("finds the part from the id range when a chapter carries no part", () => {
    const list = [chapter(100001), chapter(200001)];
    expect(chaptersByPart(list, parts).map((group) => group.heading)).toEqual(["Phần 1 · Truyện X", "Phần 2 · Truyện X"]);
  });

  it("leaves a one-part or unpartitioned book as one list without a heading", () => {
    const list = [chapter(1), chapter(2)];
    expect(chaptersByPart(list, undefined)).toEqual([{ heading: null, chapters: list }]);
    expect(chaptersByPart(list, [])).toEqual([{ heading: null, chapters: list }]);
    expect(chaptersByPart(list, [parts[0]])).toEqual([{ heading: null, chapters: list }]);
  });
});
