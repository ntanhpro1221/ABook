import { describe, expect, it, vi } from "vitest";
import {
  addRest,
  addWithDefaults,
  advanceQueue,
  buildQueue,
  itemFromPath,
  planPick,
  queueLabel,
  queueTotal,
  settle,
  summarize,
  summaryText,
  waitingAfter,
} from "./importQueue";
import type { AddedBook, ImportChoice, ImportPreview, PickedItem, TextImport } from "./textImport";

// Chọn / kéo thả nhiều file vào "Thêm sách từ file…": hàng xem trước, lỗi một file không chặn các file sau, "Thêm tất cả phần còn lại" dùng đúng mặc định
// của bước xem trước, một file thì y như cũ.

const choice = (name: string): ImportChoice => ({ ref: `C:\\Sách\\${name}`, name });
const ok = (name: string): PickedItem => ({ name, choice: choice(name) });

const preview = (title: string, extra: Partial<ImportPreview> = {}): ImportPreview => ({
  title,
  author: null,
  chapters: [
    { index: 1, title: "Bìa", firstLine: "Bìa", words: 2, chars: 10, included: false, short: true },
    { index: 2, title: "Chương 1", firstLine: "…", words: 100, chars: 500 },
  ],
  notes: [],
  hasCover: false,
  totals: { chapters: 2, words: 102 },
  ...extra,
});

/** Nguồn giả: mỗi file một bản xem trước (hay một lỗi); ghi lại mọi lần `add`. */
function fakeImporter(previews: Record<string, ImportPreview | Error>) {
  const added: { name: string; title: string; options: unknown }[] = [];
  const importer: Pick<TextImport, "preview" | "add" | "discard"> = {
    preview: async (picked, options) => {
      const found = previews[picked.name];
      if (!found) throw new Error("không có bản xem trước");
      if (found instanceof Error) throw found;
      return options?.splitChapters && found.splitOffer ? { ...found, title: `${found.title} (tách)` } : found;
    },
    add: async (picked, title, _separate, options) => {
      added.push({ name: picked.name, title, options });
      return { id: `id-${picked.name}`, how: "new", chapters: 1 } satisfies AddedBook;
    },
    discard: vi.fn(async () => undefined),
  };
  return { importer, added };
}

describe("buildQueue", () => {
  it("numbers the readable files in the order picked and lists the unreadable ones without a number", () => {
    const items = buildQueue([ok("a.epub"), { name: "anh.jpg", error: "Không nhận" }, ok("b.txt"), { name: "c.abook", opened: true }]);
    expect(items.map((item) => [item.name, item.state, item.number])).toEqual([
      ["a.epub", "waiting", 1],
      ["anh.jpg", "error", undefined],
      ["b.txt", "waiting", 2],
      ["c.abook", "opened", undefined],
    ]);
    expect(queueTotal(items)).toBe(2);
    expect(queueLabel(items, items[2].id)).toBe("Sách 2/2");
    expect(queueLabel(items, items[1].id)).toBe("");
  });

  it("puts .abook and .abookproj files last, because opening them leaves for the book page", () => {
    const items = buildQueue([ok("x.abook"), ok("a.epub"), ok("y.ABOOKPROJ"), ok("b.pdf")]);
    expect(items.map((item) => item.name)).toEqual(["a.epub", "b.pdf", "x.abook", "y.ABOOKPROJ"]);
    expect(queueLabel(items, items[0].id)).toBe("Sách 1/4");
  });
});

describe("itemFromPath", () => {
  it("accepts the kinds a single file accepts, names the rest, and lets a path with no extension through as a possible folder", () => {
    expect(itemFromPath("D:\\Truyện\\Tên truyện.epub")).toEqual({ name: "Tên truyện.epub", choice: { ref: "D:\\Truyện\\Tên truyện.epub", name: "Tên truyện.epub" } });
    for (const name of ["a.docx", "b.PDF", "c.txt", "d.abook", "e.abookproj"]) expect(itemFromPath(`/x/${name}`)).toHaveProperty("choice");
    expect(itemFromPath("D:/Truyện/Tập 1")).toHaveProperty("choice");
    const refused = itemFromPath("D:/Ảnh/bìa.JPG");
    expect(refused).toMatchObject({ name: "bìa.JPG" });
    expect((refused as { error: string }).error).toContain(".jpg");
  });
});

