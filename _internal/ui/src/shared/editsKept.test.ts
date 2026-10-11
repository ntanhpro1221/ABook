import { describe, expect, it } from "vitest";
import { brokenMusicNote, keptEditsTitle, workshopMergeNote } from "./editsKept";

describe("nhập lại sách đã sửa", () => {
  it("nói thay đổi của người nghe được giữ nguyên", () => {
    expect(keptEditsTitle(3)).toBe("Đã cập nhật sách - giữ nguyên 3 chỉnh sửa của bạn");
  });
  it("không nói gì khi máy này chưa sửa gì", () => {
    expect(keptEditsTitle(0)).toBeNull();
    expect(keptEditsTitle(undefined)).toBeNull();
  });
});

describe("mở file dự án đã sửa ở máy khác (soát UX a25 T5)", () => {
  it("nói đã gộp gì và giữ gì", () => {
    expect(workshopMergeNote({ merged: 3, kept: 1 })).toBe("Đã gộp 3 sửa từ file, 1 sửa giữ bản của máy này vì mới hơn.");
    expect(workshopMergeNote({ merged: 2, kept: 0 })).toBe("Đã gộp 2 sửa từ file.");
    expect(workshopMergeNote({ merged: 0, kept: 1 })).toBe("1 sửa giữ bản của máy này vì mới hơn.");
  });
  it("không nói gì khi hai bên như nhau", () => {
    expect(workshopMergeNote(undefined)).toBeNull();
    expect(workshopMergeNote({ merged: 0, kept: 0 })).toBeNull();
  });
});

describe("file sách có bài nhạc nền hỏng (soát a26 L4)", () => {
  it("nói một câu, sách vẫn mở", () => {
    expect(brokenMusicNote(1)).toBe("1 bài nhạc nền trong sách bị hỏng - đoạn ấy sẽ không có nhạc.");
    expect(brokenMusicNote(2)).toBe("2 bài nhạc nền trong sách bị hỏng - những đoạn ấy sẽ không có nhạc.");
  });
  it("không nói gì khi mọi bài đều lành", () => {
    expect(brokenMusicNote(0)).toBeNull();
    expect(brokenMusicNote(undefined)).toBeNull();
  });
});
