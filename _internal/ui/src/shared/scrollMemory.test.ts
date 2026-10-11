import { afterEach, describe, expect, it } from "vitest";
import { restoreScroll, revealShift, saveScroll, sessionRead, sessionWrite } from "./scrollMemory";

// Soát a30 L3: trang sách 3000 chương cuộn ở 108.280 px, mở một chương rồi Back thì về đầu; mở trang không tới chương đang nghe.

const globals = globalThis as unknown as Record<string, unknown>;
afterEach(() => {
  delete globals.sessionStorage;
});

function fakeSession() {
  const store = new Map<string, string>();
  globals.sessionStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
  };
  return store;
}

describe("restoreScroll / saveScroll", () => {
  it("quay lại trang: về đúng chỗ đã nhớ của cuốn ấy, không đụng cuốn khác", () => {
    fakeSession();
    saveScroll("book.a", { scrollTop: 108280.4 });
    const page = { scrollTop: 0 };
    let first = 0;
    restoreScroll("book.a", page, () => first++);
    expect(page.scrollTop).toBe(108280);
    expect(first).toBe(0);
    const other = { scrollTop: 0 };
    restoreScroll("book.b", other, (scroller) => (scroller.scrollTop = 500));
    expect(other.scrollTop).toBe(500);
  });

  it("bộ nhớ phiên bị chặn hay hỏng: như mở lần đầu, không văng lỗi", () => {
    globals.sessionStorage = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    expect(() => saveScroll("book.a", { scrollTop: 10 })).not.toThrow();
    expect(() => sessionWrite("x", 1)).not.toThrow();
    expect(sessionRead("x")).toBeNull();
    let first = 0;
    restoreScroll("book.a", { scrollTop: 0 }, () => first++);
    expect(first).toBe(1);
    fakeSession().set("abook.scroll.book.a", "{hỏng");
    restoreScroll("book.a", { scrollTop: 0 }, () => first++);
    expect(first).toBe(2);
  });
});

describe("revealShift: đưa chương đang nghe vào khung", () => {
  it("đã nằm trọn trong khung thì không cuộn", () => {
    expect(revealShift(100, 154, 800)).toBeNull();
    expect(revealShift(0, 800, 800)).toBeNull();
  });

  it("ở xa phía dưới hay phía trên: cuộn để hàng nằm giữa khung", () => {
    expect(revealShift(81270, 81324, 800)).toBe(81270 - 373);
    expect(revealShift(-500, -446, 800)).toBe(-500 - 373);
  });
});
