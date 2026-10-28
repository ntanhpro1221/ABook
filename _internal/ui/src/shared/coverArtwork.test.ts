import { afterEach, expect, it, vi } from "vitest";
import { coverArtwork, splitTitle } from "./cover";

afterEach(() => vi.unstubAllGlobals());

it("media artwork paints the whole long title inside its growing canvas", () => {
  const painted: { text: string; x: number; y: number }[] = [];
  const context = {
    font: "", fillStyle: "", strokeStyle: "", lineWidth: 0, globalAlpha: 1,
    measureText: (text: string) => ({ width: [...text].length * 32 }),
    createLinearGradient: () => ({ addColorStop() {} }),
    fillRect() {}, beginPath() {}, arc() {}, stroke() {},
    fillText: (text: string, x: number, y: number) => painted.push({ text, x, y }),
  };
  const canvas = { width: 0, height: 0, getContext: () => context, toDataURL: () => "data:image/png;base64,complete-title" };
  vi.stubGlobal("document", { createElement: () => canvas });
  const title = "Thất Nghiệp Chuyển Sinh - Tôi Sẽ Nghiêm Túc Nếu Đến Một Thế Giới Khác Và Những Cuộc Phiêu Lưu Sau Ngày Trở Về Quê Hương · Tập 26";
  expect(coverArtwork(title)).toBe("data:image/png;base64,complete-title");
  const [main, sub] = splitTitle(title);
  const titleLines = painted.slice(0, sub ? -1 : undefined);
  expect(titleLines.length).toBeGreaterThan(5);
  expect(titleLines.map(line => line.text).join(" ")).toBe(main);
  expect(canvas.height).toBeGreaterThan(512);
  for (const line of painted) {
    expect(line.x + context.measureText(line.text).width).toBeLessThanOrEqual(canvas.width);
    expect(line.y).toBeLessThan(canvas.height);
  }
});
