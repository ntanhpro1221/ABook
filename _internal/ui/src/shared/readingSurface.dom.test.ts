// @vitest-environment happy-dom
// Nền đọc (Cài đặt > Giao diện): đặt data-surface lên <html> cho styles.css; "Tự động" bỏ thuộc tính để theo giao diện sáng / tối.
import { afterEach, expect, it } from "vitest";
import { applyReadingSurface, READING_SURFACES, readingSurfaceOr } from "./readingSurface";

afterEach(() => applyReadingSurface("auto"));

it("chọn mặt đọc thì <html> mang data-surface; Tự động thì bỏ", () => {
  applyReadingSurface("ivory");
  expect(document.documentElement.dataset.surface).toBe("ivory");
  applyReadingSurface("auto");
  expect(document.documentElement.dataset.surface).toBeUndefined();
});

it("bốn lựa chọn nhãn ngắn, giá trị lạ về Tự động", () => {
  expect(READING_SURFACES.map((surface) => surface.label)).toEqual(["Tự động", "Giấy", "Ngà", "Đêm"]);
  expect(readingSurfaceOr("night")).toBe("night");
  expect(readingSurfaceOr("sepia")).toBe("auto");
  expect(readingSurfaceOr(undefined)).toBe("auto");
});
