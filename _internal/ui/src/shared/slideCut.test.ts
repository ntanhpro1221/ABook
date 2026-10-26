import { expect, it } from "vitest";
import { slideCut } from "./MotionRegion";

// Chủ sách 26-10 (video lướt tab bộ lọc): ảnh cũ khi lướt từng cắt `inset(-100vh ...)`, bỏ vết cắt trên / dưới theo khung cuộn - ảnh tràn
// ra phủ thanh phát và thanh điều hướng. Lướt chỉ đổi cạnh trái / phải; trên / dưới giữ đúng vết cắt khung cuộn đã có.
it("lướt giữ vết cắt trên / dưới của khung cuộn, chỉ đổi trái / phải", () => {
  expect(slideCut("inset(0px 0px 312px 0px)")(10, 20)).toBe("inset(0px 20px 312px 10px)");
  expect(slideCut("inset(48.5px 4px 0px 4px)")(0, 0)).toBe("inset(48.5px 0px 0px 0px)");
});

it("ảnh chưa có vết cắt nào thì trên / dưới bằng 0", () => {
  expect(slideCut("")(5, 0)).toBe("inset(0px 0px 0px 5px)");
});
