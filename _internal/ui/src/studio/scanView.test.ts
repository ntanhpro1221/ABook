import { describe, expect, it } from "vitest";
import { formatNumber } from "@/shared/format";
import type { ScannedFile } from "./api";
import { allExcluded, approx, keepMatter, matterFiles, unpickedMatter } from "./scanView";

const file = (path: string, matter?: string): ScannedFile =>
  ({ path, name: path, title: path, firstLine: path, words: 10, audioSeconds: 3, chars: 40, bytes: 50, ...(matter ? { matter } : {}) }) as ScannedFile;

const files = [file("0001 Bìa.txt", "Trang bìa"), file("0002 Bản quyền.txt", "Trang bản quyền"), file("0003 Chương 1.txt"), file("0004 Chương 2.txt")];

describe("trang phụ của file sách (soát a98 F1)", () => {
  it("lists the front matter and leaves it out of the book until the user ticks it", () => {
    expect(matterFiles(files).map((row) => row.path)).toEqual(["0001 Bìa.txt", "0002 Bản quyền.txt"]);
    expect(unpickedMatter(files, [])).toEqual(["0001 Bìa.txt", "0002 Bản quyền.txt"]);
    expect(unpickedMatter(files, ["0002 Bản quyền.txt"])).toEqual(["0001 Bìa.txt"]);
  });

  it("adds what the user removed by hand without repeating a path", () => {
    expect(allExcluded(files, ["0003 Chương 1.txt", "0001 Bìa.txt"], [])).toEqual(["0003 Chương 1.txt", "0001 Bìa.txt", "0002 Bản quyền.txt"]);
  });

  it("ticking a page brings it back even after it was removed by hand, and unticking leaves it out again", () => {
    const state = { keepMatter: [] as string[], excluded: ["0001 Bìa.txt", "0004 Chương 2.txt"] };
    const ticked = keepMatter(state, "0001 Bìa.txt", true);
    expect(ticked).toEqual({ keepMatter: ["0001 Bìa.txt"], excluded: ["0004 Chương 2.txt"] });
    expect(allExcluded(files, ticked.excluded, ticked.keepMatter)).toEqual(["0004 Chương 2.txt", "0002 Bản quyền.txt"]);
    expect(keepMatter({ ...ticked }, "0001 Bìa.txt", false)).toEqual({ keepMatter: [], excluded: ["0004 Chương 2.txt"] });
  });

  it("a book with no front matter excludes only what the user removed", () => {
    expect(allExcluded([file("1.txt"), file("2.txt")], ["2.txt"], [])).toEqual(["2.txt"]);
  });
});

describe("số ước tính (soát a98 F7)", () => {
  it("marks counts taken from only the start of a long file", () => {
    expect(approx(5352007, true)).toBe(`~${formatNumber(5352007)}`);
    expect(approx(1200)).toBe(formatNumber(1200));
    expect(approx(1200, false).startsWith("~")).toBe(false);
  });
});
