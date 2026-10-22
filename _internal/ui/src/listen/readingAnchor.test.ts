import { expect, it } from "vitest";
import { makeAnchor, restoreAnchor, textFingerprint } from "./readingAnchor";

it("cùng vân tay và offset Unicode với ReadingAnchorTest trên JVM", () => {
  const paragraphs = ["Chương một", "😀 Một hai ba.", "Đoạn sau."];
  expect(textFingerprint(paragraphs)).toBe("fnv1a64:bb657205cfbee8a0");
  const anchor = makeAnchor(paragraphs, 1, 2)!;
  expect(anchor.charOffset).toBe(6);
  expect(restoreAnchor(paragraphs, anchor)).toEqual({ segment: 1, word: 2 });
  expect(restoreAnchor([...paragraphs, "Mới"], anchor)).toBeUndefined();
  expect(restoreAnchor(paragraphs, { ...anchor, segment: 99 })).toBeUndefined();
  expect(restoreAnchor(paragraphs, { ...anchor, charOffset: 1.5 })).toBeUndefined();
});
