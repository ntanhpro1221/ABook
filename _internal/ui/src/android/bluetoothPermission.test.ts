import { describe, expect, it } from "vitest";
import { bluetoothStep } from "./bluetoothPermission";

// Soát a66 mục 6: lần đầu Android hỏi quyền mà không có lời giải thích; từ chối hai lần thì chỉ còn lời báo lỗi, không đường tới Cài đặt.
describe("quyền Thiết bị ở gần", () => {
  it("có quyền thì tìm máy luôn", () => {
    expect(bluetoothStep("granted")).toBe("go");
  });
  it("chưa có quyền: giải thích trước khi Android hỏi (cả khi đã từ chối một lần)", () => {
    expect(bluetoothStep("prompt")).toBe("explain");
    expect(bluetoothStep("prompt-with-rationale")).toBe("explain");
  });
  it("từ chối hẳn: chỉ tới Cài đặt", () => {
    expect(bluetoothStep("denied")).toBe("settings");
  });
});
