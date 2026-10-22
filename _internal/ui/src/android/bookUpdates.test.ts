import { describe, expect, it } from "vitest";
import { hasNewAudio, hasNewMeta, hasNewWords } from "./bookUpdates";

it("bản thu cùng cỡ đã đổi: mời cập nhật; tải xong hết nhắc", () => {
  expect(hasNewAudio({ downloaded: true, audioVersion: "new", localAudioVersion: "old" })).toBe(true);
  expect(hasNewAudio({ downloaded: true, audioVersion: "new", localAudioVersion: "new" })).toBe(false);
  expect(hasNewAudio({ downloaded: false, audioVersion: "new" })).toBe(false);
});

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

it("đổi riêng tên / tác giả / tên chương ở máy tính: dấu mô tả khác thì mời cập nhật tên, máy tính cũ không dấu thì không", () => {
  expect(hasNewMeta({ downloaded: true, metaVersion: "m2", localMetaVersion: "m1" })).toBe(true);
  expect(hasNewMeta({ downloaded: true, metaVersion: "m2" })).toBe(true);
  expect(hasNewMeta({ downloaded: true, metaVersion: "m2", localMetaVersion: "m2" })).toBe(false);
  expect(hasNewMeta({ downloaded: true, localMetaVersion: "m1" })).toBe(false);
  expect(hasNewMeta({ downloaded: false, metaVersion: "m2" })).toBe(false);
});
