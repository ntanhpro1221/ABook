import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import { scrollFadeMask } from "./scrollFade";
import { FilterRow, TabLabel } from "./ui";

// Soát 25-10 (desktop Studio): số đếm tab là số trơn thẳng chân chữ, hàng lọc là chữ gạch chân (không hộp segmented), danh sách cuộn có mép mờ.
beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

describe("TabLabel", () => {
  it("số đếm là chữ trơn cạnh tên tab: không viên thuốc, cùng đường chân chữ, trình đọc nghe 'N mục'", () => {
    const html = renderToStaticMarkup(<TabLabel count={24}>Chương</TabLabel>);
    expect(html).toMatch(/\bitems-baseline\b/);
    expect(html).not.toMatch(/rounded-full|bg-hover|px-1\.5/);
    expect(html).toMatch(/tabular[^"]*text-fg-2/);
    expect(html).toContain('<span class="sr-only">, </span>24<span class="sr-only"> mục</span>');
  });

  it("không có số thì không có gì sau tên tab", () => {
    expect(renderToStaticMarkup(<TabLabel>Nhân vật</TabLabel>)).not.toContain("tabular");
  });
});

describe("FilterRow", () => {
  const options = [{ value: "todo", label: "Chưa xem" }, { value: "done", label: "Đã xem" }];
  const html = renderToStaticMarkup(<FilterRow label="Lọc" value="todo" onChange={() => undefined} options={options} />);

  it("vẫn là nhóm radio: mục đang chọn aria-checked, mục kia nằm ngoài thứ tự Tab", () => {
    expect(html).toContain('role="radiogroup"');
    expect(html.match(/role="radio"/g)).toHaveLength(2);
    expect(html).toMatch(/aria-checked="true"[^>]*tabindex="0"/);
    expect(html).toMatch(/aria-checked="false"[^>]*tabindex="-1"/);
  });

  it("chữ gạch chân hổ phách, không khung viền / nền hộp", () => {
    const group = html.match(/<div role="radiogroup"[^>]*>/)![0];
    expect(group).not.toMatch(/\bborder\b|bg-panel|rounded/);
    // Gạch chân là một vạch chung LƯỚT giữa các mục (SlidingIndicator), không bật viền dưới của từng mục.
    expect(html).toMatch(/data-sliding-indicator="line"[^>]*bg-accent/);
    // Mục đang chọn: chữ thường (text-fg) như tab trang - hổ phách chỉ ở vạch, không ở chữ (một kiểu cho cả tab lẫn bộ lọc).
    const [selected, other] = html.match(/<button[^>]*role="radio"[^>]*>/g)!;
    expect(selected).toMatch(/border-b-2 border-transparent[^"]* text-fg"/);
    expect(selected).not.toMatch(/text-accent-text|text-fg-2/);
    expect(other).toMatch(/ text-fg-2/);
    expect(html).not.toMatch(/border-accent/);
  });
});

describe("scrollFadeMask", () => {
  it("không có gì để cuộn thì không có mặt nạ", () => {
    expect(scrollFadeMask({ top: false, bottom: false })).toBeUndefined();
  });

  it("còn hàng dưới: chỉ mờ mép dưới; đã cuộn xuống: mờ mép trên; giữa danh sách: cả hai", () => {
    expect(scrollFadeMask({ top: false, bottom: true })).toBe("linear-gradient(to bottom, black, black calc(100% - 36px), transparent)");
    expect(scrollFadeMask({ top: true, bottom: false })).toBe("linear-gradient(to bottom, transparent, black 36px, black)");
    expect(scrollFadeMask({ top: true, bottom: true }, 24)).toBe("linear-gradient(to bottom, transparent, black 24px, black calc(100% - 24px), transparent)");
  });
});
