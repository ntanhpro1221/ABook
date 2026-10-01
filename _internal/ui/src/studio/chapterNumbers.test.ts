import { describe, expect, it } from "vitest";
import { chapterNumber, chapterNumberIssues } from "./chapterNumbers";

const file = (name: string, firstLine = "") => ({ name, firstLine });

describe("chapterNumber", () => {
  it("reads the heading first, then the file name", () => {
    expect(chapterNumber("Chương 12: Gặp lại", "a.txt")).toBe(12);
    expect(chapterNumber("Hồi 3 - Quân Khuyển-nhung", "x.txt")).toBe(3);
    expect(chapterNumber("Trời đã sáng.", "0007 Mở màn.txt")).toBe(7);
    expect(chapterNumber("Trời đã sáng.", "Mở đầu.txt")).toBeNull();
  });
});

describe("chapterNumberIssues", () => {
  it("is quiet for a clean run", () => {
    expect(chapterNumberIssues([file("001.txt"), file("002.txt"), file("003.txt")])).toEqual([]);
  });

  it("names duplicates, gaps and backwards order", () => {
    const issues = chapterNumberIssues([
      file("a.txt", "Chương 10"),
      file("b.txt", "Chương 11"),
      file("c.txt", "Chương 11"),
      file("d.txt", "Chương 15"),
      file("e.txt", "Chương 9"),
    ]);
    expect(issues[0]).toContain("Chương 11 có 2 file (b.txt, c.txt)");
    expect(issues.some((line) => line.includes("chương 9 đứng sau chương 15"))).toBe(true);
    expect(issues.some((line) => line.includes("thiếu chương 12–14"))).toBe(true);
  });

  it("checks that a continued part starts right after the previous one", () => {
    expect(chapterNumberIssues([file("021.txt"), file("022.txt")], "020.txt")).toEqual([]);
    expect(chapterNumberIssues([file("019.txt"), file("020.txt")], "020.txt")[0]).toContain("làm lại các chương đã có");
    expect(chapterNumberIssues([file("024.txt"), file("025.txt")], "020.txt")[0]).toContain("thiếu chương 21–23");
  });

  it("does not guess for books without chapter numbers", () => {
    expect(chapterNumberIssues([file("Mở đầu.txt"), file("Gặp lại.txt"), file("Biển.txt")])).toEqual([]);
  });
});
