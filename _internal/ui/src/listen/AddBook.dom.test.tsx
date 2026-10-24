// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AddBookDialog } from "./AddBook";

const importer = vi.hoisted(() => ({ preview: vi.fn(), discard: vi.fn(async () => {}), choose: vi.fn(), chooseMany: vi.fn() }));
vi.mock("./source", () => ({ useSource: () => ({ textImport: importer }) }));
let root: Root, host: HTMLDivElement, client: QueryClient;
let start: ReturnType<typeof vi.fn>;
function Book({ initial }: { initial?: { ref: string; name: string } }) {
  const [open, setOpen] = useState(true);
  return <AddBookDialog open={open} onOpenChange={setOpen} initial={initial} />;
}
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  start = vi.fn((update: () => void) => { update(); return {}; });
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: start });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
});

it("multi-file step changes keep hidden AddBook controls inert then restore title focus", async () => {
  Reflect.deleteProperty(document, "startViewTransition");
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const title = this.querySelector<HTMLInputElement>('input[placeholder="Tên hiển thị trong thư viện"]');
    const height = title ? title.value === "Sách hai" ? 350 : 500 : 100;
    return { top: 0, left: 0, bottom: height, right: 300, height, width: 300, x: 0, y: 0, toJSON() {} };
  });
  importer.chooseMany.mockResolvedValue(["a", "b"].map(name => ({ name: `${name}.txt`, choice: { ref: `${name}.txt`, name: `${name}.txt` } })));
  importer.preview.mockImplementation(async (choice: { ref: string }) => ({ title: choice.ref === "a.txt" ? "Sách một" : "Sách hai", chapters: [{ index: 1, title: "Chương 1", words: 100 }], notes: [] }));
  await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><Book /></MemoryRouter></QueryClientProvider>));
  await act(async () => [...document.querySelectorAll("button")].find(b => b.textContent === "Chọn file sách")!.click());
  const skip = [...document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')].find(b => b.textContent?.includes("Bỏ cuốn này") && !b.closest(".motion-snapshot"))!;
  const body = skip.closest<HTMLElement>("[data-motion-region]")!;
  expect(body).not.toBeNull();
  expect(body.hasAttribute("inert")).toBe(true);
  const calls = importer.preview.mock.calls.length;
  await act(() => skip.click()); expect(importer.preview).toHaveBeenCalledTimes(calls);
  const finish = () => {
    for (const result of vi.mocked(HTMLElement.prototype.animate).mock.results) (result.value as Animation).onfinish?.(new Event("finish") as AnimationPlaybackEvent);
  };
  await act(finish);
  expect(body.hasAttribute("inert")).toBe(false);
  await act(async () => skip.click());
  expect(importer.preview).toHaveBeenCalledTimes(calls + 1);
  await act(finish);
  expect(body.hasAttribute("inert")).toBe(false);
  expect(body.querySelector<HTMLInputElement>('input[placeholder="Tên hiển thị trong thư viện"]')?.value).toBe("Sách hai");
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); Reflect.deleteProperty(document, "startViewTransition"); vi.restoreAllMocks(); });
for (const preview of [false, true]) for (const method of ["X", "Escape"]) it(`closing AddBook via ${method} never starts a global transition, preview=${preview}`, async () => {
  importer.preview.mockResolvedValue({ title: "Sách thử", chapters: [{ index: 1, title: "Chương 1", words: 100 }], notes: [] });
  await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><Book initial={preview ? { ref: "a.txt", name: "a.txt" } : undefined} /></MemoryRouter></QueryClientProvider>));
  expect(document.querySelector('[role="dialog"][data-state="open"]')).not.toBeNull();
  expect(document.querySelector('[role="dialog"] [data-motion-region]')).not.toBeNull();
  start.mockClear();
  await act(() => {
    if (method === "X") document.querySelector<HTMLButtonElement>('[role="dialog"] button[aria-label="Đóng"]')!.click();
    else document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  });
  expect(start).not.toHaveBeenCalled();
  expect(document.querySelector('[role="dialog"][data-state="open"]')).toBeNull();
  if (preview) expect(importer.discard).toHaveBeenCalledWith({ ref: "a.txt", name: "a.txt" });
});
