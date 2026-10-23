import { beforeEach, describe, expect, it, vi } from "vitest";

// Giao diện được dựng lại (vuốt app khỏi Recents, WebView tải lại) trong lúc việc xuất MP3 / M4B của WorkManager vẫn chạy: tiến độ và tin xong / lỗi
// không được mất (soát a107 F1). `runs` của mỗi màn xuất là biến cấp mô-đun nên mới tinh sau khi giao diện dựng lại.
const library = vi.hoisted(() => {
  const handlers = new Map<string, (event: any) => void>();
  return {
    handlers,
    addListener: vi.fn((name: string, fn: (event: any) => void) => {
      handlers.set(name, fn);
      return Promise.resolve({ remove: () => handlers.delete(name) });
    }),
    exportJobs: vi.fn(async () => ({ jobs: [] as unknown[] })),
    cancelM4bExport: vi.fn(async () => undefined),
  };
});
const toasts = vi.hoisted(() => {
  const record = vi.fn();
  return Object.assign(record, { loading: vi.fn(), success: vi.fn(), error: vi.fn() });
});
vi.mock("sonner", () => ({ toast: toasts }));
vi.mock("./plugins", () => ({ EbookLibrary: library }));

const flush = async () => {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
};

describe("xuất MP3/M4B đang chạy nền khi giao diện mở lại", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    library.handlers.clear();
    library.exportJobs.mockResolvedValue({ jobs: [] });
  });

  it("MP3: lượt đang chạy được hỏi lại từ việc nền, hiện tiến độ rồi tin XONG", async () => {
    library.exportJobs.mockResolvedValue({ jobs: [{ kind: "mp3", bookId: "b1", run: "w1", done: 3, total: 10, folder: "Music/Sách" }] });
    const { watchMp3Exports } = await import("./ExportMp3");
    watchMp3Exports();
    await flush();
    expect(toasts.loading).toHaveBeenCalledWith("Đang xuất sách…", expect.objectContaining({
      id: "mp3-export-b1",
      description: expect.objectContaining({ props: expect.objectContaining({ shown: "3/10 chương · vào Music/Sách" }) }),
    }));
    library.handlers.get("mp3Export")!({ bookId: "b1", run: "w1", finished: true, files: 10, chaptersTotal: 10, folder: "Music/Sách" });
    expect(toasts.success).toHaveBeenCalledWith("Đã xuất 10 chương", expect.objectContaining({ id: "mp3-export-b1" }));
  });

  it("MP3: tin tới trước khi trả lời của việc nền về vẫn không bị bỏ", async () => {
    const { watchMp3Exports } = await import("./ExportMp3");
    watchMp3Exports();
    const emit = library.handlers.get("mp3Export")!;
    emit({ bookId: "b1", run: "w1", done: 4, total: 10 });
    expect(toasts.loading).toHaveBeenCalledTimes(1);
    emit({ bookId: "b1", run: "w1", finished: true, files: 10, chaptersTotal: 10, folder: "Music/Sách" });
    expect(toasts.success).toHaveBeenCalledWith("Đã xuất 10 chương", expect.anything());
  });

  it("MP3: tin của lượt cũ không đè lên lượt đang theo dõi", async () => {
    library.exportJobs.mockResolvedValue({ jobs: [{ kind: "mp3", bookId: "b1", run: "w2", folder: "Music/Sách" }] });
    const { watchMp3Exports } = await import("./ExportMp3");
    watchMp3Exports();
    await flush();
    library.handlers.get("mp3Export")!({ bookId: "b1", run: "w1", error: "cũ" });
    expect(toasts.error).not.toHaveBeenCalled();
  });

  it("MP3: lượt bị hệ thống dừng sau 6 giờ báo lỗi cho người nghe", async () => {
    const { watchMp3Exports } = await import("./ExportMp3");
    watchMp3Exports();
    library.handlers.get("mp3Export")!({ bookId: "b1", run: "w1", error: "Hệ thống Android đã dừng việc xuất sau 6 giờ - bạn bấm Xuất lại để làm tiếp" });
    expect(toasts.error).toHaveBeenCalledWith("Không xuất được", expect.objectContaining({ description: expect.stringContaining("sau 6 giờ") }));
  });

  it("M4B: lượt đang chạy được hỏi lại từ việc nền, có nút Dừng, rồi tin XONG", async () => {
    library.exportJobs.mockResolvedValue({ jobs: [{ kind: "m4b", bookId: "b1", run: "w1", done: 3, total: 10, percent: 30 }, { kind: "mp3", bookId: "b2", run: "w9" }] });
    const { watchM4bExports } = await import("./ExportM4b");
    watchM4bExports();
    await flush();
    expect(toasts.loading).toHaveBeenCalledTimes(1);
    expect(toasts.loading).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
      id: "m4b-export-b1",
      action: expect.objectContaining({ label: "Dừng" }),
      description: expect.objectContaining({ props: expect.objectContaining({ shown: "3/10 chương · 30%" }) }),
    }));
    library.handlers.get("m4bExport")!({ bookId: "b1", run: "w1", finished: true, name: "Sach.m4b", size: 1000, chapters: 10, chaptersTotal: 10 });
    expect(toasts.success).toHaveBeenCalledTimes(1);
  });

  it("M4B: việc mới được xếp hàng, chưa có tiến độ, vẫn hiện thông báo", async () => {
    library.exportJobs.mockResolvedValue({ jobs: [{ kind: "m4b", bookId: "b1", run: "w1" }] });
    const { watchM4bExports } = await import("./ExportM4b");
    watchM4bExports();
    await flush();
    expect(toasts.loading).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
      description: expect.objectContaining({ props: expect.objectContaining({ shown: "Đang chuẩn bị…" }) }),
    }));
  });

  it("không hỏi được việc nền (plugin cũ, lỗi): vẫn theo dõi tin như trước", async () => {
    library.exportJobs.mockRejectedValue(new Error("không có"));
    const { watchM4bExports } = await import("./ExportM4b");
    watchM4bExports();
    await flush();
    expect(toasts.loading).not.toHaveBeenCalled();
    expect(library.handlers.has("m4bExport")).toBe(true);
  });
});
