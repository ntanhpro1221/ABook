import { findInSegments, foldedQuery, foldedText, type FindHit } from "./findText";

// Tìm chữ trong CẢ cuốn: đi qua từng chương theo thứ tự trong sách, nạp chữ của chương (cùng đường với màn đọc - source.tsx `chapterScriptQuery`,
// nên máy tính / điện thoại, sách nói / sách chỉ-chữ đều dùng chung) rồi dò từng đoạn (findText.ts). Sách dài thì chương nạp theo lô và
// nhường luồng giao diện giữa các lô (không treo ô gõ), kết quả hiện dần; chương đã chuẩn hoá được giữ trong `cache` cho lần gõ kế.

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
/** Số chương nạp cùng lúc. */
const LOT = 4;
/** Chạy liền quá chừng này (ms) thì nhường luồng giao diện. */
const SLICE_MS = 12;
/** Báo tiến độ thưa hơn chừng này (ms). */
const REPORT_MS = 120;

const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
const yieldToUi = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

export async function searchBook({
  chapters,
  load,
  query,
  cache,
  signal,
  onUpdate,
  limit = RESULT_LIMIT,
}: {
  chapters: readonly SearchChapter[];
  /** Chữ của một chương (các đoạn theo thứ tự kịch bản - chỉ số đoạn là `?at=` của màn đọc). */
  load: (chapter: SearchChapter) => Promise<{ segments: { text: string; sceneBreak?: boolean }[] }>;
  query: string;
  cache: Map<number, FoldedChapter>;
  signal?: AbortSignal;
  onUpdate?: (progress: BookSearch) => void;
  limit?: number;
}): Promise<BookSearch> {
  const folded = foldedQuery(query);
  const state: BookSearch = { hits: [], total: 0, scanned: 0, chapters: chapters.length, failed: 0, done: false };
  if (!folded) return { ...state, done: true };
  let lastReport = 0;
  let sliceStart = now();
  for (let from = 0; from < chapters.length; from += LOT) {
    if (signal?.aborted) return state;
    const lot = chapters.slice(from, from + LOT);
    const found = await Promise.all(
      lot.map(async (chapter) => {
        try {
          let text = cache.get(chapter.id);
          if (!text) {
            const script = await load(chapter);
            // Chỉ giữ chữ + dấu ngăn cảnh: mốc từng chữ của sách nói nặng gấp nhiều lần chữ.
            const segments = script.segments.map((segment) => ({ text: segment.text, sceneBreak: segment.sceneBreak }));
            text = { segments, folded: segments.map((segment) => foldedText(segment.text)) };
            cache.set(chapter.id, text);
          }
          return findInSegments(chapter.id, text.segments, folded, text.folded);
        } catch {
          return null;
        }
      }),
    );
    if (signal?.aborted) return state;
    for (const hits of found) {
      state.scanned += 1;
      if (!hits) {
        state.failed += 1;
        continue;
      }
      state.total += hits.length;
      for (const hit of hits) if (state.hits.length < limit) state.hits.push(hit);
    }
    if (from + LOT >= chapters.length) break;
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
