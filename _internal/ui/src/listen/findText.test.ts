import { describe, expect, it } from "vitest";
import { searchBook, type FoldedChapter } from "./bookSearch";
import { findInSegments, foldedQuery, foldedText, originalSpan, snippetOf } from "./findText";
import { findStatus, readerUrl } from "./FindInBook";
import { textScript } from "./textScript";

const hitsOf = (text: string, query: string) => {
  const folded = foldedQuery(query);
  const segments = [{ text }];
  return findInSegments(1, segments, folded);
};

describe("khớp bỏ dấu, không phân biệt hoa thường", () => {
  it("'nguyen' khớp 'Nguyễn', 'duc tri' khớp 'Đức Trí'", () => {
    expect(hitsOf("Anh Nguyễn bước vào.", "nguyen")).toHaveLength(1);
    expect(hitsOf("Cô gặp ĐỨC TRÍ ở cổng.", "duc tri")).toHaveLength(1);
    expect(hitsOf("Cô gặp ĐỨC TRÍ ở cổng.", "ĐỨC trí")).toHaveLength(1);
  });

  it("chữ gõ có dấu vẫn khớp chữ không dấu và ngược lại", () => {
    expect(hitsOf("Tran Nhan Tong", "Trần")).toHaveLength(1);
    expect(hitsOf("Trần Nhân Tông", "tran nhan")).toHaveLength(1);
  });

  it("chữ dựng sẵn và chữ tổ hợp (NFD) như nhau", () => {
    expect(hitsOf("Nguyễn Du", "nguyễn")).toHaveLength(1);
    expect(hitsOf("Nguyễn Du", "nguyễn")).toHaveLength(1);
  });

  it("khoảng trắng lạ (xuống dòng, khoảng trắng cứng) coi như dấu cách; ít hơn 2 ký tự thì không tìm", () => {
    expect(hitsOf("cuối\ncùng rồi", "cuoi cung")).toHaveLength(1);
    expect(foldedQuery("a")).toBe("");
    expect(foldedQuery("  an ")).toBe("an");
    expect(foldedQuery("Đ")).toBe("");
  });

  it("không khớp thì không có kết quả", () => {
    expect(hitsOf("Anh Nguyễn bước vào.", "lan")).toHaveLength(0);
  });
});

describe("đoạn trích", () => {
  it("tô đúng chữ gốc (có dấu) ở chỗ khớp", () => {
    const [hit] = hitsOf("Hôm đó anh Nguyễn Văn An bước vào quán.", "nguyen van");
    expect(hit.snippet.match).toBe("Nguyễn Văn");
    expect(hit.snippet.before).toBe("Hôm đó anh ");
    expect(hit.snippet.after).toBe(" An bước vào quán.");
  });

  it("câu dài thì cắt hai đầu bằng '…' ở ranh giới chữ", () => {
    const long = `${"mở đầu rất dài ".repeat(10)}Nguyễn${" phần đuôi cũng dài ".repeat(10)}`;
    const { snippet } = hitsOf(long, "nguyen")[0];
    expect(snippet.before.startsWith("…")).toBe(true);
    expect(snippet.after.endsWith("…")).toBe(true);
    expect(snippet.match).toBe("Nguyễn");
    expect(snippet.before.length).toBeLessThan(60);
    expect(snippet.after.length).toBeLessThan(90);
  });

  it("dấu rời đứng sau chữ cái cuối vẫn nằm trong phần tô", () => {
    const text = "xin chào Hanh́ nhé";
    const folded = foldedText(text);
    const span = originalSpan(text, folded, folded.indexOf("hanh"), 4);
    expect(text.slice(...span!)).toBe("Hanh́");
  });

  it("không dò được chỗ khớp thì lấy đầu đoạn, không tô", () => {
    expect(snippetOf("Một đoạn ngắn.", null)).toEqual({ before: "", match: "", after: "Một đoạn ngắn." });
  });
});

describe("tìm trong các đoạn của một chương", () => {
  it("chỉ số câu là chỉ số đoạn trong kịch bản (kể cả dòng ngăn cảnh), bỏ dòng ngăn cảnh", () => {
    const script = textScript(7, "Chương 7", "Chương 7\n\nMở đầu yên ắng.\n\n***\n\nLan bước vào, gặp Nguyễn.\n\nHết.");
    const hits = findInSegments(7, script.segments, foldedQuery("nguyen"));
    expect(hits).toHaveLength(1);
    expect(script.segments[hits[0].sentence].text).toContain("Nguyễn");
    expect(findInSegments(7, script.segments, foldedQuery("***"))).toHaveLength(0);
  });
});

