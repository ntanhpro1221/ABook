// @vitest-environment happy-dom
// Menu "…" của hàng chương dựng lười (BookScreen ChapterMenu, docs/PERF_WEB.md): trước khi cần chỉ là một nút trơn cùng thuộc tính; bấm thẳng
// mở ngay, rê chuột / Tab vào thì thành nút của Radix mà tiêu điểm vẫn ở nút, Enter mở như mọi menu.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import { ChapterGroups } from "./BookScreen";
import type { ListenBook, ListenChapter } from "./model";

const state = vi.hoisted(() => ({ player: { track: null, playing: false, toggle: () => {}, play: () => {} } }));
vi.mock("./player", async (original) => ({ ...(await original<typeof import("./player")>()), usePlayer: () => state.player }));
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
const menuButton = (id: number) => host.querySelector<HTMLButtonElement>(`[aria-label="Thêm tuỳ chọn cho Chương ${id}"]`)!;
const menuItems = () => [...document.querySelectorAll('[role="menu"] [role="menuitem"]')].map((item) => item.textContent?.trim());

it("chưa cần thì không dựng menu; nút trơn vẫn nói là nút mở menu", async () => {
  await render(<ChapterGroups book={book} onDone={() => {}} />);
  const button = menuButton(2);
  expect(button.getAttribute("aria-haspopup")).toBe("menu");
  expect(button.getAttribute("aria-expanded")).toBe("false");
  expect(button.dataset.state).toBe("closed");
  expect(document.querySelector('[role="menu"]')).toBeNull();
});

it("bấm thẳng (không rê chuột trước, như màn cảm ứng) mở menu ngay", async () => {
  await render(<ChapterGroups book={book} onDone={() => {}} onRename={() => {}} />);
  await act(async () => menuButton(2).dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, button: 0, pointerType: "mouse", isPrimary: true })));
  expect(menuItems()).toEqual(["Nghe từ đầu chương", "Đọc chương này", "Đã nghe xong", "Đổi tên chương"]);
  expect(menuButton(2).getAttribute("aria-expanded")).toBe("true");
});

it("Tab vào nút: tiêu điểm ở lại nút (giờ là nút của Radix), Enter mở menu, chọn mục chạy đúng việc", async () => {
  const done = vi.fn();
  await render(<ChapterGroups book={book} onDone={done} />);
  await act(async () => menuButton(3).focus());
  expect(document.activeElement).toBe(menuButton(3));
  await act(async () => menuButton(3).dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })));
  expect(menuItems()).toEqual(["Nghe từ đầu chương", "Đọc chương này", "Đã nghe xong"]);
  // Mở bằng phím: tiêu điểm vào mục đầu như mọi menu Radix.
  expect(document.activeElement?.textContent?.trim()).toBe("Nghe từ đầu chương");
  const item = [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].find((element) => element.textContent?.includes("Đã nghe xong"))!;
  await act(async () => item.click());
  expect(done).toHaveBeenCalledWith(3, true);
});
