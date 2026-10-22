import { beforeAll, describe, expect, it } from "vitest";
import { cleanSleepSchedule, choiceOr } from "./sleep";

// Lịch đêm và các mức hẹn giờ (soát a100 V2): cùng hợp đồng với webui/library.py - sai cấu trúc thì coi như chưa có lịch, không ném lỗi lúc bấm nghe.
beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

const GOOD = { from: "22:00", to: "06:00", minutes: 30 };

describe("cleanSleepSchedule", () => {
  it("giữ lịch đúng, bỏ khoá thừa", () => {
    expect(cleanSleepSchedule(GOOD)).toEqual(GOOD);
    expect(cleanSleepSchedule({ ...GOOD, extra: 1 })).toEqual(GOOD);
    expect(cleanSleepSchedule({ from: "00:00", to: "23:59", minutes: 60 })).toEqual({ from: "00:00", to: "23:59", minutes: 60 });
  });

  it.each([null, undefined, {}, [], "22:00", 5, { ...GOOD, from: 12 }, { ...GOOD, from: { bad: 1 } }, { ...GOOD, to: "6:00" }, { ...GOOD, to: "24:00" }, { ...GOOD, minutes: -10 }, { ...GOOD, minutes: 20 }, { ...GOOD, minutes: "30" }, { from: GOOD.from, to: GOOD.to }])(
    "%j không phải lịch đêm",
    (value) => expect(cleanSleepSchedule(value)).toBeNull(),
  );
});

describe("choiceOr", () => {
  it("chỉ nhận số nằm trong các mức, không thì mặc định", () => {
    expect(choiceOr(60, [10, 30, 60], 30)).toBe(60);
    for (const bad of [-30, 45, "60", null, undefined, true, NaN]) expect(choiceOr(bad, [10, 30, 60], 30)).toBe(30);
  });
});

describe("scheduleWindow", () => {
  it("lịch sai cấu trúc không ném lỗi: coi như chưa có lịch", async () => {
    const { scheduleWindow } = await import("./player");
    const night = new Date(2026, 9, 23, 23);
    expect(scheduleWindow({} as never, night)).toBeNull();
    expect(scheduleWindow({ from: 12, to: "06:00", minutes: 30 } as never, night)).toBeNull();
    expect(scheduleWindow(null, night)).toBeNull();
    expect(scheduleWindow(GOOD, night)).not.toBeNull();
    expect(scheduleWindow(GOOD, new Date(2026, 9, 23, 12))).toBeNull();
  });
});
