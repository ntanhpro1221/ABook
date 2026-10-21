import { afterEach, describe, expect, it } from "vitest";
import { BOOK_STORAGE, moveBookStorage } from "./bookStorage";

function memoryStorage(entries: Record<string, string>) {
  const store = new Map(Object.entries(entries));
  (globalThis as unknown as { localStorage: Storage }).localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  } as Storage;
  return store;
}

afterEach(() => {
  delete (globalThis as { localStorage?: Storage }).localStorage;
});

describe("những gì máy này nhớ theo mã sách", () => {
  it("cuốn đổi mã mang theo mọi khoá của nó, khoá cũ bỏ, cuốn khác không đụng", () => {
    const store = memoryStorage({
      [`${BOOK_STORAGE.readAloudVoice}old`]: "edge:vi-VN-NamMinhNeural",
      [`${BOOK_STORAGE.readAloudVoiceAt}old`]: "123",
      [`${BOOK_STORAGE.reading}old`]: '{"chapterId":2,"index":5}',
      [`${BOOK_STORAGE.suggestionsDismissed}old`]: '["dòng"]',
      [`${BOOK_STORAGE.editsSentSeen}old`]: "99",
      [`${BOOK_STORAGE.reading}other`]: "giữ",
    });
    moveBookStorage("old", "new");
    expect(Object.fromEntries(store)).toEqual({
      [`${BOOK_STORAGE.readAloudVoice}new`]: "edge:vi-VN-NamMinhNeural",
      [`${BOOK_STORAGE.readAloudVoiceAt}new`]: "123",
      [`${BOOK_STORAGE.reading}new`]: '{"chapterId":2,"index":5}',
      [`${BOOK_STORAGE.suggestionsDismissed}new`]: '["dòng"]',
      [`${BOOK_STORAGE.editsSentSeen}new`]: "99",
      [`${BOOK_STORAGE.reading}other`]: "giữ",
    });
  });

  it("bộ nhớ bị chặn thì thôi, không văng", () => {
    (globalThis as unknown as { localStorage: Storage }).localStorage = {
      getItem: () => { throw new Error("chặn"); },
    } as unknown as Storage;
    expect(() => moveBookStorage("old", "new")).not.toThrow();
  });
});
