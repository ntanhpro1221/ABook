import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  SCENE_BREAK_ALONE_GLYPHS,
  SCENE_BREAK_MAX_GLYPHS,
  SCENE_BREAK_MIN_RULE_GLYPHS,
  SCENE_BREAK_MS,
  SCENE_BREAK_ORNAMENT_GLYPHS,
  SCENE_BREAK_RULE_GLYPHS,
  isSceneBreakLine,
  paragraphsOf,
  sceneBreakGaps,
  splitParagraphs,
  textScript,
  withFreshSkips,
  withoutLines,
} from "./textScript";

// Bộ ví dụ DÙNG CHUNG với pytest (test_a_listen_scene_break_rule_is_shared.py) và test JVM (SceneBreakTest.kt): luật dòng ngăn cảnh của
// text_processing.is_scene_break_line và cách đọc to chia / lặng ở đó.
const SCENE = JSON.parse(readFileSync(new URL("../../../tests/fixtures/scene_break/cases.json", import.meta.url)).toString("utf8")) as {
  ms: number;
  ruleGlyphs: string;
  aloneGlyphs: string;
  ornamentGlyphs: string;
  minRuleGlyphs: number;
  maxGlyphs: number;
  separators: string[];
  loneSeparators: string[];
  notSeparators: string[];
  paragraphs: { name: string; text: string; paragraphs: string[]; breaks: boolean[]; gapsMs: number[] }[];
};

describe("dòng ngăn cảnh (bộ ví dụ dùng chung)", () => {
  it("has the constants of the Python rule", () => {
    expect(SCENE_BREAK_MS).toBe(SCENE.ms);
    expect(SCENE_BREAK_RULE_GLYPHS).toBe(SCENE.ruleGlyphs);
    expect(SCENE_BREAK_ALONE_GLYPHS).toBe(SCENE.aloneGlyphs);
    expect(SCENE_BREAK_ORNAMENT_GLYPHS).toBe(SCENE.ornamentGlyphs);
    expect(SCENE_BREAK_MIN_RULE_GLYPHS).toBe(SCENE.minRuleGlyphs);
    expect(SCENE_BREAK_MAX_GLYPHS).toBe(SCENE.maxGlyphs);
  });

  it("classifies the shared lines", () => {
    expect(SCENE.separators.filter((line) => !isSceneBreakLine(line))).toEqual([]);
    expect(SCENE.separators.filter((line) => !isSceneBreakLine(line, true))).toEqual([]);
    expect(SCENE.notSeparators.filter((line) => isSceneBreakLine(line))).toEqual([]);
    expect(SCENE.notSeparators.filter((line) => isSceneBreakLine(line, true))).toEqual([]);
    // một-hai dấu kẻ chỉ là ngăn cảnh khi đứng riêng một đoạn
    expect(SCENE.loneSeparators.filter((line) => isSceneBreakLine(line))).toEqual([]);
    expect(SCENE.loneSeparators.filter((line) => !isSceneBreakLine(line, true))).toEqual([]);
    expect(isSceneBreakLine("*".repeat(SCENE.maxGlyphs))).toBe(true);
    expect(isSceneBreakLine("*".repeat(SCENE.maxGlyphs + 1))).toBe(false);
  });

  it.each(SCENE.paragraphs)("splits and pauses: $name", ({ text, paragraphs, breaks, gapsMs }) => {
    const split = splitParagraphs(text);
    expect(paragraphsOf(text)).toEqual(paragraphs);
    expect(split.map((paragraph) => paragraph.sceneBreak)).toEqual(breaks);
    expect(sceneBreakGaps(split)).toEqual(gapsMs);
    // the flag rides on the reader's segments (the player reads it from there)
    expect(textScript(1, "t", text).segments.map((segment) => segment.sceneBreak === true)).toEqual(breaks);
  });

  it("does not let an unreadable non-separator line (an ellipsis) cut a run of separators", () => {
    expect(sceneBreakGaps(["A.", "***", "...", "◆", "B."].map((text) => ({ text })))).toEqual([0, SCENE_BREAK_MS, 0, 0, 0]);
  });
});

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

describe("withFreshSkips", () => {
  const chapter = (id: number, skip?: string[]) => ({ id, index: id, title: `Chương ${id}`, subtitle: "", fullTitle: `Chương ${id}`, duration: 0, available: true, part: null, state: "text" as const, ...(skip ? { skip } : {}) });

  it("brings the lines skipped after the queue was loaded into the queue's chapters (the voice and the next script read the new ones)", () => {
    const queue = [chapter(1), chapter(2)];
    const fresh = [chapter(1), chapter(2, ["Dịch: Nhóm A"])];
    const next = withFreshSkips(queue, fresh);
    expect(next).not.toBe(queue);
    expect(next[0]).toBe(queue[0]);
    expect(next[1].skip).toEqual(["Dịch: Nhóm A"]);
    expect(textScript(2, "Chương 2", "Chương 2\n\nDịch: Nhóm A\n\nMở đầu.", next[1].skip).segments).toHaveLength(2);
  });

  it("drops the lines that were taken back, and leaves the very same queue when nothing changed", () => {
    const queue = [chapter(1, ["Dịch: Nhóm A"])];
    expect(withFreshSkips(queue, [chapter(1)])[0].skip).toBeUndefined();
    expect(withFreshSkips(queue, [chapter(1, ["Dịch: Nhóm A"])])).toBe(queue);
    expect(withFreshSkips(queue, undefined)).toBe(queue);
  });
});
