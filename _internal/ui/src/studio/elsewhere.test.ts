import { describe, expect, it } from "vitest";
import { elsewhereNote, seenFor } from "./elsewhere";

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
