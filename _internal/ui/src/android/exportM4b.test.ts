import { describe, expect, it } from "vitest";
import { finishedView, progressText } from "./ExportM4b";

// Thông báo xuất M4B trên điện thoại dùng đúng chữ của máy tính (desktop/bookFileExport.ts jobView), thêm tiến độ chương.

describe("thông báo xuất M4B", () => {
  it("xong: tên file, cỡ, như máy tính", () => {
    expect(finishedView({ name: "Truyện.m4b", size: 3 * 1048576, chapters: 6, chaptersTotal: 6 })).toEqual({
      kind: "success",
      title: "Đã xuất M4B",
      description: "Truyện.m4b · 3 MB",
    });
  });

  it("còn chương chưa làm xong: nói số chương có trong file", () => {
    expect(finishedView({ name: "Truyện.m4b", size: 3 * 1048576, chapters: 4, chaptersTotal: 6 })).toMatchObject({
      description: "Truyện.m4b · 3 MB · 4/6 chương - chương chưa xong không có trong file",
    });
  });

  it("tiến độ: chương đã xong và phần trăm cả cuốn", () => {
    expect(progressText({}, 12)).toBe("12 chương");
    expect(progressText({ done: 3, total: 12, percent: 27 }, 12)).toBe("3/12 chương · 27%");
    expect(progressText({ done: 12, total: 12, percent: 100 }, 12)).toBe("12/12 chương · 99%");
    expect(progressText({ done: 0, total: 12 }, 12)).toBe("0/12 chương");
  });
});
