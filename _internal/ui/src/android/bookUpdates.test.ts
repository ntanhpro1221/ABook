import { describe, expect, it } from "vitest";
import { hasNewWords } from "./bookUpdates";

describe("sách đã tải có chữ sáng theo giọng đọc mới không", () => {
  it("chưa tải thì chưa có gì để cập nhật", () => {
    expect(hasNewWords({ downloaded: false, wordsVersion: "a1", localWordsVersion: "" })).toBe(false);
  });

  it("máy tính chưa căn chữ nào: sách không đổi, không tải lại", () => {
    expect(hasNewWords({ downloaded: true })).toBe(false);
    expect(hasNewWords({ downloaded: true, wordsVersion: "", localWordsVersion: "" })).toBe(false);
    expect(hasNewWords({ downloaded: true, localWordsVersion: "a1" })).toBe(false);
  });

  it("máy tính vừa căn chữ cho sách đã tải từ trước: có cập nhật", () => {
    expect(hasNewWords({ downloaded: true, wordsVersion: "a1", localWordsVersion: "" })).toBe(true);
    expect(hasNewWords({ downloaded: true, wordsVersion: "a1" })).toBe(true);
  });

  it("căn lại thì dấu đổi, tải xong thì dấu trùng và hết nhắc", () => {
    expect(hasNewWords({ downloaded: true, wordsVersion: "b2", localWordsVersion: "a1" })).toBe(true);
    expect(hasNewWords({ downloaded: true, wordsVersion: "b2", localWordsVersion: "b2" })).toBe(false);
  });
});
