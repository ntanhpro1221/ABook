import { describe, expect, it } from "vitest";
import { paragraphsOf, textScript } from "./textScript";

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
