import { describe, expect, it } from "vitest";
import { reachSaved, reachSummary, type Reach } from "@/studio/readingReach";

const base: Reach = { surface: "TP.HCM", lines: 3, reached: 3, recorded: 2, blocked: 0, cost: "thu lại 2 câu", chapters: [], example: null };

describe("cách đọc cho từ bất kỳ nói trước nó chạm tới bao nhiêu câu", () => {
  it("nói số câu, số câu đã thu phải thu lại và chương", () => {
    const text = reachSummary({ ...base, chapters: [{ chapterId: 1, title: "Chương 1", lines: 2, recorded: 2 }, { chapterId: 4, title: "", lines: 1, recorded: 0 }] });
    expect(text).toBe("3 câu có chữ này · 2 câu đã thu sẽ được thu lại · ở Chương 1, chương 4");
  });

  it("chưa thu câu nào thì không hứa thu lại", () => {
    expect(reachSummary({ ...base, recorded: 0 })).toContain("chưa thu câu nào nên không phải thu lại");
    expect(reachSaved({ ...base, recorded: 0 }, "Máy áp từ chương sau.")).toBe("Các câu có chữ này chưa thu nên không phải thu lại. Máy áp từ chương sau.");
  });

  it("chữ chưa có câu nào, và chữ bị ký hiệu chặn, đều nói thật", () => {
    expect(reachSummary({ ...base, lines: 0, reached: 0, recorded: 0 })).toContain("Chưa có câu nào");
    const blocked = { ...base, surface: "km/h", lines: 2, reached: 0, recorded: 0, blocked: 2 };
    expect(reachSummary(blocked)).toContain("chưa dùng được");
    expect(reachSaved(blocked, "x")).not.toContain("thu lại");
  });
});
