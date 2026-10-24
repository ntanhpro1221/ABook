// @vitest-environment node
import { beforeAll, describe, expect, it } from "vitest";
import { layoutFixtures } from "./gallery_inspect_layout_fixture.mjs";
import { normalizeRule } from "./gallery_inspect.mjs";

describe("baseline, visible control boxes, inline ink on Edge in both themes and viewports", () => {
  let results;
  beforeAll(async () => { results = await layoutFixtures({ fixture: "baseline-controls.html" }); }, 60000);
  const at = (r, id, rule) => r.findings.filter((f) => f.rule === rule && f.selector.startsWith(`#${id} >`));
  it("accepts rule12/13 names and numbers", () => {
    expect(normalizeRule("rule12")).toBe("BASELINE"); expect(normalizeRule("control-height")).toBe("CONTROL HEIGHT"); expect(normalizeRule("rule13")).toBe("CONTROL HEIGHT");
  });
  it("detects mixed size first lines in a row and separate grid columns", () => {
    for (const r of results) for (const id of ["top", "columns"]) {
      expect(at(r, id, "BASELINE")).toHaveLength(1);
      expect(Math.abs(at(r, id, "BASELINE")[0].delta)).toBeGreaterThan(1);
      expect(at(r, id, "BASELINE")[0].fontSizes).toEqual([28, 24]);
    }
  });
  it("baseline and self-baseline pass; centred icon and painted chip pass", () => {
    for (const r of results) for (const id of ["baseline", "self", "icon", "chip", "ghost-baseline"]) expect(at(r, id, "BASELINE")).toHaveLength(0);
  });
  it("detects a shifted inline label baseline", () => {
    for (const r of results) expect(r.findings.some((f) => f.rule === "BASELINE" && f.referenceSelector?.startsWith("#inline-baseline"))).toBe(true);
  });
  it("detects equal size text in separate containers and measures a segmented group as one visible box", () => {
    for (const r of results) {
      expect(at(r, "same-font", "BASELINE")[0]?.delta).toBe(2);
      expect(at(r, "segmented", "CONTROL HEIGHT")).toHaveLength(1);
      expect(at(r, "segmented", "CONTROL HEIGHT")[0]?.delta).toBe(-4);
    }
  });
  it("detects height and top/bottom differences, including a single-line textarea", () => {
    for (const r of results) {
      expect(at(r, "height", "CONTROL HEIGHT")[0]?.delta).toBe(-3.5);
      expect(at(r, "offset", "CONTROL HEIGHT")[0]?.topDelta).toBe(2);
      expect(at(r, "textarea", "CONTROL HEIGHT")[0]?.delta).toBe(-3.5);
    }
  });
  it("equal heights, transparent hit extension, ghost and multiline textarea pass", () => {
    for (const r of results) for (const id of ["equal", "ghost", "multiline"]) expect(at(r, id, "CONTROL HEIGHT")).toHaveLength(0);
  });
  it("measures inline label to opening quote ink, finds 4 px error and passes even gaps", () => {
    for (const r of results) {
      const f = at(r, "inline-gap", "INK EDGE").filter((f) => f.metric === "ink-inline-text-gap");
      expect(f).toHaveLength(1); expect(f[0].delta).toBeCloseTo(4, 1);
      expect(at(r, "inline-pass", "INK EDGE").filter((f) => f.metric === "ink-inline-text-gap")).toHaveLength(0);
    }
  });
});
