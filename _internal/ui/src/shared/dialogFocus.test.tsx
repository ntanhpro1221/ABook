import { beforeAll, describe, expect, it } from "vitest";
import { dialogOpener, focusReturnTarget } from "./ui";

// Hộp thoại đóng thì con trỏ về đúng phần tử đã mở nó (soát UX a17: Esc xong con trỏ rơi về BODY). Không có DOM trong vitest -
// dùng phần tử giả có đúng các trường hàm đọc.
beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

const fake = (connected: boolean) => ({ isConnected: connected, focus: () => undefined }) as unknown as Element;

describe("focusReturnTarget", () => {
  it("trả về phần tử đã mở hộp khi nó còn trong trang", () => {
    const opener = fake(true);
    expect(focusReturnTarget(opener, fake(true))).toBe(opener);
  });

  it("không trả gì khi hộp mở không từ phần tử nào (con trỏ ở body) hay phần tử đã bị gỡ", () => {
    const body = fake(true);
    expect(focusReturnTarget(body, body)).toBeNull();
    expect(focusReturnTarget(null, body)).toBeNull();
    expect(focusReturnTarget(fake(false), body)).toBeNull();
  });
});

describe("dialogOpener", () => {
  /** Phần tử giả: `closest('[role="menu"]')` trả `menu`; `ownerDocument.getElementById` tra trong `byId`. */
  const element = (menu: Element | null, byId: Record<string, Element> = {}) =>
    ({ closest: () => menu, ownerDocument: { getElementById: (id: string) => byId[id] ?? null } }) as unknown as Element;

  it("phần tử thường mở hộp thì chính nó", () => {
    const button = element(null);
    expect(dialogOpener(button)).toBe(button);
    expect(dialogOpener(null)).toBeNull();
  });

  it("mục của menu mở hộp thì nút mở menu (aria-labelledby của menu)", () => {
    const trigger = element(null);
    const menu = { getAttribute: (name: string) => (name === "aria-labelledby" ? "nut-menu" : null) } as unknown as Element;
    expect(dialogOpener(element(menu, { "nut-menu": trigger }))).toBe(trigger);
  });

  it("menu không có nút mở (đã gỡ) thì không có gì để trả con trỏ về", () => {
    const menu = { getAttribute: () => null } as unknown as Element;
    expect(dialogOpener(element(menu))).toBeNull();
  });
});
