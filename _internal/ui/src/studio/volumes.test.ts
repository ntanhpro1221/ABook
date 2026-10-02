import { describe, expect, it } from "vitest";
import { addStart, inOrder, moveStart, ranges, removeStart, startNumbers, volumeTitles } from "@/studio/volumes";

const files = ["a", "b", "c", "d", "e", "f"].map((path) => ({ path }));

describe("chỗ cắt tập", () => {
  it("lưu bằng đường dẫn, hiện bằng số chương, tập đầu luôn từ chương 1", () => {
    expect(startNumbers(files, ["a", "c", "e"])).toEqual([1, 3, 5]);
    expect(startNumbers(files, ["c", "e"])).toEqual([1, 3, 5]);
    expect(startNumbers(files, null)).toEqual([1]);
  });

  it("chương đầu tập bị bỏ thì tập bắt đầu ở chương còn lại kế tiếp", () => {
    expect(startNumbers(files, ["a", "c", "e"], new Set(["c"]))).toEqual([1, 3, 4]);
    expect(startNumbers(files, ["a", "d", "d"], new Set(["a", "b"]))).toEqual([1, 2]);
    expect(startNumbers(files, ["a", "f"], new Set(["f"]))).toEqual([1]);
    expect(startNumbers(files, ["zzz"])).toEqual([1]);
  });

  it("chia số chương thành các khoảng", () => {
    expect(ranges([1, 3, 6], 6)).toEqual([
      { start: 1, end: 2, chapters: 2 },
      { start: 3, end: 5, chapters: 3 },
      { start: 6, end: 6, chapters: 1 },
    ]);
  });

  it("sửa chỗ cắt chỉ trong khoảng giữa hai chỗ cắt bên cạnh", () => {
    expect(moveStart([1, 3, 6], 1, 5, 8)).toEqual([1, 5, 6].map((value) => value));
    expect(moveStart([1, 3, 6], 1, 6, 8)).toBeNull();
    expect(moveStart([1, 3, 6], 1, 1, 8)).toBeNull();
    expect(moveStart([1, 3, 6], 2, 8, 8)).toEqual([1, 3, 8]);
    expect(moveStart([1, 3, 6], 2, 9, 8)).toBeNull();
    expect(moveStart([1, 3, 6], 0, 2, 8)).toBeNull();
  });

  it("thêm và bỏ chỗ cắt", () => {
    expect(addStart([1, 5], 3, 8)).toEqual([1, 3, 5]);
    expect(addStart([1, 5], 5, 8)).toBeNull();
    expect(addStart([1, 5], 1, 8)).toBeNull();
    expect(addStart([1, 5], 9, 8)).toBeNull();
    expect(removeStart([1, 3, 5], 1)).toEqual([1, 5]);
    expect(removeStart([1, 3, 5], 0)).toEqual([1, 3, 5]);
  });

  it("xếp chương theo thứ tự của đề xuất", () => {
    expect(inOrder(files, ["b", "a", "c"]).map((file) => file.path)).toEqual(["b", "a", "c", "d", "e", "f"]);
    expect(inOrder(files, null)).toBe(files);
  });

  it("đặt tên như phần nối tiếp: tập 1 giữ tên, tập sau 'Tên · Phần N'", () => {
    expect(volumeTitles("Re:Zero", 3)).toEqual(["Re:Zero", "Re:Zero · Phần 2", "Re:Zero · Phần 3"]);
    expect(volumeTitles("Re:Zero · Phần 1", 2)).toEqual(["Re:Zero · Phần 1", "Re:Zero · Phần 2"]);
  });
});
