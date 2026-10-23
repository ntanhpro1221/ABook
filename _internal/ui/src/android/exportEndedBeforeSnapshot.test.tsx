import { beforeEach, describe, expect, it, vi } from "vitest";

// Mở lại giao diện lúc việc xuất gần xong: tin "xong" tới TRƯỚC khi bản chụp việc đang chạy (exportJobs) trả về thì bản chụp cũ không được dựng lại
// thanh tiến độ / nút Dừng cho lượt đã xong (soát a111 R3). Cùng quy tắc cho cả ba kiểu xuất.
const library = vi.hoisted(() => {
  const handlers = new Map<string, (event: any) => void>();
  let release: (value: { jobs: unknown[] }) => void = () => undefined;
  return {
    handlers,
    addListener: vi.fn((name: string, fn: (event: any) => void) => {
      handlers.set(name, fn);
      return Promise.resolve({ remove: () => handlers.delete(name) });
    }),
    // Bản chụp trả về muộn: bài thử tự quyết lúc nào nó về.
    exportJobs: vi.fn(() => new Promise<{ jobs: unknown[] }>((resolve) => (release = resolve))),
    reply: (jobs: unknown[]) => release({ jobs }),
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
  for (let index = 0; index < 6; index += 1) await Promise.resolve();
};

describe("tin xong tới trước bản chụp cũ của việc xuất", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    library.handlers.clear();
  });

  it.each([
    ["MP3", "./ExportMp3", "watchMp3Exports", "mp3Export", "mp3", { finished: true, files: 3, chaptersTotal: 3, folder: "Music/Sách" }],
    ["MP3 (lỗi)", "./ExportMp3", "watchMp3Exports", "mp3Export", "mp3", { error: "hỏng" }],
    ["M4B", "./ExportM4b", "watchM4bExports", "m4bExport", "m4b", { finished: true, name: "a.m4b", size: 10, chapters: 3, chaptersTotal: 3 }],
    ["M4B (dừng)", "./ExportM4b", "watchM4bExports", "m4bExport", "m4b", { stopped: true }],
    ["sách nói", "./ExportAudiobook", "watchAudiobookExports", "audiobookExport", "audiobook", { finished: true, chapters: 3 }],
  ])("%s: không dựng lại tiến độ cho lượt đã xong", async (_name, module, watcher, channel, kind, ending) => {
    const exports = (await import(/* @vite-ignore */ module)) as Record<string, () => void>;
    exports[watcher]();
    await flush();
    library.handlers.get(channel)!({ bookId: "b1", run: "w1", done: 2, total: 3 });
    library.handlers.get(channel)!({ bookId: "b1", run: "w1", ...ending });
    toasts.loading.mockClear();
    library.reply([{ kind, bookId: "b1", run: "w1", done: 2, total: 3, chapters: 3 }]);
    await flush();
    expect(toasts.loading).not.toHaveBeenCalled();
  });

  it("lượt khác (chưa kết thúc) của cuốn ấy vẫn được nối lại", async () => {
    const { watchMp3Exports } = await import("./ExportMp3");
    watchMp3Exports();
    await flush();
    library.handlers.get("mp3Export")!({ bookId: "b1", run: "w1", finished: true, files: 3, chaptersTotal: 3, folder: "Music/Sách" });
    library.reply([{ kind: "mp3", bookId: "b1", run: "w2", done: 1, total: 3, folder: "Music/Sách" }]);
    await flush();
    expect(toasts.loading).toHaveBeenCalledTimes(1);
  });
});
