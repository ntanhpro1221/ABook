import { describe, expect, it } from "vitest";
import fixture from "../../../tests/fixtures/script_scope.json";
import { scopeLines, scopeSelected, type ScopeMode } from "./scopeLines";
import type { Line } from "./ScriptTab";

describe("shared scene scope contract", () => {
  for (const sample of fixture.cases) it(sample.name, () => {
    const lines = fixture.lines.map((line) => ({ ...line, scene: "noMarkers" in sample ? null : line.scene })) as unknown as Line[];
    const candidates = scopeLines(lines, sample.anchor, sample.mode as ScopeMode, sample.start, sample.end);
    expect(candidates.map((line) => line.stableId)).toEqual(sample.ids);
    expect(scopeSelected(candidates, sample.toggled ?? []).map((line) => line.stableId)).toEqual(sample.selected);
  });
});
