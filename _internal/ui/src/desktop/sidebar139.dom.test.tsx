// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { BookSummary } from "@/studio/api";
import { MOTION } from "@/shared/motion";

const state = vi.hoisted(() => ({ books: [] as BookSummary[], close: vi.fn() }));
vi.mock("@/studio/data", () => ({ useLibrary: () => ({ data: { books: state.books } }), useAppInfo: () => ({ data: {} }) }));
vi.mock("@/listen/player", () => ({ useNowPlaying: () => ({ setExpanded: state.close }) }));
vi.mock("@/studio/precastInvites", () => ({ usePrecastInvites: vi.fn() }));
import { DesktopSidebar } from "./Shell";

let root: Root, host: HTMLDivElement;
const book = (id: string, queuePosition?: number): BookSummary => ({ id, title: `Sách ${id}`, running: queuePosition === undefined, starting: false, queuePosition, progress: { overall: .42 } }) as BookSummary;
const draw = (path = "/") => act(() => root.render(<MemoryRouter initialEntries={[path]}><DesktopSidebar /></MemoryRouter>));
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); state.books = []; state.close.mockClear();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 200, bottom: 50, width: 200, height: 50, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); host.remove(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });

it.each(["/", "/book/a", "/studio/new", "/settings/devices"])("ba điểm đến, trang con chọn đúng mục: %s", async path => {
  await draw(path);
  const links = [...host.querySelectorAll<HTMLAnchorElement>("[data-sidebar-top]")];
  expect(links.map(link => link.textContent)).toEqual(["Thư viện", "Studio", "Cài đặt"]);
  expect(links.map(link => link.getAttribute("href"))).toEqual(["/", "/studio", "/settings"]);
  const active = path.startsWith("/studio") ? "Studio" : path.startsWith("/settings") ? "Cài đặt" : "Thư viện";
  expect(links.filter(link => link.getAttribute("aria-current") === "page").map(link => link.textContent)).toEqual([active]);
  // Điều hướng: nền trung tính + chữ đậm thường, không dấu tích (dấu tích là của danh sách chọn).
  expect(links.find(link => link.textContent === active)?.className).toContain("bg-hover font-semibold text-fg");
  expect(host.querySelector("aside svg.lucide-check, nav svg.lucide-check")).toBeNull();
  expect(host.querySelector(".bg-accent-soft")).toBeNull();
  expect(host.textContent).not.toMatch(/Nghe|Dự án|Tạo sách nói/);
  expect(links[2].parentElement?.className).toContain("mt-auto");
});

it("ba dự án chạy/chờ, tiến độ mảnh, mở tất cả và thu player khi chọn", async () => {
  state.books = [book("d", 3), book("c", 2), book("a"), book("b", 1)];
  await draw();
  const rows = [...host.querySelectorAll<HTMLButtonElement>(".motion-row button")];
  expect(rows).toHaveLength(3);
  expect(rows.map(row => row.textContent)).toEqual([expect.stringContaining("Sách a"), expect.stringContaining("Sách b"), expect.stringContaining("Sách c")]);
  expect(host.querySelectorAll('[role="progressbar"].h-1')).toHaveLength(3);
  const all = [...host.querySelectorAll("a")].find(link => link.textContent === "Xem tất cả")!;
  expect(all.getAttribute("href")).toBe("/studio");
  await act(() => rows[0].click());
  expect(state.close).toHaveBeenCalledWith(false);
});

it("dự án vào/ra bằng list presence, hàng thoát inert đến hết chuyển động", async () => {
  state.books = [book("a")]; await draw();
  await act(() => vi.advanceTimersByTime(MOTION.medium + 300));
  state.books = [book("a"), book("b", 1)]; await draw();
  expect(host.querySelector('.motion-row[data-state="enter"]')?.textContent).toContain("Sách b");
  await act(() => vi.advanceTimersByTime(MOTION.medium + 300));
  state.books = [book("b", 1)]; await draw();
  const leaving = host.querySelector<HTMLElement>('.motion-row[data-state="exit"]');
  expect(leaving?.textContent).toContain("Sách a"); expect(leaving?.inert).toBe(true);
  await act(() => vi.advanceTimersByTime(MOTION.mediumOut + 300));
  expect(host.querySelectorAll(".motion-row")).toHaveLength(1);
  expect(host.querySelector(".motion-row")?.textContent).toContain("Sách b");
});
