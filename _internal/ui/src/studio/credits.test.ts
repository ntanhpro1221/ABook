import { describe, expect, it } from "vitest";
import { creditKind, creditLine, creditRows, creditSummary, creditWhere, droppedLines, KEEP_CREDITS } from "./credits";

describe("lines the book creator offers to leave out", () => {
  it("counts the first lines as before when no chapter ends with a support line", () => {
    const credits = creditSummary([{ credits: ["TL : NicK"] }, { credits: ["TL : NicK"] }, { credits: [] }]);
    expect(credits).toEqual({ lines: 2, head: 2, tail: 0, chapters: 2, examples: ["“TL : NicK”"] });
    expect(creditKind(credits)).toBe("dòng ghi công");
    expect(creditWhere(credits)).toBe("dòng ghi công người dịch ở đầu chương");
  });

  it("lists the end-of-chapter lines too, marked so", () => {
    const credits = creditSummary([
      { credits: ["TL : NicK"], tailCredits: ["Ủng hộ qua Momo 0912345678"] },
      { credits: [], tailCredits: ["Đọc truyện full tại truyenfull.vn"] },
      { credits: ["Editor: Deemo"] },
    ]);
    expect(credits.lines).toBe(4);
    expect(credits.chapters).toBe(3);
    expect(credits.examples).toEqual(["“TL : NicK”", "“Editor: Deemo”", "“Ủng hộ qua Momo 0912345678” (cuối chương)"]);
    expect(creditKind(credits)).toBe("dòng ghi công, xin ủng hộ, quảng cáo");
  });

  it("names only the end of the chapter when that is all there is", () => {
    const credits = creditSummary([{ tailCredits: ["Hết chương 8"] }]);
    expect(credits.examples).toEqual(["“Hết chương 8” (cuối chương)"]);
    expect(creditWhere(credits)).toBe("dòng xin ủng hộ, quảng cáo hay nguồn ở cuối chương");
  });
});

describe("xem hết rồi bỏ riêng đầu / cuối chương (soát UX a24, A9)", () => {
  const files = [
    { name: "1.txt", credits: ["TL : NicK"], tailCredits: ["Ủng hộ qua Momo"] },
    { name: "2.txt", credits: [] },
    { name: "3.txt", tailCredits: ["Hết chương 3", "Nguồn: truyenfull.vn"] },
  ];

  it("liệt kê MỌI dòng theo chương, không chỉ ba dòng mẫu", () => {
    expect(creditRows(files, (file) => file.name)).toEqual([
      { chapter: "1.txt", head: ["TL : NicK"], tail: ["Ủng hộ qua Momo"] },
      { chapter: "3.txt", head: [], tail: ["Hết chương 3", "Nguồn: truyenfull.vn"] },
    ]);
  });

  it("bỏ riêng từng loại: đếm đúng số dòng sẽ bỏ", () => {
    const credits = creditSummary(files);
    expect(droppedLines(credits, KEEP_CREDITS)).toBe(0);
    expect(droppedLines(credits, { head: true, tail: false })).toBe(1);
    expect(droppedLines(credits, { head: false, tail: true })).toBe(3);
    expect(droppedLines(credits, { head: true, tail: true })).toBe(4);
  });

  it("chỉ bỏ cuối chương: danh sách nói rõ dòng đầu chương vẫn được đọc (soát UX a25 T8)", () => {
    const drop = { head: false, tail: true };
    expect(creditLine("Dịch: Nhóm Lục Bình", "head", drop)).toEqual({ text: "“Dịch: Nhóm Lục Bình” (đầu chương, vẫn đọc)", dropped: false });
    expect(creditLine("Ủng hộ qua Momo", "tail", drop)).toEqual({ text: "“Ủng hộ qua Momo” (cuối chương, bỏ)", dropped: true });
    expect(creditLine("TL : NicK", "head", KEEP_CREDITS)).toEqual({ text: "“TL : NicK” (đầu chương)", dropped: false });
  });
});
