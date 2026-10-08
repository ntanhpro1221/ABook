import { describe, expect, it } from "vitest";
import { toneLabel } from "@/listen/voiceTone";

describe("toneLabel", () => {
  it("nói âm sắc là so với giọng gốc", () => {
    expect(toneLabel("trầm hẳn")).toBe("chỉnh trầm hẳn so với giọng gốc");
    expect(toneLabel("hơi sáng")).toBe("chỉnh hơi sáng so với giọng gốc");
  });

  it("nhãn lạ giữ nguyên, rỗng thì rỗng", () => {
    expect(toneLabel(" lạ ")).toBe("lạ");
    expect(toneLabel("")).toBe("");
  });
});
