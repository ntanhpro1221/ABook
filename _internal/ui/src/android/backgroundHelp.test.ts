import { describe, expect, it } from "vitest";
import { backgroundHelp } from "./backgroundHelp";

describe("chỉ đường cho ABook chạy nền theo hãng máy", () => {
  it("OPPO, realme, OnePlus: hoạt động nền và tự khởi chạy", () => {
    for (const maker of ["OPPO", "realme", "OnePlus"]) {
      expect(backgroundHelp(maker)).toBe("Trong trang mở ra: Pin → bật “Cho phép hoạt động nền” và “Tự khởi chạy”.");
    }
  });

  it("Xiaomi: tiết kiệm pin; Samsung: pin", () => {
    expect(backgroundHelp("Xiaomi")).toMatch(/^Trong trang mở ra: Tiết kiệm pin → chọn “Không hạn chế”/);
    expect(backgroundHelp("samsung")).toMatch(/^Trong trang mở ra: Pin → chọn “Không hạn chế”/);
  });

  it("hãng khác hay không rõ: lời chung", () => {
    expect(backgroundHelp("Google")).toMatch(/tuỳ máy/);
    expect(backgroundHelp(undefined)).toMatch(/tuỳ máy/);
  });
});
