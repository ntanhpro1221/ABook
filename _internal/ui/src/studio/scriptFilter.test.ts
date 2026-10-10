import { describe, expect, it } from "vitest";
import { UNNAMED, visibleLines, type Line } from "@/studio/ScriptTab";

// Chip người nói LỌC câu (soát UX a23 B18), không chỉ làm mờ.

function line(stableId: string, kind: string, current: string, extra: Partial<Line> = {}): Line {
  return {
    segmentId: 1, stableId, textSha256: stableId, seq: 0, paragraph: 0, text: stableId, kind, speaker: current, current, label: current,
    editable: kind !== "narration", hasAudio: false, hint: null, wish: null, emotion: null, intensity: null, lineWish: null, spoken: null, ...extra,
  };
}

const lines = [
  line("a", "narration", "NARRATOR"),
  line("b", "dialogue", "LUCIEN"),
  line("c", "dialogue", "HEIDI", { hint: { kind: "turn", note: "x" } }),
  line("d", "thought", "LUCIEN", { hint: { kind: "unsure", note: "y" } }),
  line("e", "dialogue", UNNAMED),
  line("f", "dialogue", "HEIDI", { wish: { value: "LUCIEN", label: "Lucien", state: "pending" } }),
];

describe("chip người nói lọc câu", () => {
  it("không chọn ai thì như cũ", () => {
    expect(visibleLines(lines, "all", null).map((entry) => entry.line.stableId)).toEqual(["a", "b", "c", "d", "e", "f"]);
    expect(visibleLines(lines, "speech", null).map((entry) => entry.line.stableId)).toEqual(["b", "c", "d", "e", "f"]);
  });

  it("chọn một người thì chỉ còn câu nói của người ấy, câu đang chờ đổi tính theo người mới", () => {
    expect(visibleLines(lines, "all", "LUCIEN").map((entry) => entry.line.stableId)).toEqual(["b", "d", "f"]);
    expect(visibleLines(lines, "all", "HEIDI").map((entry) => entry.line.stableId)).toEqual(["c"]);
  });

  it("chip \"Chưa rõ\" (nhóm vô danh) lọc được, và lọc \"Máy nghi\" chỉ giữ chỗ nghi của người ấy", () => {
    expect(visibleLines(lines, "all", UNNAMED).map((entry) => entry.line.stableId)).toEqual(["e"]);
    expect(visibleLines(lines, "doubt", "LUCIEN").map((entry) => entry.line.stableId)).toEqual(["d"]);
    expect(visibleLines(lines, "doubt", null).map((entry) => [entry.line.stableId, entry.context])).toEqual([["b", true], ["c", false], ["d", false]]);
  });
});
