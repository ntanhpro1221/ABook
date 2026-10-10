import { describe, expect, it } from "vitest";
import { creditKind, creditSummary, creditWhere } from "./credits";

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
