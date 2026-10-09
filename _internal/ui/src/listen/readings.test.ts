import { describe, expect, it } from "vitest";
import { readerHint } from "./labels";
import { cleanSpoken, MAX_PHRASE_WORDS, phraseKey, pickWord, readingFor, sentenceTokens, trialReadings, wordCore, wordOf } from "./readings";

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

describe("cụm chữ liền nhau trong một câu (chọn nhiều chữ để sửa cách đọc)", () => {
  const tokens = sentenceTokens("“Hạ Vy,” Hạ, Vy nói - ông Tư!");

  it("tách từng chữ hiện, nhớ dấu câu còn dính ở đầu / đuôi", () => {
    expect(tokens.map((token) => token.core)).toEqual(["Hạ", "Vy", "Hạ", "Vy", "nói", "", "ông", "Tư"]);
    expect(tokens[0]).toMatchObject({ lead: true, tail: false });
    expect(tokens[1]).toMatchObject({ lead: false, tail: true });
    expect(tokens[2]).toMatchObject({ lead: false, tail: true });
  });

  it("khoá của cụm: dấu câu đầu cụm và đuôi cụm bỏ đi, dấu câu chen giữa thì không thành cụm", () => {
    expect(phraseKey(tokens, 0, 0)).toBe("Hạ");
    expect(phraseKey(tokens, 0, 1)).toBe("Hạ Vy");
    expect(phraseKey(tokens, 2, 3)).toBeNull();
    expect(phraseKey(tokens, 4, 6)).toBeNull();
    expect(phraseKey(tokens, 6, 7)).toBe("ông Tư");
    expect(phraseKey(tokens, 7, 7)).toBe("Tư");
  });

  it("tối đa 6 chữ", () => {
    const long = sentenceTokens("a b c d e f g");
    expect(MAX_PHRASE_WORDS).toBe(6);
    expect(phraseKey(long, 0, 5)).toBe("a b c d e f");
    expect(phraseKey(long, 0, 6)).toBeNull();
  });

  it("bấm chữ đầu rồi chữ cuối: thành cụm; bấm lại trong cụm hay cụm không hợp lệ thì chọn riêng chữ vừa bấm", () => {
    const first = pickWord(tokens, null, 0);
    expect(first).toEqual({ from: 0, to: 0 });
    expect(pickWord(tokens, first, 1)).toEqual({ from: 0, to: 1 });
    expect(pickWord(tokens, first, 0)).toEqual({ from: 0, to: 0 });
    expect(pickWord(tokens, { from: 0, to: 1 }, 1)).toEqual({ from: 1, to: 1 });
    expect(pickWord(tokens, { from: 2, to: 2 }, 3)).toEqual({ from: 3, to: 3 });
    expect(pickWord(tokens, { from: 7, to: 7 }, 6)).toEqual({ from: 6, to: 7 });
  });

  it("câu không có chữ nào: không có chữ để chọn", () => {
    expect(sentenceTokens("… !").every((token) => !token.core)).toBe(true);
  });
});
