import { describe, expect, it } from "vitest";
import { ANALYSIS_CUT_COST, asksBeforeResume, stopAnalysisAdvice } from "./stopText";

describe("dừng và làm tiếp giữa pha phân tích (soát UX a23)", () => {
  it("đang tạm dừng thì hộp Dừng không mời bấm Tạm dừng (B14)", () => {
    expect(stopAnalysisAdvice({ paused: "listener", canPause: true })).not.toMatch(/bấm Tạm dừng/);
    expect(stopAnalysisAdvice({ paused: "listener", canPause: true })).toMatch(/đang tạm dừng/);
    expect(stopAnalysisAdvice({ paused: null, canPause: true })).toMatch(/bấm Tạm dừng/);
    expect(stopAnalysisAdvice({ paused: null, canPause: false })).toBe("");
  });

  it("nói đúng mức: có thể ra cuốn khác, không 'hơi khác' (B15)", () => {
    expect(ANALYSIS_CUT_COST).not.toMatch(/hơi/);
    expect(ANALYSIS_CUT_COST).toMatch(/cuốn khác/);
    expect(ANALYSIS_CUT_COST).toMatch(/người nói/);
    expect(ANALYSIS_CUT_COST).toMatch(/nhân vật/);
    expect(ANALYSIS_CUT_COST).toMatch(/giọng/);
  });

  it("chỉ hỏi trước khi làm tiếp lúc phân tích bị ngắt, sau pha phân tích thì không (B16)", () => {
    expect(asksBeforeResume({ phase: "analysis", analysisInterrupted: true })).toBe(true);
    expect(asksBeforeResume({ phase: "synthesis", analysisInterrupted: false })).toBe(false);
    expect(asksBeforeResume({ phase: "done", analysisInterrupted: true })).toBe(false);
  });
});
