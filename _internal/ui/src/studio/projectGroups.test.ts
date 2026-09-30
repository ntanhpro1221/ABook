import { describe, expect, it } from "vitest";
import type { BookSummary } from "./api";
import { groupParts, splitLive } from "./projectGroups";

const book = (id: string, title: string) => ({ id, title }) as unknown as BookSummary;

describe("groupParts", () => {
  it("keeps the parts of a continued book together, in part order, where the newest one stands", () => {
    const entries = groupParts([book("p3", "Nageki · Phần 3"), book("x", "Sách lẻ"), book("p1", "Nageki"), book("p2", "Nageki · Phần 2")]);
    expect(entries.map((entry) => (entry.kind === "book" ? entry.book.id : entry.books.map((item) => item.id)))).toEqual([
      ["p1", "p2", "p3"],
      "x",
    ]);
    expect(entries[0]).toMatchObject({ kind: "series", name: "Nageki", unit: "phần" });
  });

  it("leaves a single volume on its own", () => {
    expect(groupParts([book("a", "Truyện · Tập 1"), book("b", "Khác")]).map((entry) => entry.kind)).toEqual(["book", "book"]);
  });
});

describe("splitLive", () => {
  it("lifts the whole series of a running part into the running section, not the part alone", () => {
    const running = { ...book("p2", "Nageki · Phần 2"), running: true, paused: "listener" } as BookSummary;
    const { live, rest, books } = splitLive(groupParts([book("p1", "Nageki"), running, book("x", "Sách lẻ")]));
    expect(live).toHaveLength(1);
    expect(live[0]).toMatchObject({ kind: "series", name: "Nageki" });
    expect(rest.map((entry) => (entry.kind === "book" ? entry.book.id : entry.name))).toEqual(["x"]);
    expect(books.map((item) => item.id)).toEqual(["p2"]);
  });
});
