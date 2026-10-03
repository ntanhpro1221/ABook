import { describe, expect, it } from "vitest";
import type { ListenChapter } from "./model";
import { paragraphsFor, prepareLabel, prepareSeconds, spokenDuration, upcomingTextChapters } from "./prepareAhead";

const chapter = (id: number, state: "text" | null = "text"): ListenChapter =>
  ({ id, index: id, title: `Chương ${id}`, subtitle: "", fullTitle: "", duration: 0, available: state !== "text", state }) as ListenChapter;

describe("Làm trước", () => {
  it("lấy các chương chỉ có chữ ngay sau chương đang nghe", () => {
    const queue = [chapter(1), chapter(2), chapter(3, null), chapter(4), chapter(5)];
    expect(upcomingTextChapters(queue, 1, 2).map((item) => item.id)).toEqual([2, 4]);
    expect(upcomingTextChapters(queue, 5)).toEqual([]);
  });

  it("chia đoạn đúng như trình phát", async () => {
    const texts = await paragraphsFor([chapter(2)], async () => "Đoạn một.\n\nĐoạn   hai.");
    expect(texts).toEqual(["Đoạn một.", "Đoạn hai."]);
    const skipped = await paragraphsFor([{ ...chapter(2), skip: ["Dịch: A"] }], async () => "Dịch: A\n\nĐoạn một.");
    expect(skipped).toEqual(["Đoạn một."]);
  });

  it("nói thời gian bằng lời", () => {
    expect(spokenDuration(20)).toBe("dưới 1 phút");
    expect(spokenDuration(12 * 60)).toBe("khoảng 12 phút");
    expect(spokenDuration(80 * 60)).toBe("khoảng 1 giờ 20 phút");
    expect(prepareSeconds(14 * 3600, 1.75)).toBe(1.75 * 3600);
  });

  it("câu tiến độ", () => {
    expect(prepareLabel({ state: "running", label: "3 chương tới", total: 10, done: 4, audioSeconds: 3600, secondsLeft: 600 })).toBe(
      "Đang làm trước 3 chương tới (1 giờ nghe): 4/10 đoạn, còn khoảng 10 phút.",
    );
    expect(prepareLabel({ state: "done", label: "Chương 2", total: 5, offered: 9 })).toContain("phần còn lại");
  });
});
