// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import contract from "../../../tests/fixtures/work_priority/contract.json";
import { WorkCards, type WorkItem } from "./WorkInbox";
import type { BookSummary } from "./api";

const mocks = vi.hoisted(() => ({ mutate: vi.fn(() => Promise.resolve()) }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useMutation: () => ({ mutate: mocks.mutate, mutateAsync: mocks.mutate, isPending: false }),
  useQuery: () => ({ data: undefined, isLoading: false }),
}));
vi.mock("@/listen/clip", () => ({ useClip: () => ({ current: null, toggle: vi.fn() }) }));
vi.mock("./data", () => ({ useCachedBook: () => ({}) }));
vi.mock("./liveRefresh", () => ({ useProducingRefetch: () => false }));
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  mocks.mutate.mockClear();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); });

for (const scenario of contract.cases) {
  it(`shows counts and timing and keeps a visible candidate at one click: ${scenario.name}`, async () => {
    await act(() => root.render(<WorkCards book={scenario.book as BookSummary} items={[scenario.item as WorkItem]} onOpenReview={vi.fn()} />));
    expect(host.querySelector('[data-testid="work-priority"]')?.textContent).toBe(scenario.text);
    expect(mocks.mutate).not.toHaveBeenCalled();
    const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent === scenario.item.choices[0].label);
    expect(button).toBeDefined();
    await act(() => button!.click());
    expect(mocks.mutate).toHaveBeenCalledTimes(1);
    expect(mocks.mutate).toHaveBeenCalledWith({ speaker: scenario.item.choices[0].value });
  });
}
