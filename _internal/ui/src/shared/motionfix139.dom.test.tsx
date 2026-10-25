// @vitest-environment happy-dom
// Soát chuyển động 139 (docs/reviews/motion139.md), mục CAO: hàng tab, chân chương Kịch bản, danh sách chương ở bước Nguồn - không hiện / ẩn /
// đổi chữ cứng. (Nút phát / dừng lớn: listen/motion139.dom.test.tsx.)
import { act, type ComponentProps, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Tabs, TabsList, TabsTrigger, TooltipProvider } from "./ui";
import { ChapterFooter, type ChapterScript, type Line } from "@/studio/ScriptTab";
import { SourceStep } from "@/studio/NewProjectScreen";

vi.mock("@/studio/data", async (original) => ({ ...(await original<typeof import("@/studio/data")>()), useAppInfo: () => ({ data: { dialogs: true } }), usePreferences: () => ({ data: {} }) }));
vi.mock("@/studio/api", async (original) => ({ ...(await original<typeof import("@/studio/api")>()), api: vi.fn(() => new Promise(() => {})) }));

let root: Root, host: HTMLDivElement, client: QueryClient;
let animate: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  animate = vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });

const render = async (node: ReactNode) => {
  await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter></QueryClientProvider>));
};
const animated = (match: (element: HTMLElement) => boolean) => (animate.mock.contexts as HTMLElement[]).filter(match);
const snapshots = () => [...document.querySelectorAll<HTMLElement>(".motion-snapshot")];

