import { describe, expect, it } from "vitest";
import { homePage, listenOnlyLine, peerBarLine, peerOf, peerPage, throughPeer } from "./peerStudio";

describe("Studio của máy tính đã ghép (webui/peer_studio.py)", () => {
  it("chỉ nhận mã máy đúng dạng trong chuỗi truy vấn", () => {
    expect(peerOf("?t=abc&peer=0123456789ab")).toBe("0123456789ab");
    expect(peerOf("?t=abc")).toBe("");
    expect(peerOf("?peer=../../api")).toBe("");
    expect(peerOf("?peer=0123456789AB")).toBe("");
  });

  it("đổi gốc API sang cầu nối của máy này, giữ nguyên đường và truy vấn", () => {
    expect(throughPeer("/api/books/abc/pronunciation", "0123456789ab")).toBe("/api/peers/0123456789ab/studio/api/books/abc/pronunciation");
    expect(throughPeer("/media/books/abc/chapters/1?v=2", "0123456789ab")).toBe("/api/peers/0123456789ab/studio/media/books/abc/chapters/1?v=2");
    expect(throughPeer("/api/app", "")).toBe("/api/app");
  });

  it("mở Studio giữ mã phiên của trang, về máy này thì bỏ máy kia", () => {
    expect(peerPage("?t=abc", "0123456789ab")).toBe("/?t=abc&peer=0123456789ab#/studio");
    expect(peerPage("?t=abc&peer=ffffffffffff", "0123456789ab", "/studio/b1")).toBe("/?t=abc&peer=0123456789ab#/studio/b1");
    expect(homePage("?t=abc&peer=0123456789ab")).toBe("/?t=abc#/");
    expect(homePage("?peer=0123456789ab")).toBe("/#/");
  });

  it("nói tên máy: chỉ nghe thì bật ở đâu, không trả lời thì tự nối lại", () => {
    expect(listenOnlyLine("Máy phòng khách")).toBe("Chỉ nghe - bật quyền sửa ở Máy phòng khách: Cài đặt > Thiết bị");
    expect(peerBarLine("Máy phòng khách")).toBe("Đang mở Studio của Máy phòng khách");
    expect(peerBarLine("Máy phòng khách", { listenOnly: true })).toBe(listenOnlyLine("Máy phòng khách"));
    expect(peerBarLine("Máy phòng khách", { silent: "Máy phòng khách không trả lời (tắt hay mất mạng)", listenOnly: true })).toBe(
      "Máy phòng khách không trả lời (tắt hay mất mạng) - tự nối lại khi máy ấy trả lời",
    );
  });
});
