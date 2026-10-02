import { describe, expect, it } from "vitest";
import { keptEditsTitle } from "./editsKept";

describe("nhập lại sách đã sửa", () => {
  it("nói thay đổi của người nghe được giữ nguyên", () => {
    expect(keptEditsTitle(3)).toBe("Đã cập nhật sách - giữ nguyên 3 chỉnh sửa của bạn");
  });
  it("không nói gì khi máy này chưa sửa gì", () => {
    expect(keptEditsTitle(0)).toBeNull();
    expect(keptEditsTitle(undefined)).toBeNull();
  });
});
