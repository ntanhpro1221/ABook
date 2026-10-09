import { describe, expect, it } from "vitest";
import { editsSyncNote, holderName, sentToast, type EditsSyncState } from "./editsSync";

const sent = (over: Partial<NonNullable<EditsSyncState["last"]>> = {}): EditsSyncState => ({
  pending: 0,
  last: { state: "sent", at: Math.floor(Date.now() / 1000), ...over },
});

describe("tình trạng gửi phần sửa về máy tính", () => {
  it("chưa sửa gì, chưa gửi bao giờ: không có gì để nói", () => {
    expect(editsSyncNote(undefined)).toBeNull();
    expect(editsSyncNote({ pending: 0, last: null })).toBeNull();
  });

  it("có thay đổi chưa gửi: nói số, và cách gửi ngay", () => {
    const note = editsSyncNote({ pending: 3, last: null })!;
    expect(note.tone).toBe("pending");
    expect(note.title).toBe("3 thay đổi đang chờ gửi về máy tính");
    expect(note.lines[0]).toMatch(/Gửi về máy tính/);
  });

  it("lần gửi trước hỏng: giữ nguyên số chưa gửi và nói lý do máy trả", () => {
    const note = editsSyncNote({ pending: 2, last: { state: "error", at: 1, error: "Chưa tới được máy tính" } })!;
    expect(note.tone).toBe("error");
    expect(note.title).toBe("2 thay đổi chưa gửi về máy tính");
    expect(note.lines).toEqual(["Chưa tới được máy tính"]);
  });

  it("đã gửi: nói máy tính đã áp bao nhiêu, bao nhiêu chờ duyệt (không bao giờ tự áp), xung đột", () => {
    const note = editsSyncNote(sent({ applied: 4, waiting: 2, requests: 1, skipped: 1, skippedWishes: 1, conflicts: ["Tên sách: máy tính đã có bản riêng"] }))!;
    expect(note.tone).toBe("sent");
    expect(note.title).toMatch(/^Đã gửi về máy tính/);
    expect(note.lines).toEqual([
      "4 thay đổi đã áp trên máy tính",
      "1 việc đã thành yêu cầu trên máy tính, chờ áp dụng ở Studio",
      "2 việc đang chờ duyệt trên máy tính - chưa làm gì cho tới khi bạn đồng ý trên máy tính",
      "2 thay đổi không còn chỗ trong sách trên máy tính nên bị bỏ qua",
      "Tên sách: máy tính đã có bản riêng",
    ]);
  });

  it("đã gửi mà không có gì để kể: chỉ nói đã gửi", () => {
    expect(editsSyncNote(sent())!.lines).toEqual([]);
  });

  it("còn thay đổi mới sau lần gửi thành công: nói phần chưa gửi", () => {
    const note = editsSyncNote({ pending: 1, last: { state: "sent", at: 1 } })!;
    expect(note.tone).toBe("pending");
  });

  it("nói tên máy giữ sách khi biết (hai máy đều là máy tính)", () => {
    expect(holderName({ computer: "Lecoo" })).toBe("Lecoo");
    expect(holderName(true)).toBe("máy tính");
    expect(editsSyncNote({ pending: 2, last: null }, "Lecoo")!.title).toBe("2 thay đổi đang chờ gửi về Lecoo");
    expect(editsSyncNote(sent({ applied: 1, conflicts: ["x"] }), "Lecoo")!.lines).toEqual(["1 thay đổi đã áp trên Lecoo", "x"]);
  });

  it("thông báo sau khi gửi không lặp lời dặn của dòng tình trạng", () => {
    expect(sentToast({ pending: 0, last: { state: "sent", at: 1, applied: 2 } }, "Lecoo")).toEqual({
      title: "Đã gửi về Lecoo",
      description: "2 thay đổi đã áp trên Lecoo",
    });
    const left = sentToast({ pending: 1, last: { state: "sent", at: 1 } }, "Lecoo");
    expect(left.description).toBe("Còn 1 thay đổi chưa gửi được - sẽ thử lại khi tới được Lecoo.");
    expect(left.description).not.toMatch(/Tự gửi khi/);
  });
});
