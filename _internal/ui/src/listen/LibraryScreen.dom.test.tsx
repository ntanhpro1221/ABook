// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { LibraryScreen } from "./LibraryScreen";
import type { ListenBook } from "./model";

const state = vi.hoisted(() => ({ books: [] as ListenBook[] }));
vi.mock("./player", () => ({ usePlayer: () => ({ track: null, playing: false }) }));
vi.mock("./source", () => ({
  useSource: () => ({ kind: "desktop" }),
  useListenLibrary: () => ({ data: state.books, isLoading: false }),
  useReadAloudVoices: () => ({ data: [] }),
  useListenBook: () => ({}),
}));
let root: Root, main: HTMLElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); sessionStorage.clear(); localStorage.clear();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ top: 0, left: 0, bottom: 200, right: 300, height: 200, width: 300, x: 0, y: 0, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  state.books = Array.from({ length: 6 }, (_, i) => ({
    id: String(i), title: "Book " + i, duration: 600, narrator: "", chaptersTotal: 1, chaptersAvailable: 1,
    complete: true, producing: false, updatedAt: null, state: { chapters: {}, bookmarks: [] },
    progress: { heardSeconds: 0, totalSeconds: 600, fraction: 0, chaptersDone: 0, finished: false },
  } as ListenBook));
  main = document.createElement("main"); main.style.overflowY = "auto"; document.body.append(main); root = createRoot(main);
});
afterEach(async () => { await act(() => root.unmount()); vi.runAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); document.body.replaceChildren(); });

it.each(["filter", "sort", "search"])("%s fades results without copying library header, continue card or controls", async change => {
  await act(() => root.render(<MemoryRouter><LibraryScreen /></MemoryRouter>));
  await act(() => {
    if (change === "filter") [...main.querySelectorAll("button")].find(b => b.textContent === "Nghe xong")!.click();
    else if (change === "sort") {
      const select = main.querySelector("select")!; select.value = "author"; select.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      const input = main.querySelector("input")!;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "nothing matches");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  const images = [...document.querySelectorAll<HTMLElement>(".motion-snapshot")];
  expect(images.length).toBeGreaterThan(0);
  for (const image of images) {
    expect(image.querySelector("h1, select, input[type=search]")).toBeNull();
    expect(image.hasAttribute("inert")).toBe(true);
  }
  expect(main.querySelectorAll("h1")).toHaveLength(1);
  if (change === "filter" || change === "search") {
    // The old grouped rows live in the inert snapshot only. They must not be
    // rendered again as a flat exiting shelf under that image.
    expect(main.querySelector('[role="listitem"]')).toBeNull();
  }
});

const draw = () => act(() => root.render(<MemoryRouter><LibraryScreen header={<button>Thêm sách</button>} /></MemoryRouter>));
const search = (text: string) => act(() => {
  const input = main.querySelector("input")!;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, text);
  input.dispatchEvent(new Event("input", { bubbles: true }));
});

it("V6 header action có khoảng trống cho focus ring bên trong Collapse", async () => {
  await draw();
  const button = [...main.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent === "Thêm sách")!;
  button.focus(); expect(document.activeElement).toBe(button);
  const flow = button.closest(".motion-flow")!;
  expect(flow.classList.contains("-m-1")).toBe(true);
  expect(flow.querySelector(".motion-collapse > .flow-root")!.classList.contains("p-1")).toBe(true);
});

it("the last book leaves an animated header count and exiting actions", async () => {
  state.books = state.books.slice(0, 1); await draw();
  const count = main.querySelector("header p")!;
  vi.mocked(HTMLElement.prototype.animate).mockClear();
  state.books = []; await draw();
  const exit = main.querySelector('header .motion-panel[data-state="closed"]');
  expect(exit?.textContent).toContain("Thêm sách");
  expect(exit?.hasAttribute("inert")).toBe(true);
  expect(vi.mocked(HTMLElement.prototype.animate).mock.contexts).toContain(count);
  expect(document.querySelector('.motion-snapshot')?.textContent).toContain("1 cuốn");
});

it.each(["battery", "eta"])("upcoming text animates a same-ID %s update", async change => {
  state.books = [{ ...state.books[0], chaptersAvailable: 0, producing: true }]; await draw();
  vi.mocked(HTMLElement.prototype.animate).mockClear();
  state.books = [{ ...state.books[0], ...(change === "battery" ? { pauseReason: "battery" as const } : { eta: { phase: "analysis" as const, seconds: 300 } }) }];
  await draw();
  const box = [...main.querySelectorAll("[data-motion-region]")].find(e => e.textContent?.includes(change === "battery" ? "máy đang chạy pin" : "chương đầu nghe được"));
  expect(box).toBeDefined();
  const calls = vi.mocked(HTMLElement.prototype.animate);
  expect(calls.mock.contexts).toContain(box);
  expect(calls.mock.calls[calls.mock.contexts.indexOf(box as HTMLElement)][0]).toEqual(expect.arrayContaining([expect.objectContaining({ opacity: 1 })]));
});

it("no-results wording fades when raw query changes case", async () => {
  await draw(); await search("zz"); await act(() => vi.advanceTimersByTime(500));
  vi.mocked(HTMLElement.prototype.animate).mockClear(); await search("ZZ");
  expect(main.textContent).toContain("“ZZ”");
  expect(vi.mocked(HTMLElement.prototype.animate).mock.calls.length).toBeGreaterThan(0);
  expect([...document.querySelectorAll(".motion-snapshot")].some(e => e.textContent?.includes("“zz”"))).toBe(true);
});

it("identical search membership retains the focused tile and Windowed blocks", async () => {
  state.books = Array.from({ length: 200 }, (_, i) => ({ ...state.books[0], id: String(i), title: `Book ${i}` }));
  await draw(); await search("B"); await act(() => vi.advanceTimersByTime(500));
  const tile = main.querySelector('[role="listitem"]')!;
  const button = tile.querySelector<HTMLElement>("button[tabindex]")!; await act(() => button.focus());
  const blocks = [...main.querySelectorAll('[role="list"] > div')];
  await search("Bo");
  expect(tile.isConnected).toBe(true); expect(document.activeElement).toBe(button);
  expect(blocks.every(block => block.isConnected)).toBe(true);
});

it("same-structure membership changes keep row presence and fade the result region", async () => {
  state.books = state.books.slice(0, 3); await draw(); await search("B");
  await act(() => vi.advanceTimersByTime(500));
  const tile = main.querySelector('[role="listitem"]')!;
  vi.mocked(HTMLElement.prototype.animate).mockClear();
  state.books = state.books.slice(1); await draw();
  expect(tile.isConnected).toBe(true); expect(tile.getAttribute("data-state")).toBe("exit");
  expect(tile.hasAttribute("inert")).toBe(true);
  expect(vi.mocked(HTMLElement.prototype.animate).mock.calls.length).toBeGreaterThan(0);
  await act(() => vi.advanceTimersByTime(500)); expect(tile.isConnected).toBe(false);
});
