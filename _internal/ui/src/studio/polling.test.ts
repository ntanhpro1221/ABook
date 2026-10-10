import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { bookFailure, failureText, isGone, pollDelay, retryUnlessGone } from "./polling";

describe("nhịp hỏi máy chủ khi có lỗi", () => {
  it("sách đã mất (404) thì thôi hỏi, không thử lại", () => {
    const gone = new ApiError(404, "Không có sách này");
    expect(isGone(gone)).toBe(true);
    expect(pollDelay(15_000, { error: gone, errorUpdateCount: 3 })).toBe(false);
    expect(retryUnlessGone(0, gone)).toBe(false);
  });

  it("máy chủ lỗi (500) thì lùi dần tới trần hai phút, hết lỗi thì về nhịp cũ", () => {
    const broken = new ApiError(500, "Sổ làm việc đọc không được");
    expect(pollDelay(15_000, { error: broken, errorUpdateCount: 1 })).toBe(30_000);
    expect(pollDelay(15_000, { error: broken, errorUpdateCount: 2 })).toBe(60_000);
    expect(pollDelay(15_000, { error: broken, errorUpdateCount: 9 })).toBe(120_000);
    expect(pollDelay(15_000, { error: null, errorUpdateCount: 9 })).toBe(15_000);
    expect(pollDelay(false, { error: broken, errorUpdateCount: 2 })).toBe(false);
  });

  it("lỗi khác 404 vẫn thử lại đúng một lần", () => {
    const broken = new ApiError(500, "x");
    expect(retryUnlessGone(0, broken)).toBe(true);
    expect(retryUnlessGone(1, broken)).toBe(false);
    expect(retryUnlessGone(0, new Error("mất mạng"))).toBe(true);
  });
});

// Soát UX a23 B13: một nhịp hỏi hỏng (~15 giây máy chủ không trả lời) biến cả trang dự án thành "Không mở được sách / Failed to fetch".
describe("trang dự án khi một lần hỏi hỏng", () => {
  const offline = new TypeError("Failed to fetch");
  it("đã có bản cũ thì giữ trang (dải báo), chưa từng có mới là màn lỗi", () => {
    expect(bookFailure({ book: {} }, offline)).toBe("stale");
    expect(bookFailure(undefined, offline)).toBe("error");
    expect(bookFailure({ book: {} }, new ApiError(404, "Không có sách này"))).toBe("gone");
    expect(bookFailure({ book: {} }, null)).toBeNull();
  });
  it("lời lỗi tiếng Việt, không phải chữ của trình duyệt", () => {
    expect(failureText(offline)).toBe("Mất kết nối tới ABook.");
    expect(failureText(new ApiError(500, "Sổ dự án bị khoá"))).toBe("Sổ dự án bị khoá");
  });
});