describe("tìm cả cuốn", () => {
  const texts: Record<number, string> = {
    1: "Chương 1\n\nTrời mưa. Nguyễn đi một mình.",
    2: "Chương 2\n\nKhông có ai ở đây.",
    3: "Chương 3\n\nNguyễn về nhà.\n\nNgười nhà tên Nguyên đã đợi.\n\nHết.",
  };
  const chapters = [1, 2, 3].map((id) => ({ id }));
  const load = async (chapter: { id: number }) => textScript(chapter.id, `Chương ${chapter.id}`, texts[chapter.id]);

  it("kết quả theo thứ tự chương rồi thứ tự câu, kèm tổng", async () => {
    const result = await searchBook({ chapters, load, query: "nguyen", cache: new Map() });
    expect(result.done).toBe(true);
    expect(result.total).toBe(3);
    expect(result.hits.map((hit) => [hit.chapterId, hit.sentence])).toEqual([
      [1, 1],
      [3, 1],
      [3, 2],
    ]);
  });

  it("mỗi kết quả trỏ đúng câu: mở `?at=` ra đúng đoạn có chữ cần tìm", async () => {
    const result = await searchBook({ chapters, load, query: "nguyen", cache: new Map() });
    for (const hit of result.hits) {
      const script = await load({ id: hit.chapterId });
      expect(foldedText(script.segments[hit.sentence].text)).toContain("nguyen");
      expect(readerUrl("b1", hit, false)).toBe(`/book/b1/read/${hit.chapterId}?at=${hit.sentence}`);
    }
    expect(readerUrl("b1", result.hits[0], true)).toContain("&play=1");
  });

  it("chỉ hiện `limit` kết quả đầu nhưng vẫn đếm đủ tổng", async () => {
    const many = Array.from({ length: 30 }, (_, i) => ({ id: i + 1 }));
    const result = await searchBook({
      chapters: many,
      load: async (chapter) => textScript(chapter.id, "x", "Chương\n\nLan.\n\nLan nữa."),
      query: "lan",
      cache: new Map(),
      limit: 25,
    });
    expect(result.hits).toHaveLength(25);
    expect(result.total).toBe(60);
    expect(findStatus("lan", result, result.hits.length)).toContain("còn 35 kết quả");
  });

  it("chương không nạp được thì bỏ qua và báo", async () => {
    const result = await searchBook({
      chapters,
      load: async (chapter) => {
        if (chapter.id === 2) throw new Error("hỏng");
        return textScript(chapter.id, "x", texts[chapter.id]);
      },
      query: "nguyen",
      cache: new Map(),
    });
    expect(result.failed).toBe(1);
    expect(result.total).toBe(3);
    expect(findStatus("nguyen", result, 3)).toContain("1 chương chưa đọc được");
  });

  it("dùng lại chữ đã chuẩn hoá ở lần tìm kế (không nạp lại chương)", async () => {
    const cache = new Map<number, FoldedChapter>();
    let loads = 0;
    const counted = async (chapter: { id: number }) => {
      loads += 1;
      return load(chapter);
    };
    await searchBook({ chapters, load: counted, query: "nguyen", cache });
    await searchBook({ chapters, load: counted, query: "troi", cache });
    expect(loads).toBe(3);
  });

  it("gõ lại giữa chừng thì lần tìm cũ dừng", async () => {
    const controller = new AbortController();
    let loads = 0;
    const result = await searchBook({
      chapters: Array.from({ length: 40 }, (_, i) => ({ id: i + 1 })),
      load: async (chapter) => {
        loads += 1;
        if (loads === 5) controller.abort();
        return textScript(chapter.id, "x", "Chương\n\nLan.");
      },
      query: "lan",
      cache: new Map(),
      signal: controller.signal,
    });
    expect(result.done).toBe(false);
    expect(loads).toBeLessThan(40);
  });

  it("từ khoá quá ngắn: xong ngay, không nạp chương nào", async () => {
    let loads = 0;
    const result = await searchBook({ chapters, load: async (c) => (loads++, load(c)), query: "n", cache: new Map() });
    expect(result).toMatchObject({ done: true, total: 0 });
    expect(loads).toBe(0);
  });
});

describe("lời báo tình hình tìm", () => {
  it("nhắc gõ khi trống hoặc quá ngắn; báo không thấy", () => {
    expect(findStatus("", null, 0)).toContain("Gõ chữ");
    expect(findStatus("a", null, 0)).toContain("ít nhất 2 ký tự");
    expect(findStatus("zzz", { hits: [], total: 0, scanned: 3, chapters: 3, failed: 0, done: true }, 0)).toBe("Không thấy “zzz” trong sách.");
    expect(findStatus("zzz", { hits: [], total: 1, scanned: 1, chapters: 3, failed: 0, done: false }, 0)).toContain("đã xem 1/3 chương");
  });
});
