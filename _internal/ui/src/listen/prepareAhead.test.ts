import { describe, expect, it } from "vitest";
import type { ListenChapter } from "./model";
import {
  canPrepare,
  paragraphsFor,
  planLabel,
  prepareIntro,
  prepareLabel,
  prepareSeconds,
  readyChapterIds,
  spokenDuration,
  upcomingTextChapters,
} from "./prepareAhead";

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

describe("Làm trước trên điện thoại", () => {
  const chapters = (ready: number, total = 5) =>
    Array.from({ length: total }, (_, index) => ({ id: index + 1, title: `Chương ${index + 1}`, total: 4, done: index < ready ? 4 : 0, ready: index < ready }));

  it("giọng nào làm trước được", () => {
    expect(canPrepare({ provider: "vieneu", online: false }, false)).toBe(true);
    expect(canPrepare({ provider: "edge", online: true }, false)).toBe(false);
    expect(canPrepare({ provider: "edge", online: true }, true)).toBe(true);
    expect(canPrepare({ provider: "device", online: false }, true)).toBe(false);
    expect(prepareIntro({ online: true })).toContain("không có mạng");
    expect(prepareIntro({ online: false })).toContain("Máy đọc chậm");
  });

  it("tiến độ theo chương, còn bao lâu, đang chờ gì", () => {
    expect(prepareLabel({ state: "running", chapters: chapters(3), secondsLeft: 12 * 60 })).toBe("Đã sẵn sàng 3/5 chương · còn khoảng 12 phút");
    expect(prepareLabel({ state: "running", chapters: chapters(1), secondsLeft: 600, waitingFor: "charging" })).toBe("Đã sẵn sàng 1/5 chương · chờ cắm sạc");
    expect(prepareLabel({ state: "running", chapters: chapters(1), waitingFor: "wifi" })).toBe("Đã sẵn sàng 1/5 chương · chờ Wi-Fi");
    expect(prepareLabel({ state: "running", chapters: chapters(0), secondsLeft: null })).toBe("Đã sẵn sàng 0/5 chương");
    expect(prepareLabel({ state: "done", label: "5 chương tới", online: true, chapters: chapters(5), audioSeconds: 3600, total: 20, offered: 20 })).toBe(
      "Đã làm trước 5 chương tới (1 giờ nghe): nghe được cả khi không có mạng.",
    );
    expect(prepareLabel({ state: "done", chapters: chapters(3), total: 20, offered: 20 })).toBe("Đã sẵn sàng 3/5 chương - phần còn lại làm tiếp khi bạn nghe tới.");
    expect(prepareLabel({ state: "cancelled", chapters: chapters(2) })).toBe("Đã dừng làm trước (đã sẵn sàng 2/5 chương).");
    expect(prepareLabel({ state: "error", error: "Mất mạng nên đã dừng làm trước ở “Chương 3”." })).toBe("Mất mạng nên đã dừng làm trước ở “Chương 3”.");
  });

  it("ước trước khi bấm", () => {
    expect(planLabel({ chapters: 5, offered: 5, audioSeconds: 2 * 3600, secondsEstimate: 110 * 60 })).toBe("2 giờ nghe · máy cần khoảng 1 giờ 50 phút.");
    expect(planLabel({ chapters: 3, offered: 5, audioSeconds: 40 * 60, secondsEstimate: null })).toBe("Vừa chỗ trống cho 3 chương: 40 phút nghe.");
    expect(planLabel({ chapters: 0, offered: 0, audioSeconds: 0, secondsEstimate: null })).toBe("");
  });

  it("dấu đã làm sẵn chỉ cho đúng cuốn, đúng giọng", () => {
    const status = { state: "done" as const, bookId: "b1", voice: "edge:a", chapters: chapters(2) };
    expect([...readyChapterIds(status, "b1", "edge:a")]).toEqual([1, 2]);
    expect([...readyChapterIds(status, "b1", "")]).toEqual([1, 2]);
    expect(readyChapterIds(status, "b1", "edge:b").size).toBe(0);
    expect(readyChapterIds(status, "b2", "edge:a").size).toBe(0);
    expect(readyChapterIds({ state: "running", voice: "edge:a" }, "b1", "edge:a").size).toBe(0);
    expect(readyChapterIds(undefined, "b1", "").size).toBe(0);
  });
});
