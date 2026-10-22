import { describe, expect, it } from "vitest";
import { latestRequest, wasAborted } from "./latestRequest";

describe("yêu cầu mới nhất", () => {
  it("yêu cầu mới huỷ yêu cầu cũ, yêu cầu mới vẫn sống", () => {
    const requests = latestRequest();
    const first = requests.next();
    const second = requests.next();
    expect(first.aborted).toBe(true);
    expect(second.aborted).toBe(false);
  });

  it("đóng hộp huỷ yêu cầu đang chạy, và huỷ hai lần không sao", () => {
    const requests = latestRequest();
    const signal = requests.next();
    requests.cancel();
    requests.cancel();
    expect(signal.aborted).toBe(true);
  });

  it("nhận ra lỗi do chính ta huỷ", () => {
    expect(wasAborted(new DOMException("aborted", "AbortError"))).toBe(true);
    expect(wasAborted(new Error("mạng đứt"))).toBe(false);
    expect(wasAborted(null)).toBe(false);
  });
});
