import { foldVietnamese, type ListenBook } from "./model";

// Thứ tự sách trong Thư viện (máy tính và điện thoại dùng chung): mặc định "Nghe gần đây" - thứ tự máy chủ đã xếp theo lần nghe cuối;
// người nghe đổi được sang tên sách, tác giả, hay mới thêm. Nhớ lựa chọn trên từng máy (localStorage của máy / WebView), như các cài đặt nhỏ khác.

export type LibrarySort = "recent" | "title" | "author" | "added";

export const SORT_OPTIONS: { value: LibrarySort; label: string }[] = [
  { value: "recent", label: "Nghe gần đây" },
  { value: "title", label: "Tên sách" },
  { value: "author", label: "Tác giả" },
  { value: "added", label: "Mới thêm" },
];

const KEY = "abook-library-sort";

export function isLibrarySort(value: unknown): value is LibrarySort {
  return SORT_OPTIONS.some((option) => option.value === value);
}

/** Cách xếp đã chọn lần trước trên máy này; chưa chọn (hay không đọc được) thì "Nghe gần đây". */
export function loadLibrarySort(): LibrarySort {
  try {
    const value = localStorage.getItem(KEY);
    return isLibrarySort(value) ? value : "recent";
  } catch {
    return "recent";
  }
}

export function saveLibrarySort(sort: LibrarySort): void {
  try {
    localStorage.setItem(KEY, sort);
  } catch {
    /* không nhớ được thì lần sau về mặc định */
  }
}

/** So tên theo tiếng Việt: bỏ dấu khi so (Ă, Â, Đ... đứng theo chữ gốc), "Tập 2" đứng trước "Tập 10". */
function compareNames(a: string, b: string): number {
  return foldVietnamese(a).localeCompare(foldVietnamese(b), "vi", { numeric: true });
}

/**
 * Xếp sách theo `sort`. "recent" giữ nguyên thứ tự nhận vào (máy chủ đã xếp theo lần nghe cuối). Các kiểu khác: cùng khoá thì giữ
 * thứ tự cũ (sắp xếp ổn định); sách không có tác giả đứng sau, theo tên. "Mới thêm": cuốn vừa vào thư viện lên đầu (không có mốc
 * thì lấy lần cập nhật cuối, không có nữa thì cuối).
 */
export function sortBooks(books: ListenBook[], sort: LibrarySort): ListenBook[] {
  if (sort === "recent") return books;
  const copy = [...books];
  if (sort === "title") return copy.sort((a, b) => compareNames(a.title, b.title));
  if (sort === "author") {
    return copy.sort((a, b) => {
      const left = a.author?.trim() ?? "";
      const right = b.author?.trim() ?? "";
      if (!left !== !right) return left ? -1 : 1;
      return compareNames(left, right) || compareNames(a.title, b.title);
    });
  }
  const added = (book: ListenBook) => book.addedAt ?? book.updatedAt ?? 0;
  return copy.sort((a, b) => added(b) - added(a));
}
