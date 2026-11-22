// @vitest-environment happy-dom
// Tên một dòng (DESIGN.md §5.5): thu cỡ tới ONE_LINE_MIN_SCALE cho vừa một dòng, không vừa thì xuống dòng ở cỡ gốc, không bao giờ "…".
// happy-dom không dàn trang: giả bề ngang - chữ rộng tỉ lệ cỡ chữ (giống phông thật), khung rộng cố định.
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fitOneLine, OneLineFit } from "./OneLineFit";
import { ONE_LINE_MIN_SCALE } from "./widthClass.generated";

const BASE = 14;
/** Bề ngang một ký tự ở cỡ gốc (px). */
const GLYPH = 7;
let room = 200;

function fontSize(el: HTMLElement) {
  return parseFloat(el.style.fontSize) || BASE;
}

beforeEach(() => {
  vi.spyOn(window, "getComputedStyle").mockImplementation((el) => ({ fontSize: `${fontSize(el as HTMLElement)}px`, lineHeight: "20px" }) as CSSStyleDeclaration);
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(function (this: HTMLElement) {
    if (this.dataset.oneLineFit === undefined) return room;
    const natural = Math.ceil((this.textContent ?? "").length * GLYPH * fontSize(this) / BASE);
    return this.style.whiteSpace === "nowrap" ? Math.min(natural, room) : room;
  });
  vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockImplementation(function (this: HTMLElement) {
    const natural = Math.ceil((this.textContent ?? "").length * GLYPH * fontSize(this) / BASE);
    return this.style.whiteSpace === "nowrap" ? natural : Math.min(natural, room);
  });
});
afterEach(() => vi.restoreAllMocks());

function span(text: string) {
  const el = document.createElement("span");
  el.dataset.oneLineFit = "";
  el.textContent = text;
  document.body.append(el);
  return el;
}

it("tên ngắn giữ cỡ gốc trên một dòng", () => {
  room = 200;
  const el = span("Mai");
  expect(fitOneLine(el)).toBe("one");
  expect(el.style.fontSize).toBe("");
  expect(el.style.whiteSpace).toBe("nowrap");
  el.remove();
});

it("tên dài hơn chỗ một chút thu cỡ cho vừa một dòng, không dưới đáy chung", () => {
  room = 200;
  const el = span("x".repeat(32));   // 224 px ở cỡ gốc, chỗ 200
  expect(fitOneLine(el)).toBe("shrunk");
  const size = parseFloat(el.style.fontSize);
  expect(size).toBeLessThan(BASE);
  expect(size).toBeGreaterThanOrEqual(BASE * ONE_LINE_MIN_SCALE);
  expect(el.scrollWidth).toBeLessThanOrEqual(el.clientWidth);
  expect(el.style.lineHeight).toBe("20px");   // hàng không co theo chữ nhỏ
  el.remove();
});

it("tên dài hẳn xuống dòng ở cỡ gốc thay vì cắt", () => {
  room = 200;
  const el = span("x".repeat(60));   // 420 px: cần thu dưới 0,75 mới vừa
  expect(fitOneLine(el)).toBe("wrap");
  expect(el.style.fontSize).toBe("");
  expect(el.style.whiteSpace).toBe("normal");   // nút cha whitespace-nowrap không kéo chữ đã xuống dòng về một dòng (leftfix C1)
  el.remove();
});

it("chỗ rộng ra thì đo lại và trả về cỡ gốc", () => {
  room = 200;
  const el = span("x".repeat(32));
  expect(fitOneLine(el)).toBe("shrunk");
  room = 400;
  expect(fitOneLine(el)).toBe("one");
  expect(el.style.fontSize).toBe("");
  el.remove();
});

it("thành phần: không lớp truncate / text-ellipsis, gắn trạng thái đo", async () => {
  room = 200;
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<div><OneLineFit className="text-sm">{"Supertonic F1 - giọng nữ trầm ấm đọc truyện dài cho những đêm khuya"}</OneLineFit></div>));
    const el = host.querySelector<HTMLElement>("[data-one-line-fit]")!;
    expect(el.className).not.toMatch(/truncate|ellipsis|line-clamp/);
    expect(el.dataset.fit).toBe("wrap");
    expect(el.textContent).not.toContain("…");
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});
