import { findInSegments, foldedQuery, foldedText, type FindHit } from "./findText";

// Tìm chữ trong CẢ cuốn: đi qua từng chương theo thứ tự trong sách, nạp chữ của chương rồi dò từng đoạn (findText.ts). Nguồn có `loadMany`
// (máy tính: một lần hỏi máy chủ cho cả lô - source.tsx `chapterTexts`) thì nạp gộp nhiều chương; không có (điện thoại đọc file trên máy) hay lần
// gộp hỏng thì nạp từng chương (cùng đường với màn đọc - source.tsx `chapterScriptQuery`). Hai đường cho cùng các đoạn, cùng chỉ số `?at=`.
// Sách dài thì chương nạp theo lô và nhường luồng giao diện giữa các lô (không treo ô gõ), kết quả hiện dần; chương đã chuẩn hoá được giữ trong
// `cache` cho lần gõ kế.

/** Chữ một chương: các đoạn theo thứ tự kịch bản (chỉ số đoạn là `?at=` của màn đọc). */
export interface ChapterText {
  segments: { text: string; sceneBreak?: boolean }[];
}

/** Chữ một chương, đã chuẩn hoá để so khớp - giữ lại giữa các lần gõ trong cùng một lần mở ô tìm. */
export interface FoldedChapter {
  segments: { text: string; sceneBreak?: boolean }[];
  folded: string[];
}

export interface SearchChapter {
  id: number;
}

export interface BookSearch {
  /** Kết quả theo thứ tự trong sách, chỉ `limit` cái đầu. */
  hits: FindHit[];
  /** Tổng số chỗ khớp (kể cả phần không hiện). */
  total: number;
  scanned: number;
  chapters: number;
  /** Số chương không nạp được chữ (bỏ qua). */
  failed: number;
  done: boolean;
}

export const RESULT_LIMIT = 200;
/** Số chương nạp cùng lúc khi nạp từng chương. */
const LOT = 4;
/** Số chương xin trong một lần nạp gộp (máy chủ cũng chặn ở 64 - server.py SEARCH_TEXT_CHAPTERS). */
export const BULK = 64;
/** Chạy liền quá chừng này (ms) thì nhường luồng giao diện. */
const SLICE_MS = 12;
/** Báo tiến độ thưa hơn chừng này (ms). */
const REPORT_MS = 120;

const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
const yieldToUi = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

function folded(script: ChapterText): FoldedChapter {
  // Chỉ giữ chữ + dấu ngăn cảnh: mốc từng chữ của sách nói nặng gấp nhiều lần chữ.
  const segments = script.segments.map((segment) => ({ text: segment.text, sceneBreak: segment.sceneBreak }));
  return { segments, folded: segments.map((segment) => foldedText(segment.text)) };
}

export async function searchBook({
  chapters,
  load,
  loadMany,
  query,
  cache,
  signal,
  onUpdate,
  limit = RESULT_LIMIT,
}: {
  chapters: readonly SearchChapter[];
  /** Chữ của một chương (các đoạn theo thứ tự kịch bản - chỉ số đoạn là `?at=` của màn đọc). */
  load: (chapter: SearchChapter) => Promise<ChapterText>;
  /** Chữ của nhiều chương trong một lần (tới `BULK` chương): null = chương không đọc được; chương không có trong kết quả (lô quá nặng) thì
   *  xin lại ở lần kế. Lỗi (sách của máy khác, máy chủ không có đường gộp) thì phần còn lại nạp từng chương bằng `load`. */
  loadMany?: (chapters: SearchChapter[]) => Promise<Map<number, ChapterText | null>>;
  query: string;
  cache: Map<number, FoldedChapter>;
  signal?: AbortSignal;
  onUpdate?: (progress: BookSearch) => void;
  limit?: number;
}): Promise<BookSearch> {
  const needle = foldedQuery(query);
  const state: BookSearch = { hits: [], total: 0, scanned: 0, chapters: chapters.length, failed: 0, done: false };
  if (!needle) return { ...state, done: true };
  // Một chương: chữ đã chuẩn hoá, hay null khi không đọc được.
  const one = async (chapter: SearchChapter): Promise<FoldedChapter | null> => {
    try {
      let text = cache.get(chapter.id);
      if (!text) {
        text = folded(await load(chapter));
        cache.set(chapter.id, text);
      }
      return text;
    } catch {
      return null;
    }
  };
  // Một lô gộp: các chương đầu của `lot` mà máy chủ đã trả (theo thứ tự); dừng ở chương đầu tiên chưa được trả.
  const many = async (lot: readonly SearchChapter[]): Promise<(FoldedChapter | null)[]> => {
    const missing = lot.filter((chapter) => !cache.has(chapter.id));
    const loaded = missing.length ? await loadMany!(missing) : new Map<number, ChapterText | null>();
    const out: (FoldedChapter | null)[] = [];
    for (const chapter of lot) {
      let text = cache.get(chapter.id);
      if (!text) {
        if (!loaded.has(chapter.id)) break;
        const script = loaded.get(chapter.id);
        if (!script) {
          out.push(null);
          continue;
        }
        text = folded(script);
        cache.set(chapter.id, text);
      }
      out.push(text);
    }
    if (!out.length) throw new Error("Máy chủ không trả chương nào");
    return out;
  };
  let bulk = Boolean(loadMany);
  let lastReport = 0;
  let sliceStart = now();
  let from = 0;
  while (from < chapters.length) {
    if (signal?.aborted) return state;
    let found: (FoldedChapter | null)[];
    if (bulk) {
      try {
        found = await many(chapters.slice(from, from + BULK));
      } catch {
        bulk = false;
        continue;
      }
    } else {
      found = await Promise.all(chapters.slice(from, from + LOT).map(one));
    }
    if (signal?.aborted) return state;
    for (const text of found) {
      const chapter = chapters[from];
      from += 1;
      state.scanned += 1;
      let hits: FindHit[] | null = null;
      try {
        hits = text && findInSegments(chapter.id, text.segments, needle, text.folded);
      } catch {
        hits = null;
      }
      if (!hits) {
        state.failed += 1;
        continue;
      }
      state.total += hits.length;
      for (const hit of hits) if (state.hits.length < limit) state.hits.push(hit);
    }
    if (from >= chapters.length) break;
    if (now() - lastReport >= REPORT_MS) {
      lastReport = now();
      onUpdate?.({ ...state, hits: [...state.hits] });
    }
    if (now() - sliceStart >= SLICE_MS) {
      await yieldToUi();
      sliceStart = now();
    }
  }
  state.done = true;
  onUpdate?.({ ...state, hits: [...state.hits] });
  return state;
}
