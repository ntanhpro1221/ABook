import { seriesIndex } from "@/listen/model";
import type { BookSummary } from "./api";

export type Entry = { kind: "book"; book: BookSummary } | { kind: "series"; name: string; unit: string; books: BookSummary[] };

/** Các phần của một cuốn ("Tên", "Tên · Phần 2"... - "Làm tiếp cuốn này") đứng chung một nhóm, theo thứ tự phần, ở chỗ của
 *  phần mới nhất; dự án lẻ giữ nguyên thứ tự. Truyện dài làm nhiều đợt có thể thành hàng chục dự án. */
export function groupParts(books: BookSummary[]): Entry[] {
  const places = seriesIndex(books);
  const members = new Map<string, BookSummary[]>();
  for (const book of books) {
    const place = places.get(book.id);
    if (place?.volume != null) members.set(place.key, [...(members.get(place.key) ?? []), book]);
  }
  const entries: Entry[] = [];
  const shown = new Set<string>();
  for (const book of books) {
    const place = places.get(book.id);
    const group = place?.volume != null ? members.get(place.key) : undefined;
    if (!place || !group || group.length < 2) {
      entries.push({ kind: "book", book });
      continue;
    }
    if (shown.has(place.key)) continue;
    shown.add(place.key);
    const ordered = [...group].sort((a, b) => (places.get(a.id)?.volume ?? 0) - (places.get(b.id)?.volume ?? 0));
    entries.push({ kind: "series", name: place.series, unit: place.unit, books: ordered });
  }
  return entries;
}

export const entryBooks = (entry: Entry) => (entry.kind === "book" ? [entry.book] : entry.books);
const isLive = (book: BookSummary) => Boolean(book.running || book.starting);

/** Mục "Đang chạy" và phần còn lại: một phần đang chạy (hay tạm dừng) kéo CẢ nhóm của nó lên - không để phần 2 ở trên và
 *  phần 1 đứng lẻ bên dưới (soát UX 30-09). `live`: các cuốn thật sự đang chạy, cho tiêu đề mục. */
export function splitLive(entries: Entry[]): { live: Entry[]; rest: Entry[]; books: BookSummary[] } {
  const live = entries.filter((entry) => entryBooks(entry).some(isLive));
  return { live, rest: entries.filter((entry) => !live.includes(entry)), books: live.flatMap(entryBooks).filter(isLive) };
}
