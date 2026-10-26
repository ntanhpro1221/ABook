import { describe, expect, it } from "vitest";
import { isUnpaired, nativeError } from "./nativeError";

describe("lỗi từ lõi native (soát a68 lỗi 4, 5)", () => {
  it("câu cho người nghe, chữ kỹ thuật riêng, 401 là đã bỏ ghép", () => {
    const error = Object.assign(new Error("Không tới được máy kia - kiểm tra máy ấy đang mở ABook"), {
      code: "UNREACHABLE",
      data: { technical: "ConnectException: Failed to connect to /10.0.2.2:47679" },
    });
    expect(nativeError(error)).toEqual({
      message: "Không tới được máy kia - kiểm tra máy ấy đang mở ABook",
      code: "UNREACHABLE",
      technical: "ConnectException: Failed to connect to /10.0.2.2:47679",
    });
    expect(isUnpaired(error)).toBe(false);
    expect(isUnpaired(Object.assign(new Error("Máy kia đã bỏ ghép"), { code: "UNPAIRED" }))).toBe(true);
    expect(nativeError("lạ").message).toBe("lạ");
  });
});
