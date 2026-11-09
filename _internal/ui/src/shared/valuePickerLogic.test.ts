import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  PAGE_STEPS, SNAP_STEPS, VALUE_SPECS, chipIndex, clampValue, formatNumber, fromFraction, isDetent, parseValue, stepValue, toFraction,
  type ValueSpec,
} from "./valuePickerLogic";

// MỘT bộ ca cho ba nền (Android ValuePickerLogicTest.kt, Qt tst_value_picker): tests/fixtures/value_picker/cases.json.
type Case = { spec: string; op: string; in: number | string; out: unknown; clamped?: boolean; steps?: number; prev?: number };
const fixture = JSON.parse(readFileSync(new URL("../../../tests/fixtures/value_picker/cases.json", import.meta.url)).toString("utf8")) as {
  snapSteps: number;
  pageSteps: number;
  specs: Record<string, ValueSpec>;
  cases: Case[];
};

describe("bộ chọn giá trị: hợp đồng chung", () => {
  it("bảng miền của web là bảng của fixture", () => {
    expect(SNAP_STEPS).toBe(fixture.snapSteps);
    expect(PAGE_STEPS).toBe(fixture.pageSteps);
    expect(JSON.parse(JSON.stringify(VALUE_SPECS))).toEqual(fixture.specs);
  });

  it.each(fixture.cases.map((item) => [`${item.spec} ${item.op} ${JSON.stringify(item.in)}`, item] as const))("%s", (_name, item) => {
    const spec = fixture.specs[item.spec];
    switch (item.op) {
      case "clamp":
        expect(clampValue(spec, item.in as number)).toEqual({ value: item.out, clamped: item.clamped });
        break;
      case "step":
        expect(stepValue(spec, item.in as number, item.steps!)).toBe(item.out);
        break;
      case "fromFraction":
        expect(fromFraction(spec, item.in as number)).toBe(item.out);
        break;
      case "toFraction":
        expect(toFraction(spec, item.in as number)).toBeCloseTo(item.out as number, 9);
        break;
      case "parse":
        expect(parseValue(spec, item.in as string)).toEqual(item.out === null ? null : { value: item.out, clamped: item.clamped });
        break;
      case "chip":
        expect(chipIndex(spec, item.in as number)).toBe(item.out);
        break;
      case "detent":
        expect(isDetent(spec, item.prev!, item.in as number)).toBe(item.out);
        break;
      case "format":
        expect(formatNumber(spec, item.in as number)).toBe(item.out);
        break;
      default:
        throw new Error(`ca lạ: ${item.op}`);
    }
  });

  it("kéo tới được MỌI giá trị trong biên (nấc hút không nuốt bước kề)", () => {
    for (const [name, spec] of Object.entries(fixture.specs)) {
      const reached = new Set<number>();
      for (let i = 0; i <= 20000; i++) reached.add(fromFraction(spec, i / 20000));
      const count = Math.round((spec.max - spec.min) / spec.step) + 1;
      expect(reached.size, name).toBe(count);
    }
  });
});
