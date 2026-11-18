import { describe, expect, it } from "vitest";
import saveable from "../../../tests/fixtures/book_metadata/saveable.json";
import { cleanMetadata, metadataSaveable, type BookMetadata } from "./BookMetadata";

// Nút "Lưu thông tin" của hộp Sửa sách: so bản nháp như máy chủ sẽ làm sạch (book_metadata.clean) với thông tin đang có.
// Cùng ca với tests/test_book_metadata.py và desktop_qt tst_d2_editbook.qml.

describe("metadataSaveable", () => {
  for (const item of saveable.cases) {
    it(item.name, () => {
      expect(cleanMetadata(item.draft as BookMetadata)).toEqual(item.cleaned);
      expect(metadataSaveable(item.draft as BookMetadata, item.book as BookMetadata)).toBe(item.saveable);
    });
  }

  it("turns off once the reloaded book holds what the server kept", () => {
    const draft: BookMetadata = { author: "  Tô   Hoài ", genres: ["Fantasy", ""] };
    expect(metadataSaveable(draft, {})).toBe(true);
    expect(metadataSaveable(draft, { author: "Tô Hoài", genres: ["Fantasy"] })).toBe(false);
  });
});
