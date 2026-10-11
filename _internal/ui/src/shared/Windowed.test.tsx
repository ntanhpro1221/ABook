import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { blockHeight, firstBlocks, Windowed, WINDOW_BLOCK } from "./Windowed";

// Danh sách rất dài chỉ dựng phần gần màn hình (shared/Windowed): trang sách 3000 chương từng dựng ~39.000 nút DOM.

const globals = globalThis as unknown as Record<string, unknown>;
afterEach(() => {
  delete globals.IntersectionObserver;
});

function rows(count: number) {
  return Array.from({ length: count }, (_, index) => `Chương ${index + 1}`);
}

function html(count: number, keep?: number) {
  return renderToString(
    <Windowed items={rows(count)} estimate={50} keep={keep} row={(item, index) => <p key={item} data-at={index}>{item}</p>} />,
  );
}

describe("Windowed", () => {
  it("dựng khối đầu và khối của chương đang nghe, khối khác là ô trống cao bằng số hàng", () => {
    globals.IntersectionObserver = class {};
    const page = html(3000, 2500);
    expect(page.match(/<p /g)?.length).toBe(WINDOW_BLOCK * 2);
    expect(page).toContain(">Chương 1<");
    expect(page).toContain(">Chương 2501<");
    expect(page).not.toContain(">Chương 41<");
    expect(page).toContain(`height:${WINDOW_BLOCK * 50}px`);
  });

  it("danh sách ngắn, hay nơi không có IntersectionObserver, dựng hết như cũ", () => {
    globals.IntersectionObserver = class {};
    expect(html(WINDOW_BLOCK * 2).match(/<p /g)?.length).toBe(WINDOW_BLOCK * 2);
    delete globals.IntersectionObserver;
    expect(html(3000).match(/<p /g)?.length).toBe(3000);
  });

  it("chỉ số trong cả danh sách đi theo hàng (aria-posinset)", () => {
    globals.IntersectionObserver = class {};
    expect(html(3000, 100)).toContain('data-at="100"');
  });
});

describe("firstBlocks / blockHeight", () => {
  it("khối đầu luôn có; chương đang nghe ngoài danh sách thì bỏ qua", () => {
    expect([...firstBlocks(3000, 40)]).toEqual([0]);
    expect([...firstBlocks(3000, 40, 85)]).toEqual([0, 2]);
    expect([...firstBlocks(3000, 40, 5000)]).toEqual([0]);
  });

  it("đã đo thì dùng số đo, khối cuối ngắn hơn thì ước theo số hàng còn lại", () => {
    expect(blockHeight(1, 3000, 40, 50, new Map([[1, 1234]]))).toBe(1234);
    expect(blockHeight(74, 2990, 40, 50, new Map())).toBe(30 * 50);
  });
});
