import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  PAGE_STEPS, SNAP_STEPS, VALUE_SPECS, chipRows, chipIndex, tickLabels, clampValue, formatNumber, fromFraction, isDetent, parseValue, stepValue, toFraction,
  type ValueSpec,
} from "./valuePickerLogic";

// MỘT bộ ca cho ba nền (Android ValuePickerLogicTest.kt, Qt tst_value_picker): tests/fixtures/value_picker/cases.json.
type Case = { spec: string; op: string; in: number | string; out: unknown; clamped?: boolean; steps?: number; prev?: number };
const fixture = JSON.parse(readFileSync(new URL("../../../tests/fixtures/value_picker/cases.json", import.meta.url)).toString("utf8")) as {
  snapSteps: number;
  pageSteps: number;
  specs: Record<string, ValueSpec>;
  cases: Case[];
  chipRows: {widths: number[]; available: number; gap: number; out: number[]}[];
  tickLabels: {fractions: number[]; widths: number[]; total: number; minInset: number; gap: number; inset: number; aligned: boolean}[];
};

describe("bộ chọn giá trị: hợp đồng chung", () => {
  it("balances overflowing rows and never leaves an orphan", () => {
    for (const c of fixture.chipRows) expect(chipRows(c.widths, c.available, c.gap).map(row => row.length)).toEqual(c.out);
  });

  it("centres each label under its detent, or drops the detents", () => {
    for (const c of fixture.tickLabels) {
      const plan = tickLabels(c.fractions, c.widths, c.total, c.minInset, c.gap);
      expect(plan.inset).toBeCloseTo(c.inset, 9);
      expect(plan.aligned, JSON.stringify(c.fractions)).toBe(c.aligned);
    }
  });

  it("inverts every step and spaces wide-domain detents by at least 24dp at 360dp", () => {
    for (const [name, spec] of Object.entries(fixture.specs)) {
      for (let i = 0; i <= Math.round((spec.max - spec.min) / spec.step); i++) {
        const value = stepValue(spec, spec.min, i);
        expect(fromFraction(spec, toFraction(spec, value)), `${name} ${value}`).toBe(value);
      }
      if (spec.min > 0 && spec.max / spec.min >= 8) {
        for (let i = 1; i < spec.typical.length; i++) expect((toFraction(spec, spec.typical[i]) - toFraction(spec, spec.typical[i - 1])) * 200, name).toBeGreaterThanOrEqual(24);
      }
    }
  });
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
