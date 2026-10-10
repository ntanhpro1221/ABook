import { describe, expect, it } from "vitest";
import { unpairCopy, unpairDone, type UnsentEdits } from "./unpair";

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
    expect(copy.title).toBe("Thôi ghép Máy bàn?");
    expect(copy.lines[0]).toBe("2 cuốn có 3 thay đổi chưa gửi về Máy bàn sẽ mất: “Sách một”, “Sách hai”.");
    expect(copy.send).toBe("Gửi trước rồi thôi ghép");
    expect(copy.discard).toBe("Vẫn thôi ghép, bỏ thay đổi");
    expect(copy.cancel).toBe("Huỷ");
  });

  it("máy kia tới được thì “Gửi trước” là nút chính", () => {
    expect(unpairCopy("Máy bàn", "điện thoại", two, true)!.sendPrimary).toBe(true);
  });

  it("máy kia đang tắt thì “Gửi trước” vẫn có nhưng không là nút chính, kèm dòng nói máy ấy tắt", () => {
    const copy = unpairCopy("Máy bàn", "điện thoại", two, false)!;
    expect(copy.send).toBe("Thử gửi trước rồi thôi ghép");
    expect(copy.sendPrimary).toBe(false);
    expect(copy.lines[1]).toContain("Máy bàn đang tắt");
  });

  it("lời hỏi thật của máy tính (`reachable` trong phần sửa chưa gửi) thắng trạng thái cũ của danh sách máy", () => {
    const off = unpairCopy("Máy bàn", "máy tính", { ...two, reachable: false }, true)!;
    expect(off.sendPrimary).toBe(false);
    const on = unpairCopy("Máy bàn", "máy tính", { ...two, reachable: true }, false)!;
    expect(on.sendPrimary).toBe(true);
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

  it("máy kia có phần đã tải thì hỏi dù không còn sửa chưa gửi, nói rõ MB sẽ mất và chỗ nghe vẫn giữ", () => {
    const cached: UnsentEdits = { books: [], changes: 0, sendable: true, cache: { books: 3, bytes: 5 * 1024 * 1024, places: 2 } };
    const copy = unpairCopy("Máy bàn", "máy tính", cached, true)!;
    expect(copy.send).toBeNull();
    expect(copy.discard).toBe("Thôi ghép");
    expect(copy.lines[0]).toContain("3 cuốn của Máy bàn sẽ rời Thư viện");
    expect(copy.lines[0]).toContain("đã tải về máy tính này sẽ bị xoá");
    expect(copy.lines[1]).toContain("Chỗ nghe và dấu trang của 2 cuốn vẫn giữ");
  });

  it("không có gì để mất thì gỡ như thường; lời báo sau khi gỡ nhắc chỗ nghe còn giữ", () => {
    expect(unpairCopy("Máy bàn", "máy tính", { books: [], changes: 0, sendable: true, cache: { books: 0, bytes: 0, places: 0 } }, true)).toBeNull();
    expect(unpairDone("Máy bàn", { books: [], changes: 0, sendable: true, cache: { books: 1, bytes: 0, places: 1 } }).description).toContain("Chỗ nghe và dấu trang vẫn giữ");
    expect(unpairDone("Máy bàn", null).description).not.toContain("vẫn giữ");
  });
});
