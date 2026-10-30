import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { EXTEND_CHOICES, FADE_CHOICES, SAFETY_STOP_CHOICES, SCHEDULE_MINUTES, cleanSleepSchedule } from "./sleep";

// Miền giá trị của tuỳ chọn nghe: MỘT bảng chung (tests/fixtures/settings/ranges.json) cho Python, giao diện và lõi Kotlin (soát a102 B3).
const ranges = JSON.parse(readFileSync(new URL("../../../tests/fixtures/settings/ranges.json", import.meta.url)).toString("utf8")) as {
  choices: Record<string, { values: (string | number)[]; default: string | number }>;
  booleans: Record<string, boolean>;
  schedule: { minutes: number[]; clock: string };
};

describe("bảng miền chung", () => {
  it("các hằng của sleep.ts là bảng của fixture", () => {
    expect(FADE_CHOICES).toEqual(ranges.choices.sleepFadeSeconds.values);
    expect(EXTEND_CHOICES).toEqual(ranges.choices.sleepExtendMinutes.values);
    expect(SAFETY_STOP_CHOICES).toEqual(ranges.choices.safetyStopHours.values);
    expect(SCHEDULE_MINUTES).toEqual(ranges.schedule.minutes);
  });

  it("lịch đêm: các mức phút và giờ theo bảng chung", () => {
    const clock = new RegExp(ranges.schedule.clock);
    expect(clock.test("23:59")).toBe(true);
    expect(clock.test("24:00")).toBe(false);
    for (const minutes of ranges.schedule.minutes) expect(cleanSleepSchedule({ from: "22:00", to: "06:00", minutes })).not.toBeNull();
    expect(cleanSleepSchedule({ from: "22:00", to: "06:00", minutes: Math.max(...ranges.schedule.minutes) + 1 })).toBeNull();
  });
});
