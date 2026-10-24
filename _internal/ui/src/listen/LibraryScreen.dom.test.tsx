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
