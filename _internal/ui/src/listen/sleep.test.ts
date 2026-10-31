import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { remoteSleepAfter, remoteSleepCommand, remoteSleepMode, rewindAfter, sleepButtonLabel, sleepLabel, sleepSpoken } from "./sleep";

describe("hẹn giờ tắt của loa / TV", () => {
  it("đọc lời máy giữ phiên phát như hẹn giờ ở đây: chỉ trôi khi thiết bị đang phát", () => {
    const at = 1_000_000;
    const counting = remoteSleepMode({ kind: "minutes", minutes: 15, left: 600, counting: true }, at);
    expect(sleepLabel(counting, at)).toBe("10:00");
    expect(sleepLabel(counting, at + 30_000)).toBe("9:30");
    const paused = remoteSleepMode({ kind: "minutes", minutes: 15, left: 600, counting: false }, at);
    expect(sleepLabel(paused, at + 30_000)).toBe("10:00");
    expect(remoteSleepMode({ kind: "chapter" }, at)).toEqual({ kind: "chapter" });
    expect(remoteSleepMode(null, at)).toEqual({ kind: "off" });
    expect(remoteSleepMode(undefined, at)).toEqual({ kind: "off" });
  });

  it("gửi đúng lệnh cho từng lựa chọn, tắt là không phút nào", () => {
    expect(remoteSleepCommand({ kind: "minutes", minutes: 30 })).toEqual({ action: "sleep", minutes: 30 });
    expect(remoteSleepCommand({ kind: "chapter" })).toEqual({ action: "sleep", endOfChapter: true });
    expect(remoteSleepCommand({ kind: "off" })).toEqual({ action: "sleep", minutes: 0 });
  });

  it("nút đổi ngay khi bấm, trước khi loa / TV trả lời", () => {
    expect(remoteSleepAfter({ action: "sleep", minutes: 30 }, true)).toEqual({ kind: "minutes", minutes: 30, left: 1800, counting: true });
    expect(remoteSleepAfter({ action: "sleep", minutes: 30 }, false)).toEqual({ kind: "minutes", minutes: 30, left: 1800, counting: false });
    expect(remoteSleepAfter({ action: "sleep", endOfChapter: true }, true)).toEqual({ kind: "chapter" });
    expect(remoteSleepAfter({ action: "sleep", minutes: 0 }, true)).toBeNull();
  });
});

describe("nhãn trên nút hẹn giờ", () => {
  it("có đơn vị, không giống giờ đồng hồ", () => {
    const at = 1_000_000;
    const mode = remoteSleepMode({ kind: "minutes", minutes: 15, left: 891, counting: true }, at); // 14:51
    expect(sleepButtonLabel(mode, at)).toBe("15 phút");
    expect(sleepButtonLabel(mode, at + 40_000)).toBe("15 phút");
    expect(sleepButtonLabel(mode, at + 120_000)).toBe("13 phút");
    expect(sleepButtonLabel(mode, at + 850_000)).toBe("41 giây");
    expect(sleepButtonLabel({ kind: "chapter" }, at)).toBe("Hết chương");
    expect(sleepButtonLabel({ kind: "off" }, at)).toBe("");
  });

  it("còn 59,5 giây: không bao giờ \"60 giây\" - đồng hồ trong bảng đã là 1:00, nút và lời đọc nói 1 phút", () => {
    const at = 1_000_000;
    const mode = remoteSleepMode({ kind: "minutes", minutes: 5, left: 59.5, counting: false }, at);
    expect(sleepLabel(mode, at)).toBe("1:00");
    expect(sleepButtonLabel(mode, at)).toBe("1 phút");
    expect(sleepSpoken(mode, at)).toBe("Hẹn giờ ngủ: còn 1 phút");
    const later = remoteSleepMode({ kind: "minutes", minutes: 5, left: 59, counting: false }, at);
    expect(sleepButtonLabel(later, at)).toBe("59 giây");
    expect(sleepSpoken(later, at)).toBe("Hẹn giờ ngủ: còn 59 giây");
  });
});

describe("tự lùi khi nghe lại", () => {
  it("follows the cases shared with the Android player (tests/fixtures/auto_rewind)", () => {
    const shared = JSON.parse(readFileSync(new URL("../../../tests/fixtures/auto_rewind/cases.json", import.meta.url)).toString("utf8")) as {
      cases: [number, number][];
    };
    for (const [pausedMs, seconds] of shared.cases) expect(rewindAfter(pausedMs), `tạm dừng ${pausedMs} ms`).toBe(seconds);
  });
});