describe("planPick", () => {
  it("keeps one file as it is today and only queues from two files on", () => {
    expect(planPick([])).toEqual({ kind: "none" });
    expect(planPick([ok("a.epub")])).toEqual({ kind: "single", item: ok("a.epub") });
    expect(planPick([{ name: "anh.jpg", error: "Không nhận" }])).toEqual({ kind: "single", item: { name: "anh.jpg", error: "Không nhận" } });
    const plan = planPick([ok("a.epub"), ok("b.epub")]);
    expect(plan.kind).toBe("queue");
  });
});

describe("advanceQueue", () => {
  it("steps through the files; a file that cannot be read is marked and the next one still opens", async () => {
    const queue = buildQueue([ok("a.epub"), ok("hong.pdf"), ok("b.txt")]);
    const opened: string[] = [];
    const load = async (item: { name: string }) => {
      if (item.name === "hong.pdf") throw new Error("PDF này không có chữ.");
      opened.push(item.name);
    };
    const failed = vi.fn();
    const first = await advanceQueue(queue, load, async (items) => items, failed);
    expect(first.current?.name).toBe("a.epub");
    // người dùng thêm a.epub xong -> sang cuốn kế: hong.pdf lỗi, b.txt mở
    const afterA = settle(first.items, first.current!.id, { state: "added", bookId: "id-a" });
    const second = await advanceQueue(afterA, load, async (items) => items, failed);
    expect(second.current?.name).toBe("b.txt");
    expect(second.items.find((item) => item.name === "hong.pdf")).toMatchObject({ state: "error", note: "PDF này không có chữ." });
    expect(failed).toHaveBeenCalledTimes(1);
    expect(opened).toEqual(["a.epub", "b.txt"]);
    const done = await advanceQueue(settle(second.items, second.current!.id, { state: "added" }), load, async (items) => items);
    expect(done.current).toBeNull();
    expect(summarize(done.items)).toMatchObject({ added: 2, failed: 1 });
  });

  it("hands the .abook files to openBooks once only those are left", async () => {
    const queue = buildQueue([ok("x.abook"), ok("a.epub")]);
    const load = vi.fn(async () => undefined);
    const afterA = settle(queue, queue.find((item) => item.name === "a.epub")!.id, { state: "added" });
    const openBooks = vi.fn(async (items) => items.map((item: { state: string }) => ({ ...item, state: item.state === "waiting" ? "opened" : item.state })));
    const result = await advanceQueue(afterA, load, openBooks);
    expect(load).not.toHaveBeenCalled();
    expect(openBooks).toHaveBeenCalledTimes(1);
    expect(result.current).toBeNull();
    expect(result.items.find((item) => item.name === "x.abook")?.state).toBe("opened");
  });
});

describe("addWithDefaults", () => {
  it("adds with the file's own name and the default chapters, without any pick the listener did not make", async () => {
    const { importer, added } = fakeImporter({ "a.epub": preview("Chuyến phà") });
    expect(await addWithDefaults(importer, choice("a.epub"))).toEqual({ state: "added", note: undefined, bookId: "id-a.epub" });
    expect(added).toEqual([{ name: "a.epub", title: "Chuyến phà", options: { splitChapters: false } }]);
  });

  it("splits a whole-story TXT when the machine is sure, like the preview step", async () => {
    const { importer, added } = fakeImporter({ "t.txt": preview("Truyện", { splitOffer: 12, splitHeadings: 12 }) });
    await addWithDefaults(importer, choice("t.txt"));
    expect(added[0]).toMatchObject({ title: "Truyện (tách)", options: { splitChapters: true } });
  });

  it("does not add a book the library already has (the preview step offers “Mở cuốn đó”, not Add)", async () => {
    const { importer, added } = fakeImporter({
      "a.epub": preview("Đã có", { existing: { id: "cu", title: "Đã có" } }),
      "b.epub": preview("Cùng file", { sameSource: { id: "cu2", title: "Cùng file", chapters: 3 } }),
    });
    expect(await addWithDefaults(importer, choice("a.epub"))).toEqual({ state: "existing", note: "Đã có trong thư viện", bookId: "cu" });
    expect(await addWithDefaults(importer, choice("b.epub"))).toMatchObject({ state: "existing", bookId: "cu2" });
    expect(added).toEqual([]);
  });

  it("refuses a book with no name or no chapter to add, and passes a read error on", async () => {
    const { importer } = fakeImporter({
      "ten.epub": preview("  "),
      "rong.epub": preview("Rỗng", { chapters: [] }),
      "hong.epub": new Error("File EPUB bị hỏng."),
    });
    await expect(addWithDefaults(importer, choice("ten.epub"))).rejects.toThrow(/tên sách/);
    await expect(addWithDefaults(importer, choice("rong.epub"))).rejects.toThrow(/chưa có chương/);
    await expect(addWithDefaults(importer, choice("hong.epub"))).rejects.toThrow("File EPUB bị hỏng.");
  });
});

