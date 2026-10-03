import { describe, expect, it } from "vitest";
import { paragraphsOf, textScript, withoutLines } from "./textScript";

// Cùng các ca với ParagraphsTest.kt (Paragraphs.withoutLines): lõi đọc to của điện thoại phải chia ra đúng các đoạn như màn đọc.
describe("withoutLines", () => {
  it("skips only the chosen lines among the first six of the chapter", () => {
    const text = "Chương 2\n\nDịch:  Nhóm A\n\nMở đầu.\n\nDịch: Nhóm A";
    expect(paragraphsOf(withoutLines(text, ["Dịch: Nhóm A"]))).toEqual(["Chương 2", "Mở đầu."]);
    expect(withoutLines(text, [])).toBe(text);
    const late = [1, 2, 3, 4, 5, 6].map((n) => `Dòng ${n}.`).join("\n") + "\nDịch: Nhóm A";
    expect(paragraphsOf(withoutLines(late, ["Dịch: Nhóm A"]))).toHaveLength(7);
  });

  it("is what the reader shows when the listener skipped a credit line", () => {
    const script = textScript(2, "Chương 2", "Chương 2\n\nDịch: Nhóm A\n\nMở đầu.", ["Dịch: Nhóm A"]);
    expect(script.segments.map((segment) => segment.text)).toEqual(["Chương 2", "Mở đầu."]);
  });
});

describe("paragraphsOf", () => {
  it("splits on blank lines and joins the lines a typesetter broke", () => {
    expect(paragraphsOf("Một dòng bị\nbẻ giữa chừng.\n\nĐoạn hai.\r\n\r\n\r\nĐoạn ba.\n")).toEqual([
      "Một dòng bị bẻ giữa chừng.",
      "Đoạn hai.",
      "Đoạn ba.",
    ]);
  });

  it("takes each line as a paragraph when the file has no blank line at all", () => {
    expect(paragraphsOf("Dòng một.\nDòng hai.\n  Dòng ba.  \n")).toEqual(["Dòng một.", "Dòng hai.", "Dòng ba."]);
  });

  it("keeps each line a paragraph in a file that has only a few blank lines (one after the title)", () => {
    expect(paragraphsOf("Chương 1\n\nDòng một.\nDòng hai!\n“Dòng ba?”\nDòng bốn")).toEqual([
      "Chương 1",
      "Dòng một.",
      "Dòng hai!",
      "“Dòng ba?”",
      "Dòng bốn",
    ]);
    expect(paragraphsOf(`Tựa\n\n${"x".repeat(201)}\nkhông dấu`)).toEqual(["Tựa", "x".repeat(201), "không dấu"]);
  });

  it("still joins lines a typesetter broke mid-sentence, even if one of them ends a sentence", () => {
    expect(paragraphsOf("A\n\nMột dòng dài bị bẻ,\nmột dòng nữa kết thúc.\nRồi câu sau tiếp\nvà hết.")).toEqual([
      "A",
      "Một dòng dài bị bẻ, một dòng nữa kết thúc. Rồi câu sau tiếp và hết.",
    ]);
  });

  it("gives nothing for an empty chapter", () => {
    expect(paragraphsOf("\n \n\n")).toEqual([]);
  });
});

describe("textScript", () => {
  it("is an untimed script whose first paragraph is the heading when it is the chapter title", () => {
    const script = textScript(3, "Chương 3: Cơn mưa", "Chương 3: Cơn mưa\n\nMưa kéo đến.\n\nÔng Tám đứng dậy.\n");
    expect(script.timed).toBe(false);
    expect(script.segments.map((segment) => [segment.kind, segment.text])).toEqual([
      ["heading", "Chương 3: Cơn mưa"],
      ["narration", "Mưa kéo đến."],
      ["narration", "Ông Tám đứng dậy."],
    ]);
    expect(script.segments.every((segment) => segment.start === null && segment.speaker === "")).toBe(true);
    expect(new Set(script.segments.map((segment) => segment.paragraph)).size).toBe(3);
  });

  it("does not take a first sentence for the heading when it is not the title", () => {
    const script = textScript(1, "Chương 1", "Chương 1 - Khởi đầu\n\nNội dung.");
    expect(script.segments[0].kind).toBe("narration");
  });
});
