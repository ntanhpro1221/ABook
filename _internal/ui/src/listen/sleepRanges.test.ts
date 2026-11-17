import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { EXTEND_RANGE, FADE_RANGE, LAST_SLEEP_DEFAULT, SCHEDULE_MINUTES, cleanLastSleep, cleanSleepSchedule, lastSleepAfter } from "./sleep";
import { VALUE_SPECS } from "@/shared/valuePickerLogic";

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

describe("lần hẹn giờ cuối (lastSleep)", () => {
  const table = (JSON.parse(readFileSync(new URL("../../../tests/fixtures/settings/ranges.json", import.meta.url)).toString("utf8")) as {
    lastSleep: { kinds: string[]; minutes: { min: number; max: number; step: number }; chapters: { min: number; max: number; step: number };
      default: unknown; cases: [unknown, unknown][] };
  }).lastSleep;

  it("mặc định, miền và bảng ca chung với Python / Qt / Android", () => {
    expect(LAST_SLEEP_DEFAULT).toEqual(table.default);
    expect([VALUE_SPECS.sleepMinutes.min, VALUE_SPECS.sleepMinutes.max, VALUE_SPECS.sleepMinutes.step]).toEqual([table.minutes.min, table.minutes.max, table.minutes.step]);
    expect([VALUE_SPECS.sleepChapters.min, VALUE_SPECS.sleepChapters.max, VALUE_SPECS.sleepChapters.step]).toEqual([table.chapters.min, table.chapters.max, table.chapters.step]);
    for (const [given, cleaned] of table.cases) expect(cleanLastSleep(given), JSON.stringify(given)).toEqual(cleaned);
  });

  it("đặt phút / chương cập nhật đúng loại, tắt thì giữ nguyên", () => {
    const last = { kind: "minutes", minutes: 45, chapters: 3 } as const;
    expect(lastSleepAfter(last, { kind: "chapter", chapters: 2 })).toEqual({ kind: "chapter", minutes: 45, chapters: 2 });
    expect(lastSleepAfter(last, { kind: "chapter" })).toEqual({ kind: "chapter", minutes: 45, chapters: 1 });
    expect(lastSleepAfter(last, { kind: "minutes", minutes: 20 })).toEqual({ kind: "minutes", minutes: 20, chapters: 3 });
    expect(lastSleepAfter(last, { kind: "off" })).toBe(last);
  });
});
