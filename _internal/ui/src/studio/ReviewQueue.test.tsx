import { beforeEach, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { ReviewQueue } from "./ReviewQueue";
import { AnimatedRows } from "@/shared/MotionPresence";
import { mergeRows } from "@/shared/motion";

const mocks = vi.hoisted(() => ({ items: [] as Record<string, unknown>[], mutate: vi.fn() }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (initial: unknown) => [typeof initial === "function" ? initial() : initial, vi.fn()],
  useRef: (initial: unknown) => ({ current: initial }),
  useEffect: vi.fn(),
}));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({}), useQuery: () => ({}),
  useInfiniteQuery: () => ({ data: { pages: [{ items: mocks.items, counts: {}, redoChapters: [] }] } }),
  useMutation: () => ({ mutate: mocks.mutate }),
}));
vi.mock("@/listen/clip", () => ({ useClip: () => ({ current: null }) }));
vi.mock("./data", () => ({ useCachedBook: () => ({}) }));
vi.mock("./liveRefresh", () => ({ useProducingRefetch: () => false }));

function nodes(tree: unknown): ReactElement<Record<string, unknown>>[] {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== "object" || !("props" in tree)) return [];
  const node = tree as ReactElement<Record<string, unknown>>;
  return [node, ...nodes(node.props.children)];
}
const item = (id: string, chapter: number) => ({ stableId: id, segmentId: chapter, chapterId: chapter, audioSha256: `sha-${id}`, verdict: null, pendingSpoken: null, text: id, kind: "unverified" });
const keyOf = (row: Record<string, unknown>) => String(row.stableId);
beforeEach(() => vi.clearAllMocks());

it("phán A rồi B và câu cuối C khi A vẫn exit: payload luôn thuộc đúng câu được bấm", () => {
  const original = [item("A", 11), item("B", 22), item("C", 33)];
  let shown = mergeRows<Record<string, unknown>>([], original, keyOf, true);
  const click = (id: string) => {
    const list = nodes(ReviewQueue({ bookId: "book" })).find((node) => node.type === AnimatedRows)!;
    const render = list.props.children as (row: Record<string, unknown>, index: number) => ReactElement<{ onVerdict: (value: string) => void }>;
    const index = shown.findIndex((row) => row.key === id);
    render(shown[index].item, index).props.onVerdict("ok");
  };
  mocks.items = original;
  click("A");
  mocks.items = original.slice(1);
  shown = mergeRows(shown, mocks.items, keyOf);
  expect(shown.map((row) => [row.key, row.state])).toEqual([["A", "exit"], ["B", "idle"], ["C", "idle"]]);
  click("B");
  mocks.items = original.slice(2);
  shown = mergeRows(shown, mocks.items, keyOf);
  click("C");
  expect(mocks.mutate.mock.calls.map(([payload]) => payload)).toEqual(original.map((row) => ({
    stableId: row.stableId, chapterId: row.chapterId, audioSha256: row.audioSha256, verdict: "ok", seen: null,
  })));
  click("A");
  expect(mocks.mutate).toHaveBeenCalledTimes(3);
});
