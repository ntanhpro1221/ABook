import { describe, expect, it } from "vitest";
import { NOTIFICATION_ROW_HINT, NOTIFICATION_WHY } from "./notifications";

// Soát a77 #11: nút tạm dừng / tua ở khay và màn khoá là thông báo của phiên media - không cần quyền thông báo. Lời mời quyền chỉ được hứa thứ thật sự cần nó.
describe("notification permission copy", () => {
  for (const [name, text] of [["invitation", NOTIFICATION_WHY], ["settings row", NOTIFICATION_ROW_HINT]] as const) {
    it(`${name} does not claim the pause and skip buttons depend on the permission`, () => {
      expect(text).not.toMatch(/để có nút|chưa có nút|vì ABook chưa được phép/i);
    });
    it(`${name} names what the permission does bring`, () => {
      expect(text).toMatch(/xong|cần duyệt|xuất/i);
    });
  }
  it("the settings row reassures that listening controls still work", () => {
    expect(NOTIFICATION_ROW_HINT).toMatch(/tạm dừng/);
    expect(NOTIFICATION_ROW_HINT).toMatch(/vẫn/);
  });
});
