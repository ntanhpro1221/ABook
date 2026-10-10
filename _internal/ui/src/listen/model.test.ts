import { describe, expect, it } from "vitest";
import { bookMatchesQuery, bookmarkReadPath, chaptersByPart, foldVietnamese, listeningBook, otherBooksToHear, partHeading, resumePoint, seriesIndex, seriesOf, twinBookIds, volumeBadge, type BookPart, type ListenBook, type ListenChapter } from "./model";

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

  // Soát UX 05-10: ba bản cùng tên không số + "Tập 2" từng gom thành "4 tập" mà chỉ một cuốn có nhãn.
  it("does not guess volume 1 among look-alike unnumbered copies", () => {
    const places = seriesIndex([
      { id: "a", title: "Chuyến phà" },
      { id: "b", title: "Chuyến phà" },
      { id: "c", title: "Chuyến phà · Tập 2" },
    ]);
    expect(places.get("a")?.volume).toBeNull();
    expect(places.get("b")?.volume).toBeNull();
    expect(places.get("c")?.volume).toBe(2);
  });

  it("gives volume 1 to the audiobook, not to its text-only copy", () => {
    const places = seriesIndex([
      { id: "text", title: "Chuyến phà", stage: "text" },
      { id: "audio", title: "Chuyến phà", stage: null },
      { id: "two", title: "Chuyến phà · Tập 2" },
    ]);
    expect(places.get("audio")?.volume).toBe(1);
    expect(places.get("text")?.volume).toBeNull();
    expect(places.get("two")?.key).toBe(places.get("audio")?.key);
  });

  it("lets a lone text-only book be volume 1 when nothing else claims it", () => {
    const places = seriesIndex([
      { id: "text", title: "Chuyến phà", stage: "text" },
      { id: "two", title: "Chuyến phà · Tập 2" },
    ]);
    expect(places.get("text")?.volume).toBe(1);
  });

  it("does not pick between two audiobooks of the same title even if a text copy exists", () => {
    const places = seriesIndex([
      { id: "x", title: "Chuyến phà" },
      { id: "y", title: "Chuyến phà" },
      { id: "text", title: "Chuyến phà", stage: "text" },
      { id: "two", title: "Chuyến phà · Tập 2" },
    ]);
    expect(["x", "y", "text"].map((id) => places.get(id)?.volume)).toEqual([null, null, null]);
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

describe("volumeBadge", () => {
  it("labels the unnumbered volume 1 of a series, and nothing the cover already labels", () => {
    expect(volumeBadge({ title: "Chuyến phà" }, 1, "tập")).toBe("Tập 1");
    expect(volumeBadge({ title: "Nageki" }, 1, "phần")).toBe("Phần 1");
    expect(volumeBadge({ title: "Chuyến phà · Tập 2" }, 2, "tập"), "tên đã có số").toBeNull();
    expect(volumeBadge({ title: "Phần đã đổi tên", series: { root: "p1", part: 2 } }, 2, "phần"), "phần nối tiếp có nhãn riêng").toBeNull();
    expect(volumeBadge({ title: "Sách lẻ" }, null, "tập")).toBeNull();
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

it("matches a book by title, author or narrator without marks or case", () => {
  const book = { title: "Tắt đèn", author: "Ngô Tất Tố", narrator: "Đức Trí" };
  for (const query of ["tat den", "NGO TAT TO", "duc tri", ""]) expect(bookMatchesQuery(book, foldVietnamese(query.trim()))).toBe(true);
  expect(bookMatchesQuery(book, foldVietnamese("nguyen"))).toBe(false);
  expect(bookMatchesQuery({ title: "Sống mãi", author: "Nguyễn Huy Thiệp", narrator: "" }, foldVietnamese("nguyen huy"))).toBe(true);
  expect(bookMatchesQuery({ title: "Chí Phèo", narrator: "" }, foldVietnamese("nguyễn"))).toBe(false);
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

describe("listeningBook", () => {
  const entry = (id: string, at: number | null, finished = false) =>
    ({ id, progress: { finished }, state: { last: at === null ? null : { chapterId: 1, seconds: 5, at } } }) as unknown as ListenBook;
  const shelf = [entry("a", 100), entry("b", 300), entry("c", null), entry("d", 900, true)];

  it("takes the most recently heard unfinished book when nothing is playing", () => {
    expect(listeningBook(shelf, null)?.id).toBe("b");
    expect(listeningBook([entry("c", null)], null)).toBeUndefined();
  });

  it("follows the book in the player even before the library reports its position", () => {
    // Bắt đầu phát cuốn "c" (chưa có chỗ nghe trong thư viện đã tải) - thẻ phải theo cuốn đang phát, không đứng ở cuốn "b".
    expect(listeningBook(shelf, "c")?.id).toBe("c");
    expect(listeningBook(shelf, "a")?.id).toBe("a");
  });

  it("ignores a playing book that is finished or not on the shelf", () => {
    expect(listeningBook(shelf, "d")?.id).toBe("b");
    expect(listeningBook(shelf, "zzz")?.id).toBe("b");
  });
});

describe("otherBooksToHear", () => {
  const book = (id: string, over: Partial<{ at: number | null; finished: boolean; caughtUp: boolean; available: number; stage: "text" | null }> = {}) =>
    ({
      id,
      stage: over.stage ?? null,
      chaptersAvailable: over.available ?? (over.stage === "text" ? 0 : 5),
      chaptersTotal: 5,
      progress: { finished: over.finished ?? false, caughtUp: over.caughtUp ?? false },
      state: { last: over.at == null ? null : { chapterId: 1, seconds: 5, at: over.at } },
    }) as unknown as ListenBook;

  it("đang nghe dở trước (gần nhất trước), rồi cuốn chưa nghe, tối đa 3", () => {
    const shelf = [book("new1"), book("old", { at: 100 }), book("recent", { at: 900 }), book("new2"), book("mid", { at: 500 })];
    expect(otherBooksToHear(shelf, "cur", true).map((item) => item.id)).toEqual(["recent", "mid", "old"]);
    expect(otherBooksToHear(shelf.filter((item) => item.id !== "old" && item.id !== "mid"), "cur", true).map((item) => item.id)).toEqual(["recent", "new1", "new2"]);
  });

  it("bỏ cuốn vừa nghe, cuốn đã xong, đã nghe hết phần có, chưa có chương nghe được", () => {
    const shelf = [book("cur", { at: 900 }), book("done", { at: 800, finished: true }), book("caught", { at: 700, caughtUp: true }), book("empty", { available: 0 }), book("ok")];
    expect(otherBooksToHear(shelf, "cur", true).map((item) => item.id)).toEqual(["ok"]);
    expect(otherBooksToHear([book("cur")], "cur", true)).toEqual([]);
  });

  it("sách chỉ có chữ chỉ mời khi máy có giọng đọc", () => {
    const shelf = [book("text", { stage: "text" }), book("audio")];
    expect(otherBooksToHear(shelf, "cur", false).map((item) => item.id)).toEqual(["audio"]);
    expect(otherBooksToHear(shelf, "cur", true).map((item) => item.id)).toEqual(["text", "audio"]);
  });
});

describe("bookmarkReadPath", () => {
  it("opens the reader on the sentence a reader bookmark points to; a player bookmark has no sentence", () => {
    expect(bookmarkReadPath("b1", { id: "m", chapterId: 3, seconds: 0, note: "", at: 1, index: 12, quote: "Trời đã sáng." })).toBe("/book/b1/read/3?at=12");
    expect(bookmarkReadPath("b1", { id: "m", chapterId: 3, seconds: 0, note: "", at: 1, index: 0, quote: "" })).toBe("/book/b1/read/3?at=0");
    expect(bookmarkReadPath("b1", { id: "m", chapterId: 3, seconds: 64, note: "", at: 1 })).toBeNull();
  });
});

describe("twinBookIds", () => {
  it("marks books that share a title (ignoring case, accents and spacing) and leaves the others alone", () => {
    const twins = twinBookIds([
      { id: "a", title: "Truyện Kiều" },
      { id: "b", title: "truyen  kieu" },
      { id: "c", title: "Tắt đèn" },
    ]);
    expect([...twins].sort()).toEqual(["a", "b"]);
    expect(twinBookIds([]).size).toBe(0);
  });
});
