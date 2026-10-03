import { describe, expect, it } from "vitest";
import { countTokens, LAST_WORD_HOLD_MS, splitPieces, usableWords, WORD_LEAD_MS, wordIndexAt, type WordSpan } from "./words";

const TEXT = "Trời vừa hửng sáng, sương mù.";
const WORDS: WordSpan[] = [
  [100, 400],
  [400, 600],
  [600, 900],
  [900, 1500],
  [1700, 2000],
  [2000, 2400],
];

describe("tách câu thành chữ hiện", () => {
  it("đếm đúng và ghép lại đúng từng ký tự", () => {
    expect(countTokens(TEXT)).toBe(6);
    const odd = "  Một hai \n ba  ";
    expect(countTokens(odd)).toBe(3);
    const pieces = splitPieces(odd);
    expect(pieces.map((piece) => piece.text).join("")).toBe(odd);
    expect(pieces.filter((piece) => piece.word >= 0).map((piece) => [piece.word, piece.text])).toEqual([[0, "Một"], [1, "hai"], [2, "ba"]]);
    expect(splitPieces("")).toEqual([]);
  });
});

describe("mốc chữ dùng được", () => {
  it("nhận khi đúng số chữ, hình và thứ tự", () => {
    expect(usableWords(TEXT, WORDS)).toBe(WORDS);
  });

  it("bỏ qua khi thiếu, sai số chữ, sai hình hay đi lùi", () => {
    expect(usableWords(TEXT, undefined)).toBeNull();
    expect(usableWords(TEXT, [])).toBeNull();
    expect(usableWords(TEXT, WORDS.slice(1))).toBeNull();
    expect(usableWords(TEXT, WORDS.map(([start]) => start))).toBeNull();
    expect(usableWords(TEXT, WORDS.map(([start, end]) => [start, end, 0]))).toBeNull();
    expect(usableWords(TEXT, WORDS.map(([start]) => [String(start), 1]))).toBeNull();
    expect(usableWords("a b", [[500, 600], [100, 200]])).toBeNull();
    expect(usableWords("a b", [[100, 50], [200, 300]])).toBeNull();
    expect(usableWords("a b", [[100, Number.NaN], [200, 300]])).toBeNull();
  });
});

describe("chữ đang đọc theo đồng hồ phát", () => {
  it("chưa tới chữ đầu thì chưa sáng chữ nào", () => {
    expect(wordIndexAt(WORDS, 0)).toBe(-1);
    expect(wordIndexAt(WORDS, 100 - WORD_LEAD_MS - 1)).toBe(-1);
  });

  it("sáng sớm một chút so với mốc bắt đầu", () => {
    expect(wordIndexAt(WORDS, 100 - WORD_LEAD_MS)).toBe(0);
    expect(wordIndexAt(WORDS, 399 - WORD_LEAD_MS)).toBe(0);
    expect(wordIndexAt(WORDS, 400 - WORD_LEAD_MS)).toBe(1);
  });

  it("đúng chữ ở giữa câu, kể cả lúc ngắt hơi: chữ trước vẫn sáng cho tới khi chữ sau bắt đầu", () => {
    expect(wordIndexAt(WORDS, 650)).toBe(2);
    expect(wordIndexAt(WORDS, 1600)).toBe(3);
    expect(wordIndexAt(WORDS, 1700 - WORD_LEAD_MS)).toBe(4);
    expect(wordIndexAt(WORDS, 2300)).toBe(5);
  });

  it("chữ cuối tắt sau một nhịp nếu câu kế chưa tới", () => {
    expect(wordIndexAt(WORDS, 2400 + LAST_WORD_HOLD_MS)).toBe(5);
    expect(wordIndexAt(WORDS, 2400 + LAST_WORD_HOLD_MS + 1)).toBe(-1);
  });

  it("đi hết một câu dài mà chỉ tăng, không nhảy lùi (mô phỏng nhịp khung hình 60 Hz)", () => {
    const long: WordSpan[] = Array.from({ length: 400 }, (_, i) => [i * 250, (i + 1) * 250]);
    let previous = -1;
    for (let ms = 0; ms < 400 * 250; ms += 16) {
      const index = wordIndexAt(long, ms);
      expect(index).toBeGreaterThanOrEqual(previous);
      expect(index - previous).toBeLessThanOrEqual(1);
      previous = index;
    }
    expect(previous).toBe(399);
  });
});
