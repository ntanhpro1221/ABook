import { beforeEach, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import type { ReadSession } from "./importQueue";
import { AddBookDialog } from "./AddBook";

const mocks = vi.hoisted(() => ({
  importer: { choose: vi.fn(), chooseMany: vi.fn(), preview: vi.fn(), discard: vi.fn() },
  changes: [] as unknown[],
}));
// Chạy chính callback của hộp; không cần DOM cho bộ chọn native trả Promise.
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useState: (value: unknown) => [value, (next: unknown) => mocks.changes.push(next)],
  useRef: (value: unknown) => ({ current: value }),
  useEffect: () => undefined,
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
beforeEach(() => { vi.clearAllMocks(); mocks.changes.length = 0; mocks.importer.discard.mockResolvedValue(undefined); });

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
