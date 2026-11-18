// @vitest-environment happy-dom
// Sách -> quyển -> chương (như Hako): sách một quyển hiện chương thẳng như trước; sách nhiều quyển hiện hàng quyển (bìa, số chương,
// tiến độ), bấm một quyển thì ra chương của quyển ấy, nút "Các quyển" quay lại.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { ChapterGroups } from "./BookScreen";
import type { ListenBook, ListenChapter } from "./model";

const state = vi.hoisted(() => ({ player: { track: null, playing: false, toggle: () => {}, play: () => {} } }));
vi.mock("./player", async (original) => ({ ...(await original<typeof import("./player")>()), usePlayer: () => state.player, useNowPlaying: () => ({ expanded: false, setExpanded: () => {} }) }));
vi.mock("./source", async (original) => ({ ...(await original<typeof import("./source")>()), useSource: () => ({ kind: "desktop" }) }));

let root: Root;
let host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(() => root.unmount());
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

const chapter = (id: number) => ({ id, index: id - 1, subtitle: "", title: `Chương ${id}`, fullTitle: `Chương ${id}`, duration: 60, available: true }) as ListenChapter;
const book = { id: "b", title: "Sách", narrator: "", duration: 180, chaptersTotal: 3, chaptersAvailable: 3, complete: true, producing: false, updatedAt: null,
  state: { chapters: {} }, progress: { heardSeconds: 0, totalSeconds: 180, fraction: 0, chaptersDone: 0, finished: false }, chapters: [1, 2, 3].map(chapter) } as ListenBook;
const render = (node: ReactNode) =>
  act(() => root.render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter></QueryClientProvider>));
const volumes = (rows: ListenChapter[]) => [
  { id: 1, number: 1, title: "Tập một", cover: null, chapters: rows.slice(0, 2) },
  { id: 2, number: 2, title: "Tập hai", cover: null, chapters: rows.slice(2) },
];

it("sách một quyển: danh sách chương thẳng, không có tầng quyển", async () => {
  await render(<ChapterGroups book={{ ...book, volumes: [{ id: 1, number: 1, title: "Quyển 1", cover: null, chapters: book.chapters! }] }} onDone={() => {}} />);
  expect(host.querySelector('[aria-label="Các quyển"]')).toBeNull();
  expect(host.textContent).toContain("Chương 3");
});

it("tiến độ quyển theo thời lượng khi hai chương dài khác nhau", async () => {
  const chapters = [{ ...chapter(1), duration: 60 }, { ...chapter(2), duration: 120 }, chapter(3)];
  const weighted = { ...book, chapters, volumes: volumes(chapters), state: { chapters: { "1": { done: true } } } } as unknown as ListenBook;
  await render(<ChapterGroups book={weighted} onDone={() => {}} />);
  expect(host.textContent).toContain("2 chương · Đã nghe 33%");
});

it("sách nhiều quyển: hàng quyển có số chương và tiến độ; chọn quyển ra chương của nó, quay lại về danh sách quyển", async () => {
  const many = { ...book, volumes: volumes(book.chapters!), state: { chapters: { "1": { done: true } } } } as unknown as ListenBook;
  await render(<ChapterGroups book={many} onDone={() => {}} />);
  const rows = [...host.querySelectorAll<HTMLButtonElement>('[aria-label="Các quyển"] [role=listitem] button')];
  expect(rows.map((row) => row.textContent)).toEqual([expect.stringContaining("Tập một"), expect.stringContaining("Tập hai")]);
  expect(rows[0].textContent).toContain("2 chương · Đã nghe 50%");
  expect(host.textContent).not.toContain("Chương 3");
  await act(async () => rows[1].click());
  expect(host.textContent).toContain("Chương 3");
  expect(host.textContent).not.toContain("Chương 1");
  const back = [...host.querySelectorAll("button")].find((button) => button.textContent === "Các quyển")!;
  await act(async () => back.click());
  expect(host.querySelectorAll('[aria-label="Các quyển"] [role=listitem]')).toHaveLength(2);
});

// Soát 0.4.173 B11: trình sửa quyển mở được ở cả ba dạng danh sách - một quyển không chia phần, một quyển chia nhiều phần, nhiều quyển (như máy tính).
it("the volume editor is offered whether the book has parts, no parts or several volumes", async () => {
  const parts = [{ part: 1, title: "Sách · Phần 1", chapters: [1, 2] }, { part: 2, title: "Sách · Phần 2", chapters: [3, 3] }];
  for (const shape of [{ ...book }, { ...book, parts }, { ...book, volumes: volumes(book.chapters!) }] as ListenBook[]) {
    await render(<ChapterGroups book={shape} onDone={() => {}} onRename={() => {}} />);
    expect([...host.querySelectorAll("button")].filter((button) => button.textContent === "Sắp xếp quyển")).toHaveLength(1);
  }
});

// Soát 0.4.173 B13c/d: id quyển mới không tái dùng id vừa xoá; hết chương thì không thêm quyển (như máy tính và điện thoại).
it("a new volume never reuses a removed id and cannot start on the last volume's chapter", async () => {
  const { nextVolumeId, canAddVolume } = await import("./VolumeEditor");
  expect(nextVolumeId([{ id: 1 }], [{ id: 1 }, { id: 2 }])).toBe(3);
  expect(nextVolumeId([], undefined)).toBe(1);
  expect(canAddVolume([{ start: 1 }, { start: 3 }], 3)).toBe(false);
  expect(canAddVolume([{ start: 1 }, { start: 2 }], 3)).toBe(true);
  expect(canAddVolume(Array.from({ length: 99 }, (_, index) => ({ start: index + 1 })), 500)).toBe(false);
});

// Soát 0.4.173 B6: hàng quyển giống nhau trên web và Android - quyển không có ảnh riêng dùng bìa sách (sách không ảnh: bìa vẽ nhỏ, chữ cái đầu
// của tên sách), mỗi hàng một thanh "Đã nghe" (Android: volume_progress_<id>).
it("volume rows without artwork reuse the book's drawn cover and show a heard bar", async () => {
  const many = { ...book, volumes: volumes(book.chapters!), state: { chapters: { "1": { done: true } } } } as unknown as ListenBook;
  await render(<ChapterGroups book={many} onDone={() => {}} />);
  const rows = [...host.querySelectorAll<HTMLButtonElement>('[aria-label="Các quyển"] [role=listitem] button')];
  expect(rows.map((row) => row.querySelector("[aria-hidden] span")?.textContent)).toEqual(["S", "S"]);
  expect(rows.map((row) => row.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow"))).toEqual(["50", "0"]);
});
