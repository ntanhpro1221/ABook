// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import contract from "../../../tests/fixtures/voice_review/contract.json";
import { WorkCards, type WorkItem } from "./WorkInbox";
import { keepRequests } from "./minorGroups";
import type { BookSummary } from "./api";

const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async original => ({ ...await original<typeof import("./api")>(), api: mocks.api }));
vi.mock("@/listen/clip", () => ({ useClip: () => ({ current: null, toggle: vi.fn() }) }));
let root: Root, host: HTMLDivElement, client: QueryClient, taps: number;
const entry = (extra: Partial<WorkItem> = {}): WorkItem => ({ ...contract, examples: [], affected: 1, doubt: .6, score: .6, options: [], ...extra } as WorkItem);
const book = { id: "b", phase: "done", running: false } as BookSummary;
const draw = (item: WorkItem) => act(() => root.render(<QueryClientProvider client={client}><WorkCards book={book} items={[item]} onOpenReview={vi.fn()} /></QueryClientProvider>));
const click = (label: string) => act(() => { taps++; [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.click(); });
const tick = (text: string) => act(() => { taps++; host.querySelector<HTMLInputElement>(`input[aria-label="Gồm câu này: ${text}"]`)!.click(); });
const sent = () => mocks.api.mock.calls.map(call => call[1].body);

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  mocks.api.mockReset(); mocks.api.mockResolvedValue({ lines: 2, speaker: "LAN", requestedAt: 10 });
  taps = 0; host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });

it("caller một câu vẫn một bấm, mở thẻ không gửi yêu cầu", async () => {
  await draw(entry({ kind: "caller", keepGroups: undefined }));
  expect(sent()).toEqual([]);
  await click("Lan");
  expect(sent()[0].lines).toEqual(contract.lines);
  expect(taps).toBe(1);
});

it("quãng chỉ nhận câu chọn thêm và giữ qua polling", async () => {
  const item = entry(); await draw(item); await click("Chọn quãng");
  expect(sent()).toEqual([]);
  expect([...host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')].map(x => x.checked)).toEqual([true, false, false]);
  await tick("Chúng tôi hiểu rồi.");
  await draw({ ...item });
  await click("Lan");
  expect(sent()[0].lines.map((line: { stableId: string }) => line.stableId)).toEqual(contract.selectedIds);
  expect(sent()[0].seen).toEqual({ near: "", far: "" });
  expect(taps).toBe(3);
});

it("giữ riêng không đổi phía trả lời chưa được chọn", async () => {
  await draw(entry()); await click("Chọn quãng"); await tick("Chúng tôi hiểu rồi."); await click("Giữ riêng");
  expect(sent().map(body => [body.speaker, body.lines.map((line: { stableId: string }) => line.stableId)])).toEqual([["MAI", contract.selectedIds]]);
  expect(taps).toBe(3);
  expect(keepRequests(entry(), [])).toEqual([]);
});

it("cùng một nhóm gửi một identity, một lần tạo người", async () => {
  await draw(entry()); await click("Chọn quãng"); await tick("Chúng tôi hiểu rồi."); await click("Cùng một nhóm");
  expect(sent()[0]).toMatchObject({ speaker: contract.newPerson, newGender: "unknown", lines: [contract.contextLines[0], contract.contextLines[2]] });
  expect(taps).toBe(3);
});

it("bỏ ngoại lệ rồi khép quãng trở về đúng một câu", async () => {
  await draw(entry()); await click("Chọn quãng"); await tick("Chúng tôi hiểu rồi."); await tick("Chúng tôi đã sẵn sàng.");
  await click("Chọn quãng"); await click("Lan");
  expect(sent()[0].lines).toEqual(contract.lines);
  expect(taps).toBe(5);
});

it("quãng rỗng chặn mọi hành động và nguồn đổi đặt lại lựa chọn", async () => {
  const item = entry(); await draw(item); await click("Chọn quãng"); await tick("Chúng tôi đã sẵn sàng.");
  for (const label of ["Lan", "Cùng một nhóm", "Giữ riêng"]) expect([...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === label)!.disabled).toBe(true);
  await draw({ ...item, contextLines: item.contextLines!.map(line => ({ ...line, textSha256: "changed" })) });
  expect(host.querySelector<HTMLButtonElement>('[aria-expanded="false"]')).not.toBeNull();
  expect(sent()).toEqual([]);
});

it("chọn quãng mười câu bằng ba bấm, ngoại lệ thêm một bấm", async () => {
  const contextLines = Array.from({ length: 10 }, (_, index) => ({ stableId: `line-${index}`, textSha256: `sha-${index}` }));
  const contextExamples = contextLines.map((line, index) => ({ ...contract.contextExamples[0], ...line, segmentId: index + 10, text: `Câu tự viết ${index}.` }));
  await draw(entry({ lines: [contextLines[0]], contextLines, contextExamples }));
  await click("Chọn quãng"); await click("Chọn hết"); await click("Lan");
  expect(sent()[0].lines).toEqual(contextLines);
  expect(taps).toBe(3);
});

it("chọn cả rồi bỏ ngoại lệ chỉ gửi đúng ID còn chọn", async () => {
  await draw(entry()); await click("Chọn quãng"); await click("Chọn hết"); await tick("Các bạn hãy đứng ở đây."); await click("Lan");
  expect(sent()[0].lines.map((line: { stableId: string }) => line.stableId)).toEqual(contract.selectedIds);
  expect(taps).toBe(4);
});
