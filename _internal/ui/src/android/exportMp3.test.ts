import { describe, expect, it } from "vitest";
import { finishedToast } from "./ExportMp3";

// Thông báo "Đã xuất" nói rõ chỗ lưu (thư mục), kèm nút mở thư mục khi máy cho (soát UX a9).

describe("thông báo xuất MP3 xong", () => {
  it("xuất riêng chương đổi không bị báo nhầm là chương chưa làm xong", () => {
    expect(finishedToast({ files: 2, chaptersTotal: 5, folder: "Music/Sách", selection: true }).note).toBe("");
  });
  it("nói thư mục đã lưu", () => {
    expect(finishedToast({ files: 12, chaptersTotal: 12, folder: "Music/Sách thử", uri: "content://x/tree/y/document/z" })).toEqual({
      title: "Đã xuất 12 chương",
      note: "",
      uri: "content://x/tree/y/document/z",
    });
  });

  it("không có nút mở thư mục thì chỗ lưu nằm ngay trong dòng; chương chưa làm xong là lưu ý", () => {
    const toast = finishedToast({ files: 3, chaptersTotal: 5, folder: "Music/Sách thử" });
    expect(toast.title).toBe("Đã xuất 3 chương vào Music/Sách thử");
    expect(toast.note).toBe("Các chương chưa làm xong sẽ không có trong bản xuất.");
    expect(toast.uri).toBeUndefined();
  });
});
