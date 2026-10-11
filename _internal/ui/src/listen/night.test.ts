import { describe, expect, it } from "vitest";
import { heardSinceNight } from "./night";

describe("thẻ 'Tối qua' sau khi đã nghe tiếp (soát a26 L2)", () => {
  const ended = 1_000_000;

  it("ẩn khi chỗ nghe được lưu hẳn sau lúc tự dừng - người nghe đã nghe tiếp", () => {
    expect(heardSinceNight(ended, ended + 15 * 60)).toBe(true);
  });
  it("vẫn hiện khi chưa nghe gì thêm", () => {
    expect(heardSinceNight(ended, ended - 30)).toBe(false);
    expect(heardSinceNight(ended, undefined)).toBe(false);
    expect(heardSinceNight(ended, null)).toBe(false);
  });
  it("lần lưu ngay lúc dừng (hẹn hết chương lưu chương kế ở 0:00) chưa phải nghe tiếp", () => {
    expect(heardSinceNight(ended, ended + 2)).toBe(false);
  });
});
