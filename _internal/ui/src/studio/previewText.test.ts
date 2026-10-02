import { describe, expect, it } from "vitest";
import { previewCaption, refusalText } from "./previewText";

describe("refusalText", () => {
  it("says why in plain words for the reasons the server gives", () => {
    expect(refusalText("producing", "x")).toBe("Đang làm sách - nghe thử khi máy rảnh");
    expect(refusalText("gpu", "x")).toBe("Card đồ hoạ đang bận");
    expect(refusalText("studio", "x")).toBe("Cần cài phần làm sách trước");
  });

  it("falls back to the server's own message for any other refusal", () => {
    expect(refusalText("timeout", "Máy đọc thử quá lâu")).toBe("Máy đọc thử quá lâu");
    expect(refusalText(undefined, "Lỗi 500")).toBe("Lỗi 500");
    expect(refusalText(42, "Lỗi 500")).toBe("Lỗi 500");
  });
});

describe("previewCaption", () => {
  it("names the line and the voice, and promises only 'about like this'", () => {
    expect(previewCaption("“Đi thôi, Natasha.”", "Lucien")).toBe("Bản thu đầu sẽ gần như vầy · câu “Đi thôi, Natasha.” · giọng Lucien");
  });

  it("cuts a long line and leaves the voice out when there is none to name", () => {
    const caption = previewCaption(`${"từ ".repeat(60)}cuối`, "");
    expect(caption).toContain("…”");
    expect(caption).not.toContain("giọng");
  });
});
