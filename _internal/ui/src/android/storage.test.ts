import { describe, expect, it } from "vitest";
import type { ListenBook } from "@/listen/model";
import { booksBySize } from "./storage";

const book = (id: string, remote = false) => ({ id, title: `Sách ${id}`, remote }) as unknown as ListenBook;

describe("booksBySize", () => {
  it("lists the largest book first and skips folders that match no book", () => {
    const sizes = [{ id: "a", bytes: 10 }, { id: "gone", bytes: 99 }, { id: "b", bytes: 300 }, { id: "c", bytes: 20 }];
    expect(booksBySize(sizes, [book("a"), book("b"), book("c")]).map((entry) => entry.book.id)).toEqual(["b", "c", "a"]);
  });

  it("leaves out books that only exist on the computer", () => {
    expect(booksBySize([{ id: "a", bytes: 5 }, { id: "r", bytes: 7 }], [book("a"), book("r", true)]).map((entry) => entry.book.id)).toEqual(["a"]);
  });
});
