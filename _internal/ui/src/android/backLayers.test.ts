// @vitest-environment node
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";
import { backLayerCount, pushBackLayer, topBackLayer } from "@/shared/backStack";
import { backStep, closingLayers, dismissTopLayer, hasActionToast, hasOpenLayer, historyIndex, isOpenLayer, parentPath } from "./backLayers";

class FakeKeyboardEvent {
  constructor(
    public type: string,
    public init: { key: string },
  ) {}
  get key() {
    return this.init.key;
  }
}
(globalThis as unknown as Record<string, unknown>).KeyboardEvent ??= FakeKeyboardEvent;

type Fake = { getAttribute(name: string): string | null; contains(other: unknown): boolean; children: Fake[] };

const el = (role: string | null, state: string | null, children: Fake[] = []): Fake => ({
  getAttribute: (name: string) => (name === "role" ? role : name === "data-state" ? state : null),
  contains: (other: unknown) => other === children[0] || children.some((child) => child === other || child.contains(other)),
  children,
});

function fakeDocument(elements: Fake[], toast: "none" | "plain" | "action" = "none") {
  const events: { type: string; key: string }[] = [];
  return {
    events,
    doc: {
      // Như trang thật: '[data-state="open"]' hay '[data-state="closed"]' (lớp đang chạy hiệu ứng đóng, a120).
      querySelectorAll: (selector: string) => elements.filter((item) => selector.includes(`"${item.getAttribute("data-state")}"`)),
      querySelector: (selector: string) => (selector.includes("[data-button]") && toast === "action" ? {} : null),
      dispatchEvent: (event: Event) => {
        events.push({ type: event.type, key: (event as KeyboardEvent).key });
        return true;
      },
    },
  };
}

const cleanups: (() => void)[] = [];
function register(name: string, log: string[], element: Fake | null = null) {
  cleanups.push(pushBackLayer(() => log.push(name), () => element as unknown as Element));
}
afterEach(() => {
  while (cleanups.length) cleanups.pop()!();
});

describe("Back đóng lớp Radix (hộp, tấm trượt, menu, bảng nổi, danh sách chọn)", () => {
  it("nhận ra lớp đang mở và bỏ qua tooltip hay lớp đang đóng", () => {
    expect(isOpenLayer(el("menu", "open"))).toBe(true);
    expect(isOpenLayer(el("dialog", "open"))).toBe(true); // Dialog, Sheet, Popover
    expect(isOpenLayer(el("alertdialog", "open"))).toBe(true);
    expect(isOpenLayer(el("listbox", "open"))).toBe(true); // Select
    expect(isOpenLayer(el("dialog", "closed"))).toBe(false);
    expect(isOpenLayer(el("tooltip", "open"))).toBe(false);
    expect(isOpenLayer(el(null, "open"))).toBe(false);
  });

  it("có lớp mở thì gửi đúng một Esc", () => {
    const { doc, events } = fakeDocument([el("dialog", "open"), el("menu", "open")]);
    expect(hasOpenLayer(doc)).toBe(true);
    expect(dismissTopLayer(doc)).toBe(true);
    expect(events).toEqual([{ type: "keydown", key: "Escape" }]);
  });

  it("không có lớp nào thì không làm gì để Back lùi trang", () => {
    const { doc, events } = fakeDocument([el("tooltip", "open"), el("dialog", "closed")]);
    expect(dismissTopLayer(doc)).toBe(false);
    expect(events).toEqual([]);
  });
});

