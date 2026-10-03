import { describe, expect, it } from "vitest";
import { failedSourcesNote } from "./CoverSearch";

describe("tìm bìa trên mạng", () => {
  it("nói tên nguồn như người đọc biết, không phải tên hàm của máy chủ", () => {
    const note = failedSourcesNote(["itunes", "open_library", "google_books"]);
    expect(note).toContain("iTunes, Open Library, Google Books");
    expect(note).not.toContain("google_books");
    expect(failedSourcesNote(["lạ_nguồn"])).toContain("lạ nguồn");
  });
});
