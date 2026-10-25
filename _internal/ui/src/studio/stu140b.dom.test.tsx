// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ReviewQueue } from "./ReviewQueue";
import { TellerModeSwitch } from "./TellerModeSwitch";
import { PrecastWaitSwitch } from "./PrecastReview";
import { ProjectInfoDialog, projectDetails } from "./ProjectInfo";
import { HeaderProgress, chapterMark } from "./ProjectScreen";
import { projectStatus, queueLabel } from "./data";
import type { BookSummary } from "./api";

// Soát Studio 25-10 (stu140b): đầu trang dự án, hàng "Cần nghe lại", hàng chương, công tắc thành hàng cài đặt.
const h = vi.hoisted(() => ({ api: vi.fn(), clip: { current: "", loading: false, toggle: vi.fn(), stop: vi.fn() } }));
vi.mock("./api", async (original) => ({ ...await original<typeof import("./api")>(), api: h.api }));
vi.mock("@/listen/clip", () => ({ useClip: () => h.clip }));
vi.mock("@/listen/source", () => ({ useCast: () => ({ isSuccess: true }), useSource: () => ({}), useReadAloudVoices: () => ({ data: [] }) }));
let root: Root, host: HTMLElement, client: QueryClient;
const book = (extra: Partial<BookSummary> = {}) => ({ id: "b", title: "Sách", phase: "synthesis", running: true, progress: { overall: 0.45, analysis: 1, synthesis: 0.3 }, settings: {}, ...extra }) as unknown as BookSummary;
const draw = (node: ReactNode) => act(() => root.render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>));
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  h.api.mockReset(); h.api.mockResolvedValue({});
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); vi.restoreAllMocks(); document.body.replaceChildren(); });

const reviewItem = (extra: Record<string, unknown> = {}) => ({ stableId: "s1", segmentId: 1, chapterId: 3, chapterTitle: "Chương 3", text: "Xin chào các bạn", textSha256: "t", audioSha256: "w", playable: true, chapterClip: null, kind: "unverified", reason: "Máy chưa nghe lại được", heard: "", similarity: null, verdict: null, pendingSpoken: null, ...extra });
const review = (items: unknown[]) => client.setQueryData(["review", "b", false, "todo"], { pages: [{ items, redoChapters: [], counts: {}, minor: 0 }], pageParams: [""] });

it("hàng nghe lại: câu trước, một dòng 'lý do · chương', không viên chữ riêng", async () => {
  review([reviewItem()]);
  await draw(<ReviewQueue bookId="b" />);
  const row = host.querySelector('[data-review-row="s1"]')!;
  expect(row.querySelector("p")?.textContent).toBe("Xin chào các bạn");
  const meta = row.querySelector(".dot-join")!;
  expect(meta.textContent).toBe("Máy chưa nghe lại đượcChương 3"); // dấu "·" do CSS (DotJoin), không nằm trong chữ
  expect(meta.querySelector(".text-warning")?.textContent).toBe("Máy chưa nghe lại được"); // lý do mang màu mức nặng
  expect(row.querySelector(".rounded-full.px-2")).toBeNull(); // trước đây lý do là một viên chữ
});

it("'Máy nghe ra' chỉ hiện khi KHÁC câu; khớp thì không có gì để so", async () => {
  review([reviewItem({ heard: "xin chào các bạn.", similarity: 1 }), reviewItem({ stableId: "s2", segmentId: 2, heard: "Xin chào các bản", similarity: 0.71 })]);
  await draw(<ReviewQueue bookId="b" />);
  expect(host.querySelector('[data-review-row="s1"]')!.textContent).not.toContain("Máy nghe ra");
  const second = host.querySelector('[data-review-row="s2"]')!.textContent!;
  expect(second).toContain("Máy nghe ra: “Xin chào các bản”");
  expect(second).toContain("khớp 71%");
});

