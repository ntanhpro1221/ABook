import { describe, expect, it } from "vitest";
import { redoExportNote } from "./exportText";

describe("hộp Xuất khi có chương chờ thu lại (soát UX a25 T9)", () => {
  it("nói rõ bản xuất dùng bản thu cũ", () => {
    expect(redoExportNote(3, false)).toBe("3 chương đang chờ thu lại theo sửa của bạn - sách xuất dùng bản thu cũ của các chương ấy.");
    expect(redoExportNote(1, true)).toBe(
      "1 chương đang chờ thu lại theo sửa của bạn - sách xuất dùng bản thu cũ của các chương ấy; tên giọng ghi trong sách có thể đã là giọng mới.",
    );
  });

  it("không có chương nào chờ thì không nói gì", () => {
    expect(redoExportNote(0, true)).toBeNull();
  });
});
