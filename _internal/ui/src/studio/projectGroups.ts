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
    if (place?.volume != null) members.set(place.series, [...(members.get(place.series) ?? []), book]);
  }
  const entries: Entry[] = [];
  const shown = new Set<string>();
  for (const book of books) {
    const place = places.get(book.id);
    const group = place?.volume != null ? members.get(place.series) : undefined;
    if (!place || !group || group.length < 2) {
      entries.push({ kind: "book", book });
      continue;
    }
    if (shown.has(place.series)) continue;
    shown.add(place.series);
    const ordered = [...group].sort((a, b) => (places.get(a.id)?.volume ?? 0) - (places.get(b.id)?.volume ?? 0));
    entries.push({ kind: "series", name: place.series, unit: place.unit, books: ordered });
  }
  return entries;
}
