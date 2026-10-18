import { describe, expect, it } from "vitest";
import { downloadShare, downloadText, isContinuation, moodOf, swapButton } from "./musicScenes";

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

describe("nhãn không khí của đoạn (soát UX a60)", () => {
  const calm = { peacefulness: 0.2, tension: 0.1 };
  it("giữ tên các cảm xúc mạnh như cũ, kể cả khi trục căng thẳng cao", () => {
    expect(moodOf({ valence: 0, tension: 0.9, emotions: { sadness: 0.8, tenderness: 0.6, joy: 0.2 } })).toBe("buồn · dịu dàng");
    expect(moodOf({ valence: 0, emotions: { fear: 0.5 } }, { fear: "sợ hãi" })).toBe("sợ hãi");
  });
  it("không cảm xúc nào đủ mạnh thì gọi theo căng thẳng trước, rồi vui/buồn", () => {
    expect(moodOf({ valence: -0.6, tension: 0.5, emotions: calm })).toBe("căng thẳng");
    expect(moodOf({ valence: -0.4, tension: 0.49, emotions: calm })).toBe("buồn");
    expect(moodOf({ valence: 0.4, tension: 0.2, emotions: calm })).toBe("tươi vui");
    expect(moodOf({ valence: 0.39, tension: 0.49, emotions: calm })).toBe("êm");
    expect(moodOf({ valence: -0.39, tension: -0.8, emotions: calm })).toBe("êm");
  });
  it("đoạn không có cảm xúc từng câu cũng được gọi tên theo trục đã chọn bài", () => {
    expect(moodOf({ valence: 0, tension: 0.7 })).toBe("căng thẳng");
    expect(moodOf({ valence: 0.1 })).toBe("êm");
  });
});
