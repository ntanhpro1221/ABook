import { renderToString } from "react-dom/server";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReadAloudVoice } from "@/listen/readAloud";

// "Xuất sách nói" của sách Nghe ngay trên điện thoại (android/ExportAudiobook.tsx): chữ dùng chung với máy tính, thông báo theo tin của việc nền (ListenExportWorker.kt).
// Plugin native và thông báo (sonner) được thay bằng bản giả - phần Kotlin có test JVM riêng (ListenExportTest) và một bài thử trên máy Android (ListenExportOnDeviceTest).
const library = vi.hoisted(() => {
  const handlers: Array<(event: unknown) => void> = [];
  return {
    handlers,
    addListener: vi.fn(async (_name: string, handler: (event: unknown) => void) => {
      handlers.push(handler);
      return { remove: vi.fn() };
    }),
    audiobookJobs: vi.fn(async () => ({ jobs: [] as unknown[] })),
    cancelAudiobookExport: vi.fn(async () => undefined),
    openFile: vi.fn(async () => ({ opened: true })),
  };
});
const toasts = vi.hoisted(() => {
  const fn = Object.assign(vi.fn(), { loading: vi.fn(), success: vi.fn(), error: vi.fn() });
  return fn;
});
vi.mock("./plugins", () => ({ EbookLibrary: library, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("sonner", () => ({ toast: toasts }));
vi.mock("@capacitor/core", () => ({ Capacitor: { convertFileSrc: (path: string) => path } }));

import { AudiobookPhoneForm, finishedView, progressView, spaceText, watchAudiobookExports } from "./ExportAudiobook";

beforeAll(() => {
  const store = new Map<string, string>();
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  } as Storage;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    localStorage: globals.localStorage,
  });
});

