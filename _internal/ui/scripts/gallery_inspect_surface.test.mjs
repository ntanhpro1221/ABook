// @vitest-environment node
import { beforeAll, describe, expect, it } from "vitest";
import { layoutFixtures } from "./gallery_inspect_layout_fixture.mjs";
import { browserAvailable } from "./gallery_browser.mjs";

describe.skipIf(!browserAvailable)("surface columns, trailing geometric ink, fill and menu rows on Edge", () => {
  let results;
  beforeAll(async () => { results = await layoutFixtures({ fixture: "surface-fill.html" }); }, 60000);
  const at = (r, id, metric) => r.findings.filter(f => f.selector.startsWith(`#${id} >`) && f.metric === metric);
  it("finds all three sheet body offsets relative to its title; flush body passes", () => {
    for (const r of results) {
      expect(at(r, "sheet-bad", "surface-ink-left")).toHaveLength(3);
      expect(at(r, "sheet-good", "surface-ink-left")).toHaveLength(0);
    }
  });
  it("uses narrow trailing path ink and accepts compensated glyph", () => {
    for (const r of results) {
      expect(at(r, "chevron-bad", "trailing-icon-right")[0]?.delta).toBeCloseTo(-10 / 3);
      expect(at(r, "chevron-good", "trailing-icon-right")).toHaveLength(0);
    }
  });
  it("requires 6px fill inset and accepts 12px padding", () => {
    for (const r of results) {
      expect(at(r, "fill-bad", "fill-inset-left")).toHaveLength(1);
      expect(at(r, "fill-bad", "fill-inset-right")).toHaveLength(1);
      expect(r.findings.filter(f => f.rule === "FILL INSET" && f.selector.startsWith("#fill-good >"))).toHaveLength(0);
    }
  });
  it("detects selection fill ending before sibling control; full-row fill passes", () => {
    for (const r of results) {
      expect(at(r, "selection-bad", "selection-fill-end")).toHaveLength(1);
      expect(at(r, "selection-good", "selection-fill-end")).toHaveLength(0);
    }
  });
  it("compares menu role heights across differing DOM structures", () => {
    for (const r of results) {
      expect(at(r, "menu-bad", "menu-row-height")[0]?.delta).toBe(6);
      expect(at(r, "menu-good", "menu-row-height")).toHaveLength(0);
    }
  });
});
