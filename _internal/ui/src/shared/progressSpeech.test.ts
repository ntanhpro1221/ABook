import { describe, expect, it } from "vitest";
import { jobView, type ExportJob, type JobView } from "@/desktop/bookFileExport";
import { AUDIOBOOK_COPY } from "@/desktop/listenExport";
import { progressMilestone, spokenProgress } from "./progressSpeech";

// Soát a31 A6: thông báo tiến độ xuất ghi "đã m:ss" mỗi giây trong vùng aria-live - trình đọc màn hình đọc lại mỗi giây. Lời đọc chỉ đổi
// khi đổi pha hay qua mốc 25 %.

describe("spokenProgress", () => {
  it("chỉ đổi ở mốc 25 %", () => {
    expect([0, 0.1, 0.24, 0.25, 0.49, 0.5, 0.74, 0.99, 1].map(progressMilestone)).toEqual([0, 0, 0, 25, 25, 50, 50, 75, 100]);
    expect(spokenProgress("Đang tải sẵn nhạc nền", 0.37)).toBe(spokenProgress("Đang tải sẵn nhạc nền", 0.41));
    expect(spokenProgress("Đang tải sẵn nhạc nền", 0.51)).toBe("Đang tải sẵn nhạc nền · 50%");
  });

  it("không biết tiến độ thì chỉ nói pha", () => {
    expect(spokenProgress("Đang đóng gói sách…")).toBe("Đang đóng gói sách…");
    expect(progressMilestone(Number.NaN)).toBeNull();
  });
});

/** Dòng mô tả và lời đọc của một thông báo đang làm. */
function loading(view: JobView): { description: string; spoken?: string } {
  if (view.kind !== "loading") throw new Error(`không phải đang làm: ${view.kind}`);
  return view;
}

describe("jobView: lời đọc của thông báo đang xuất", () => {
  it("đồng hồ chạy (đã 0:05 -> 0:06) không đổi lời đọc", () => {
    const at = (elapsed: number) => loading(jobView({ state: "running", elapsed }, 10));
    expect(at(5).description).not.toBe(at(6).description);
    expect(at(5).spoken).toBe("Đang đóng gói sách…");
    expect(at(6).spoken).toBe(at(5).spoken);
  });

  it("xuất sách nói: lời đọc theo mốc 25 % và đổi khi sang pha ghép file", () => {
    const at = (percent: number, phase: ExportJob["phase"] = "voice") =>
      loading(jobView({ state: "running", phase, chapter: 2, chapters: 10, percent, secondsLeft: 90 - percent }, 0, false, AUDIOBOOK_COPY));
    expect(at(31).description).not.toBe(at(44).description);
    expect(at(31).spoken).toBe(at(44).spoken);
    expect(at(31).spoken).not.toBe(at(52).spoken);
    expect(at(99, "encode").spoken).toBe("Đang ghép file âm thanh");
  });
});
