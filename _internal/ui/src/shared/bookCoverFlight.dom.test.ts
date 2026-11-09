// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { captureBookCover, landBookCover } from "./bookCoverFlight";

let complete: () => void;
const box = (x: number, y: number, width: number, height: number): DOMRect =>
  ({ x, y, left: x, top: y, width, height, right: x + width, bottom: y + height, toJSON() {} });
beforeEach(() => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: false } as MediaQueryList);
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({
    finished: new Promise<void>(resolve => { complete = resolve; }), cancel() {},
  }) as unknown as Animation);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    return this.dataset.target ? box(260, 100, 192, 288) : box(40, 300, 160, 240);
  });
});
afterEach(() => { captureBookCover("", ""); document.body.replaceChildren(); vi.restoreAllMocks(); });

it.each([false, true])("book cover moves at full opacity and cleans up in either direction (back=%s)", async back => {
  document.body.innerHTML = '<div data-book-cover="b"></div>';
  const source = document.body.firstElementChild as HTMLElement;
  captureBookCover(back ? "/book/b" : "/", back ? "/" : "/book/b");
  const clone = document.querySelector<HTMLElement>("[data-book-cover-flight]")!;
  expect(clone.style.position).toBe("fixed");
  expect(source.style.visibility).toBe("");
  source.remove();
  const target = document.createElement("div"); target.dataset.bookCover = "b"; target.dataset.target = "1"; document.body.prepend(target);
  landBookCover(back);
  expect(clone.animate).toHaveBeenCalledWith([
    { transform: "none", opacity: 1 }, { transform: "translate(220px, -200px) scale(1.2)", opacity: 1 },
  ], expect.objectContaining({ duration: back ? 200 : 300 }));
  expect(target.style.visibility).toBe("hidden");
  complete(); await Promise.resolve();
  expect(target.style.visibility).toBe("");
  expect(clone.isConnected).toBe(false);
});

it("interrupted navigation and a missing target restore visibility without a leaked overlay", () => {
  document.body.innerHTML = '<div data-book-cover="b"></div>';
  const source = document.body.firstElementChild as HTMLElement;
  captureBookCover("/", "/book/b"); captureBookCover("/book/b", "/settings");
  expect(source.style.visibility).toBe("");
  expect(document.querySelector("[data-book-cover-flight]")).toBeNull();
  captureBookCover("/", "/book/b"); source.remove(); landBookCover(false); captureBookCover("", "");
  expect(document.querySelector("[data-book-cover-flight]")).toBeNull();
});

it("a book query may publish its cover after the route has committed", async () => {
  let frame: FrameRequestCallback = () => {};
  vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation(cb => { frame = cb; return 1; });
  document.body.innerHTML = '<div data-book-cover="b"></div>';
  captureBookCover("/", "/book/b"); document.querySelector('[data-book-cover="b"]')!.remove();
  landBookCover(false);
  expect(document.querySelector("[data-book-cover-flight]")).not.toBeNull();
  const target = document.createElement("div"); target.dataset.bookCover = "b"; target.dataset.target = "1"; document.body.prepend(target);
  frame(16);
  expect(target.style.visibility).toBe("hidden");
  expect(target.animate).toHaveBeenCalled();
  complete(); await Promise.resolve();
  expect(target.style.visibility).toBe("");
});

it("reduced motion keeps the actual cover and creates no flying geometry", () => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: true } as MediaQueryList);
  document.body.innerHTML = '<div data-book-cover="b"></div>';
  captureBookCover("/", "/book/b"); landBookCover(false);
  expect(document.querySelector("[data-book-cover-flight]")).toBeNull();
  expect((document.body.firstElementChild as HTMLElement).style.visibility).toBe("");
});
