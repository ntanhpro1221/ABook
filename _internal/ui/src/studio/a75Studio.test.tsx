import { renderToString } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";
import { api, type BookSummary } from "./api";
import { ReviewQueue } from "./ReviewQueue";
import { WorkCards, type WorkItem } from "./WorkInbox";
import { toast } from "sonner";

const captured = vi.hoisted(() => ({
  mutations: [] as { onSuccess?: (answer: Record<string, unknown>) => void }[],
  infinite: null as null | { queryFn: (context: { pageParam: string }) => Promise<unknown>; getNextPageParam: (last: { nextCursor: string | null }) => string | undefined },
}));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useQuery: () => ({}),
  useMutation: (options: { onSuccess?: (answer: Record<string, unknown>) => void }) => {
    captured.mutations.push(options);
    return { mutate: vi.fn(), isPending: false };
  },
  useInfiniteQuery: (options: NonNullable<typeof captured.infinite>) => {
    captured.infinite = options;
    const item = (id: number) => ({ segmentId: id, stableId: `s${id}`, chapterId: 1, chapterTitle: "Chương 1", text: `Câu ${id}`,
      kind: "failed", verdict: null, playable: false, pendingSpoken: null, textSha256: "", similarity: null });
    return { data: { pages: [
      { counts: {}, pending: 605, redoChapters: [], items: [item(600)], nextCursor: "c600", remaining: 5 },
      { counts: {}, pending: 605, redoChapters: [], items: [item(601)], nextCursor: "c601", remaining: 4 },
    ] }, isLoading: false, hasNextPage: true, fetchNextPage: vi.fn(), isFetchingNextPage: false };
  },
}));
vi.mock("@/listen/clip", () => ({ useClip: () => ({ current: null, stop: vi.fn(), toggle: vi.fn() }) }));
vi.mock("./data", () => ({ useCachedBook: () => ({}) }));
vi.mock("./api", async (original) => ({ ...await original<typeof import("./api")>(), api: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
beforeEach(() => {
  captured.mutations.length = 0;
  vi.clearAllMocks();
});

it("thông báo đổi người nói dùng số máy chủ ghi, kể cả khi khác số câu phía giao diện", () => {
  const item = { kind: "speaker", key: "s", title: "Ai nói", problem: "", affected: 2501, options: [], current: "Vai cũ", currentValue: "OLD",
    examples: [], lines: Array.from({ length: 2501 }, (_, i) => ({ stableId: `s${i}`, textSha256: "sha" })),
    choices: [{ value: "NEW", label: "Vai mới" }] } as unknown as WorkItem;
  renderToString(<WorkCards book={{ id: "b1", phase: "done" } as BookSummary} items={[item]} onOpenReview={() => undefined} />);
  captured.mutations[0].onSuccess?.({ lines: 17, speaker: "NEW", requestedAt: 1 });
  expect(toast.success).toHaveBeenCalledWith("Đã ghi: 17 câu này của Vai mới", expect.anything());
});

it("hàng nghe gộp các trang, giữ bộ lọc ở máy chủ và còn nút tải tiếp", async () => {
  const html = renderToString(<ReviewQueue bookId="b1" />);
  expect(html).toContain("Câu 600");
  expect(html).toContain("Câu 601");
  expect(html).toContain("Tải tiếp · còn 4 câu");
  await captured.infinite?.queryFn({ pageParam: "mốc + 601" });
  const url = new URL(vi.mocked(api).mock.calls[0][0], "http://localhost");
  expect(url.searchParams.get("filter")).toBe("todo");
  expect(url.searchParams.get("cursor")).toBe("mốc + 601");
  expect(captured.infinite?.getNextPageParam({ nextCursor: "next" })).toBe("next");
  expect(captured.infinite?.getNextPageParam({ nextCursor: null })).toBeUndefined();
});
