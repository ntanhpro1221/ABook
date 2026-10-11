import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { anchorAt, anchorShift, blockHeight, BlockSizes, blockVisible, firstBlocks, rowHeightOf, Windowed, WINDOW_BLOCK } from "./Windowed";

// Danh sách rất dài chỉ dựng phần gần màn hình (shared/Windowed): trang sách 3000 chương từng dựng ~39.000 nút DOM.

const globals = globalThis as unknown as Record<string, unknown>;
afterEach(() => {
  delete globals.IntersectionObserver;
  delete globals.sessionStorage;
});

function rows(count: number) {
  return Array.from({ length: count }, (_, index) => `Chương ${index + 1}`);
}

function html(count: number, keep?: number, memory?: string) {
  return renderToString(
    <Windowed items={rows(count)} estimate={50} keep={keep} memory={memory} row={(item, index) => <p key={item} data-at={index}>{item}</p>} />,
  );
}

/** sessionStorage giả (vitest không có DOM). */
function fakeSession(entries: Record<string, string> = {}) {
  const store = new Map(Object.entries(entries));
  globals.sessionStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
  };
  return store;
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

  it("quay lại trang: ô trống cao đúng số đo đã nhớ trong phiên, không theo số ước", () => {
    globals.IntersectionObserver = class {};
    const sizes = new BlockSizes(3000, WINDOW_BLOCK);
    sizes.record([{ index: 0, width: 800, height: 2140, filled: true }]);
    sizes.record([{ index: 7, width: 800, height: 2200, filled: true }]);
    fakeSession({ "abook.blocks.sach-1": JSON.stringify(sizes) });
    const page = html(3000, undefined, "sach-1");
    expect(page).toContain("height:2200px");
    // Khối chưa đo lần nào: chiều cao một hàng đo được (2140 / 40 = 53,5), không phải 50.
    expect(page).toContain(`height:${WINDOW_BLOCK * 53.5}px`);
    expect(page).not.toContain(`height:${WINDOW_BLOCK * 50}px`);
  });

  it("bộ nhớ phiên bị chặn: vẫn dựng như chưa nhớ gì", () => {
    globals.IntersectionObserver = class {};
    globals.sessionStorage = {
      getItem: () => {
        throw new Error("SecurityError");
      },
    };
    expect(html(3000, undefined, "sach-1")).toContain(`height:${WINDOW_BLOCK * 50}px`);
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

// Soát a30 L5/L4: thư viện ước 90 px/cuốn mà thật ~50 (Studio 57 mà thật 50): cuộn lên qua khối chưa đo thì khung nhìn nhảy 2.400 px.
describe("BlockSizes: ước theo số đo thật", () => {
  it("khối đầu đo được thì mọi khối chưa vẽ lấy chiều cao một hàng của nó, không theo số ước", () => {
    const sizes = new BlockSizes(300, 60);
    expect(sizes.height(3, 90)).toBe(60 * 90);
    expect(sizes.record([{ index: 0, width: 1000, height: 3000, filled: true }])).toBe(true);
    expect(sizes.row).toBe(50);
    expect(sizes.height(3, 90)).toBe(3000);
    expect(sizes.height(0, 90)).toBe(3000);
  });

  it("ô trống (khối chưa dựng) không tính là số đo; chiều cao một hàng giữ từ lần đo đầu", () => {
    const sizes = new BlockSizes(3000, 40);
    sizes.record([{ index: 5, width: 800, height: 2000, filled: false }]);
    expect(sizes.row).toBeNull();
    sizes.record([{ index: 0, width: 800, height: 2140, filled: true }]);
    expect(sizes.record([{ index: 9, width: 800, height: 4000, filled: true }])).toBe(false);
    expect(sizes.row).toBe(53.5);
    expect(sizes.height(9, 54)).toBe(4000);
    expect(rowHeightOf(new Map([[0, 2140], [74, 1070]]), 2980, 40)).toBe(53.5);
    expect(rowHeightOf(new Map(), 3000, 40)).toBeNull();
  });

  // L6: thư viện 1280 -> 400 px giữ 3.009 px cũ cho khối chưa vẽ trong khi thật là 7.597.
  it("bề rộng đổi thì xoá số đo cũ và đo lại từ khối đang dựng", () => {
    const sizes = new BlockSizes(300, 60);
    sizes.record([
      { index: 0, width: 1000, height: 3000, filled: true },
      { index: 2, width: 1000, height: 3010, filled: true },
    ]);
    const changed = sizes.record([
      { index: 0, width: 360, height: 7560, filled: true },
      { index: 2, width: 360, height: 3010, filled: false },
    ]);
    expect(changed).toBe(true);
    expect([...sizes.measured]).toEqual([[0, 7560]]);
    expect(sizes.row).toBe(126);
    expect(sizes.height(2, 90)).toBe(7560);
    // Khung bị ẩn (bề rộng 0) không xoá gì.
    expect(sizes.record([{ index: 0, width: 0, height: 0, filled: true }])).toBe(false);
    expect(sizes.row).toBe(126);
  });

  it("thêm sách: bỏ số đo của khối từ chỗ đổi trở đi, giữ chiều cao một hàng", () => {
    const sizes = new BlockSizes(150, 60);
    sizes.record([{ index: 0, width: 1000, height: 3000, filled: true }]);
    sizes.record([{ index: 2, width: 1000, height: 750, filled: true }]);
    sizes.resize(170);
    expect([...sizes.measured.keys()]).toEqual([0]);
    expect(sizes.height(2, 90)).toBe(50 * 50);
  });

  it("nhớ trong phiên: đọc lại đúng danh sách ấy, khác danh sách thì bỏ", () => {
    const sizes = new BlockSizes(3000, 40);
    sizes.record([{ index: 0, width: 800, height: 2140, filled: true }]);
    const saved = JSON.parse(JSON.stringify(sizes)) as unknown;
    const back = BlockSizes.from(saved, 3000, 40);
    expect(back.row).toBe(53.5);
    expect(back.width).toBe(800);
    expect([...back.measured]).toEqual([[0, 2140]]);
    expect(BlockSizes.from(saved, 2999, 40).row).toBeNull();
    expect(BlockSizes.from("hỏng", 3000, 40).measured.size).toBe(0);
  });
});

describe("anchorAt / anchorShift: giữ nội dung đang thấy đứng yên", () => {
  /** Các khối xếp dọc từ `start` (so với mép khung khi scrollTop = `scroll`). */
  const boxes = (heights: number[], start: number) => {
    const tops = heights.map((_, index) => start + heights.slice(0, index).reduce((sum, height) => sum + height, 0));
    return (index: number) => ({ top: tops[index], bottom: tops[index] + heights[index] });
  };

  it("khối neo là khối nằm ở mép trên khung", () => {
    const heights = [2000, 2000, 2000, 2000];
    expect(anchorAt(4, boxes(heights, 300), 0)).toEqual({ index: 0, top: 300 });
    expect(anchorAt(4, boxes(heights, -4500), 0)).toEqual({ index: 2, top: -500 });
    expect(anchorAt(4, boxes(heights, -9000), 0)).toBeNull();
  });

  // L5: cuộn LÊN, khối 1 (ô trống ước 5.400) thành hàng thật 3.000 - mọi thứ phía dưới dồn lên 2.400 px.
  it("khối phía trên đổi chiều cao: bù đúng phần chênh", () => {
    const scrollTop = 9000;
    const before = boxes([3000, 5400, 3000, 3000], -scrollTop);
    const anchor = anchorAt(4, before, 0)!;
    expect(anchor.index).toBe(2);
    const after = boxes([3000, 3000, 3000, 3000], -scrollTop);
    const shift = anchorShift({ ...anchor, scrollTop }, { top: after(anchor.index).top, scrollTop });
    expect(shift).toBe(-2400);
    // Bù xong: khối neo về đúng chỗ cũ trên màn hình.
    expect(boxes([3000, 3000, 3000, 3000], -(scrollTop + shift))(2).top).toBe(anchor.top);
  });

  it("khối phía dưới đổi, hay người dùng cuộn giữa chừng: không bù", () => {
    const before = { index: 1, top: -200, scrollTop: 5000 };
    expect(anchorShift(before, { top: -200, scrollTop: 5000 })).toBe(0);
    // Người dùng cuộn thêm 120 px: khối lên 120 px theo - không phải lệch.
    expect(anchorShift(before, { top: -320, scrollTop: 5120 })).toBe(0);
    expect(anchorShift(before, { top: -200.3, scrollTop: 5000 })).toBe(0);
  });
});

// L1: tiêu điểm ở chương 3, PageDown x30 thì khối bị gỡ, tiêu điểm rơi về BODY, Tab kế nhảy tới chương 41 và cuộn ngược.
describe("blockVisible: giữ khối có tiêu điểm", () => {
  it("khối chứa tiêu điểm và hai khối kề nó vẫn dựng khi đã cuộn xa", () => {
    const shown = new Set([40, 41]);
    expect(blockVisible(0, shown, -1, 0)).toBe(true);
    expect(blockVisible(1, shown, -1, 0)).toBe(true);
    expect(blockVisible(2, shown, -1, 0)).toBe(false);
    expect(blockVisible(0, shown, -1, null)).toBe(false);
    expect(blockVisible(37, shown, 37, null)).toBe(true);
    expect(blockVisible(41, shown, -1, null)).toBe(true);
  });
});
