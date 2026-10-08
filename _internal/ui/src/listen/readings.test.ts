import { describe, expect, it } from "vitest";
import { readerHint } from "./labels";
import { cleanSpoken, readingFor, sentenceWords, trialReadings, wordCore, wordOf } from "./readings";

// "Đọc từ này là…": chữ người nghe giữ ra khoá gì, cách đọc gõ vào gửi đi thế nào (cùng luật khoá với abook/readaloud/readings.py,
// Readings.kt - bộ ví dụ chung tests/fixtures/book_edits/readings/).

describe("chữ người nghe giữ", () => {
  it("bỏ dấu câu và ngoặc hai đầu, giữ gạch / nháy ở giữa", () => {
    expect(wordCore("“Haruto,”")).toBe("Haruto");
    expect(wordCore("(Haruto-kun)!")).toBe("Haruto-kun");
    expect(wordCore("Lucien's")).toBe("Lucien's");
    expect(wordCore("…")).toBe("");
  });

  it("về NFC như khoá của máy chủ", () => {
    expect(wordCore("Tôkyô.")).toBe("Tôkyô");
  });

  it("chữ thứ mấy của câu theo đơn vị chữ hiện (như mốc từng chữ)", () => {
    const text = "“Haruto,” Kate nói.";
    expect(wordOf(text, 0)).toBe("Haruto");
    expect(wordOf(text, 1)).toBe("Kate");
    expect(wordOf(text, 2)).toBe("nói");
    expect(wordOf(text, 3)).toBe("");
  });
});

describe("cách đọc gõ vào", () => {
  it("gọn khoảng trắng như máy chủ làm sạch", () => {
    expect(cleanSpoken("  Ha  ru\ttô ")).toBe("Ha ru tô");
  });

  it("nghe thử: một mục cho đúng từ ấy; ô trống hay gõ đúng chữ của sách thì không có cách đọc riêng", () => {
    expect(trialReadings("“Haruto,”", " Ha ru tô")).toEqual({ Haruto: "Ha ru tô" });
    expect(trialReadings("Haruto", "")).toBeUndefined();
    expect(trialReadings("Haruto", "Haruto")).toBeUndefined();
  });

  it("cách đọc đang đặt: khớp đúng hoa thường, như lúc đọc", () => {
    const list = [{ surface: "Haruto", spoken: "Ha ru tô" }];
    expect(readingFor(list, "Haruto")).toBe("Ha ru tô");
    expect(readingFor(list, "haruto")).toBe("");
    expect(readingFor(undefined, "Haruto")).toBe("");
  });
});

describe("lời nhắc màn đọc nói cách mở “Đọc từ này là…”", () => {
  const base = { textOnly: true, canSpeak: true, timed: false, tapped: false, coarse: false, wish: false };

  it("chuột phải trên máy tính, giữ trên điện thoại; chỉ khi sửa được cuốn", () => {
    expect(readerHint({ ...base, readings: true })).toContain("Bấm chuột phải vào một chữ đọc sai để sửa cách đọc.");
    expect(readerHint({ ...base, coarse: true, tapped: true, readings: true })).toContain("Giữ vào một chữ đọc sai");
    expect(readerHint(base)).not.toContain("sửa cách đọc");
  });
});

describe("các từ của một câu (chọn từ muốn sửa cách đọc)", () => {
  it("mỗi từ một lần, bỏ dấu câu hai đầu, giữ thứ tự", () => {
    expect(sentenceWords("“Haruto,” Kate nói. Haruto cười.")).toEqual(["Haruto", "Kate", "nói", "cười"]);
    expect(sentenceWords("… !")).toEqual([]);
  });
});
