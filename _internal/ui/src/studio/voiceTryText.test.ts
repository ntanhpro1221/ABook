import { describe, expect, it } from "vitest";
import { byGender, estimateText, rerecordText, tryKey } from "./voiceTryText";

const voices = [
  { name: "A", gender: "male" },
  { name: "B", gender: "female" },
  { name: "C", gender: "male" },
];

describe("byGender", () => {
  it("keeps one gender or all, in the server's order", () => {
    expect(byGender(voices, "male").map((voice) => voice.name)).toEqual(["A", "C"]);
    expect(byGender(voices, "female").map((voice) => voice.name)).toEqual(["B"]);
    expect(byGender(voices, "all").map((voice) => voice.name)).toEqual(["A", "B", "C"]);
  });
});

describe("estimateText", () => {
  it("says the book's own pace is from this machine", () => {
    expect(estimateText(25 * 60, true)).toBe("khoảng 25 phút trên máy này");
    expect(estimateText(25 * 60)).toBe("khoảng 25 phút trên máy này");
  });

  it("says a guess is a guess, and a short job is under a minute", () => {
    expect(estimateText(3 * 3600, false)).toBe("khoảng 3 giờ - ước chừng, vì cuốn chưa xong chương nào để đo");
    expect(estimateText(30, true)).toBe("chưa tới 1 phút trên máy này");
  });
});

describe("rerecordText", () => {
  it("names how many recorded lines a change records again", () => {
    expect(rerecordText("Noah", { lines: 1200, seconds: 2 * 3600, measured: true })).toBe(
      "Đổi giọng là thu lại 1.200 câu đã thu của Noah, khoảng 2 giờ trên máy này.",
    );
  });

  it("says nothing is lost when nothing is recorded yet", () => {
    expect(rerecordText("Noah", { lines: 0, seconds: 0, measured: false })).toBe(
      "Chưa câu nào của Noah được thu - đổi giọng không phải thu lại gì.",
    );
  });
});

describe("tryKey", () => {
  it("is one clip per book, character and voice", () => {
    const one = tryKey("b", { character: "NOAH", preset: "Thanh Bình" });
    expect(tryKey("b", { character: "NOAH", preset: "Thanh Bình" })).toBe(one);
    expect(tryKey("b", { character: "NOAH", preset: "Quốc Tuấn" })).not.toBe(one);
    expect(tryKey("b", { character: "NOAH", gender: "female" })).not.toBe(tryKey("b", { character: "NOAH", avoid: "female" }));
  });
});
