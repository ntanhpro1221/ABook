import { describe, expect, it, vi } from "vitest";
import { onceReporter } from "./saveFailure";

describe("onceReporter", () => {
  it("báo lần lỗi đầu, im ở các lần sau trong cùng phiên", () => {
    const show = vi.fn();
    const report = onceReporter(show);
    report(new Error("Ổ đĩa chứa thư mục “ABook” đã đầy - dọn bớt rồi thử lại."));
    report(new Error("lần hai"));
    report("lạ");
    expect(show).toHaveBeenCalledTimes(1);
    expect(show).toHaveBeenCalledWith("Ổ đĩa chứa thư mục “ABook” đã đầy - dọn bớt rồi thử lại.");
  });
});
