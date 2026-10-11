import { afterEach, describe, expect, it } from "vitest";
import { setApiTransport, type ApiInit } from "@/studio/api";
import { BULK, searchBook, type ChapterText, type FoldedChapter } from "./bookSearch";
import type { ListenChapter } from "./model";
import { chapterScriptQuery, chapterTexts, type ListenSource, type SearchText } from "./source";
import { textScript } from "./textScript";

// "Tìm trong sách" với sách dài: nguồn có đường gộp (máy tính) thì một lần hỏi cho cả lô chương thay vì hỏi từng chương (sách 3000 chương
// mất ~20 giây). Kết quả, thứ tự, tổng, số chương hỏng phải y hệt đường từng chương; lô bị máy chủ cắt ngắn / đường gộp hỏng vẫn tìm đủ.

afterEach(() => setApiTransport(null));

const N = 150;
const chapters = Array.from({ length: N }, (_, i) => ({ id: i + 1 }));
// Chương 7 không đọc được; chương chia hết cho 5 có hai chỗ khớp, có dòng ngăn cảnh (không bao giờ là kết quả).
const script = (id: number): ChapterText =>
  textScript(id, `Chương ${id}`, id % 5 ? `Chương ${id}\n\nTrời mưa.\n\nLan về nhà ${id}.` : `Chương ${id}\n\nLan đi.\n\n***\n\nLan về ${id}.`);
const load = async (chapter: { id: number }) => {
  if (chapter.id === 7) throw new Error("hỏng");
  return script(chapter.id);
};
const answer = (lot: { id: number }[]) => new Map(lot.map((chapter) => [chapter.id, chapter.id === 7 ? null : script(chapter.id)]));
const shape = (result: Awaited<ReturnType<typeof searchBook>>) => ({
  hits: result.hits.map((hit) => [hit.chapterId, hit.sentence, hit.snippet.match]),
  total: result.total,
  failed: result.failed,
  scanned: result.scanned,
  done: result.done,
});

describe("tìm cả cuốn bằng đường gộp", () => {
  it("dùng đường gộp khi nguồn có: kết quả y hệt đường từng chương, ít lần hỏi", async () => {
    const before = await searchBook({ chapters, load, query: "lan ve", cache: new Map() });
    let single = 0;
    const lots: number[] = [];
    const after = await searchBook({
      chapters,
      load: async (chapter) => (single++, load(chapter)),
      loadMany: async (lot) => (lots.push(lot.length), answer(lot)),
      query: "lan ve",
      cache: new Map(),
      limit: 40,
    });
    expect(single).toBe(0);
    expect(lots).toEqual([BULK, BULK, N - 2 * BULK]);
    expect(shape(after)).toEqual(shape({ ...before, hits: before.hits.slice(0, 40) }));
    expect(after).toMatchObject({ failed: 1, scanned: N, done: true });
    expect(after.total).toBe(N - 1);
  });

  it("máy chủ trả thiếu (lô quá nặng): xin tiếp từ chương chưa có, không bỏ sót, không lặp", async () => {
    const before = await searchBook({ chapters, load, query: "lan", cache: new Map() });
    const asked: number[][] = [];
    const after = await searchBook({
      chapters,
      load,
      loadMany: async (lot) => {
        asked.push(lot.map((chapter) => chapter.id));
        return answer(lot.slice(0, 10));
      },
      query: "lan",
      cache: new Map(),
    });
    expect(shape(after)).toEqual(shape(before));
    expect(asked.map((lot) => lot[0])).toEqual(Array.from({ length: N / 10 }, (_, i) => i * 10 + 1));
  });

  it("đường gộp hỏng (sách của máy khác, máy chủ cũ): phần còn lại tìm từng chương, kết quả vẫn y hệt", async () => {
    const before = await searchBook({ chapters, load, query: "lan", cache: new Map() });
    let bulkCalls = 0;
    let single = 0;
    const after = await searchBook({
      chapters,
      load: async (chapter) => (single++, load(chapter)),
      loadMany: async (lot) => {
        bulkCalls += 1;
        if (bulkCalls > 1) throw new Error("409");
        return answer(lot);
      },
      query: "lan",
      cache: new Map(),
    });
    expect(shape(after)).toEqual(shape(before));
    expect(bulkCalls).toBe(2);
    expect(single).toBe(N - BULK);
  });

  it("máy chủ không trả chương nào: không lặp mãi, tìm từng chương", async () => {
    const before = await searchBook({ chapters, load, query: "lan", cache: new Map() });
    const after = await searchBook({ chapters, load, loadMany: async () => new Map(), query: "lan", cache: new Map() });
    expect(shape(after)).toEqual(shape(before));
  });

  it("gõ lại giữa chừng thì lần tìm cũ dừng, không hỏi thêm", async () => {
    const controller = new AbortController();
    let lots = 0;
    const result = await searchBook({
      chapters,
      load,
      loadMany: async (lot) => {
        lots += 1;
        controller.abort();
        return answer(lot);
      },
      query: "lan",
      cache: new Map(),
      signal: controller.signal,
    });
    expect(result.done).toBe(false);
    expect(lots).toBe(1);
  });

  it("lần gõ kế dùng lại chữ đã nạp, chỉ xin chương chưa có (và chương lần trước không đọc được)", async () => {
    const cache = new Map<number, FoldedChapter>();
    const asked: number[] = [];
    const loadMany = async (lot: { id: number }[]) => (asked.push(...lot.map((chapter) => chapter.id)), answer(lot));
    await searchBook({ chapters: chapters.slice(0, 20), load, loadMany, query: "lan", cache });
    asked.length = 0;
    const result = await searchBook({ chapters, load, loadMany, query: "troi", cache });
    expect(asked.slice(0, 2)).toEqual([7, 21]);
    expect(asked).toHaveLength(N - 20 + 1);
    expect(result.failed).toBe(1);
  });
});

