import { describe, expect, it } from "vitest";
import { examplesPage, keepRequests, moreText, pickedLines, pickNote, toggleLine } from "@/studio/minorGroups";

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

describe("thẻ nhóm lớn: vài câu đầu, Xem thêm theo trang", () => {
  const first = ["a", "b", "c"];

  it("hỏi trang kế từ câu đã có, tới khi đủ tổng", () => {
    const page = examplesPage("sach", "pick:NGƯỜI HẦU", first, [], 7, 2);
    expect(page).toEqual({ loaded: first, total: 7, next: "/api/books/sach/work/examples?key=pick%3ANG%C6%AF%E1%BB%9CI%20H%E1%BA%A6U&offset=3&limit=2" });
    expect(examplesPage("sach", "k", first, ["d", "e"], 7, 2).next).toContain("offset=5&limit=2");
    expect(examplesPage("sach", "k", first, ["d", "e", "f", "g"], 7, 2)).toMatchObject({ loaded: ["a", "b", "c", "d", "e", "f", "g"], next: null });
  });

  it("thẻ đã mang đủ câu (bản chụp trong file dự án, nhóm nhỏ) không hỏi thêm", () => {
    expect(examplesPage("sach", "k", first, [], undefined, 100)).toEqual({ loaded: first, total: 3, next: null });
  });

  it("nút nói đang hiện bao nhiêu trên tổng", () => {
    expect(moreText(20, 900)).toBe("Xem thêm (đang hiện 20/900 câu)");
  });
});
