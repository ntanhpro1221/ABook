import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ChapterError } from "./ChapterError";

// Lỗi thô của từng chương ("RuntimeError: CUDA out of memory...") từng hiện nguyên văn trên hàng chương; nay là câu cho người nghe,
// nguyên văn nằm sau "Chi tiết".

describe("lỗi của một chương", () => {
  it("lỗi quen: câu tiếng Việt ở dòng chính, nguyên văn chỉ nằm trong khung chi tiết", () => {
    const html = renderToString(<ChapterError raw="RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB" />);
    const summary = html.slice(html.indexOf("<summary"), html.indexOf("</summary>"));
    expect(summary).toContain("Card đồ hoạ hết bộ nhớ.");
    expect(summary).toContain("Chi tiết");
    expect(summary).not.toContain("CUDA");
    expect(html).toContain("bấm Tiếp tục");
    expect(html).toContain("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB");
  });

  it("lỗi lạ: câu chung, không đọc nguyên văn lên mặt hàng chương", () => {
    const html = renderToString(<ChapterError raw="KeyError: 'speaker'" />);
    const summary = html.slice(html.indexOf("<summary"), html.indexOf("</summary>"));
    expect(summary).toContain("Có lỗi khi làm sách.");
    expect(summary).not.toContain("KeyError");
    expect(html).toContain("KeyError: &#x27;speaker&#x27;");
  });
});
