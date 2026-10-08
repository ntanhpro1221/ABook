// @vitest-environment node
import { describe, expect, it } from "vitest";
import { dismissTopLayer, hasOpenLayer, isOpenLayer } from "./backLayers";

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

const el = (role: string | null, state: string | null) => ({
  getAttribute: (name: string) => (name === "role" ? role : name === "data-state" ? state : null),
});

function fakeDocument(elements: ReturnType<typeof el>[]) {
  const events: { type: string; key: string }[] = [];
  return {
    events,
    doc: {
      querySelectorAll: () => elements.filter((item) => item.getAttribute("data-state") === "open"),
      dispatchEvent: (event: Event) => {
        events.push({ type: event.type, key: (event as KeyboardEvent).key });
        return true;
      },
    },
  };
}

describe("Back đóng lớp đang mở", () => {
  it("nhận ra menu, hộp thoại, tấm trượt đang mở và bỏ qua tooltip hay lớp đang đóng", () => {
    expect(isOpenLayer(el("menu", "open"))).toBe(true);
    expect(isOpenLayer(el("dialog", "open"))).toBe(true);
    expect(isOpenLayer(el("alertdialog", "open"))).toBe(true);
    expect(isOpenLayer(el("listbox", "open"))).toBe(true);
    expect(isOpenLayer(el("dialog", "closed"))).toBe(false);
    expect(isOpenLayer(el("tooltip", "open"))).toBe(false);
    expect(isOpenLayer(el(null, "open"))).toBe(false);
  });

  it("có lớp mở thì gửi Esc và báo đã xử lý", () => {
    const { doc, events } = fakeDocument([el("dialog", "open"), el("menu", "open")]);
    expect(hasOpenLayer(doc)).toBe(true);
    expect(dismissTopLayer(doc)).toBe(true);
    expect(events).toEqual([{ type: "keydown", key: "Escape" }]);
  });

  it("không có lớp nào thì không làm gì để Back chạy hành vi cũ", () => {
    const { doc, events } = fakeDocument([el("tooltip", "open"), el("dialog", "closed")]);
    expect(dismissTopLayer(doc)).toBe(false);
    expect(events).toEqual([]);
  });
});
