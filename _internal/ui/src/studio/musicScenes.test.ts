import { describe, expect, it } from "vitest";
import { downloadShare, downloadText, isContinuation, swapButton } from "./musicScenes";

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

describe("tải sẵn nhạc nền (soát UX a23 B12)", () => {
  it("báo MB đã tải / tổng khi biết cỡ, không thì đếm bài", () => {
    const mb = 1024 * 1024;
    const known = { active: true, done: 1, total: 3, doneBytes: 12 * mb, totalBytes: 30 * mb };
    expect(downloadText(known)).toBe("Đang tải sẵn nhạc nền: 12 MB / 30 MB (bài 2/3)");
    expect(downloadShare(known)).toBeCloseTo(0.4);
    const unknown = { active: true, done: 2, total: 2, doneBytes: 0, totalBytes: 0 };
    expect(downloadText(unknown)).toBe("Đang tải sẵn nhạc nền: bài 2/2");
    expect(downloadShare(unknown)).toBe(1);
  });
});
