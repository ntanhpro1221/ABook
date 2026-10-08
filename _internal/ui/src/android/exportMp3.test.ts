import { describe, expect, it } from "vitest";
import { finishedToast } from "./ExportMp3";

// Thông báo "Đã xuất" nói rõ chỗ lưu (thư mục), kèm nút mở thư mục khi máy cho (soát UX a9).

describe("thông báo xuất MP3 xong", () => {
  it("nói thư mục đã lưu", () => {
    expect(finishedToast({ files: 12, chaptersTotal: 12, folder: "Music/Sách thử", uri: "content://x/tree/y/document/z" })).toEqual({
      title: "Đã xuất 12 chương",
      description: "Lưu ở Music/Sách thử.",
      uri: "content://x/tree/y/document/z",
    });
  });

  it("chương chưa làm xong: vẫn nói chỗ lưu trước, rồi mới tới lưu ý", () => {
    const toast = finishedToast({ files: 3, chaptersTotal: 5, folder: "Music/Sách thử" });
    expect(toast.description).toBe("Lưu ở Music/Sách thử. Các chương chưa làm xong sẽ không có trong bản xuất.");
    expect(toast.uri).toBeUndefined();
  });
});
