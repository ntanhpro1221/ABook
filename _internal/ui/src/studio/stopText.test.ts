import { describe, expect, it } from "vitest";
import { ANALYSIS_CUT_COST, ANALYSIS_STOP_FACT, asksBeforeResume, pauseNotice, queueWaitNotice, stopAnalysisAdvice } from "./stopText";

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

describe("lời của hộp Dừng và toast Tạm dừng / Tiếp tục (soát a88)", () => {
  it("hộp Dừng nói cả hai nửa: phần đã làm còn nguyên, làm tiếp mới có giá (T2)", () => {
    expect(ANALYSIS_STOP_FACT).toMatch(/được giữ nguyên/);
    expect(ANALYSIS_STOP_FACT).not.toMatch(/mất phần/);
    expect(`${ANALYSIS_STOP_FACT} - ${ANALYSIS_CUT_COST}`).toMatch(/làm tiếp từ chỗ dừng - có thể ra một cuốn khác/);
  });

  it("toast Tiếp tục không nói 'làm tiếp' khi máy chủ báo sách vẫn đang tạm dừng (T1)", () => {
    expect(pauseNotice(false, { paused: null }, false)).toMatchObject({ title: "Đang làm tiếp", warn: false });
    expect(pauseNotice(false, { paused: "battery" }, false)).toMatchObject({ title: "Sách vẫn đang tạm dừng", warn: true });
    expect(pauseNotice(false, { paused: "listener" }, false).description).toMatch(/chưa làm tiếp được/);
    expect(pauseNotice(false, { paused: null }, true).description).toMatch(/trên pin/);
    expect(pauseNotice(true, { paused: "listener" }, false).title).toBe("Đang tạm dừng");
  });

  it("cuốn xếp hàng sau cuốn đang tạm dừng nói vì sao chờ và làm gì, không khuyên Dừng giữa phân tích (T5)", () => {
    const manual = queueWaitNotice({ id: "a", title: "Sách A", paused: "listener" });
    expect(manual).toMatch(/Sách A/);
    expect(manual).toMatch(/Tiếp tục/);
    expect(manual).not.toMatch(/Dừng/);
    expect(queueWaitNotice({ id: "a", title: "Sách A", paused: "battery" })).toMatch(/cắm sạc/);
  });
});
