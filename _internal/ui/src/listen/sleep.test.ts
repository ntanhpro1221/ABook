import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { remoteSleepAfter, remoteSleepCommand, remoteSleepMode, rewindAfter, sleepButtonLabel, sleepExtendLabel, sleepExtendMinutes, sleepExtended, sleepFrom, sleepLabel, sleepLeftMs, sleepSafetyNet, sleepSpoken } from "./sleep";

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

describe("nghe thêm là hẹn lại, không cộng dồn", () => {
  const at = 5_000_000;
  const minutesLeft = (mode: ReturnType<typeof sleepFrom>, now: number) => (sleepLeftMs(mode, now) ?? 0) / 60_000;

  it("hẹn 10 phút, còn 7 phút, bấm ba lần: còn 10 phút chứ không phải 37", () => {
    let mode = sleepFrom({ kind: "minutes", minutes: 10 }, true, at);
    const later = at + 3 * 60_000;
    for (let i = 0; i < 3; ++i) mode = sleepExtended(mode, 10, true, later);
    expect(minutesLeft(mode, later)).toBeCloseTo(10, 5);
    expect(mode).toMatchObject({ kind: "minutes", minutes: 10 });
  });

  it("còn nguyên 10 phút thì bấm vẫn 10 phút", () => {
    const mode = sleepFrom({ kind: "minutes", minutes: 10 }, true, at);
    expect(minutesLeft(sleepExtended(mode, 10, true, at), at)).toBeCloseTo(10, 5);
  });

  it("số đã chọn thắng \"Mỗi lần nghe thêm\": hẹn 30 phút, bước 5 phút vẫn về 30", () => {
    const mode = sleepFrom({ kind: "minutes", minutes: 30 }, false, at);
    const longer = sleepExtended(mode, 5, false, at);
    expect(minutesLeft(longer, at)).toBeCloseTo(30, 5);
    expect(sleepExtendMinutes(mode, 5)).toBe(30);
    expect(sleepExtendLabel(sleepExtendMinutes(mode, 5))).toBe("Hẹn lại 30 phút");
  });

  it("đồng hồ đang dừng vẫn về đúng số đã hẹn và vẫn dừng", () => {
    const paused = { kind: "minutes" as const, minutes: 15, leftMs: 4 * 60_000, since: null };
    const again = sleepExtended(paused, 10, false, at);
    expect(again).toEqual({ kind: "minutes", minutes: 15, leftMs: 15 * 60_000, since: null });
  });

  it("hết chương: đếm \"Mỗi lần nghe thêm\" từ bây giờ, bấm tiếp vẫn không cộng dồn", () => {
    const first = sleepExtended({ kind: "chapter" }, 15, true, at);
    expect(first).toEqual({ kind: "minutes", minutes: 15, leftMs: 15 * 60_000, since: at });
    expect(minutesLeft(sleepExtended(first, 15, true, at + 60_000), at + 60_000)).toBeCloseTo(15, 5);
    expect(sleepExtendMinutes({ kind: "chapter" }, 15)).toBe(15);
    expect(sleepExtendMinutes({ kind: "off" }, 15)).toBe(15);
  });

  it("lưới an toàn đếm 1 phút nhưng hẹn lại về \"Mỗi lần nghe thêm\", không về 1 phút", () => {
    const net = sleepSafetyNet(true, at);
    expect(minutesLeft(net, at)).toBeCloseTo(1, 5);
    expect(sleepExtendMinutes(net, 15)).toBe(15);
    expect(sleepExtendLabel(sleepExtendMinutes(net, 15))).toBe("Hẹn lại 15 phút");
    const again = sleepExtended(net, 15, true, at + 10_000);
    expect(minutesLeft(again, at + 10_000)).toBeCloseTo(15, 5);
    expect(again).toMatchObject({ kind: "minutes", minutes: 15 });
    expect(minutesLeft(sleepExtended(again, 15, true, at + 10_000), at + 10_000)).toBeCloseTo(15, 5);
  });

  it("nhãn nút chung một chữ cho mọi nơi", () => {
    expect(sleepExtendLabel(10)).toBe("Hẹn lại 10 phút");
  });
});
