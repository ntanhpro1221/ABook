// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ReadingProblem } from "./ReadingProblem";
import { WorkCards, type WorkItem } from "./WorkInbox";
import { NameReadings } from "./NameReadings";
import { AnalysisModelPicker } from "./AnalysisModelPicker";
import { TellerModeSwitch } from "./TellerModeSwitch";
import { MusicModuleNotice } from "./MusicModuleNotice";
import { ReviewQueue } from "./ReviewQueue";
import type { BookSummary } from "./api";
import type { LocalMusicView } from "./musicLocal";

const h = vi.hoisted(() => ({ api: vi.fn(), clip: { current: "", loading: false, toggle: vi.fn(), stop: vi.fn() } }));
vi.mock("./api", async original => ({ ...await original<typeof import("./api")>(), api: h.api }));
vi.mock("@/listen/clip", () => ({ useClip: () => h.clip }));
vi.mock("@/listen/source", () => ({ useCast: () => ({ isSuccess: true }), useSource: () => ({}), useReadAloudVoices: () => ({ data: [] }) }));
let root: Root, host: HTMLElement, client: QueryClient;
const book = { id: "b", phase: "done", running: false } as BookSummary;
const item = (extra: Partial<WorkItem> = {}): WorkItem => ({
  key: "w", kind: "speaker", title: "Ai nói", problem: "Chọn người nói", current: "Mai", currentValue: "Mai",
  affected: 1, doubt: 1, score: 1, options: [], choices: [{ label: "Mai", value: "Mai" }],
  lines: [{ stableId: "s1", textSha256: "a" }],
  examples: [{ segmentId: 1, chapterId: 1, chapterTitle: "Chương 1", seq: 1, speaker: "Mai", text: "Xin chào", hasAudio: true }], ...extra,
});
const draw = (node: ReactNode) => act(() => root.render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>));
const click = (label: string) => act(() => [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.click());
const finish = () => act(() => {
  for (const call of vi.mocked(HTMLElement.prototype.animate).mock.results) (call.value as Animation).onfinish?.(new Event("finish") as AnimationPlaybackEvent);
});
const animated = (element: Element | null) => expect(vi.mocked(HTMLElement.prototype.animate).mock.contexts).toContain(element);
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); h.clip.current = ""; h.clip.loading = false; h.api.mockReset();
  h.api.mockResolvedValue({ entries: [], items: [], lines: 0, recorded: 0 });
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ top: 0, left: 0, bottom: 200, right: 300, height: 200, width: 300, x: 0, y: 0, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); document.body.replaceChildren(); });

it("lời từ chối giữ vùng để fade cả khi lỗi được xoá", async () => {
  const use = vi.fn();
  const view = (problem: string) => <ReadingProblem id="bad" problem={problem} suggestion="Mai" onUse={use} />;
  await draw(view("")); const region = host.firstElementChild;
  await draw(view("Cách đọc chưa đúng")); animated(region); await finish();
  await click("Dùng “Mai”"); expect(use).toHaveBeenCalledWith("Mai");
  await draw(view("")); animated(region);
  expect(host.firstElementChild).toBe(region);
  expect(document.querySelector(".motion-snapshot")?.hasAttribute("inert")).toBe(true);
});

it.each(["speaker", "narrator"] as const)("form %s mở/khép bằng Collapse và inert ngay khi khép", async kind => {
  const entry = item(kind === "narrator" ? { kind, narratorSection: { chapterIndex: 0, fromSeq: 1, toSeq: 2, narrator: "Mai", appliesNote: "", choices: [] } } : {});
  await draw(<WorkCards book={book} items={[entry]} onOpenReview={vi.fn()} />);
  const name = kind === "speaker" ? "Người khác…" : "Người kể khác…";
  const input = host.querySelector<HTMLInputElement>(kind === "speaker" ? '[aria-label="Tên người nói mới"]' : '[aria-label="Tên người kể của đoạn"]')!;
  const body = input.closest<HTMLElement>(".motion-collapse")!;
  expect(body.hasAttribute("inert")).toBe(true);
  await click(name); expect(body.dataset.state).toBe("open"); animated(body);
  expect(document.activeElement).toBe(input);
  await click(name); expect(body.hasAttribute("inert")).toBe(true); expect(body.dataset.state).toBe("closed");
});

it("đổi phạm vi fade cả số ảnh hưởng và dấu sẽ đổi trong ví dụ", async () => {
  const entry = item({ kind: "turn", allLines: [{ stableId: "s1", textSha256: "a" }, { stableId: "s2", textSha256: "b" }] });
  await draw(<WorkCards book={book} items={[entry]} onOpenReview={vi.fn()} />);
  await finish(); vi.mocked(HTMLElement.prototype.animate).mockClear();
  await click("Cả chuỗi · 2");
  expect(host.textContent).toContain("sẽ đổi");
  expect([...document.querySelectorAll(".motion-snapshot")].some(node => node.textContent?.includes("Ảnh hưởng"))).toBe(true);
  expect([...document.querySelectorAll(".motion-snapshot")].some(node => node.textContent?.includes("Xin chào"))).toBe(true);
});

