// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AddBookDialog } from "./AddBook";

const importer = vi.hoisted(() => ({ preview: vi.fn(), discard: vi.fn(async () => {}) }));
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
