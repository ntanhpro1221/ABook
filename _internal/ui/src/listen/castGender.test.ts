import { describe, expect, it } from "vitest";
import { genderText } from "./castNarrator";

// Ô giới của tab Nhân vật không bao giờ trống và không bịa giới: cast.json để trống thì `genderNote` nói vì sao (Android
// Cast.genderText, Qt CastLogic.genderText - cùng chữ).
describe("genderText", () => {
  it("shows the recorded gender, else why it is empty", () => {
    expect(genderText({ gender: "Nữ" })).toBe("Nữ");
    expect(genderText({ gender: "", genderNote: "group" })).toBe("Nhóm");
    expect(genderText({ gender: "", genderNote: "child" })).toBe("Trẻ em");
    expect(genderText({ gender: "", genderNote: "unknown" })).toBe("Chưa rõ");
    expect(genderText({ gender: "" })).toBe("Chưa rõ");
  });
});