describe("addRest (“Thêm tất cả phần còn lại”)", () => {
  it("adds every later book with the defaults, notes the one that fails, and never stops", async () => {
    const queue = buildQueue([ok("a.epub"), ok("b.epub"), ok("hong.epub"), ok("c.epub"), { name: "anh.jpg", error: "Không nhận" }]);
    const { importer, added } = fakeImporter({
      "b.epub": preview("Sách B"),
      "hong.epub": new Error("File EPUB bị hỏng."),
      "c.epub": preview("Sách C", { existing: { id: "cu", title: "Sách C" } }),
    });
    const seen: string[] = [];
    const items = await addRest(importer, queue, queue[0].id, { state: "added", bookId: "id-a" }, { working: (name) => seen.push(name), openBooks: async (rest) => rest });
    expect(items.map((item) => [item.name, item.state])).toEqual([
      ["a.epub", "added"],
      ["b.epub", "added"],
      ["hong.epub", "error"],
      ["c.epub", "existing"],
      ["anh.jpg", "error"],
    ]);
    expect(items[2].note).toBe("File EPUB bị hỏng.");
    expect(added.map((entry) => entry.name)).toEqual(["b.epub"]);
    expect(seen).toEqual(["c.epub", "hong.epub", "b.epub"]); // từ cuốn cuối về trước: thư viện xếp cuốn mới lên đầu
    expect(importer.discard).toHaveBeenCalledTimes(1); // bản tạm của cuốn hỏng
    expect(summarize(items)).toEqual({ added: 2, existing: 1, skipped: 0, failed: 2, opened: 0 });
  });

  it("adds the book being viewed last, so the library (newest on top) shows the batch in the order picked", async () => {
    const queue = buildQueue([ok("a.epub"), ok("b.epub"), ok("c.epub")]);
    const { importer, added } = fakeImporter({ "b.epub": preview("B"), "c.epub": preview("C") });
    const order: string[] = [];
    const items = await addRest(
      importer,
      queue,
      queue[0].id,
      async () => {
        order.push(...added.map((entry) => entry.name), "a.epub");
        return { state: "added", bookId: "id-a" };
      },
      { openBooks: async (rest) => rest },
    );
    expect(order).toEqual(["c.epub", "b.epub", "a.epub"]);
    expect(items.map((item) => [item.name, item.state])).toEqual([
      ["a.epub", "added"],
      ["b.epub", "added"],
      ["c.epub", "added"],
    ]);
  });

  it("leaves the .abook files for openBooks, after the text books", async () => {
    const queue = buildQueue([ok("a.epub"), ok("x.abook"), ok("b.epub")]);
    const { importer, added } = fakeImporter({ "b.epub": preview("B") });
    const openBooks = vi.fn(async (rest) => rest);
    const items = await addRest(importer, queue, queue[0].id, { state: "added" }, { openBooks });
    expect(added.map((entry) => entry.name)).toEqual(["b.epub"]);
    expect(openBooks).toHaveBeenCalledTimes(1);
    expect(waitingAfter(items, queue[0].id).map((item) => item.name)).toEqual(["x.abook"]);
  });
});

describe("summaryText", () => {
  it("says what happened in the listener's words", () => {
    expect(summaryText({ added: 3, existing: 1, skipped: 0, failed: 1, opened: 0 })).toBe("Đã thêm 3 sách · 1 cuốn đã có trong thư viện · 1 file chưa đọc được");
    expect(summaryText({ added: 0, existing: 0, skipped: 2, failed: 0, opened: 0 })).toBe("Bỏ qua 2 cuốn");
    expect(summaryText({ added: 0, existing: 0, skipped: 0, failed: 0, opened: 0 })).toBe("Không thêm cuốn nào");
  });
});
