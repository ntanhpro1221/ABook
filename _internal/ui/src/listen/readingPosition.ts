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
  rev?: { counter: number; node: string; epoch?: string };
}

export const MAX_LISTENING_COUNTER = 2 ** 40;
// Compare the complete match too: JavaScript's `$` alone also accepts a final newline.
const validEpoch = (value: unknown): value is string => typeof value === "string" && /^1*$/.exec(value)?.[0] === value;
export function validReadingRevision(value: unknown): value is NonNullable<ReadingPosition["rev"]> {
  if (!value || typeof value !== "object") return false;
  const rev = value as Record<string, unknown>;
  return Number.isInteger(rev.counter) && typeof rev.counter === "number" && rev.counter > 0 && rev.counter <= MAX_LISTENING_COUNTER
    && typeof rev.node === "string" && /^[A-Za-z0-9_-]{1,64}$/.exec(rev.node)?.[0] === rev.node
    && (rev.epoch === undefined || validEpoch(rev.epoch));
}

export function newerReading(a: ReadingPosition, b: ReadingPosition): boolean {
  const left: NonNullable<ReadingPosition["rev"]> = validReadingRevision(a.rev) ? a.rev : { counter: 0, node: "" };
  const right: NonNullable<ReadingPosition["rev"]> = validReadingRevision(b.rev) ? b.rev : { counter: 0, node: "" };
  if (left.counter || right.counter) {
    return (left.epoch ?? "") > (right.epoch ?? "") || (left.epoch ?? "") === (right.epoch ?? "")
      && (left.counter > right.counter || left.counter === right.counter && left.node > right.node);
  }
  return a.at > b.at;
}

let readingNode: string | undefined;
export function nextReadingRevision(book: ListenBook | undefined, local?: ReadingPosition): NonNullable<ReadingPosition["rev"]> {
  readingNode ??= crypto.randomUUID().replaceAll("-", "");
  const revisions = [book?.state.reading?.rev, book?.state.last?.rev, local?.rev].filter(validReadingRevision);
  const validClock = (value: unknown): number => typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= MAX_LISTENING_COUNTER ? value : 0;
  let epoch = [book?.state._epoch, ...revisions.map((rev) => rev.epoch ?? "")].filter(validEpoch).sort().at(-1) ?? "";
  let counter = Math.max(epoch === (book?.state._epoch ?? "") ? validClock(book?.state._clock) : 0,
    ...revisions.filter((rev) => (rev.epoch ?? "") === epoch).map((rev) => rev.counter), 0) + 1;
  if (counter > MAX_LISTENING_COUNTER) { epoch += "1"; counter = 1; }
  return { counter, node: readingNode, ...(epoch ? { epoch } : {}) };
}

export const readingRecord = (book: ListenBook | undefined): string => book?.records?.find((record) => record.active)?.id ?? "default";
export const readingKey = (bookId: string, record: string): string => `${BOOK_STORAGE.reading}${bookId}#${record}`;

export function localReading(bookId: string, record: string): ReadingPosition | undefined {
  try {
    const value = JSON.parse(localStorage.getItem(readingKey(bookId, record)) ?? "null");
    if (value && Number.isInteger(value.chapterId) && Number.isInteger(value.index) && value.index >= 0 && Number.isFinite(value.at)) {
      if (!validReadingRevision(value.rev)) delete value.rev;
      return value;
    }
  } catch { /* bộ nhớ bị chặn */ }
  return undefined;
}

export function latestReading(book: ListenBook | undefined): ReadingPosition | undefined {
  if (!book) return undefined;
  const local = localReading(book.id, readingRecord(book));
  const saved = book.state.reading;
  if (local?.pending && !local.rev) local.rev = nextReadingRevision(book, local);
  const latest = local && (!saved || newerReading(local, saved)) ? local : saved;
  return latest && book.chapters?.some((chapter) => chapter.id === latest.chapterId) ? latest : undefined;
}

/** Anchor thắng chỉ số; câu trích tìm đoạn gần chỉ số cũ nhất. Không sửa chữ truyện. */
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
