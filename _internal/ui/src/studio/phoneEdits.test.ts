import { describe, expect, it } from "vitest";
import { describePush } from "./PhoneEdits";

const push = (over: Partial<Parameters<typeof describePush>[0]>) => ({
  at: Math.floor(Date.now() / 1000),
  device: "a1b2c3d4e5f6",
  name: "Pixel",
  applied: 0,
  skipped: 0,
  requests: 0,
  waiting: 0,
  conflicts: [],
  ...over,
});

describe("kể lần điện thoại gửi phần sửa về", () => {
  it("nói máy tính đã áp, đã ghi thành yêu cầu, đang chờ duyệt và bỏ qua bao nhiêu", () => {
    const text = describePush(push({ applied: 3, requests: 1, waiting: 2, skipped: 1 }));
    expect(text).toContain("Pixel");
    expect(text).toContain("3 thay đổi đã áp, 1 việc đã thành yêu cầu, 2 việc đang chờ duyệt, 1 không còn chỗ trong sách (bỏ qua)");
  });

  it("lần gửi không mang gì mới thì nói thẳng", () => {
    expect(describePush(push({}))).toContain("không có gì mới");
  });
});
