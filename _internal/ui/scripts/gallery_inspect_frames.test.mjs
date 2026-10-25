// @vitest-environment node
import { beforeAll, describe, expect, it } from "vitest";
import { layoutFixtures } from "./gallery_inspect_layout_fixture.mjs";
import { browserAvailable } from "./gallery_browser.mjs";

describe.skipIf(!browserAvailable)("frames and list coverage on Edge", () => {
  let results;
  beforeAll(async () => { results = await layoutFixtures({ fixture: "frames-lists.html" }); }, 60000);
  it("flags cards inside cards and dialogs, accepts controls and flat sections", () => {
    for (const r of results) {
      const found = r.findings.filter(f => f.rule === "NESTED CARD");
      expect(found).toHaveLength(2);
      expect(found.every(f => /#(nested|dialog)-bad >/.test(f.selector))).toBe(true);
    }
  });
  it("measures every marked list and detects both divider and permanent fill overhang", () => {
    for (const r of results) {
      expect(r.layout.listEdges.map(l => l.name)).toEqual(["bad", "good"]);
      expect(r.findings.filter(f => f.metric === "list-hairline-overhang" && f.selector.startsWith("#list-bad >"))).toHaveLength(2);
      expect(r.findings.filter(f => f.metric === "list-fill-overhang" && f.selector.startsWith("#list-bad >"))).toHaveLength(1);
      expect(r.findings.filter(f => f.metric?.startsWith("list-") && f.selector.startsWith("#list-good >"))).toHaveLength(0);
    }
  });
  it("measures row columns without treating inline text highlights as new columns or cards", () => {
    for (const r of results) expect(r.findings.filter(f => ['SIBLING CONSISTENCY', 'FILL INSET'].includes(f.rule) && f.selector.startsWith('#inline-good >'))).toHaveLength(0);
  });
});
