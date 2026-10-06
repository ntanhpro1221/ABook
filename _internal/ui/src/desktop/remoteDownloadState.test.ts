import { describe, expect, it } from "vitest";
import { downloadFraction, downloadMenuLabel, downloadNote, type RemoteDownload } from "./remoteDownloadState";

const status = (over: Partial<RemoteDownload> = {}): RemoteDownload => ({
  state: "none",
  files: 4,
  filesDone: 0,
  bytes: 1000,
  bytesDone: 0,
  error: "",
  ...over,
});

describe("tải sách của máy khác về máy này", () => {
  it("chưa tải gì: mời tải, không có dòng tình trạng", () => {
    expect(downloadNote(status(), "Máy phòng khách")).toBeNull();
    expect(downloadMenuLabel(status(), "Máy phòng khách")).toEqual({
      label: "Tải về máy",
      hint: "Để nghe cả khi Máy phòng khách tắt",
      disabled: false,
    });
  });

  it("đang tải: phần trăm theo byte, nút dừng", () => {
    const note = downloadNote(status({ state: "running", bytesDone: 345, filesDone: 1 }), "")!;
    expect(note).toMatchObject({ tone: "running", title: "Đang tải về máy… 34%", action: "cancel" });
    expect(downloadMenuLabel(status({ state: "running", bytesDone: 345 }), "").label).toBe("Dừng tải về máy");
  });

  it("không biết cỡ file: tính theo số file", () => {
    expect(downloadFraction(status({ bytes: 0, filesDone: 1 }))).toBe(0.25);
  });

  it("máy kia tắt giữa chừng: nói lý do, phần đã tải vẫn giữ, mời tải tiếp", () => {
    const note = downloadNote(status({ state: "failed", bytesDone: 500, error: "Không kết nối được máy kia." }), "")!;
    expect(note.tone).toBe("error");
    expect(note.title).toBe("Chưa tải xong về máy (50%)");
    expect(note.detail).toMatch(/Không kết nối được máy kia\. Phần đã tải vẫn giữ/);
    expect(note.action).toBe("resume");
    expect(downloadMenuLabel(status({ state: "none", filesDone: 2, bytesDone: 500 }), "").label).toBe("Tải nốt về máy");
  });

  it("đã tải xong: nghe được cả khi máy kia tắt, mục trong menu mờ đi", () => {
    expect(downloadNote(status({ state: "done", filesDone: 4, bytesDone: 1000 }), "Máy A")).toMatchObject({
      tone: "done",
      detail: "Nghe được cả khi Máy A tắt",
      action: null,
    });
    expect(downloadMenuLabel(status({ state: "done" }), "Máy A").disabled).toBe(true);
  });
});
