import { describe, expect, it } from "vitest";
import type { BookSummary } from "./api";
import { groupParts } from "./projectGroups";

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
