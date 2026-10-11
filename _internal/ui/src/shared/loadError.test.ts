import { describe, expect, it } from "vitest";
import { folderName } from "./MissingLibrary";
import { failedEmpty } from "./ui";

describe("failedEmpty", () => {
  it("lỗi tải mà chưa có gì để hiện: thẻ lỗi, không phải “Chưa có sách”", () => {
    expect(failedEmpty({ isError: true, data: undefined })).toBe(true);
    expect(failedEmpty({ isError: true, data: [] })).toBe(true);
  });
  it("đã có dữ liệu từ lần trước thì cứ hiện dữ liệu; không lỗi thì không phải lỗi", () => {
    expect(failedEmpty({ isError: true, data: [{ id: "a" }] })).toBe(false);
    expect(failedEmpty({ isError: false, data: [] })).toBe(false);
  });
});

describe("folderName", () => {
  it("chỉ tên thư mục cuối, không cả đường dẫn (có tên tài khoản Windows)", () => {
    expect(folderName("C:\\Users\\An\\Sách nói\\")).toBe("Sách nói");
    expect(folderName("/home/an/Audiobooks")).toBe("Audiobooks");
  });
});