it("hai phán quyết là nút chính của hàng: cùng một kiểu chữ nhấn, chưa chọn thì aria-pressed=false", async () => {
  review([reviewItem()]);
  await draw(<ReviewQueue bookId="b" />);
  const buttons = [...host.querySelectorAll<HTMLButtonElement>('[data-review-row="s1"] button[aria-pressed]')];
  expect(buttons.map((button) => button.textContent)).toEqual(["Ổn", "Cần thu lại"]);
  expect(buttons.map((button) => button.getAttribute("aria-pressed"))).toEqual(["false", "false"]);
  expect(buttons[0].className).toContain("text-accent-text");
  expect(buttons[1].className).toContain("text-accent-text");
});

it("công tắc 'Nhân vật tự kể' là hàng cài đặt, công tắc bên phải, không khung viền", async () => {
  client.setQueryData(["narrator-mode", "b"], { available: true, mode: "narrator", castLocked: false });
  await draw(<TellerModeSwitch book={book({ running: false, phase: "done" })} />);
  const row = host.querySelector(".settings-row")!;
  expect(row.querySelector(".settings-row-control [role=switch]")).not.toBeNull();
  expect(row.querySelector(".settings-row-label")?.textContent).toContain("Nhân vật tự kể");
  expect(host.querySelector(".rounded-xl.border")).toBeNull();
});

it("công tắc 'Duyệt trước khi thu' cũng là hàng cài đặt, lời giải thích theo trạng thái", async () => {
  await draw(<PrecastWaitSwitch book={book({ phase: "analysis", precast: { wait: true } as BookSummary["precast"] })} />);
  expect(host.querySelector(".settings-row-control [role=switch]")?.getAttribute("aria-checked")).toBe("true");
  expect(host.querySelector(".settings-row-label")?.textContent).toContain("Dừng sau phân tích");
  expect(host.querySelector(".rounded-xl.border")).toBeNull();
});

it("tiến độ đầu trang: thanh mảnh + phần trăm khi sách đang chạy; sách xong thì khép", async () => {
  await draw(<HeaderProgress book={book()} />);
  expect(host.querySelector('[role="progressbar"]')).not.toBeNull();
  expect(host.textContent).toContain("45%");
  expect(host.textContent).not.toContain("tổng");
  await draw(<HeaderProgress book={book({ phase: "done", running: false })} />);
  expect(host.querySelector('[data-state="closed"]')).not.toBeNull();
});

it("hàng chương: chỉ chương lệch khỏi mặc định mới có dấu", () => {
  expect(chapterMark({ status: "completed", statusLabel: "Đã xong", redo: false })).toBeNull();
  expect(chapterMark({ status: "pending", statusLabel: "Chờ", redo: false })).toBeNull();
  expect(chapterMark({ status: "synthesizing", statusLabel: "Đang thu âm", redo: false })).toBeNull();
  expect(chapterMark({ status: "failed", statusLabel: "Lỗi", redo: false })).toEqual({ label: "Lỗi", tone: "danger" });
  expect(chapterMark({ status: "completed", statusLabel: "Mất file audio", redo: false })?.tone).toBe("warning");
  expect(chapterMark({ status: "completed", statusLabel: "Chờ thu lại", redo: true })).toEqual({ label: "Chờ thu lại", tone: "muted" });
});

it("hàng đợi nói còn mấy việc trước, không nói 'thứ N'", () => {
  expect(queueLabel(1)).toBe("Sắp tới lượt");
  expect(queueLabel(6)).toBe("Còn 5 việc trước");
  const status = projectStatus(book({ queuePosition: 6, running: false }));
  expect(status).toMatchObject({ label: "Còn 5 việc trước", tone: "warning" });
});

it("chi tiết dự án: giọng kể, model phân tích, ngày tạo - phần kỹ thuật không còn ở đầu trang", async () => {
  const detailed = book({ settings: { analyzer: "qwen3.5:9b", profileLabel: "Cân bằng" } as BookSummary["settings"], createdAt: 1_790_000_000 } as unknown as Partial<BookSummary>);
  const lines = projectDetails(detailed);
  expect(lines.some((line) => /qwen|9b/i.test(line))).toBe(true);
  expect(lines).toContain("Cân bằng");
  await draw(<ProjectInfoDialog book={detailed} open onOpenChange={() => undefined} />);
  expect(document.body.textContent).toContain("Chi tiết dự án");
});
