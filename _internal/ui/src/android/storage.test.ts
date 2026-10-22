import { describe, expect, it } from "vitest";
import type { ListenBook } from "@/listen/model";
import { isDownloading, storedEntries } from "./storage";

const book = (id: string, remote = false) => ({ id, title: `Sách ${id}`, remote }) as unknown as ListenBook;

describe("storedEntries", () => {
  it("lists the largest first; a downloaded book is a book, anything else is a partial", () => {
    const sizes = [{ id: "a", bytes: 10 }, { id: "gone", bytes: 99 }, { id: "b", bytes: 300 }, { id: "c", bytes: 20 }];
    const entries = storedEntries(sizes, [book("a"), book("b"), book("c")]);
    expect(entries.map((entry) => [entry.id, entry.kind])).toEqual([["b", "book"], ["gone", "partial"], ["c", "book"], ["a", "book"]]);
  });

  it("books that only exist on the computer are partials (streamed cache), never whole books", () => {
    const entries = storedEntries([{ id: "a", bytes: 5 }, { id: "r", bytes: 7 }], [book("a"), book("r", true)]);
    expect(entries.map((entry) => [entry.id, entry.kind, entry.title])).toEqual([["r", "partial", "Sách r"], ["a", "book", "Sách a"]]);
  });

  it("names a partial from its own manifest, then the computer's list, then a generic name", () => {
    const entries = storedEntries(
      [{ id: "x", bytes: 3, title: "Từ gói" }, { id: "y", bytes: 2 }, { id: "z", bytes: 1 }],
      [],
      new Map([["y", "Từ máy tính"]]),
    );
    expect(entries.map((entry) => entry.title)).toEqual(["Từ gói", "Từ máy tính", "Sách tải dở"]);
  });
});

describe("isDownloading", () => {
  it("is true only while a download event is still running", () => {
    expect(isDownloading(undefined)).toBe(false);
    expect(isDownloading({})).toBe(true);
    expect(isDownloading({ finished: true })).toBe(false);
    expect(isDownloading({ error: "x" })).toBe(false);
    expect(isDownloading({ cancelled: true })).toBe(false);
  });
});