const plan = (over: Record<string, unknown> = {}) => ({ chapters: 12, chars: 504000, audioSeconds: 36000, secondsEstimate: null, readyChapters: 0, bytes: 600 * 1048576, ...over });
const local: ReadAloudVoice = { id: "vieneu:duc-tri", name: "Đức Trí", provider: "vieneu", online: false };
const edge: ReadAloudVoice = { id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My", provider: "edge", online: true };

describe("thông báo xuất sách nói", () => {
  it("tiến độ: cùng chữ với máy tính - chương, phần trăm, còn bao lâu", () => {
    expect(progressView({ phase: "voice", chapter: 3, chapters: 12, percent: 27, secondsLeft: 5400, waiting: null })).toMatchObject({
      kind: "loading",
      title: "Đang làm sách nói…",
      description: "Chương 3/12 · 27% · còn khoảng 1 giờ 30 phút",
      progress: 0.27,
    });
  });

  it("nhường người đang nghe thì nói thế thay cho thời gian còn lại", () => {
    expect(progressView({ phase: "voice", chapter: 3, chapters: 12, percent: 27, secondsLeft: 5400, waiting: "listening" })).toMatchObject({
      description: "Chương 3/12 · 27% · nhường cho chương đang nghe",
    });
  });

  it("ghép file: nói đang ghép", () => {
    expect(progressView({ phase: "encode", chapter: 12, chapters: 12, percent: 99 })).toMatchObject({ description: "Đang ghép file âm thanh · Chương 12/12" });
  });

  it("xong: tên file, cỡ, và chương thiếu nếu có", () => {
    expect(finishedView({ name: "Truyện.m4b", size: 3 * 1048576, chapters: 12, chaptersTotal: 12 })).toEqual({
      kind: "success",
      title: "Đã xuất sách nói",
      description: "Truyện.m4b · 3 MB",
    });
    expect(finishedView({ name: "Truyện.m4b", size: 3 * 1048576, chapters: 10, chaptersTotal: 12 })).toMatchObject({
      description: "Truyện.m4b · 3 MB · 10/12 chương - chương chưa xong không có trong file",
    });
  });

  it("chỗ trống cần nói bằng MB / GB", () => {
    expect(spaceText({ bytes: 600 * 1048576 })).toContain("600 MB");
    expect(spaceText({ bytes: 3 * 1073741824 })).toContain("3 GB");
  });
});

describe("hộp xuất sách nói trên điện thoại", () => {
  const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

  it("nói giọng đang chọn, dài bao nhiêu, chỗ trống cần; không nhắc MP3 hay ffmpeg", () => {
    const html = text(renderToString(<AudiobookPhoneForm voice={local} plan={plan()} planError="" />));
    expect(html).toContain("Đức Trí");
    expect(html).toMatch(/12 chương · .*nghe\./);
    expect(html).toContain("Lúc làm cần khoảng");
    expect(html).toContain("M4B");
    expect(html).not.toMatch(/MP3|ffmpeg/i);
    expect(html).not.toContain("Chữ của cả cuốn được gửi");
  });

  it("giọng trực tuyến: cảnh báo gửi cả cuốn ra ngoài, như máy tính", () => {
    expect(text(renderToString(<AudiobookPhoneForm voice={edge} plan={plan()} planError="" />))).toContain("Chữ của cả cuốn được gửi tới máy chủ Microsoft để đọc.");
  });

  it("chương đã làm sẵn từ lần trước: nói làm tiếp từ đó", () => {
    expect(text(renderToString(<AudiobookPhoneForm voice={local} plan={plan({ readyChapters: 3 })} planError="" />))).toContain("Đã có sẵn 3/12 chương từ lần trước - làm tiếp từ đó.");
  });

  it("chưa có giọng: bảo đi tải giọng; chưa tính xong: Đang tính; bị từ chối: nói lý do", () => {
    expect(text(renderToString(<AudiobookPhoneForm voice={undefined} plan={undefined} planError="" />))).toContain("Máy chưa có giọng đọc nào");
    expect(text(renderToString(<AudiobookPhoneForm voice={local} plan={undefined} planError="" />))).toContain("Đang tính độ dài…");
    expect(text(renderToString(<AudiobookPhoneForm voice={local} plan={undefined} planError="Sách chưa tải về điện thoại" />))).toContain("Sách chưa tải về điện thoại");
  });
});

describe("theo dõi việc nền", () => {
  beforeEach(() => {
    library.handlers.length = 0;
    vi.clearAllMocks();
    library.audiobookJobs.mockResolvedValue({ jobs: [] });
  });

  const emit = (event: Record<string, unknown>) => library.handlers.forEach((handler) => handler(event));
  const watch = async () => {
    const stop = watchAudiobookExports();
    await Promise.resolve();
    return stop;
  };

  it("tin tiến độ thành thông báo có nút Dừng, nút ấy dừng đúng cuốn", async () => {
    await watch();
    emit({ bookId: "b1", run: "r1", phase: "voice", chapter: 2, chapters: 5, percent: 30, secondsLeft: null, waiting: null });
    expect(toasts.loading).toHaveBeenCalledTimes(1);
    const [title, options] = toasts.loading.mock.calls[0];
    expect(title).toBe("Đang làm sách nói…");
    expect(options).toMatchObject({ id: "audiobook-export-b1", description: "Chương 2/5 · 30%" });
    options.action.onClick();
    expect(library.cancelAudiobookExport).toHaveBeenCalledWith({ bookId: "b1" });
  });

  it("tin của lượt cũ không đè lên lượt mới", async () => {
    await watch();
    emit({ bookId: "b-stale", run: "r2", phase: "voice", chapter: 1, chapters: 5, percent: 0 });
    toasts.loading.mockClear();
    emit({ bookId: "b-stale", run: "r1", phase: "voice", chapter: 4, chapters: 5, percent: 80 });
    emit({ bookId: "b-stale", run: "r1", stopped: true });
    expect(toasts.loading).not.toHaveBeenCalled();
    expect(toasts).not.toHaveBeenCalled();
  });

  it("xong: thông báo thành công kèm nút Mở file", async () => {
    await watch();
    emit({ bookId: "b1", run: "r1", phase: "voice", chapter: 1, chapters: 2, percent: 10 });
    emit({ bookId: "b1", run: "r1", finished: true, name: "S.m4b", size: 1048576, chapters: 2, chaptersTotal: 2, uri: "content://x/1" });
    expect(toasts.success).toHaveBeenCalledWith("Đã xuất sách nói", expect.objectContaining({ id: "audiobook-export-b1", description: "S.m4b · 1 MB" }));
    toasts.success.mock.calls[0][1].action.onClick();
    expect(library.openFile).toHaveBeenCalledWith({ uri: "content://x/1" });
  });

  it("dừng và lỗi có lời của máy tính", async () => {
    await watch();
    emit({ bookId: "b1", run: "r1", phase: "voice", chapter: 1, chapters: 2, percent: 10 });
    emit({ bookId: "b1", run: "r1", stopped: true });
    expect(toasts).toHaveBeenCalledWith("Đã dừng xuất sách nói", expect.objectContaining({ description: "Phần đã làm được giữ - xuất lại để làm tiếp từ đó." }));
    emit({ bookId: "b2", run: "r9", error: "Hết chỗ trống" });
    expect(toasts.error).toHaveBeenCalledWith("Không xuất được sách nói", expect.objectContaining({ description: "Hết chỗ trống" }));
  });

  it("mở lại app giữa chừng: hiện lại tiến độ của lượt đang chạy", async () => {
    library.audiobookJobs.mockResolvedValue({ jobs: [{ bookId: "b7", run: "r7", phase: "voice", chapter: 6, chapters: 9, percent: 61, secondsLeft: 600, waiting: null }] });
    await watch();
    await Promise.resolve();
    expect(toasts.loading).toHaveBeenCalledWith("Đang làm sách nói…", expect.objectContaining({ id: "audiobook-export-b7", description: "Chương 6/9 · 61% · còn khoảng 10 phút" }));
  });
});
