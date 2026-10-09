import { beforeEach, describe, expect, it, vi } from "vitest";
import { isLibrarySort, loadLibrarySort, saveLibrarySort, sortBooks } from "./librarySort";
import type { ListenBook } from "./model";

const book = (id: string, title: string, extra: Partial<ListenBook> = {}) => ({ id, title, ...extra }) as ListenBook;
const ids = (books: ListenBook[]) => books.map((item) => item.id);

describe("xếp sách trong thư viện", () => {
  const books = [
    book("a", "Tập 10", { author: "Nguyễn Nhật Ánh", addedAt: 100, updatedAt: 900 }),
    book("b", "Đêm trắng", { author: "Dostoevsky", addedAt: 300 }),
    book("c", "Ăn mày dĩ vãng", { addedAt: 200 }),
    book("d", "Tập 2", { author: "Nguyễn Nhật Ánh", updatedAt: 150 }),
    book("e", "Zebra", { author: "Anh Đức" }),
  ];

  it("Nghe gần đây: giữ thứ tự máy chủ đã xếp", () => {
    expect(sortBooks(books, "recent")).toBe(books);
  });

  it("Tên sách: bỏ dấu khi so, số theo giá trị", () => {
    // Ăn (an), Đêm (dem), Tập 2, Tập 10, Zebra
    expect(ids(sortBooks(books, "title"))).toEqual(["c", "b", "d", "a", "e"]);
  });

  it("Tên sách: Đ đứng cạnh D, không cuối bảng chữ cái", () => {
    const list = [book("1", "Em"), book("2", "Đào"), book("3", "Dưa"), book("4", "Ân")];
    expect(ids(sortBooks(list, "title"))).toEqual(["4", "2", "3", "1"]) // Ân, Đào (dao), Dưa (dua), Em;
  });

  it("Tác giả: sách không có tác giả đứng sau; cùng tác giả theo tên sách", () => {
    // Anh Đức, Dostoevsky, Nguyễn Nhật Ánh (Tập 2, Tập 10), rồi Ăn mày dĩ vãng không tác giả
    expect(ids(sortBooks(books, "author"))).toEqual(["e", "b", "d", "a", "c"]);
  });

  it("Mới thêm: cuốn vừa vào lên đầu; thiếu mốc thì lấy lần cập nhật, không có nữa thì cuối", () => {
    // b 300, c 200, d (cập nhật) 150, a 100, e không có mốc
    expect(ids(sortBooks(books, "added"))).toEqual(["b", "c", "d", "a", "e"]);
  });

  it("không đụng tới danh sách gốc", () => {
    const before = ids(books);
    sortBooks(books, "title");
    sortBooks(books, "author");
    sortBooks(books, "added");
    expect(ids(books)).toEqual(before);
  });

  it("cùng khoá thì giữ thứ tự cũ", () => {
    const same = [book("x", "Giống", { addedAt: 5 }), book("y", "Giống", { addedAt: 5 }), book("z", "Giống", { addedAt: 5 })];
    expect(ids(sortBooks(same, "title"))).toEqual(["x", "y", "z"]);
    expect(ids(sortBooks(same, "added"))).toEqual(["x", "y", "z"]);
  });
});

describe("nhớ cách xếp trên máy này", () => {
  // Môi trường thử là Node: không có localStorage thật.
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
    });
  });

  it("chưa chọn: Nghe gần đây", () => {
    expect(loadLibrarySort()).toBe("recent");
  });

  it("nhớ lựa chọn", () => {
    saveLibrarySort("author");
    expect(loadLibrarySort()).toBe("author");
  });

  it("giá trị lạ trong bộ nhớ: về mặc định", () => {
    localStorage.setItem("abook-library-sort", "random");
    expect(loadLibrarySort()).toBe("recent");
    expect(isLibrarySort("random")).toBe(false);
  });
});
