import { describe, expect, it } from "vitest";
import { isContinuation, swapButton } from "./musicScenes";

describe("continued music pieces", () => {
  it("shows a piece that only keeps the track above playing as a continuation", () => {
    expect(isContinuation({ link: "a", continued: true })).toBe(true);
    expect(isContinuation({ link: "a" })).toBe(false);
  });

  it("treats a pinned, silenced or trackless piece as its own choice", () => {
    expect(isContinuation({ link: "a", continued: true, pinned: true })).toBe(false);
    expect(isContinuation({ link: null, continued: true, silenced: true })).toBe(false);
    expect(isContinuation({ link: null, continued: true })).toBe(false);
  });

  it("says that swapping a continuation changes the track from there on", () => {
    expect(swapButton({ link: "a", continued: true }).text).toBe("Đổi từ đây");
    expect(swapButton({ link: "a", continued: true }).title).toMatch(/từ chỗ này trở đi/);
    expect(swapButton({ link: "a" })).toEqual({ text: "Đổi bài" });
  });
});
