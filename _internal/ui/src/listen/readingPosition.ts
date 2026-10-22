import { BOOK_STORAGE } from "@/shared/bookStorage";
import type { ListenBook, Script } from "./model";
import { restoreAnchor, type ReadingAnchor } from "./readingAnchor";

export interface ReadingPosition {
  chapterId: number;
  index: number;
  at: number;
  anchor?: ReadingAnchor;
  quote?: string;
  pending?: boolean;
}

export const readingRecord = (book: ListenBook | undefined): string => book?.records?.find((record) => record.active)?.id ?? "default";
export const readingKey = (bookId: string, record: string): string => `${BOOK_STORAGE.reading}${bookId}#${record}`;

export function localReading(bookId: string, record: string): ReadingPosition | undefined {
  try {
    const value = JSON.parse(localStorage.getItem(readingKey(bookId, record)) ?? "null");
    if (value && Number.isInteger(value.chapterId) && Number.isInteger(value.index) && value.index >= 0 && Number.isFinite(value.at)) return value;
  } catch { /* bộ nhớ bị chặn */ }
  return undefined;
}

export function latestReading(book: ListenBook | undefined): ReadingPosition | undefined {
  if (!book) return undefined;
  const local = localReading(book.id, readingRecord(book));
  const saved = book.state.reading;
  const latest = local && (!saved || local.at > saved.at) ? local : saved;
  return latest && book.chapters?.some((chapter) => chapter.id === latest.chapterId) ? latest : undefined;
}

/** Anchor thắng chỉ số; câu trích của dấu trang tìm đoạn gần chỉ số cũ nhất. Không sửa chữ truyện. */
export function readingIndex(script: Script, place: Pick<ReadingPosition, "index" | "anchor" | "quote">): number {
  const paragraphs = script.segments.map((segment) => segment.text);
  const anchored = restoreAnchor(paragraphs, place.anchor);
  if (anchored) return anchored.segment;
  if (place.quote) {
    const normal = (text: string) => text.normalize("NFC").replace(/\s+/gu, " ").trim();
    const quote = normal(place.quote).replace(/…$/u, "");
    const matches = paragraphs.flatMap((text, index) => quote && normal(text).startsWith(quote) ? [index] : []);
    if (matches.length) return matches.reduce((best, index) => Math.abs(index - place.index) < Math.abs(best - place.index) ? index : best);
  }
  return Math.max(0, Math.min(paragraphs.length - 1, Number.isFinite(place.index) ? Math.trunc(place.index) : 0));
}