it("1.1 hàng tab tràn: mũi tên luôn dựng, chỉ đổi data-state (mờ tại chỗ); mép mờ đổi bằng biến có transition", async () => {
  await render(
    <Tabs value="a">
      <TabsList label="Mục">{["a", "b", "c", "d", "e", "f"].map((value) => <TabsTrigger key={value} value={value}>Tab {value}</TabsTrigger>)}</TabsList>
    </Tabs>,
  );
  const list = host.querySelector<HTMLElement>("[data-tab-row]")!;
  const arrow = (label: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
  // Đầu hàng, chưa tràn: mũi tên vẫn có trong cây (không gắn / gỡ), ở trạng thái khép.
  expect(arrow("Xem các tab trước")?.getAttribute("data-state")).toBe("closed");
  expect(arrow("Xem các tab sau")?.getAttribute("data-state")).toBe("closed");
  expect(arrow("Xem các tab trước")?.classList).toContain("motion-hold");
  expect(list.classList).toContain("tab-row-fade");
  expect(list.style.getPropertyValue("--tab-fade-l")).toBe("0px");
  // Tràn và cuộn vài px: cùng hai nút ấy mở ra, mép mờ hai bên rộng ra.
  const before = arrow("Xem các tab trước");
  Object.defineProperty(list, "scrollWidth", { configurable: true, value: 600 });
  Object.defineProperty(list, "clientWidth", { configurable: true, value: 200 });
  await act(() => { list.scrollLeft = 40; list.dispatchEvent(new Event("scroll")); });
  expect(arrow("Xem các tab trước")).toBe(before);
  expect(before?.getAttribute("data-state")).toBe("open");
  expect(arrow("Xem các tab sau")?.getAttribute("data-state")).toBe("open");
  expect(list.style.getPropertyValue("--tab-fade-l")).not.toBe("0px");
  expect(list.style.getPropertyValue("--tab-fade-r")).not.toBe("0px");
});

const line = (id: string, extra: Partial<Line> = {}) => ({
  segmentId: Number(id.replace(/\D/g, "")) || 1, stableId: id, textSha256: id, seq: 1, paragraph: 1, text: `Câu ${id}`, kind: "dialogue", speaker: "A", current: "A", label: "A",
  editable: true, hasAudio: false, hint: null, wish: null, emotion: null, intensity: null, lineWish: null, spoken: null, ...extra,
}) as Line;
const script = (lines: Line[]) => ({ chapterId: 1, index: 0, title: "Chương 1", previous: null, next: null, castReady: true, firstPerson: null, cast: [], others: [], lines }) as unknown as ChapterScript;

it("1.3 chân chương Kịch bản: \"Duyệt N câu\" -> dòng chữ mờ qua tại chỗ (vùng riêng), không đổi cứng", async () => {
  const footer = (lines: Line[]) => <ChapterFooter bookId="b" script={script(lines)} onNext={() => {}} onUndoable={() => {}} />;
  await render(footer([line("s1"), line("s2")]));
  expect(host.textContent).toContain("Duyệt 2 câu");
  const box = host.firstElementChild as HTMLElement;
  expect(box.hasAttribute("data-motion-region")).toBe(true);
  animate.mockClear();
  // Gán người cho câu chưa quyết cuối cùng: nút và chú thích nhường chỗ cho dòng chữ.
  const done = { state: "pending", value: "A" } as unknown as Line["wish"];
  await render(footer([line("s1", { wish: done }), line("s2", { wish: done })]));
  expect(host.textContent).toContain("Mọi câu nói trong chương đã có người quyết.");
  expect(host.firstElementChild).toBe(box);
  expect(animated((element) => element === box)).toHaveLength(1);
  expect(snapshots().some((image) => image.textContent?.includes("Duyệt 2 câu"))).toBe(true);
});

const files = (count: number) => Array.from({ length: count }, (_, i) => ({ path: `${i}.txt`, name: `c${i}.txt`, title: `Chương ${i + 1}`, firstLine: "", words: 50, chars: 200, audioSeconds: 20, credits: [], tailCredits: [] }));
const step = (list: ReturnType<typeof files>) => ({
  scan: { files: list, totals: { words: 50 * list.length, chapters: list.length, audioSeconds: 20 * list.length }, skipped: [], missing: [] }, title: "Sách", total: list.length, limit: null, later: 0,
  scanning: false, problem: null, dropCredits: { head: false, tail: false }, matter: { files: [], keep: [] }, onKeepMatter: vi.fn(), onTitle: vi.fn(), onPaths: vi.fn(), onAddFiles: vi.fn(),
  onRemove: vi.fn(), onLimit: vi.fn(), onDropCredits: vi.fn(), onSplit: vi.fn(),
}) as unknown as ComponentProps<typeof SourceStep>;

it("1.4 bước Nguồn: bỏ một chương thì hàng ấy khép tại chỗ (exit, inert), hàng khác đứng yên; danh sách không làm cả bước mờ lại", async () => {
  await render(<SourceStep {...step(files(3))} />);
  const list = host.querySelector<HTMLElement>('[role="list"][aria-label="Các chương sẽ làm"]')!;
  expect(list.querySelectorAll(".motion-row")).toHaveLength(3);
  animate.mockClear();
  // "Bỏ chương này" ở chương giữa.
  await render(<SourceStep {...step(files(3).filter((file) => file.path !== "1.txt"))} />);
  const leaving = [...list.querySelectorAll<HTMLElement>(".motion-row")].find((row) => row.textContent?.includes("c1.txt"));
  expect(leaving?.getAttribute("data-state")).toBe("exit");
  expect(leaving?.hasAttribute("inert")).toBe(true);
  expect([...list.querySelectorAll<HTMLElement>(".motion-row:not([data-state=exit])")].map((row) => row.textContent?.includes("c0.txt") || row.textContent?.includes("c2.txt"))).toEqual([true, true]);
  // Vùng cả bước (cha của danh sách) không chụp ảnh / mờ lại cả bước kể cả thanh cuộn của khung 340 px.
  expect(animated((element) => element !== list && element.contains(list))).toHaveLength(0);
  // "Hoàn tác": hàng mở lại tại chỗ.
  await render(<SourceStep {...step(files(3))} />);
  const back = [...list.querySelectorAll<HTMLElement>(".motion-row")].find((row) => row.textContent?.includes("c1.txt"));
  expect(back?.getAttribute("data-state")).toBe("enter");
});