describe("chữ của nhiều chương từ nguồn", () => {
  const chapter = (id: number, extra: Partial<ListenChapter> = {}) => ({ id, title: `Chương ${id}`, ...extra }) as ListenChapter;
  const text = "Chương 2\n\nDòng ghi công.\n\nLan về nhà.\n\n* * *\n\nHết.";

  it("chương chỉ-có-chữ dựng đoạn y như màn đọc (kể cả dòng đã bỏ), chương nghe được lấy câu của máy chủ", async () => {
    const asked: { id: number; text: boolean }[][] = [];
    const segments = [{ text: "Lan nói." }, { text: "***", sceneBreak: true }];
    const source = {
      searchTexts: async (_bookId: string, lot: { id: number; text: boolean }[]) => {
        asked.push(lot);
        return [{ id: 1, segments }, { id: 2, text }, { id: 3, failed: true }] satisfies SearchText[];
      },
      chapterText: async () => text,
    } as unknown as ListenSource;
    const list = [chapter(1), chapter(2, { state: "text", skip: ["Dòng ghi công."] }), chapter(3), chapter(4)];
    const found = await chapterTexts(source, "b", list);
    expect(asked).toEqual([[{ id: 1, text: false }, { id: 2, text: true }, { id: 3, text: false }, { id: 4, text: false }]]);
    const reader = await chapterScriptQuery(source, "b", list[1]).queryFn();
    expect(found.get(2)!.segments).toEqual(reader.segments);
    expect(found.get(2)!.segments.map((segment) => segment.text)).not.toContain("Dòng ghi công.");
    expect(found.get(1)).toEqual({ segments });
    expect(found.get(3)).toBeNull();
    expect(found.has(4)).toBe(false);
  });

  it("máy tính hỏi một lần cho cả lô, kèm các chương chỉ-có-chữ", async () => {
    const calls: [string, ApiInit | undefined][] = [];
    setApiTransport(async (path, init) => {
      calls.push([path, init]);
      return { chapters: [{ id: 1, segments: [] }] };
    });
    const { httpSource } = await import("@/desktop/httpSource");
    expect(await httpSource.searchTexts!("sach", [{ id: 1, text: false }, { id: 2, text: true }, { id: 3, text: true }])).toEqual([{ id: 1, segments: [] }]);
    expect(await httpSource.searchTexts!("sach", [{ id: 9, text: false }])).toEqual([{ id: 1, segments: [] }]);
    expect(calls.map(([path]) => path)).toEqual([
      "/api/listen/books/sach/search-texts?chapters=1,2,3&text=2,3",
      "/api/listen/books/sach/search-texts?chapters=9",
    ]);
  });
});
