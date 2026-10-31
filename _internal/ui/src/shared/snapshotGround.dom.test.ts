// @vitest-environment happy-dom
// Chủ sách 26-10 (video "Nghe tiếp" -> "Tạm dừng"): ảnh cũ của nhãn trong nút màu nhấn lấy nền trang, phủ một khung đen lên chữ. Ảnh cũ phải
// mang đúng nền thật phía sau nó: nền tổ tiên gần nhất, cộng các lớp trong suốt một phần.
import { expect, it } from "vitest";
import { colorAlpha, groundCss, snapshotGround } from "./motion";

it("độ đục đọc được mọi dạng màu đã tính", () => {
  expect(colorAlpha("rgba(0, 0, 0, 0)")).toBe(0);
  expect(colorAlpha("transparent")).toBe(0);
  expect(colorAlpha("rgb(232, 166, 64)")).toBe(1);
  expect(colorAlpha("rgba(255, 255, 255, 0.06)")).toBe(0.06);
  expect(colorAlpha("oklch(0.7 0.1 70 / 0.5)")).toBe(0.5);
  expect(colorAlpha("color(srgb 1 1 1 / 12%)")).toBe(0.12);
});

it("nhãn trong suốt nằm trong nút màu nhấn: ảnh cũ lấy nền nút, không lấy nền trang", () => {
  document.body.innerHTML = `<div style="background-color: rgb(17, 17, 17)"><button style="background-color: rgb(232, 166, 64)"><span id="label">Nghe tiếp</span></button></div>`;
  expect(groundCss(snapshotGround(document.getElementById("label")!, "rgb(17, 17, 17)"))).toBe("rgb(232, 166, 64)");
});

it("lớp nền trong suốt một phần chồng lên nền đục bên dưới", () => {
  document.body.innerHTML = `<div style="background-color: rgb(20, 20, 20)"><div style="background-color: rgba(255, 255, 255, 0.06)"><span id="row">Hàng</span></div></div>`;
  expect(groundCss(snapshotGround(document.getElementById("row")!, "white"))).toBe("linear-gradient(rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.06)), rgb(20, 20, 20)");
});

it("không tổ tiên nào có nền: dùng nền trang", () => {
  document.body.innerHTML = `<span id="bare">Chữ</span>`;
  expect(groundCss(snapshotGround(document.getElementById("bare")!, "rgb(250, 248, 244)"))).toBe("rgb(250, 248, 244)");
});
