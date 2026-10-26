// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ReviewQueue } from "./ReviewQueue";
import { WorkCards, type WorkItem } from "./WorkInbox";
import type { BookSummary } from "./api";

const mocks = vi.hoisted(() => ({ mutate: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({}), useQuery: () => ({}),
  useMutation: () => ({ mutate: mocks.mutate }),
  useInfiniteQuery: () => ({ data: { pages: [{ pending: 1, counts: {}, redoChapters: [], items: [{
    stableId: "line", segmentId: 1, chapterId: 1, chapterTitle: "Chương 1", audioSha256: "sha", verdict: null,
    pendingSpoken: null, text: "Câu cần nghe", textSha256: "text-sha", kind: "failed", playable: true, reason: "Cần kiểm tra",
  }] }] } }),
}));
vi.mock("@/listen/clip", () => ({ useClip: () => ({ current: null, toggle: vi.fn() }) }));
vi.mock("./data", () => ({ useCachedBook: () => ({}) }));
vi.mock("./liveRefresh", () => ({ useProducingRefetch: () => false }));
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  mocks.mutate.mockClear(); host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); });
const buttons = () => [...host.querySelectorAll<HTMLButtonElement>("button")];

it("Cần nghe lại: phán quyết là nút có icon; liên kết mở ngữ cảnh dùng mực phụ", async () => {
  const script = vi.fn();
  await act(() => root.render(<ReviewQueue bookId="book" onOpenScript={script} />));
  const decisions = buttons().filter(button => button.hasAttribute("data-decision"));
  expect(decisions.map(button => button.textContent)).toEqual(["Ổn", "Cần thu lại"]);
  for (const decision of decisions) { expect(decision.classList.contains("shared-button")).toBe(true); expect(decision.querySelector("svg")).not.toBeNull(); }
  const links = buttons().filter(button => /Sửa cách đọc|Mở Kịch bản/.test(button.textContent ?? ""));
  expect(links).toHaveLength(2);
  for (const link of links) { expect(link.classList.contains("text-fg-2")).toBe(true); expect(link.classList.contains("text-accent-text")).toBe(false); }
  await act(() => decisions[0].click()); expect(mocks.mutate).toHaveBeenCalledWith(expect.objectContaining({ stableId: "line", verdict: "ok" }));
  await act(() => links.find(link => link.textContent?.includes("Mở Kịch bản"))!.click()); expect(script).toHaveBeenCalledWith(1, "line");
});

it("WorkCards dùng ở hộp việc và Precast: chọn người có icon, đường mở Kịch bản lùi về mực phụ", async () => {
  const script = vi.fn();
  const item: WorkItem = { kind: "speaker", key: "speaker", title: "Ai nói câu này", problem: "Chọn người nói", affected: 1, current: "An", options: [], doubt: 0, score: 0,
    examples: [{ segmentId: 1, chapterId: 1, chapterTitle: "Chương 1", seq: 1, speaker: "An", text: "Câu thử", hasAudio: false }], lines: [{ stableId: "line", textSha256: "sha" }], choices: [{ value: "AN", label: "An" }] };
  await act(() => root.render(<WorkCards book={{ id: "book" } as BookSummary} items={[item]} onOpenReview={vi.fn()} onOpenScript={script} />));
  const decision = host.querySelector<HTMLButtonElement>("[data-choice][data-decision]")!;
  expect(decision.textContent).toBe("An"); expect(decision.querySelector(".lucide-check")).not.toBeNull();
  const link = buttons().find(button => button.textContent === "Tìm người khác")!;
  expect(link.classList.contains("text-fg-2")).toBe(true);
  await act(() => decision.click()); expect(mocks.mutate).toHaveBeenCalledWith({ speaker: "AN" });
  await act(() => link.click()); expect(script).toHaveBeenCalledWith(1, "line", undefined, "speaker");
});
