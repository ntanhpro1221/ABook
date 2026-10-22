import { describe, expect, it } from "vitest";
import { MEASURED_ON, estimate, matchesMeasured, timeBasis } from "./timeEstimate";

// Soát a92 T2: thời gian hứa là số đo của MỘT máy; máy khác / model phân tích khác chỉ được khoảng rộng, và nhãn không nhận là "máy này".

describe("matchesMeasured", () => {
  it("chỉ coi là máy đã đo khi cùng loại card và dùng model phân tích mặc định", () => {
    const card = { name: "NVIDIA GeForce RTX 5060 Laptop GPU", memory: 8 * 1024 ** 3 };
    expect(matchesMeasured(card, "")).toBe(true);
    expect(matchesMeasured(card, "qwen3.5:9b")).toBe(false);
    expect(matchesMeasured({ name: "NVIDIA GeForce RTX 3060", memory: 12 * 1024 ** 3 }, "")).toBe(false);
    expect(matchesMeasured(null, "")).toBe(false);
  });
});

describe("estimate", () => {
  it("máy đã đo: đúng số đo", () => {
    const exact = estimate(113_000, 100, true);
    expect(exact.analysis).toBeCloseTo(113 * 2.1 * 60, 5);
    expect(exact.totalLow).toBeCloseTo(113 * (2.1 + 2.5) * 60, 5);
    expect(exact.totalHigh).toBeCloseTo(113 * (2.1 + 3.8) * 60, 5);
  });
  it("máy khác: khoảng rộng, bao cả số đo và rộng hơn hai phía", () => {
    const exact = estimate(113_000, 100, true);
    const wide = estimate(113_000, 100, false);
    expect(wide.totalLow).toBeLessThan(exact.totalLow);
    expect(wide.totalHigh).toBeGreaterThan(exact.totalHigh * 2);
    expect(wide.analysisHigh).toBeGreaterThan(wide.analysisLow);
    expect(wide.firstChapter).toBeGreaterThan(exact.firstChapter);
  });
});

describe("timeBasis", () => {
  it("không bao giờ nhận số đo của máy khác là của máy này", () => {
    for (const exact of [true, false]) {
      const text = timeBasis(exact);
      expect(text).not.toMatch(/Trên (máy này|máy tính)/);
      expect(text).toContain("tham khảo");
      expect(text).toContain(MEASURED_ON);
    }
    expect(timeBasis(false)).toContain("máy của bạn có thể");
  });
});
