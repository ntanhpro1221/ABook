import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { EXTEND_RANGE, FADE_RANGE, SCHEDULE_MINUTES, cleanSleepSchedule } from "./sleep";

// Miền giá trị của tuỳ chọn nghe: MỘT bảng chung (tests/fixtures/settings/ranges.json) cho Python, giao diện và lõi Kotlin (soát a102 B3).
const ranges = JSON.parse(readFileSync(new URL("../../../tests/fixtures/settings/ranges.json", import.meta.url)).toString("utf8")) as {
  choices: Record<string, { values: (string | number)[]; default: string | number }>;
  numbers: Record<string, { min: number; max: number; step: number; default: number }>;
  booleans: Record<string, boolean>;
  schedule: { minutes: { min: number; max: number; step: number }; clock: string };
};

describe("bảng miền chung", () => {
  it("các hằng của sleep.ts là bảng của fixture", () => {
    const { sleepFadeSeconds: fade, sleepExtendMinutes: extend } = ranges.numbers;
    expect([FADE_RANGE.min, FADE_RANGE.max, FADE_RANGE.step]).toEqual([fade.min, fade.max, fade.step]);
    expect([EXTEND_RANGE.min, EXTEND_RANGE.max, EXTEND_RANGE.step]).toEqual([extend.min, extend.max, extend.step]);
    expect([SCHEDULE_MINUTES.min, SCHEDULE_MINUTES.max, SCHEDULE_MINUTES.step]).toEqual([ranges.schedule.minutes.min, ranges.schedule.minutes.max, ranges.schedule.minutes.step]);
  });

  it("lịch đêm: các mức phút và giờ theo bảng chung", () => {
    const clock = new RegExp(ranges.schedule.clock);
    expect(clock.test("23:59")).toBe(true);
    expect(clock.test("24:00")).toBe(false);
    const { min, max, step } = ranges.schedule.minutes;
    for (const minutes of [min, min + step, max]) expect(cleanSleepSchedule({ from: "22:00", to: "06:00", minutes })).not.toBeNull();
    for (const minutes of [min - step, min + step / 2, max + step]) expect(cleanSleepSchedule({ from: "22:00", to: "06:00", minutes })).toBeNull();
  });
});
