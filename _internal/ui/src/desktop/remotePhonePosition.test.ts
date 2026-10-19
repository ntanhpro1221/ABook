import { describe, expect, it } from "vitest";
import { phonePosition, type RemotePhone } from "./RemotePhone";

const phone = (patch: Partial<RemotePhone>): RemotePhone =>
  ({ device: "d", name: "Pixel", kind: "phone", via: "remote", localBookId: "b", bookId: "b", bookTitle: "", chapterId: 1, chapterTitle: "",
    position: 0, duration: 7, playing: false, buffering: false, rate: 1, books: [], stream: true, acks: [], age: 0, known: true, cover: null,
    ...patch }) as RemotePhone;

describe("vị trí điện thoại trên thanh máy tính (soát a68 lỗi 17)", () => {
  it("không vượt độ dài chương, cả khi đang dừng", () => {
    expect(phonePosition(phone({ position: 8, playing: false }), 0, 0)).toBe(7);
    expect(phonePosition(phone({ position: 5, playing: true, age: 10 }), 0, 0)).toBe(7);
    expect(phonePosition(phone({ position: 5, playing: true, age: 1, rate: 1.5 }), 0, 0)).toBe(6.5);
    expect(phonePosition(phone({ position: 812, duration: 0 }), 0, 0)).toBe(812);
  });
});
