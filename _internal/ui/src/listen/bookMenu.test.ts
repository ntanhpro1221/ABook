import { describe, expect, it } from "vitest";
import { moreMenuHasItems } from "./bookMenu";

describe("menu Tuỳ chọn khác của trang sách", () => {
  const none = { records: false, finishedToggle: false, edit: false, platform: false, extra: null };
  it("thiết bị chỉ được nghe, sách chỉ có chữ, không mục nào: ẩn", () => {
    expect(moreMenuHasItems(none)).toBe(false);
    expect(moreMenuHasItems({ ...none, extra: false })).toBe(false);
  });
  it("có bất kỳ nhóm nào thì hiện", () => {
    for (const key of ["records", "finishedToggle", "edit", "platform"] as const) expect(moreMenuHasItems({ ...none, [key]: true })).toBe(true);
    expect(moreMenuHasItems({ ...none, extra: {} })).toBe(true);
  });
});
