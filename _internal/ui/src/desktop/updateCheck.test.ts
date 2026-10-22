import { describe, expect, it } from "vitest";
import { checkLine, UPDATE_CHECK_WAIT_MS } from "./updateCheck";

describe("kiểm tra bản mới", () => {
  it("đang dùng bản mới nhất thì nói rõ bản nào", () => {
    expect(checkLine({ state: "latest" }, "0.4.122")).toEqual({ tone: "ok", text: "ABook 0.4.122 là bản mới nhất." });
    expect(checkLine({ state: "latest" }, "")?.text).toBe("ABook là bản mới nhất.");
  });

  it("bản mới đã có thì không thêm lời (mục cập nhật hiện thay)", () => {
    expect(checkLine({ state: "found" }, "0.4.122")).toBeNull();
  });

  it("lỗi mạng: lời của vỏ, hay lời chung khi vỏ không trả lời - không lộ chuỗi kỹ thuật", () => {
    expect(checkLine({ state: "failed", message: "Bạn kiểm tra mạng." }, "1")).toEqual({ tone: "error", text: "Bạn kiểm tra mạng." });
    const silent = checkLine(null, "1");
    expect(silent?.tone).toBe("error");
    expect(silent?.text).toMatch(/kiểm tra mạng/);
    // Vỏ tự bỏ cuộc sau 30 giây; trang đợi lâu hơn một chút rồi mới tự kết luận.
    expect(UPDATE_CHECK_WAIT_MS).toBeGreaterThan(30_000);
  });
});
