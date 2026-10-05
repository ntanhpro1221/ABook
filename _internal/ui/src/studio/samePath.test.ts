import { describe, expect, it } from "vitest";
import { samePath } from "./samePath";

describe("samePath", () => {
  it("treats / and \\ the same", () => {
    expect(samePath("D:/Truyện/whole.txt", "D:\\Truyện\\whole.txt")).toBe(true);
  });
  it("ignores a trailing slash and the case of a Windows path", () => {
    expect(samePath("d:\\truyện\\", "D:/Truyện")).toBe(true);
    expect(samePath("\\\\may\\Chung\\a.txt", "//MAY/chung/A.TXT")).toBe(true);
  });
  it("keeps the case of other paths and tells different files apart", () => {
    expect(samePath("/home/a/Whole.txt", "/home/a/whole.txt")).toBe(false);
    expect(samePath("D:/Truyện/a.txt", "D:/Truyện/b.txt")).toBe(false);
  });
  it("collapses doubled separators inside the path", () => {
    expect(samePath("D:\\\\Truyện//a.txt", "D:/Truyện/a.txt")).toBe(true);
  });
});
