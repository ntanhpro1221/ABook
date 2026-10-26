import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { formatPercent } from "./format";
import { heardBarProps, Progress } from "./ui";

// Số phần trăm của mọi thanh tiến độ nói cùng một số với chữ cạnh nó (formatPercent): chưa xong thì chưa bao giờ 100%, tổng 0 thì 0% chứ không "NaN%".
describe("phần trăm tiến độ", () => {
  it("phân số không xác định (0/0, tổng chưa biết): 0%, không NaN", () => {
    expect(formatPercent(Number.NaN)).toBe("0%");
    expect(heardBarProps(Number.NaN)["aria-valuenow"]).toBe(0);
    expect(heardBarProps(Number.NaN)["aria-valuetext"]).toBe("đã nghe 0%");
    const html = renderToStaticMarkup(<Progress value={Number.NaN} label="Đã nghe" />);
    expect(html).not.toContain("NaN");
  });

  it("99,6% chưa xong: thanh đọc 99 như chữ, không 100", () => {
    expect(formatPercent(0.996)).toBe("99%");
    expect(heardBarProps(0.996)["aria-valuenow"]).toBe(99);
    expect(heardBarProps(0.996)["aria-valuetext"]).toBe("đã nghe 99%");
    expect(renderToStaticMarkup(<Progress value={0.997} label="Tiến độ" />)).toContain('aria-valuenow="99"');
    expect(heardBarProps(1)["aria-valuenow"]).toBe(100);
  });
});
