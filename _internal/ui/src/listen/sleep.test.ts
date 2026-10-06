import { describe, expect, it } from "vitest";
import { remoteSleepAfter, remoteSleepCommand, remoteSleepMode, sleepLabel } from "./sleep";

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
