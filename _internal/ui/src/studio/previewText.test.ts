import { describe, expect, it } from "vitest";
import { previewCaption, refusalText, tryNote } from "./previewText";

describe("refusalText", () => {
  it("says why in plain words for the reasons the server gives", () => {
    expect(refusalText("producing", "x")).toContain("cuốn ấy xong");
    expect(refusalText("producing", "Máy đang phân tích cuốn “A”", true)).toBe("Máy đang phân tích cuốn “A”");
    expect(refusalText("gpu", "x")).toContain("Card đồ hoạ đang bận");
    expect(refusalText("studio", "x")).toContain("Cần cài phần làm sách");
  });

  it("falls back to the server's own message for any other refusal", () => {
    expect(refusalText("timeout", "Máy đọc thử quá lâu")).toBe("Máy đọc thử quá lâu");
    expect(refusalText(undefined, "Lỗi 500")).toBe("Lỗi 500");
    expect(refusalText(42, "Lỗi 500")).toBe("Lỗi 500");
  });
});

describe("previewCaption", () => {
  it("names the line and the voice, and promises only 'about like this'", () => {
    expect(previewCaption("“Đi thôi, Natasha.”", "Lucien")).toBe("Lúc thu thật sẽ nghe gần như vậy · câu “Đi thôi, Natasha.” · giọng Lucien");
  });

  it("cuts a long line and leaves the voice out when there is none to name", () => {
    const caption = previewCaption(`${"từ ".repeat(60)}cuối`, "");
    expect(caption).toContain("…”");
    expect(caption).not.toContain("giọng");
  });
});

describe("tryNote", () => {
  const idle = { pending: false, refusal: "", playing: false, caption: null, bookBusy: false };

  it("says nothing before the first try on an idle book", () => {
    expect(tryNote(idle)).toBeNull();
  });

  it("tells a book that is being recorded up front, in the listener's words", () => {
    expect(tryNote({ ...idle, bookBusy: true })).toContain("cuốn này xong");
  });

  it("says waiting, then playing, then done - never only a silent button", () => {
    expect(tryNote({ ...idle, pending: true })).toContain("Máy đang đọc thử");
    expect(tryNote({ ...idle, playing: true, caption: "câu mẫu" })).toBe("Đang phát · câu mẫu");
    expect(tryNote({ ...idle, caption: "câu mẫu" })).toContain("Đã nghe xong");
  });

  it("a refusal wins over everything but the wait", () => {
    expect(tryNote({ ...idle, refusal: "Card đồ hoạ đang bận", caption: "x", bookBusy: true })).toBe("Card đồ hoạ đang bận");
  });
});
