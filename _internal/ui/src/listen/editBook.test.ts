import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { setApiTransport, type ApiInit } from "@/studio/api";
import { authorSaveable, saveAuthor } from "./EditBook";

// Ô "Tác giả" của hộp Sửa sách: khi nào lưu được, và lệnh gửi đi (PUT /api/books/<mã>/author - abook/webui/book_edits.set_author).

beforeAll(() => {
  const store = new Map<string, string>();
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  } as Storage;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    localStorage: globals.localStorage,
  });
});

afterEach(() => setApiTransport(null));

describe("authorSaveable", () => {
  it("lets a changed name through and nothing else", () => {
    expect(authorSaveable("Nguyễn Nhật Ánh", "")).toBe(true);
    expect(authorSaveable("Nguyễn Nhật Ánh", undefined)).toBe(true);
    expect(authorSaveable("Nguyễn Nhật Ánh", "Nguyễn Nhật Ánh")).toBe(false);
  });

  it("treats stray spaces as no change, as the server cleans them", () => {
    expect(authorSaveable("  Nguyễn   Nhật Ánh ", "Nguyễn Nhật Ánh")).toBe(false);
    expect(authorSaveable("   ", "")).toBe(false);
    expect(authorSaveable("   ", undefined)).toBe(false);
  });

  it("lets the name be cleared when the book has an author", () => {
    expect(authorSaveable("", "Nguyễn Nhật Ánh")).toBe(true);
  });
});

describe("saveAuthor", () => {
  it("sends the typed name and returns what the server kept", async () => {
    const calls: [string, ApiInit | undefined][] = [];
    setApiTransport(async (path, init) => {
      calls.push([path, init]);
      return { author: "Tác giả" };
    });
    expect(await saveAuthor("sach-1", "  Tác   giả ")).toBe("Tác giả");
    expect(calls).toEqual([["/api/books/sach-1/author", { method: "PUT", body: { author: "  Tác   giả " } }]]);
  });

  it("passes an empty name through: the listener clears the author", async () => {
    setApiTransport(async () => ({ author: "" }));
    expect(await saveAuthor("sach-1", "")).toBe("");
  });
});
