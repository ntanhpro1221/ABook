import { describe, expect, it } from "vitest";
import { isSourceRef, sourceName } from "./sourceRef";

describe("sourceName", () => {
  it("shows the last name of an upload reference, never the reference", () => {
    expect(sourceName("up:Lần gửi a1/Bộ truyện/Tập 1")).toBe("Tập 1");
    expect(sourceName("up:Cả truyện/tron bo.txt")).toBe("tron bo.txt");
    expect(sourceName("up:Truyện")).toBe("Truyện");
  });
  it("decodes the file name of a chapter reference", () => {
    expect(sourceName("ref:redo:abc-1:0:645%20M%E1%BB%9F.txt")).toBe("645 Mở.txt");
    expect(sourceName("ref:next:abc:12:647.txt")).toBe("647.txt");
  });
  it("keeps working for plain paths on the computer", () => {
    expect(sourceName("D:\\Truyện\\Tập 2")).toBe("Tập 2");
    expect(sourceName("D:/Truyện/a.txt")).toBe("a.txt");
  });
  it("tells references from paths", () => {
    expect(isSourceRef("up:a/b")).toBe(true);
    expect(isSourceRef("ref:redo:x:0:a.txt")).toBe(true);
    expect(isSourceRef("D:\\up:a")).toBe(false);
  });
});
