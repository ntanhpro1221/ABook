import { expect, it } from "vitest";
import contract from "../../../tests/fixtures/work_priority/contract.json";
import { applyWhen, PENDING_NOTE } from "./decisions";
import { priorityText, type WorkPriority } from "./workPriority";
import type { BookSummary } from "./api";

it("keeps the shared server order and counts without sorting on confidence", () => {
  expect(contract.items.map(item => item.key)).toEqual(contract.order);
  expect(contract.items[0].priority).toMatchObject({ lines: 2, recordedLines: 1, recordedChapters: 1, estimatedActions: 1 });
});

for (const scenario of contract.cases) {
  it(`shared wording and live application time: ${scenario.name}`, () => {
    const note = PENDING_NOTE[applyWhen(scenario.book as BookSummary)];
    expect(note).toBe(scenario.note);
    const item = { ...scenario.item, priority: scenario.item.priority as WorkPriority };
    expect(priorityText(item, note)).toBe(scenario.text);
  });
}
