import { describe, expect, it } from "vitest";
import { unpairCopy, type UnsentEdits } from "./unpair";

const two: UnsentEdits = {
  books: [
    { title: "Sách một", changes: 2 },
    { title: "Sách hai", changes: 1 },
  ],
  changes: 3,
  sendable: true,
};

describe("gỡ ghép khi còn sửa chưa gửi", () => {
  it("không hỏi gì khi không còn sửa nào", () => {
    expect(unpairCopy("Máy bàn", "điện thoại", null, true)).toBeNull();
    expect(unpairCopy("Máy bàn", "điện thoại", { books: [], changes: 0, sendable: true }, true)).toBeNull();
  });

  it("nói số cuốn, số thay đổi và tên máy, kèm lựa chọn gửi trước khi máy kia tới được", () => {
    const copy = unpairCopy("Máy bàn", "điện thoại", two, true)!;
    expect(copy.title).toBe("Gỡ ghép Máy bàn?");
    expect(copy.lines[0]).toBe("2 cuốn có 3 thay đổi chưa gửi về Máy bàn sẽ mất: “Sách một”, “Sách hai”.");
    expect(copy.send).toBe("Gửi trước rồi gỡ");
    expect(copy.discard).toBe("Vẫn gỡ, bỏ thay đổi");
    expect(copy.cancel).toBe("Huỷ");
  });

  it("máy kia không tới được thì không mời gửi và nói vì sao", () => {
    const copy = unpairCopy("Máy bàn", "điện thoại", two, false)!;
    expect(copy.send).toBeNull();
    expect(copy.lines[1]).toContain("Chưa tới được Máy bàn");
  });

  it("máy kia là điện thoại (không nhận sửa) thì chỉ có bỏ hay huỷ", () => {
    const copy = unpairCopy("Điện thoại bạn", "máy tính", { ...two, sendable: false }, true)!;
    expect(copy.send).toBeNull();
    expect(copy.lines[1]).toBe("Điện thoại bạn không nhận phần sửa - những thay đổi này chỉ có trên máy tính này.");
  });

  it("chỉ kể tên ba cuốn đầu", () => {
    const many: UnsentEdits = { books: [1, 2, 3, 4, 5].map((n) => ({ title: `S${n}`, changes: 1 })), changes: 5, sendable: true };
    expect(unpairCopy("M", "điện thoại", many, true)!.lines[0]).toBe("5 cuốn có 5 thay đổi chưa gửi về M sẽ mất: “S1”, “S2”, “S3” và 2 cuốn khác.");
  });
});
