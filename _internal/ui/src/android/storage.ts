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

/** Thứ người dùng bấm xoá khỏi điện thoại (sự kiện "abook-remove-from-phone"): cuốn trong Thư viện, hay `partial` - phần đã tải chưa thành sách. */
export interface RemovableFromPhone {
  id: string;
  title: string;
  partial?: boolean;
}

/** Một thư mục sách trên máy theo Kotlin `storage()`: `title` là tên trong gói sách của chính thư mục (đã tải hay nghe thẳng), nếu có. */
export interface StoredFolder {
  id: string;
  bytes: number;
  title?: string;
}

export interface StoredEntry {
  id: string;
  title: string;
  bytes: number;
  /** "book": cuốn đã tải xong, đang trong Thư viện - xoá cả cuốn. "partial": phần chiếm chỗ mà không phải một cuốn đã tải xong (tải dở, hay gói đã cất để
   *  nghe thẳng): xoá riêng "phần đã tải", cuốn vẫn nằm ở máy tính. */
  kind: "book" | "partial";
}

/** Mọi thứ đang chiếm chỗ trên điện thoại, cái chiếm nhiều nhất đứng đầu. Thư mục tải dở / chỉ-nghe-thẳng cũng có hàng để xoá (soát a97 V6) - trước đây
 *  chúng nằm trong tổng "Sách trên máy" mà không có nút nào để lấy lại chỗ. `names`: tên sách theo mã ở máy tính, cho thư mục chưa có gói sách nào. */
export function storedEntries(sizes: StoredFolder[], library: ListenBook[], names: ReadonlyMap<string, string> = new Map()): StoredEntry[] {
  const byId = new Map(library.map((book) => [book.id, book]));
  return sizes
    .map(({ id, bytes, title }): StoredEntry => {
      const book = byId.get(id);
      const kind = book && !book.remote ? "book" : "partial";
      return { id, bytes, kind, title: book?.title || title || names.get(id) || "Sách tải dở" };
    })
    .sort((a, b) => b.bytes - a.bytes);
}

/** Cuốn có lượt tải còn chạy (chưa xong, lỗi hay huỷ): xoá thư mục của nó lúc này làm hỏng lượt tải. */
export function isDownloading(event: { finished?: boolean; error?: string; cancelled?: boolean } | undefined): boolean {
  return Boolean(event) && !event!.finished && !event!.error && !event!.cancelled;
}
