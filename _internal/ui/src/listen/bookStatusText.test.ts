import { describe, expect, it } from "vitest";
import type { ListenBook } from "./model";
import { bookStatusText } from "./LibraryScreen";

// Thẻ sách chỉ có chữ ở Thư viện: dòng phụ nói tác giả (nếu có), không nói giọng nào đọc ("Hoài My (Edge)").

const book = (extra: Partial<ListenBook>) => ({ id: "x", stage: "text", chaptersTotal: 3, ...extra }) as unknown as ListenBook;

describe("bookStatusText - sách chỉ có chữ", () => {
  it("nói tác giả khi có", () => {
    expect(bookStatusText(book({ author: "Nguyễn Nhật Ánh" }), true)).toBe("Nguyễn Nhật Ánh · 3 chương");
  });
  it("không có tác giả: chỉ số chương, không nói tên giọng", () => {
    expect(bookStatusText(book({}), true)).toBe("3 chương");
    expect(bookStatusText(book({ author: "  " }), true)).toBe("3 chương");
  });
  it("máy chưa có giọng đọc: Chỉ có chữ", () => {
    expect(bookStatusText(book({}), false)).toBe("Chỉ có chữ · 3 chương");
  });
});
