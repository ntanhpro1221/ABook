import { describe, expect, it } from "vitest";
import { findInSegments, foldedQuery } from "./findText";
import { bookMatchesQuery, foldVietnamese } from "./model";

// Chữ của sách hay có hai dấu cách liền nhau (TXT, PDF) hay dấu cách không ngắt (tên sách "Tập 2"): người tìm gõ một dấu cách thường vẫn phải thấy.
describe("tìm khi chữ có nhiều khoảng trắng liền nhau", () => {
  it("Tìm trong sách: 'nguyen an' khớp 'Nguyễn  An' (hai dấu cách) và 'Nguyễn\\r\\nAn', tô đúng cả cụm", () => {
    const hits = findInSegments(1, [{ text: "Ông Nguyễn  An đến." }, { text: "Bà Nguyễn\r\nAn" }], foldedQuery("nguyen an"));
    expect(hits.map((hit) => hit.sentence)).toEqual([0, 1]);
    expect(hits[0].snippet.match).toBe("Nguyễn An");
    expect(hits[0].snippet.after).toBe(" đến.");
  });

  it("Tìm sách: 'tap 2' khớp tên có dấu cách không ngắt hay hai dấu cách", () => {
    const folded = foldVietnamese("tap 2");
    expect(bookMatchesQuery({ title: "Truyện · Tập 2", author: "", narrator: "" }, folded)).toBe(true);
    expect(bookMatchesQuery({ title: "Truyện Tập  2", author: "", narrator: "" }, folded)).toBe(true);
    expect(bookMatchesQuery({ title: "Truyện Tập 3", author: "", narrator: "" }, folded)).toBe(false);
  });
});
