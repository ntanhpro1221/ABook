import { describe, expect, it } from "vitest";
import { focusAfterChange } from "./workFocus";

// Soát a31 K4: Enter "Nhận: …" làm thẻ rời danh sách -> tiêu điểm về BODY. Giờ: sang thẻ kế, hết thẻ thì về dòng báo cuối danh sách.

describe("focusAfterChange", () => {
  it("quyết xong một thẻ: tiêu điểm sang thẻ kế ở đúng chỗ ấy", () => {
    const before = { open: ["a", "b", "c"], decided: [] };
    expect(focusAfterChange(before, { open: ["a", "c"], decided: ["b"] }, "b")).toBe("c");
  });

  it("quyết thẻ cuối danh sách: thẻ trước nó", () => {
    expect(focusAfterChange({ open: ["a", "b"], decided: [] }, { open: ["a"], decided: ["b"] }, "b")).toBe("a");
  });

  it("quyết thẻ chờ duyệt cuối cùng: về dòng báo (hết thẻ)", () => {
    expect(focusAfterChange({ open: ["a"], decided: [] }, { open: [], decided: ["a"] }, "a")).toBe("end");
  });

  it("Hoàn tác ở thẻ đã quyết: thẻ đã quyết kế; hết thì thẻ vừa trở lại chờ duyệt", () => {
    expect(focusAfterChange({ open: ["x"], decided: ["a", "b"] }, { open: ["a", "x"], decided: ["b"] }, "a")).toBe("b");
    expect(focusAfterChange({ open: ["x"], decided: ["a"] }, { open: ["a", "x"], decided: [] }, "a")).toBe("a");
  });

  it("thẻ còn nguyên chỗ (chỉ vẽ lại): giữ thẻ ấy", () => {
    expect(focusAfterChange({ open: ["a", "b"], decided: [] }, { open: ["a", "b"], decided: [] }, "b")).toBe("b");
  });

  it("Hoàn tác ở thông báo (không thẻ nào giữ tiêu điểm): thẻ vừa trở lại chờ duyệt", () => {
    expect(focusAfterChange({ open: ["x"], decided: ["a"] }, { open: ["a", "x"], decided: [] }, null)).toBe("a");
    expect(focusAfterChange({ open: ["x"], decided: [] }, { open: ["x", "y"], decided: [] }, null)).toBeNull();
  });

  it("Hoàn tác thẻ vai phụ (ở \"đã quyết\" là từng câu, mã khác): thẻ nhóm vừa trở lại", () => {
    expect(focusAfterChange({ open: ["x"], decided: ["role:1", "role:2"] }, { open: ["role", "x"], decided: [] }, null)).toBe("role");
    // Thẻ mới tới từ máy (đã quyết không bớt): không giật tiêu điểm
    expect(focusAfterChange({ open: ["x"], decided: ["a"] }, { open: ["x", "new"], decided: ["a"] }, null)).toBeNull();
  });
});
