import { describe, expect, it } from "vitest";
import { matchPhrase, shortcutHint, spokenEditLabel } from "@/studio/reviewText";

describe("chữ tab Cần nghe lại", () => {
  it("độ khớp nói khớp với cái gì", () => {
    expect(matchPhrase("15%")).toBe("máy nghe lại khớp 15% với chữ của câu");
  });

  it("nút sửa cách đọc nói tự nhiên và nhắc câu giống hệt", () => {
    expect(spokenEditLabel(0)).toBe("Sửa cách máy đọc câu này");
    expect(spokenEditLabel(3)).toBe("Sửa cách máy đọc câu này (còn 3 câu giống hệt)");
  });

  it("dòng phím tắt chỉ hiện khi đang nghe liền", () => {
    expect(shortcutHint(false)).toBeNull();
    expect(shortcutHint(true)).toContain("O");
  });
});
