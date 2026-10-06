import { describe, expect, it } from "vitest";
import {
  defaultExportFolder,
  exportWhereHint,
  jobView,
  lastExportHint,
  M4B_COPY,
  missingChaptersNote,
  packingText,
  RECENT_SECONDS,
  type ExportJob,
} from "./bookFileExport";

describe("defaultExportFolder", () => {
  it("joins with the separator the library path already uses", () => {
    expect(defaultExportFolder("D:\\Sách\\Thư viện")).toBe("D:\\Sách\\Thư viện\\Đã xuất");
    expect(defaultExportFolder("D:\\Sách\\")).toBe("D:\\Sách\\Đã xuất");
    expect(defaultExportFolder("/home/an/sach")).toBe("/home/an/sach/Đã xuất");
  });

  it("says nothing it does not know", () => {
    expect(defaultExportFolder(undefined)).toBeNull();
    expect(defaultExportFolder("")).toBeNull();
  });
});

describe("exportWhereHint", () => {
  it("tells the picker case and the fixed-folder case apart", () => {
    expect(exportWhereHint(true, "D:\\Sách")).toMatch(/chọn thư mục/);
    expect(exportWhereHint(false, "D:\\Sách")).toBe("Lưu vào D:\\Sách\\Đã xuất");
    expect(exportWhereHint(false, undefined)).toMatch(/Đã xuất/);
  });
});

describe("packingText", () => {
  it("changes as time passes", () => {
    expect(packingText(4, 0)).toBe("4 chương · đã 0:00");
    expect(packingText(4, 75)).toBe("4 chương · đã 1:15");
  });
});

describe("jobView", () => {
  const done: ExportJob = { state: "done", id: "a", finishedAgo: 5, result: { folder: "D:/Sách/Đã xuất", file: "D:/Sách/Đã xuất/Truyện.abook", size: 5 * 1048576 } };

  it("shows the time passed while packing, with the chapter count only when it is known", () => {
    expect(jobView({ state: "running", elapsed: 75 }, 4)).toEqual({ kind: "loading", title: "Đang đóng gói sách…", description: "4 chương · đã 1:15" });
    expect(jobView({ state: "running", elapsed: 75 })).toMatchObject({ kind: "loading", description: "đã 1:15" });
  });

  it("says where the file is once done, or the folder when every part has its own file", () => {
    expect(jobView(done)).toEqual({ kind: "success", title: "Đã xuất file sách", description: "D:/Sách/Đã xuất/Truyện.abook · 5 MB" });
    expect(jobView({ state: "done", result: { folder: "D:/Sách/Bộ", parts: [{}, {}] } })).toMatchObject({ description: "D:/Sách/Bộ" });
  });

  it("reports an error with the server's words", () => {
    expect(jobView({ state: "error", error: "Ổ đĩa đầy" })).toEqual({ kind: "error", title: "Không xuất được file sách", description: "Ổ đĩa đầy" });
  });

  it("on reopening the page only repeats what finished recently, but always follows a running job", () => {
    expect(jobView(done, 0, true).kind).toBe("success");
    expect(jobView({ ...done, finishedAgo: RECENT_SECONDS + 1 }, 0, true)).toEqual({ kind: "none" });
    expect(jobView({ state: "running", elapsed: 3000 }, 0, true).kind).toBe("loading");
    expect(jobView({ state: "idle" }, 0, true)).toEqual({ kind: "none" });
  });
});

describe("lastExportHint", () => {
  it("names the last file, or the running state, and is silent when nothing was exported", () => {
    expect(lastExportHint({ state: "done", result: { folder: "D:/x", file: "D:/x/a.abook" } })).toBe("Lần xuất gần nhất: D:/x/a.abook");
    expect(lastExportHint({ state: "running" })).toMatch(/Đang đóng gói/);
    expect(lastExportHint({ state: "idle" })).toBeNull();
    expect(lastExportHint({ state: "error", error: "x" })).toBeNull();
    expect(lastExportHint(undefined)).toBeNull();
  });
});

describe("M4B export", () => {
  const m4b = (chapters: number, chaptersTotal: number): ExportJob => ({
    state: "done",
    id: "m",
    result: { folder: "D:/x", file: "D:/x/Truyện.m4b", size: 3 * 1048576, chapters, chaptersTotal },
  });

  it("speaks with its own words while running, when done and when failing", () => {
    expect(jobView({ state: "running", elapsed: 5 }, 2, false, M4B_COPY)).toMatchObject({ kind: "loading", title: "Đang làm file M4B…" });
    expect(jobView(m4b(6, 6), 0, false, M4B_COPY)).toEqual({ kind: "success", title: "Đã xuất M4B", description: "D:/x/Truyện.m4b · 3 MB" });
    expect(jobView({ state: "error", error: "x" }, 0, false, M4B_COPY)).toMatchObject({ title: "Không xuất được M4B" });
    expect(lastExportHint({ state: "running" }, M4B_COPY)).toBe("Đang làm file M4B - xem thông báo ở góc màn hình");
  });

  it("says when unfinished chapters were left out of the file", () => {
    expect(jobView(m4b(4, 6), 0, false, M4B_COPY)).toMatchObject({
      description: "D:/x/Truyện.m4b · 3 MB · 4/6 chương - chương chưa xong không có trong file",
    });
    expect(missingChaptersNote({ folder: "D:/x", chapters: 6, chaptersTotal: 6 })).toBe("");
    expect(missingChaptersNote({ folder: "D:/x", file: "D:/x/a.abook" })).toBe("");
  });
});