it("thêm ví dụ và icon phát được fade tại thẻ đang giữ state", async () => {
  const first = item();
  const entry = item({ pick: true, examples: Array.from({ length: 6 }, (_, i) => ({ ...first.examples[0], segmentId: i + 1, text: `Câu ${i}` })) });
  const view = () => <WorkCards book={book} items={[entry]} onOpenReview={vi.fn()} />;
  await draw(view()); await click("Xem cả 6 câu");
  expect(host.querySelectorAll('button[aria-label^="Nghe câu"]')).toHaveLength(6);
  expect(document.querySelector(".motion-snapshot")?.textContent).toContain("Câu 0");
  await finish();
  const button = host.querySelector('button[aria-label="Nghe câu: Câu 0"]')!;
  const region = button.firstElementChild;
  h.clip.current = "work-1"; await draw(view()); animated(region);
});

it("Thêm cách đọc fade khi đổi nút/form và khi báo nhập nhiều từ", async () => {
  client.setQueryData(["pronunciations", "b"], { items: [], unseen: 1 });
  await draw(<NameReadings bookId="b" />); await click("Thêm cách đọc"); await finish();
  const input = host.querySelector<HTMLInputElement>("#add-any-word")!;
  await act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "hai từ");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(host.textContent).toContain("không có khoảng trắng"); animated(input.closest("[data-motion-region]"));
  await finish(); await act(() => host.querySelector<HTMLButtonElement>('[data-add-any-word] [aria-label="Đóng"]')!.click());
  expect(document.querySelector(".motion-snapshot")?.textContent).toContain("Chữ đọc sai");
});

it("bộ phân tích đến muộn và đổi lựa chọn dùng cùng vùng chuyển động", async () => {
  await draw(<AnalysisModelPicker value="" onChange={vi.fn()} />); const region = host.firstElementChild;
  await act(() => client.setQueryData(["analysis-models"], { default: "base", models: [{ name: "other", size: 1, parameters: "4b" }], reachable: true }));
  await act(() => vi.advanceTimersByTime(1));
  animated(region); expect(host.querySelector("details")).not.toBeNull(); await finish();
  await draw(<AnalysisModelPicker value="other" onChange={vi.fn()} />); animated(region);
});

it("bộ phân tích chỉ hiện nhãn dễ đọc, giữ khoá trong giá trị gửi máy chủ", async () => {
  client.setQueryData(["analysis-models"], { default: "base", models: [{ name: "qwen3.5:9b", size: 5e9, parameters: "9b" }], reachable: true });
  const change = vi.fn();
  await draw(<AnalysisModelPicker value="qwen3.5:9b" onChange={change} />); await finish();
  expect(host.textContent).not.toMatch(/qwen|9b|Tên kỹ thuật/);
  expect(host.textContent).toContain("9 tỉ tham số");
  expect(host.querySelector<HTMLSelectElement>('select')?.value).toBe("qwen3.5:9b");
  await act(() => {
    const select = host.querySelector<HTMLSelectElement>('select')!;
    select.value = ""; select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(change).toHaveBeenCalledWith("");
});

it("công tắc tự kể xuất hiện sau query và fade lời hướng dẫn khi mode đổi", async () => {
  client.setQueryData(["narrator-mode", "b"], { available: false });
  await draw(<TellerModeSwitch book={book} />); const region = host.firstElementChild;
  await act(() => client.setQueryData(["narrator-mode", "b"], { available: true, mode: "narrator", castLocked: false }));
  await act(() => vi.advanceTimersByTime(1)); animated(region); await finish();
  const hint = host.querySelector(".settings-row-label"); // lời giải thích nằm trong vùng chữ của hàng cài đặt
  await act(() => client.setQueryData(["narrator-mode", "b"], { available: true, mode: "teller", castLocked: false }));
  await act(() => vi.advanceTimersByTime(1)); animated(hint);
});

it("cờ analysing thuần boolean vẫn fade khối phân tích nhạc", async () => {
  const view = (analysing: boolean) => <MusicModuleNotice queryKey={["local"]} view={{ module: { state: "ready", analysing, stale: 0 } } as LocalMusicView} />;
  await draw(view(false)); const region = host.firstElementChild;
  await draw(view(true)); animated(region); expect(host.querySelector('[role="status"]')).toBe(region);
});

it("thẻ nghe lại fade icon và form sửa chữ, giữ cùng node thẻ", async () => {
  client.setQueryData(["review", "b", false, "todo"], { pages: [{ items: [{ stableId: "s1", segmentId: 1, chapterId: 1, chapterTitle: "Một", text: "Xin chào", textSha256: "t", audioSha256: "w", playable: true, chapterClip: null, kind: "text-low", similarity: null, verdict: null, pendingSpoken: null }], redoChapters: [], counts: {}, minor: 0 }], pageParams: [""] });
  await draw(<ReviewQueue bookId="b" />);
  const row = host.querySelector('[data-review-row="s1"]')!;
  const button = row.querySelector('button[aria-label^="Nghe câu"]')!;
  h.clip.current = "review-1"; await draw(<ReviewQueue bookId="b" />); animated(button.firstElementChild);
  await finish();
  await act(() => row.querySelector<HTMLButtonElement>('button:has(svg.lucide-pen-line)')!.click());
  expect(row.querySelector("input")).not.toBeNull();
  expect([...document.querySelectorAll(".motion-snapshot")].some(node => node.textContent?.includes("Sửa cách đọc"))).toBe(true);
});
