import { afterEach, describe, expect, it } from "vitest";
import { pageFocusKey, scrollMotion } from "./motion";

// Soát a31 K2 (tiêu điểm sang h1 khi đổi trang) và M2 (mọi chỗ cuộn mượt đi qua một hàm kiểm "giảm chuyển động").

const globals = globalThis as unknown as Record<string, unknown>;
const original = globals.window;

function reduceMotion(reduce: boolean) {
  globals.window = { matchMedia: (query: string) => ({ matches: reduce && query.includes("reduce") }) };
}

afterEach(() => {
  globals.window = original;
});

describe("pageFocusKey", () => {
  it("đổi chương trong chế độ Đọc là cùng một trang - chương tự sang khi đang nghe không giật tiêu điểm", () => {
    expect(pageFocusKey("/book/a/read/c1")).toBe(pageFocusKey("/book/a/read/c2"));
    expect(pageFocusKey("/book/a/read")).toBe(pageFocusKey("/book/a/read/c2"));
  });

  it("trang khác nhau thì khoá khác nhau", () => {
    expect(pageFocusKey("/book/a")).not.toBe(pageFocusKey("/book/a/read/c1"));
    expect(pageFocusKey("/studio/a")).not.toBe(pageFocusKey("/studio/b"));
    expect(pageFocusKey("/")).toBe("/");
  });
});

describe("scrollMotion", () => {
  it("trượt êm, trừ khi người dùng xin giảm chuyển động", () => {
    reduceMotion(false);
    expect(scrollMotion()).toBe("smooth");
    expect(scrollMotion(false)).toBe("auto");
    reduceMotion(true);
    expect(scrollMotion()).toBe("auto");
  });

  it("không có matchMedia (trình dựng thử) thì vẫn chạy", () => {
    globals.window = {};
    expect(scrollMotion()).toBe("smooth");
  });
});
