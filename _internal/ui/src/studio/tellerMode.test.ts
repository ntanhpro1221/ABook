import { describe, expect, it } from "vitest";
import { costText, needsConfirm, tellerHint, type TellerModeView, type TellerPlan } from "./tellerMode";

const plan = (over: Partial<TellerPlan> = {}): TellerPlan => ({ direction: "on", lines: 120, recorded: 80, seconds: 600, measured: true, tellers: ["MAI"], ...over });
const view = (over: Partial<TellerModeView> = {}): TellerModeView => ({ available: true, mode: "narrator", castLocked: true, applied: false, plan: plan(), ...over });

describe("costText", () => {
  it("nói số câu phải thu lại và thời gian khi đã có bản thu", () => {
    const text = costText(plan(), true);
    expect(text).toContain("120 câu lời kể sẽ đọc bằng giọng của MAI");
    expect(text).toContain("Thu lại 80 câu đã thu");
  });
  it("chưa thu câu nào thì nói thẳng là không tốn gì", () => {
    expect(costText(plan({ recorded: 0 }), true)).toContain("không phải thu lại gì");
  });
  it("tắt thì trả câu về giọng dẫn", () => {
    expect(costText(plan({ direction: "off" }), false)).toContain("sẽ trở về giọng dẫn");
  });
  it("không có câu nào thì không hứa gì", () => {
    expect(costText(plan({ lines: 0, recorded: 0 }), true)).toContain("Chưa có câu lời kể nào");
    expect(costText(null, false)).toContain("Không còn câu nào");
  });
});

describe("needsConfirm", () => {
  it("chỉ hỏi lại khi đã phân vai và có câu đã thu bị bỏ", () => {
    expect(needsConfirm(view())).toBe(true);
    expect(needsConfirm(view({ plan: plan({ recorded: 0 }) }))).toBe(false);
    expect(needsConfirm(view({ castLocked: false, plan: null }))).toBe(false);
    expect(needsConfirm(undefined)).toBe(false);
  });
});

describe("tellerHint", () => {
  it("mô tả cả hai trạng thái", () => {
    expect(tellerHint(false)).toContain("Mặc định");
    expect(tellerHint(true)).toContain("đọc bằng giọng của họ");
  });
});
