import { describe, expect, it } from "vitest";
import { keepRequests, pickedLines, pickNote, toggleLine } from "@/studio/minorGroups";

const line = (stableId: string) => ({ stableId, textSha256: `sha-${stableId}` });

describe("chọn câu trên thẻ vai phụ cả cuốn", () => {
  const lines = [line("b"), line("d"), line("e"), line("g")];

  it("bỏ chọn rồi chọn lại một câu", () => {
    const left = toggleLine(new Set(), "d");
    expect(pickedLines(lines, left).map((picked) => picked.stableId)).toEqual(["b", "e", "g"]);
    expect(pickedLines(lines, toggleLine(left, "d"))).toEqual(lines);
  });

  it("không sửa tập cũ", () => {
    const left = new Set(["b"]);
    toggleLine(left, "e");
    expect([...left]).toEqual(["b"]);
  });

  it("nói đang chọn bao nhiêu câu", () => {
    expect(pickNote(4, 4)).toBe("Đang chọn cả 4 câu");
    expect(pickNote(3, 4)).toBe("Đang chọn 3/4 câu");
    expect(pickNote(0, 4)).toBe("Chưa chọn câu nào trong 4 câu");
  });
});

describe("giữ nguyên", () => {
  it("thẻ thường giữ người đang nói cho mọi câu", () => {
    expect(keepRequests({ lines: [line("a")], currentValue: "NPC_LOCAL::c1::r1::lính gác" })).toEqual([
      { lines: [line("a")], speaker: "NPC_LOCAL::c1::r1::lính gác" },
    ]);
  });

  it("thẻ nhóm giữ người của từng vai, bỏ vai không còn câu", () => {
    const keepGroups = [
      { speaker: "NPC_LOCAL::c1::r1::lính gác", lines: [line("b"), line("d")] },
      { speaker: "NPC_LOCAL::c2::r7::lính gác", lines: [line("e")] },
      { speaker: "NPC_LOCAL::c2::r9::lính gác", lines: [] },
    ];
    expect(keepRequests({ lines: [line("b"), line("d"), line("e")], keepGroups })).toEqual(keepGroups.slice(0, 2));
  });

  it("thẻ không có người đang nói thì không giữ được", () => {
    expect(keepRequests({ lines: [line("a")] })).toEqual([]);
  });
});
