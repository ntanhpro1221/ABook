import { useQuery } from "@tanstack/react-query";
import type { ListenBook } from "@/listen/model";
import { EbookLibrary } from "./plugins";

// Dung lượng sách trên điện thoại: tổng + từng cuốn (Kotlin LibraryPlugin.storage), để người nghe biết nên xoá cuốn nào.

export function useStorage() {
  return useQuery({ queryKey: ["storage"], queryFn: () => EbookLibrary.storage() });
}

/** Cỡ cuốn này trên máy; undefined khi chưa đo xong hay cuốn không nằm trên máy. */
export function useBookBytes(bookId: string): number | undefined {
  return useStorage().data?.books.find((entry) => entry.id === bookId)?.bytes;
}

export interface SizedBook {
  book: ListenBook;
  bytes: number;
}

/** Sách đang nằm trên điện thoại, cuốn chiếm nhiều chỗ nhất đứng đầu. Thư mục không ứng với cuốn nào của thư viện thì bỏ qua
 *  (vẫn nằm trong tổng). */
export function booksBySize(sizes: { id: string; bytes: number }[], library: ListenBook[]): SizedBook[] {
  const byId = new Map(library.map((book) => [book.id, book]));
  return sizes
    .flatMap(({ id, bytes }) => {
      const book = byId.get(id);
      return book && !book.remote ? [{ book, bytes }] : [];
    })
    .sort((a, b) => b.bytes - a.bytes);
}