describe("Back đóng lớp tự đăng ký (useBackLayer)", () => {
  it("màn Đang nghe, rồi panel trong nó: panel đóng trước, màn sau", () => {
    const log: string[] = [];
    register("đang nghe", log);
    register("panel", log);
    const { doc } = fakeDocument([]);
    expect(dismissTopLayer(doc)).toBe(true);
    expect(log).toEqual(["panel"]);
  });

  it("gỡ lớp (đóng bằng tay, rời trang) thì lớp dưới lên trên", () => {
    const log: string[] = [];
    const remove = pushBackLayer(() => log.push("khung ghép"));
    register("đang nghe", log);
    remove();
    remove(); // gỡ hai lần không hỏng ngăn xếp
    expect(backLayerCount()).toBe(1);
    expect(dismissTopLayer(fakeDocument([]).doc)).toBe(true);
    expect(log).toEqual(["đang nghe"]);
  });

  it("bước con nằm trong hộp Radix (Sửa câu › Ai nói): về menu câu, chưa đóng hộp", () => {
    const log: string[] = [];
    const step = el(null, null);
    const dialog = el("dialog", "open", [step]);
    register("bước con", log, step);
    const { doc, events } = fakeDocument([dialog]);
    expect(dismissTopLayer(doc)).toBe(true);
    expect(log).toEqual(["bước con"]);
    expect(events).toEqual([]);
  });

  it("hộp / bảng nổi mở từ màn Đang nghe (nằm ngoài nó): đóng hộp trước, màn Đang nghe còn nguyên", () => {
    const log: string[] = [];
    register("đang nghe", log, el(null, null));
    const { doc, events } = fakeDocument([el("dialog", "open")]);
    expect(dismissTopLayer(doc)).toBe(true);
    expect(log).toEqual([]);
    expect(events).toHaveLength(1);
  });

  it("lớp trên cùng là lớp mở sau cùng", () => {
    register("a", []);
    register("b", []);
    expect(topBackLayer()).toBeDefined();
    expect(backLayerCount()).toBe(2);
  });
});

describe("Back gỡ thông báo có nút", () => {
  it("thông báo có nút (Hoàn tác, Mở…) là một lớp; thông báo chữ thì không", () => {
    let dismissed = 0;
    const withAction = fakeDocument([], "action");
    expect(hasActionToast(withAction.doc)).toBe(true);
    expect(dismissTopLayer(withAction.doc, undefined, () => dismissed++)).toBe(false);
    expect(dismissed).toBe(0); // Không dùng dismiss-all kể cả khi metadata không có.
    const plain = fakeDocument([], "plain");
    expect(dismissTopLayer(plain.doc, undefined, () => dismissed++)).toBe(false);
    expect(dismissed).toBe(0);
  });

  it("hộp đang mở thì đóng hộp trước, thông báo để sau", () => {
    let dismissed = 0;
    const { doc, events } = fakeDocument([el("dialog", "open")], "action");
    expect(dismissTopLayer(doc, undefined, () => dismissed++)).toBe(true);
    expect(events).toHaveLength(1);
    expect(dismissed).toBe(0);
  });
});

describe("Back khi không còn lớp: trang trước -> trang cha -> thu nhỏ ở Thư viện", () => {
  it("trang cha theo đường dẫn", () => {
    expect(parentPath("/settings/voice")).toBe("/settings");
    expect(parentPath("/settings")).toBe("/");
    expect(parentPath("/book/abc/read/ch2")).toBe("/book/abc");
    expect(parentPath("/book/abc/read")).toBe("/book/abc");
    expect(parentPath("/book/abc")).toBe("/");
    expect(parentPath("/settings/devices")).toBe("/settings");
  });

  it("có lịch sử thì lùi trang; không có (mở từ thông báo / file) thì lên trang cha; chỉ Thư viện mới thu nhỏ", () => {
    expect(backStep("/settings/voice", 2)).toEqual({ kind: "history" });
    expect(backStep("/settings/voice", 0)).toEqual({ kind: "replace", to: "/settings" });
    expect(backStep("/book/x/read/c", 0)).toEqual({ kind: "replace", to: "/book/x" });
    expect(backStep("/studio", 0)).toEqual({ kind: "replace", to: "/" });
    expect(backStep("/", 5)).toEqual({ kind: "minimize" });
    expect(backStep("/", 0)).toEqual({ kind: "minimize" });
  });

  it("đọc vị trí lịch sử của react-router", () => {
    expect(historyIndex({ idx: 3, key: "k" })).toBe(3);
    expect(historyIndex(null)).toBe(0);
    expect(historyIndex({})).toBe(0);
  });
});

