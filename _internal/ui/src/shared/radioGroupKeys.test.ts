import { beforeAll, describe, expect, it, vi } from "vitest";
import { radioGroupKeys } from "./ui";

// Mũi tên trong nhóm radio (soát a100 V1): chỉ phím đến từ một nút radio CỦA CHÍNH nhóm mới đổi lựa chọn. Trước đây phím của nhóm lồng
// (tốc độ giọng nằm trong nhóm giọng rỗng) nổi lên nhóm ngoài và đặt giọng mặc định thành `undefined`. Không có DOM trong vitest - phần tử giả.
beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

/** Sự kiện phím: `target` là nút radio thuộc `group` (hay thuộc nhóm khác nếu `owner` khác), `radios` là các nút radio của currentTarget. */
function press(key: string, options: { group?: object; owner?: object; defaultPrevented?: boolean; radios?: { focus: () => void }[]; target?: object | null } = {}) {
  const group = options.group ?? {};
  const owner = options.owner ?? group;
  const radio = { closest: (selector: string) => (selector === '[role="radio"]' ? radio : selector === '[role="radiogroup"]' ? owner : null) };
  const target = options.target === undefined ? { closest: (selector: string) => (selector === '[role="radio"]' ? radio : null) } : options.target;
  const preventDefault = vi.fn();
  const event = {
    key,
    target,
    defaultPrevented: options.defaultPrevented ?? false,
    preventDefault,
    currentTarget: { ...group, querySelectorAll: () => options.radios ?? [] },
  };
  // currentTarget phải là chính `group` để so với nhóm chủ của nút radio.
  Object.assign(group, { querySelectorAll: () => options.radios ?? [] });
  event.currentTarget = group as never;
  return { event: event as never, preventDefault };
}

describe("radioGroupKeys", () => {
  it("mũi tên từ nút radio của nhóm chọn mục kế và đưa tiêu điểm tới nó", () => {
    const changed = vi.fn(), focus = vi.fn();
    const { event, preventDefault } = press("ArrowRight", { radios: [{ focus: vi.fn() }, { focus }] });
    radioGroupKeys(["a", "b"], "a", changed)(event);
    expect(changed).toHaveBeenCalledWith("b");
    expect(focus).toHaveBeenCalled();
    expect(preventDefault).toHaveBeenCalled();
  });

  it("nhóm rỗng không phát gì dù phím nổi lên từ nhóm con", () => {
    const changed = vi.fn();
    const { event, preventDefault } = press("ArrowRight");
    radioGroupKeys([], "", changed)(event);
    expect(changed).not.toHaveBeenCalled();
    expect(preventDefault).not.toHaveBeenCalled();
  });

  it("phím đã được nhóm con xử lý (defaultPrevented) thì nhóm ngoài bỏ qua", () => {
    const changed = vi.fn();
    const { event } = press("ArrowRight", { defaultPrevented: true, radios: [{ focus: vi.fn() }, { focus: vi.fn() }] });
    radioGroupKeys(["a", "b"], "a", changed)(event);
    expect(changed).not.toHaveBeenCalled();
  });

  it("phím đến từ radio của nhóm khác (lồng bên trong) thì bỏ qua", () => {
    const changed = vi.fn();
    const { event } = press("ArrowRight", { owner: {}, radios: [{ focus: vi.fn() }, { focus: vi.fn() }] });
    radioGroupKeys(["a", "b"], "a", changed)(event);
    expect(changed).not.toHaveBeenCalled();
  });

  it("phím từ phần tử không phải nút radio (nút Thử, ô chọn) thì bỏ qua", () => {
    const changed = vi.fn();
    const { event } = press("ArrowRight", { target: { closest: () => null }, radios: [{ focus: vi.fn() }, { focus: vi.fn() }] });
    radioGroupKeys(["a", "b"], "a", changed)(event);
    expect(changed).not.toHaveBeenCalled();
  });

  it("Home và End về đầu / cuối; chưa chọn mục nào thì mũi tên tới đầu / cuối", () => {
    const changed = vi.fn();
    const radios = [{ focus: vi.fn() }, { focus: vi.fn() }, { focus: vi.fn() }];
    radioGroupKeys(["a", "b", "c"], "b", changed)(press("End", { radios }).event);
    radioGroupKeys(["a", "b", "c"], "b", changed)(press("Home", { radios }).event);
    radioGroupKeys(["a", "b", "c"], "x", changed)(press("ArrowLeft", { radios }).event);
    expect(changed.mock.calls.map(([value]) => value)).toEqual(["c", "a", "c"]);
  });
});
