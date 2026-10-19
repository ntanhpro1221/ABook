import { describe, expect, it } from "vitest";
import { ApiError, serverMessage, technicalOf, UNEXPECTED_ERROR } from "./api";

describe("lỗi không ngờ của máy chủ (soát a64)", () => {
  it("nguyên văn lỗi Python thành câu người dùng hiểu, nguyên văn giữ cho Chi tiết", () => {
    expect(serverMessage(500, "TypeError: note() got multiple values for argument 'kind'")).toEqual({
      message: UNEXPECTED_ERROR,
      technical: "TypeError: note() got multiple values for argument 'kind'",
    });
    expect(serverMessage(500, "KeyError")).toMatchObject({ message: UNEXPECTED_ERROR });
  });

  it("lời máy chủ đã viết cho người dùng, hay lỗi không phải 500, giữ nguyên", () => {
    expect(serverMessage(500, "Thư viện sách hỏng - mở lại app.")).toEqual({ message: "Thư viện sách hỏng - mở lại app." });
    expect(serverMessage(400, "ValueError: x")).toEqual({ message: "ValueError: x" });
  });

  it("technicalOf chỉ có ở lỗi không ngờ", () => {
    expect(technicalOf(new ApiError(500, UNEXPECTED_ERROR, { technical: "OSError: [WinError 5]" }))).toBe("OSError: [WinError 5]");
    expect(technicalOf(new Error("x"))).toBe("");
  });
});
