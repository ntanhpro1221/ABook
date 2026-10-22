import { beforeEach, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import type { ReadSession } from "./importQueue";
import { AddBookDialog } from "./AddBook";

const mocks = vi.hoisted(() => ({
  importer: { choose: vi.fn(), chooseMany: vi.fn(), preview: vi.fn(), discard: vi.fn() },
  changes: [] as unknown[],
  effects: [] as (() => void | (() => void))[],
}));
// Chạy chính callback của hộp; không cần DOM cho bộ chọn native trả Promise.
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (value: unknown) => [value, (next: unknown) => mocks.changes.push(next)],
  useRef: (value: unknown) => ({ current: value }),
  useEffect: (effect: () => void | (() => void)) => { mocks.effects.push(effect); },
}));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }));
vi.mock("react-router", () => ({ useNavigate: () => vi.fn() }));
vi.mock("./source", () => ({ useSource: () => ({ textImport: mocks.importer }) }));
vi.mock("@/shared/ui", () => ({ Button: "button", Dialog: "dialog" }));

function nodes(tree: unknown): ReactElement<Record<string, unknown>>[] {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== "object" || !("props" in tree)) return [];
  const element = tree as ReactElement<Record<string, unknown>>;
  return [element, ...nodes(element.props.children)];
}
function pending<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
beforeEach(() => { vi.clearAllMocks(); mocks.changes.length = 0; mocks.effects.length = 0; mocks.importer.discard.mockResolvedValue(undefined); });
/** Gắn hộp như React: chạy mọi effect của lần vẽ, trả các hàm dọn (gỡ hộp). */
const mount = () => mocks.effects.map((effect) => effect()).filter((cleanup): cleanup is () => void => typeof cleanup === "function");

it("a84_03 only turns on the reversible PDF proposals marked as defaults", async () => {
  mocks.importer.preview.mockResolvedValue({ title: "PDF", chapters: [{ index: 1, title: "Chương 1" }], notes: [], suggestions: [
    { chapter: 1, line: "TÊN SÁCH", defaultOn: true },
    { chapter: 1, line: "Tôi vẫn chờ anh." },
  ] });
  AddBookDialog({ open: true, onOpenChange: vi.fn(), initial: { ref: "a.pdf", name: "a.pdf" } });
  mount();
  await flush();
  const sets = mocks.changes.filter((change) => change instanceof Set) as Set<string>[];
  expect(sets.some((set) => set.has("TÊN SÁCH") && !set.has("Tôi vẫn chờ anh."))).toBe(true);
});

it.each([true, false])("discards a picker result after closing (many=%s)", async (many) => {
  const picked = { ref: "temp/a.epub", name: "a.epub" };
  const late = pending<unknown>();
  mocks.importer.chooseMany = many ? vi.fn(() => late.promise) : undefined as never;
  mocks.importer.choose.mockReturnValue(late.promise);
  const tree = AddBookDialog({ open: true, onOpenChange: vi.fn() });
  const all = nodes(tree);
  (all.find((node) => node.props.children === "Chọn file sách")!.props.onClick as () => void)();
  (all[0].props.onOpenChange as (open: boolean) => void)(false);
  mocks.changes.length = 0;
  late.resolve(many ? [{ name: picked.name, choice: picked }] : picked);
  await flush();
  expect(mocks.importer.preview).not.toHaveBeenCalled();
  expect(mocks.importer.discard).toHaveBeenCalledWith(picked);
  expect(mocks.changes).toEqual([]);
});

it.each([false, true])("passes cancellation through to the book-opening side effect (queue=%s)", async (queue) => {
  const late = pending<void>();
  const opened = vi.fn();
  const onBookFile = async (_path: string, session?: ReadSession) => {
    await late.promise;
    session?.still();
    opened();
  };
  const initial = { ref: "a.abook", name: "a.abook" };
  // Một file chọn riêng đi qua read(), giống đường dẫn dán vào hộp.
  mocks.importer.chooseMany = vi.fn(async () => queue
    ? [{ name: initial.name, choice: initial }, { name: "b.abook", choice: { ref: "b.abook", name: "b.abook" } }]
    : [{ name: initial.name, choice: initial }]);
  const all = nodes(AddBookDialog({ open: true, onOpenChange: vi.fn(), onBookFile }));
  (all.find((node) => node.props.children === "Chọn file sách")!.props.onClick as () => void)();
  await flush();
  (all[0].props.onOpenChange as (open: boolean) => void)(false);
  late.resolve();
  await flush();
  expect(opened).not.toHaveBeenCalled();
});

it("does not show a picker error returned after closing", async () => {
  let reject!: (error: Error) => void;
  mocks.importer.chooseMany = vi.fn(() => new Promise((_resolve, failed) => { reject = failed; }));
  const all = nodes(AddBookDialog({ open: true, onOpenChange: vi.fn() }));
  (all.find((node) => node.props.children === "Chọn file sách")!.props.onClick as () => void)();
  (all[0].props.onOpenChange as (open: boolean) => void)(false);
  mocks.changes.length = 0;
  reject(new Error("late picker error"));
  await flush();
  expect(mocks.changes).toEqual([]);
});

it("cancels a read in progress when the dialog leaves the page", async () => {
  const late = pending<unknown>();
  mocks.importer.preview.mockReturnValue(late.promise);
  AddBookDialog({ open: true, onOpenChange: vi.fn(), initial: { ref: "a.epub", name: "a.epub" } });
  const cleanups = mount();
  await flush();
  expect(mocks.importer.preview).toHaveBeenCalledTimes(1);
  for (const cleanup of cleanups) cleanup();
  mocks.changes.length = 0;
  late.resolve({ title: "Sách muộn", chapters: [] });
  await flush();
  expect(mocks.changes).toEqual([]);
});

it("StrictMode's unmount and remount still reads the shared file", async () => {
  const first = pending<unknown>();
  const second = pending<unknown>();
  mocks.importer.preview.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  AddBookDialog({ open: true, onOpenChange: vi.fn(), initial: { ref: "shared.epub", name: "shared.epub" } });
  for (const cleanup of mount()) cleanup();
  mount();
  await flush();
  expect(mocks.importer.preview).toHaveBeenCalledTimes(2);
  first.resolve({ title: "Lần đọc đã huỷ", chapters: [] });
  const shown = { title: "Sách chia sẻ", chapters: [] };
  second.resolve(shown);
  await flush();
  expect(mocks.changes).toContain(shown);
  expect(mocks.changes).not.toContainEqual({ title: "Lần đọc đã huỷ", chapters: [] });
});
