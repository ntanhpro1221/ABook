// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ReviewQueue } from "./ReviewQueue";
import { WorkCards, type WorkItem } from "./WorkInbox";
import type { BookSummary } from "./api";
import { TooltipProvider } from "@/shared/ui";

const mocks = vi.hoisted(() => ({ mutate: vi.fn(), toggle: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({}), useQuery: () => ({}),
  useMutation: () => ({ mutate: mocks.mutate }),
  useInfiniteQuery: () => ({ data: { pages: [{ pending: 1, counts: {}, redoChapters: [], items: [{
    stableId: "line", segmentId: 1, chapterId: 1, chapterTitle: "Chương 1", audioSha256: "sha", verdict: null,
    pendingSpoken: null, text: "Câu cần nghe", textSha256: "text-sha", kind: "failed", playable: true, reason: "Cần kiểm tra",
  }] }] } }),
}));
vi.mock("@/listen/clip", () => ({ useClip: () => ({ current: null, toggle: mocks.toggle }) }));
vi.mock("./data", () => ({ useCachedBook: () => ({}) }));
vi.mock("./liveRefresh", () => ({ useProducingRefetch: () => false }));
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  mocks.mutate.mockClear(); mocks.toggle.mockClear(); host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });
const buttons = () => [...host.querySelectorAll<HTMLButtonElement>("button")];

it("vai phụ nhiều câu: đề xuất tên trong chương, chọn giới và mở giọng dùng cùng đường sửa", async () => {
  const voice = vi.fn();
  const item: WorkItem = { kind: "unnamed", key: "role", title: "Vai phụ", problem: "Trong chương này", affected: 2,
    current: "người gác", currentValue: "NPC_LOCAL::c1::người gác", options: [], doubt: .5, score: .3, examples: [],
    suggestedName: "Người gác chương 1", pickVoice: { name: "NPC", displayName: "người gác" },
    lines: [{ stableId: "a", textSha256: "sha-a" }, { stableId: "b", textSha256: "sha-b" }], choices: [] };
  await act(() => root.render(<WorkCards book={{ id: "book" } as BookSummary} items={[item]} onOpenReview={vi.fn()} onPickVoice={voice} />));
  expect(mocks.mutate).not.toHaveBeenCalled();
  await act(() => buttons().find(button => button.textContent === "Giới / giọng")!.click());
  expect(voice).toHaveBeenCalledWith(item.pickVoice);
  await act(() => buttons().find(button => button.textContent === "Đặt tên")!.click());
  expect(host.querySelector<HTMLInputElement>('[aria-label="Tên người nói mới"]')!.value).toBe("Người gác chương 1");
  await act(() => buttons().find(button => button.textContent === "Nữ")!.click());
  expect(mocks.mutate).toHaveBeenCalledWith({ speaker: "Người gác chương 1", newGender: "female" });
});

it("người gọi: hiện loại việc, giữ lựa chọn máy và không mời hiệu ứng chưa có", async () => {
  const item: WorkItem = { kind: "caller", key: "caller:a", title: "Ai nói từ xa?", problem: "Đầu dây bên kia", affected: 1,
    current: "An", currentValue: "AN", keepLabel: "Giữ An (máy đề xuất)", suggested: false,
    options: [], doubt: .6, score: .6, examples: [], lines: [{ stableId: "a", textSha256: "sha-a" }], choices: [{ label: "Lan", value: "LAN" }] };
  await act(() => root.render(<WorkCards book={{ id: "book" } as BookSummary} items={[item]} onOpenReview={vi.fn()} />));
  expect(host.textContent).toContain("Người gọi / ngoài khung");
  expect(host.textContent).not.toContain("Lọc giọng");
  expect(mocks.mutate).not.toHaveBeenCalled();
  await act(() => buttons().find(button => button.textContent === item.keepLabel)!.click());
  expect(mocks.mutate).toHaveBeenCalledWith({ speaker: "AN" });
});

it("thẻ gọi hay nói: nghe ứng viên dùng clip riêng, chọn người dùng đường sửa có sẵn", async () => {
  const item: WorkItem = { kind: "vocative", key: "vocative:1", title: "Tên người nghe", problem: "Câu này gọi Minh", affected: 1,
    current: "Minh", currentValue: "MINH", options: [], doubt: .95, score: 1,
    examples: [], lines: [{ stableId: "line", textSha256: "sha" }],
    choices: [{ value: "LAN", label: "Lan", sampleId: 41 }, { value: "NARRATOR", label: "Người kể", samplePreset: "narrator" }] };
  await act(() => root.render(<TooltipProvider><WorkCards book={{ id: "book" } as BookSummary} items={[item]} onOpenReview={vi.fn()} /></TooltipProvider>));
  await act(() => host.querySelector<HTMLButtonElement>('[aria-label="Nghe Lan nói"]')!.click());
  expect(mocks.toggle).toHaveBeenCalledWith("work-voice-41", expect.stringContaining("/41"));
  expect(mocks.mutate).not.toHaveBeenCalled();
  await act(() => host.querySelector<HTMLButtonElement>('[aria-label="Nghe Người kể nói"]')!.click());
  expect(mocks.toggle).toHaveBeenCalledWith("work-voice-narrator", expect.stringContaining("/media/voices/narrator"));
  await act(() => buttons().find(button => button.textContent === "Lan")!.click());
  expect(mocks.mutate).toHaveBeenCalledWith({ speaker: "LAN" });
});

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
