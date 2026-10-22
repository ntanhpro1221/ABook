import { describe, expect, it } from "vitest";
import { sameTitle, splitOutcome } from "./splitOffer";

describe("split offer and the lone title line", () => {
  it("compares book titles without case, spacing or accent form", () => {
    expect(sameTitle("Ngọn đèn cuối cùng", "  ngọn  ĐÈN cuối cùng ")).toBe(true);
    expect(sameTitle("Ngọn đèn cuối cùng".normalize("NFD"), "Ngọn đèn cuối cùng")).toBe(true);
    expect(sameTitle("Ngọn đèn", "Ngọn đèn cuối cùng")).toBe(false);
    expect(sameTitle("", "")).toBe(false);
  });

  it("a84_02 keeps the title line in the chapter count even when it also names the book", () => {
    const plan = { chapters: 5, preamble: true, titleLine: "Ngọn đèn cuối cùng" };
    expect(splitOutcome(plan, "Ngọn đèn cuối cùng")).toEqual({ chapters: 5, titleAsName: true, titleStays: true });
    expect(splitOutcome(plan, "Tên khác")).toEqual({ chapters: 5, titleAsName: false, titleStays: true });
  });

  it("leaves a plan without a lone title line alone", () => {
    expect(splitOutcome({ chapters: 4, preamble: true, titleLine: "" }, "x")).toEqual({ chapters: 4, titleAsName: false, titleStays: false });
    expect(splitOutcome({ chapters: 3, preamble: false }, "x").chapters).toBe(3);
  });
});
