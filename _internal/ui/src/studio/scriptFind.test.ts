import { describe, expect, it } from "vitest";
import { findRanges, splitByRanges, wrapIndex } from "@/studio/scriptFind";

describe("ô tìm chữ trong kịch bản", () => {
  it("khớp không phân biệt hoa thường và dấu, trả vị trí trong chữ gốc", () => {
    const text = "Tuấn nhìn Đác-lát rồi Tuấn đi.";
    expect(findRanges(text, "tuan").map(([a, b]) => text.slice(a, b))).toEqual(["Tuấn", "Tuấn"]);
    expect(findRanges(text, "dac-lat").map(([a, b]) => text.slice(a, b))).toEqual(["Đác-lát"]);
    expect(findRanges(text, "  ")).toEqual([]);
    expect(findRanges(text, "xyz")).toEqual([]);
  });

  it("chữ gõ rời dấu (NFD) vẫn tô trọn ký tự", () => {
    const text = "Tuấn".normalize("NFD") + " đi";
    const [[a, b]] = findRanges(text, "tuan");
    expect(text.slice(a, b)).toBe("Tuấn".normalize("NFD"));
  });

  it("cắt đoạn để tô và chuyển vòng", () => {
    expect(splitByRanges("abcabc", [[1, 2], [4, 5]])).toEqual([["a", false], ["b", true], ["ca", false], ["b", true], ["c", false]]);
    expect([wrapIndex(3, 3), wrapIndex(-1, 3), wrapIndex(0, 0)]).toEqual([0, 2, 0]);
  });
});
