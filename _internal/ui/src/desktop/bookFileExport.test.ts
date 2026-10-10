import { afterEach, describe, expect, it } from "vitest";
import { setApiTransport } from "@/studio/api";
import {
  clipStart,
  defaultExportFolder,
  exportWhereHint,
  jobView,
  lastExportHint,
  lastExportPlace,
  M4B_COPY,
  missingChaptersNote,
  packingText,
  RECENT_SECONDS,
  runningExports,
  type ExportJob,
} from "./bookFileExport";

afterEach(() => setApiTransport(null));

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
    expect(jobView(done)).toEqual({ kind: "success", title: "Đã xuất file sách", description: "Truyện.abook · 5 MB", place: "D:/Sách/Đã xuất/Truyện.abook" });
    expect(jobView({ state: "done", result: { folder: "D:/Sách/Bộ", parts: [{}, {}] } })).toMatchObject({ description: "Bộ · 2 file", place: "D:/Sách/Bộ" });
    // Sách nói MP3: thư mục tên sách + số file + cỡ; đường dài của Windows không bày cả ra thông báo.
    const mp3 = { folder: "C:\\Users\\An\\Audiobooks\\Đã xuất\\Bến sông mùa lũ", files: 6, size: 3 * 1048576 };
    expect(jobView({ state: "done", result: mp3 })).toMatchObject({ description: "Bến sông mùa lũ · 6 file · 3 MB", place: mp3.folder });
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
    expect(lastExportHint({ state: "done", result: { folder: "D:/x", file: "D:/x/a.abook" } })).toBe("Lần xuất gần nhất: File sách · a.abook");
    expect(lastExportHint({ state: "running" })).toMatch(/Đang đóng gói/);
    expect(lastExportHint({ state: "idle" })).toBeNull();
    expect(lastExportHint({ state: "error", error: "x" })).toBeNull();
    expect(lastExportHint(undefined)).toBeNull();
  });
});

describe("lastExportHint with format and time", () => {
  const now = new Date(2026, 9, 10, 14, 30).getTime();

  it("says the format, when it was made (from the job's age) and the name", () => {
    const job: ExportJob = { state: "done", finishedAgo: 25 * 60, result: { folder: "D:/x/Chuyện thử", files: 3, format: "mp3" } };
    expect(lastExportHint(job, undefined, now)).toBe("Lần xuất gần nhất: MP3 · 10/10 14:05 · Chuyện thử");
  });

  it("tells M4B and book files from their extension when the job carries no format", () => {
    const m4b: ExportJob = { state: "done", finishedAgo: 0, result: { folder: "D:/x", file: "D:/x/Hành trình.m4b" } };
    expect(lastExportHint(m4b, undefined, now)).toBe("Lần xuất gần nhất: M4B · 10/10 14:30 · Hành trình.m4b");
  });
});

describe("lastExportHint with long paths", () => {
  const long = "D:\\Sách nói\\Đã xuất\\Một cuốn truyện có cái tên dài dằng dặc từ đầu đến cuối.m4b";

  it("names the file, never the start of the path, and keeps the full path for the tooltip", () => {
    const job: ExportJob = { state: "done", result: { folder: "D:\\Sách nói\\Đã xuất", file: long } };
    const hint = lastExportHint(job)!;
    expect(hint.startsWith("Lần xuất gần nhất: M4B · …")).toBe(true);
    expect(hint.endsWith("đến cuối.m4b")).toBe(true);
    expect(hint).not.toContain("D:");
    expect(lastExportPlace(job)).toBe(long);
  });

  it("names the folder when the result is a folder of MP3s", () => {
    const job: ExportJob = { state: "done", result: { folder: "D:/Sách nói/Truyện ngắn", files: 12 } };
    expect(lastExportHint(job)).toBe("Lần xuất gần nhất: MP3 · Truyện ngắn");
    expect(lastExportPlace(job)).toBe("D:/Sách nói/Truyện ngắn");
  });

  it("has no place before anything was exported", () => {
    expect(lastExportPlace({ state: "running" })).toBeUndefined();
    expect(lastExportPlace(undefined)).toBeUndefined();
  });
});

describe("clipStart", () => {
  it("cuts at the start so the end of the name stays", () => {
    expect(clipStart("abcdefghij", 6)).toBe("…fghij");
    expect(clipStart("abcdef", 6)).toBe("abcdef");
    expect(clipStart("ab", 6)).toBe("ab");
  });
});

describe("runningExports", () => {
  it("lists the books with a job of this kind still running, from the server's list", async () => {
    setApiTransport(async (path) => {
      expect(path).toBe("/api/export-jobs");
      return {
        bookfile: [],
        m4b: [{ bookId: "m", state: "running" }],
        audiobook: [
          { bookId: "a", state: "running", chapter: 2, chapters: 9, percent: 20 },
          { bookId: "b", state: "done" },
        ],
      };
    });
    expect(await runningExports("audiobook")).toEqual(["a"]);
    expect(await runningExports("m4b")).toEqual(["m"]);
    expect(await runningExports("bookfile")).toEqual([]);
  });

  it("treats a failed or odd answer as nothing running", async () => {
    setApiTransport(async () => {
      throw new Error("mạng chớp");
    });
    expect(await runningExports("audiobook")).toEqual([]);
    setApiTransport(async () => ({}));
    expect(await runningExports("audiobook")).toEqual([]);
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
    expect(jobView(m4b(6, 6), 0, false, M4B_COPY)).toEqual({ kind: "success", title: "Đã xuất M4B", description: "Truyện.m4b · 3 MB", place: "D:/x/Truyện.m4b" });
    expect(jobView({ state: "error", error: "x" }, 0, false, M4B_COPY)).toMatchObject({ title: "Không xuất được M4B" });
    expect(lastExportHint({ state: "running" }, M4B_COPY)).toBe("Đang làm file M4B - xem thông báo ở góc màn hình");
  });

  it("says when unfinished chapters were left out of the file", () => {
    expect(jobView(m4b(4, 6), 0, false, M4B_COPY)).toMatchObject({
      description: "Truyện.m4b · 3 MB · 4/6 chương - chương chưa xong không có trong file",
    });
    expect(missingChaptersNote({ folder: "D:/x", chapters: 6, chaptersTotal: 6 })).toBe("");
    expect(missingChaptersNote({ folder: "D:/x", file: "D:/x/a.abook" })).toBe("");
  });
});
