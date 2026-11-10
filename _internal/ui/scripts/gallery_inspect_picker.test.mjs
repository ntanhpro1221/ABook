// @vitest-environment node
import { describe, expect, it } from "vitest";
import { layoutFixtures } from "./gallery_inspect_layout_fixture.mjs";
import { browserAvailable } from "./gallery_browser.mjs";

describe.skipIf(!browserAvailable)("value picker gallery gate", () => {
  it("rejects orphan rows and repeated units, accepts balanced rows", async () => {
    for (const result of await layoutFixtures({fixture: "value-picker.html"})) {
      const found = result.findings.filter(f => f.rule === "PICKER GEOMETRY");
      expect(found.filter(f => f.metric === "picker-chip-rows").map(f => f.selector)).toEqual(["#orphan"]);
      expect(found.filter(f => f.metric === "picker-numeric-label")).toHaveLength(1);
      expect(found.some(f => f.selector.startsWith("#balanced") || f.selector.startsWith("#aligned"))).toBe(false);
      expect(found.some(f => f.selector.startsWith("#shifted") && f.metric === "picker-tick-centre")).toBe(true);
      expect(found.some(f => f.selector.startsWith("#missing") && f.metric === "picker-tick-count")).toBe(true);
      expect(found.some(f => f.selector.startsWith("#under-button") && f.metric === "picker-label-bounds")).toBe(true);
    }
  }, 60000);
});
