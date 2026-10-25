import { renderToString } from "react-dom/server";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { ListenBook } from "@/listen/model";

// "Xuất MP3" kèm nhạc nền trên điện thoại (soát a99 V3, android/ExportMp3.tsx): hộp nhỏ chỉ mở khi cuốn có nhạc theo chương, ô "Kèm nhạc nền" gửi `music` cho việc nền
// (Mp3ExportWorker.kt), hộp nói trước là file .m4a, thông báo xong nói định dạng và đoạn thiếu nhạc. Plugin native và thông báo được thay bằng bản giả.
const library = vi.hoisted(() => ({
  exportMp3: vi.fn(async (_options: { bookId: string; cover?: string; pick?: boolean; chapterIds?: number[]; music?: boolean }) => ({ started: true, run: "r1", folder: "Music/Truyện", chapters: 3 })),
  exportHistory: vi.fn(async () => ({ exports: [] as { kind: string; changed: number[] }[] })),
  m4bMusicState: vi.fn(async (_options: { bookId: string }) => ({ available: false, enabled: false })),
  addListener: vi.fn(async () => ({ remove: vi.fn() })),
}));
const toasts = vi.hoisted(() => Object.assign(vi.fn(), { loading: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: library, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("sonner", () => ({ toast: toasts }));
vi.mock("@capacitor/core", () => ({ Capacitor: { convertFileSrc: (path: string) => path, isNativePlatform: () => true } }));

import { chooseMp3, exportMp3, finishedToast, Mp3MusicForm, OPEN_MP3_EVENT, type Mp3DialogDetail } from "./ExportMp3";

const book = { id: "sach", title: "Truyện", cover: "bia.jpg", chaptersAvailable: 3, stage: "audio" } as unknown as ListenBook;
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= new EventTarget();
});

beforeEach(() => {
  library.exportMp3.mockClear();
  library.m4bMusicState.mockClear();
  library.exportHistory.mockClear();
});

describe("xuất MP3 kèm nhạc nền", () => {
  it("cuốn không có nhạc: bấm là chạy ngay, không mở hộp, không gửi music", async () => {
    const opened = vi.fn();
    window.addEventListener(OPEN_MP3_EVENT, opened);
    await chooseMp3(book);
    window.removeEventListener(OPEN_MP3_EVENT, opened);
    expect(opened).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(library.exportMp3).toHaveBeenCalledTimes(1));
    expect(library.exportMp3.mock.calls[0][0]).not.toHaveProperty("music");
  });

  it("cuốn có nhạc: mở hộp nhỏ với trạng thái nhạc của cuốn, chưa chạy gì", async () => {
    library.m4bMusicState.mockResolvedValueOnce({ available: true, enabled: true });
    const opened = vi.fn();
    window.addEventListener(OPEN_MP3_EVENT, opened);
    await chooseMp3(book);
    window.removeEventListener(OPEN_MP3_EVENT, opened);
    expect(library.exportMp3).not.toHaveBeenCalled();
    const detail = (opened.mock.calls[0][0] as CustomEvent<Mp3DialogDetail>).detail;
    expect(detail.state).toEqual({ available: true, enabled: true });
    expect(detail.book.id).toBe("sach");
  });

  it("không hỏi được trạng thái nhạc: xuất như trước", async () => {
    library.m4bMusicState.mockRejectedValueOnce(new Error("hỏng"));
    await chooseMp3(book);
    await vi.waitFor(() => expect(library.exportMp3).toHaveBeenCalledTimes(1));
    expect(library.exportMp3.mock.calls[0][0]).not.toHaveProperty("music");
  });

  it("ô đã tích thì gửi `music` cho việc nền", async () => {
    await exportMp3(book, false, undefined, true);
    expect(library.exportMp3).toHaveBeenCalledWith(expect.objectContaining({ bookId: "sach", music: true }));
  });

  it("hộp nhỏ: tích ô thì nói trước chương sẽ là file .m4a; bỏ tích thì không nhắc; cắm sạc khi cuốn dài", () => {
    const on = renderToString(<Mp3MusicForm music onMusic={() => undefined} chapters={30} />);
    expect(text(on)).toContain("Kèm nhạc nền");
    expect(text(on)).toContain("file .m4a thay vì .mp3");
    expect(text(on)).toContain("cắm sạc");
    const off = renderToString(<Mp3MusicForm music={false} onMusic={() => undefined} chapters={30} />);
    expect(text(off)).not.toContain(".m4a");
    expect(text(off)).not.toContain("cắm sạc");
  });

  it("thông báo xong: đoạn thiếu nhạc là lưu ý, đủ cả thì không có lưu ý", () => {
    expect(finishedToast({ files: 12, chaptersTotal: 12, folder: "Music/Truyện", musicMissing: 2 }).note).toBe("2 đoạn thiếu nhạc vì chưa tải được bài.");
    expect(finishedToast({ files: 12, chaptersTotal: 12, folder: "Music/Truyện" }).note).toBe("");
  });
});
