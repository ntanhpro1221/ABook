import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { BookCover } from "@/shared/BookCover";
import { coverColor } from "@/shared/cover";

const TRACKER = "url(https://tracker.invalid/a109-reader-unique)";

describe("màu bìa trong file sách của người khác", () => {
  it("chỉ nhận #rrggbb", () => {
    expect(coverColor("#0a141e")).toBe("#0a141e");
    expect(coverColor(" #0A141E ")).toBe("#0a141e");
    for (const bad of [TRACKER, "red", "#abc", "#aabbccdd", "#aabbcc;background:url(x)", "", undefined, null, 7]) {
      expect(coverColor(bad as never)).toBe("");
    }
  });

  it("bìa ảnh không bao giờ vẽ url() từ trường màu", () => {
    const image = { url: "/media/books/b/cover?v=1", color: TRACKER, width: 1, height: 1 };
    const html = renderToStaticMarkup(<BookCover title="Sách thử" image={image} />);
    expect(html).not.toContain("tracker.invalid");
    expect(html).not.toContain("url(");
  });

  it("màu hợp lệ vẫn là nền của bìa", () => {
    const image = { url: "/media/books/b/cover?v=1", color: "#0a141e", width: 1, height: 1 };
    expect(renderToStaticMarkup(<BookCover title="Sách thử" image={image} />)).toContain("background-color:#0a141e");
  });
});