describe("Mọi lớp tự dựng đã đăng ký vào ngăn xếp Back", () => {
  const source = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
  it.each([
    ["../listen/PlayerViews.tsx", /useBackLayer\(mobile && open,[\s\S]*<Sheet open=\{open && showPanel\}/],
    ["../listen/LineWishes.tsx", /useBackLayer\(view !== "menu"/],
    ["./DevicesScreen.tsx", /useBackLayer\(manual,[\s\S]*useBackLayer\(open,/],
  ])("%s", (path, pattern) => {
    expect(source(path)).toMatch(pattern);
  });

  it("App: listener Back đăng ký một lần, không còn nhánh riêng cho màn Đang nghe", () => {
    const app = source("./App.tsx");
    expect(app).toMatch(/addListener\("backButton"[\s\S]*?\}, \[\]\);/);
    expect(app).not.toMatch(/if \(expanded\) setExpanded\(false\)/);
  });
});

describe("Back khi một lớp đang chạy hiệu ứng đóng (a120)", () => {
  it("Back kế tiếp kết thúc animation đang ra để nhả lớp trước nhịp Esc, không chờ hết thời lượng", () => {
    const elements = [el("dialog", "open"), { ...el("menu", "closed"), getAnimations: () => [{ finish: () => { elements.pop(); } }] }];
    const { doc, events } = fakeDocument(elements);
    const waits: (() => void)[] = [];
    dismissTopLayer(doc, undefined, undefined, (step) => waits.push(step));
    expect(elements).toHaveLength(1);
    waits.shift()!();
    expect(events).toEqual([{ type: "keydown", key: "Escape" }]);
  });
  it("menu vừa đóng còn trong trang để chạy hiệu ứng: Esc cho hộp bên dưới chờ nó rời trang rồi mới gửi - Back thứ hai không bị nuốt", () => {
    const menu = el("menu", "closed");
    const elements = [el("dialog", "open"), menu];
    const { doc, events } = fakeDocument(elements);
    expect(closingLayers(doc)).toEqual([menu]);
    const waits: (() => void)[] = [];
    expect(dismissTopLayer(doc, undefined, undefined, (step) => waits.push(step))).toBe(true);
    expect(events).toEqual([]); // chưa gửi: menu còn là lớp "cao nhất" của Radix
    waits.shift()!(); // một khung hình sau, menu vẫn đang đóng
    expect(events).toEqual([]);
    elements.pop(); // hiệu ứng đóng xong, Radix gỡ menu
    waits.shift()!();
    expect(events).toEqual([{ type: "keydown", key: "Escape" }]);
  });

  it("không có lớp nào đang đóng thì gửi Esc ngay", () => {
    const { doc, events } = fakeDocument([el("dialog", "open")]);
    dismissTopLayer(doc, undefined, undefined, () => {
      throw new Error("không được chờ");
    });
    expect(events).toEqual([{ type: "keydown", key: "Escape" }]);
  });

  it("lớp đóng dở kẹt mãi (hiệu ứng không chạy) thì vẫn gửi sau giới hạn chờ", async () => {
    const { doc, events } = fakeDocument([el("dialog", "open"), el("menu", "closed")]);
    const waits: (() => void)[] = [];
    dismissTopLayer(doc, undefined, undefined, (step) => waits.push(step));
    const started = Date.now();
    while (!events.length && Date.now() - started < 2000) {
      await new Promise((resolve) => setTimeout(resolve, 50));
      waits.shift()?.();
    }
    expect(events).toEqual([{ type: "keydown", key: "Escape" }]);
  });
});
