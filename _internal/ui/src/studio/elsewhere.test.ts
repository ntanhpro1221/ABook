import { describe, expect, it } from "vitest";
import { elsewhereNote, seenDelivery, seenFor, theirDelivery, verdictWord, voiceWas } from "./elsewhere";

// Soát a27 lỗi 4: mọi chỗ sửa gửi `seen`, lệch thì hỏi giữ của mình / lấy của máy kia.

describe("sửa cùng một chỗ từ hai máy", () => {
  it("sends what this card saw for every line of the click, nothing seen as empty", () => {
    expect(seenFor([{ stableId: "a" }, { stableId: "b" }], { a: "LUCIEN" })).toEqual({ a: "LUCIEN", b: "" });
    expect(seenFor([{ stableId: "a" }], undefined)).toEqual({ a: "" });
  });

  it("says what the other place had set, or that nobody had decided", () => {
    expect(elsewhereNote(1, "Rhine")).toEqual({
      title: "Chỗ này vừa được sửa ở máy hay cửa sổ khác",
      description: "Trước đó đang là Rhine - lần ghi của bạn đã thay nó.",
    });
    expect(elsewhereNote(3, "").title).toBe("3 câu vừa được sửa ở máy hay cửa sổ khác");
    expect(elsewhereNote(3, "").description).toBe("Trước đó chưa ai quyết khác - lần ghi của bạn đã thay nó.");
  });
});

describe("giọng, cách đọc một câu, thu lại (uxfix28 A)", () => {
  it("sends the delivery this screen saw without its state, and null when nobody had changed the line", () => {
    expect(seenDelivery({ kind: "", emotion: "sad", intensity: 2, state: "pending" } as never)).toEqual({ kind: "", emotion: "sad", intensity: 2 });
    expect(seenDelivery({ kind: "dialogue", emotion: "", intensity: null, spoken: "Chào." })).toEqual({ kind: "dialogue", emotion: "", intensity: null, spoken: "Chào." });
    expect(seenDelivery(null)).toBeNull();
    expect(seenDelivery(undefined)).toBeNull();
  });

  it("takes back only what the other machine had set, nothing when it had set nothing", () => {
    expect(theirDelivery({ kind: "", emotion: "sad", intensity: null, spoken: null })).toEqual({ emotion: "sad" });
    expect(theirDelivery({ kind: "thought", emotion: "", intensity: 0, spoken: "" })).toEqual({ kind: "thought", intensity: 0, spoken: "" });
    expect(theirDelivery({ kind: "", emotion: "", intensity: null, spoken: null })).toBeNull();
    expect(theirDelivery(null)).toBeNull();
  });

  it("names a verdict and a voice choice the way the listener saw them", () => {
    expect(verdictWord("ok")).toBe("“Ổn”");
    expect(verdictWord("redo")).toBe("“Cần thu lại”");
    expect(verdictWord("")).toBe("");
    expect(voiceWas({ voice: "Thanh Bình", gender: "" })).toBe("giọng Thanh Bình");
    expect(voiceWas({ voice: "", gender: "female" })).toBe("nhân vật nữ");
    expect(voiceWas({ voice: "", gender: "" })).toBe("");
  });
});
