import { renderToString } from "react-dom/server";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { ListenBook } from "@/listen/model";

// "Xuất M4B" kèm nhạc nền trên điện thoại (android/ExportM4b.tsx): hộp nhỏ chỉ mở khi cuốn có nhạc theo chương, ô "Kèm nhạc nền" gửi `music` cho việc nền
// (M4bExportWorker.kt), tiến độ và thông báo xong dùng chữ của máy tính. Plugin native và thông báo được thay bằng bản giả.
const library = vi.hoisted(() => ({
  exportM4b: vi.fn(async (_options: { bookId: string; cover?: string; music?: boolean }) => ({ started: true, run: "r1", chapters: 3 })),
  m4bMusicState: vi.fn(async (_options: { bookId: string }) => ({ available: false, enabled: false })),
  cancelM4bExport: vi.fn(async () => undefined),
  addListener: vi.fn(async () => ({ remove: vi.fn() })),
}));
const toasts = vi.hoisted(() => Object.assign(vi.fn(), { loading: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: library, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("sonner", () => ({ toast: toasts }));
vi.mock("@capacitor/core", () => ({ Capacitor: { convertFileSrc: (path: string) => path, isNativePlatform: () => true } }));

import { chooseM4b, exportM4b, finishedView, M4bMusicForm, OPEN_M4B_EVENT, progressText, type M4bDialogDetail } from "./ExportM4b";

const book = { id: "sach", title: "Truyện", cover: "bia.jpg", chaptersAvailable: 3, stage: "audio" } as unknown as ListenBook;
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= new EventTarget();
});

beforeEach(() => {
  library.exportM4b.mockClear();
  library.m4bMusicState.mockClear();
});

describe("xuất M4B kèm nhạc nền", () => {
  it("cuốn không có nhạc: bấm là chạy ngay, không mở hộp, không kèm nhạc", async () => {
    const opened = vi.fn();
    window.addEventListener(OPEN_M4B_EVENT, opened);
    await chooseM4b(book);
    window.removeEventListener(OPEN_M4B_EVENT, opened);
    expect(opened).not.toHaveBeenCalled();
    expect(library.exportM4b).toHaveBeenCalledWith(expect.objectContaining({ bookId: "sach", music: false }));
  });

  it("cuốn có nhạc: mở hộp nhỏ với trạng thái nhạc của cuốn, chưa chạy gì", async () => {
    library.m4bMusicState.mockResolvedValueOnce({ available: true, enabled: true });
    const opened = vi.fn();
    window.addEventListener(OPEN_M4B_EVENT, opened);
    await chooseM4b(book);
    window.removeEventListener(OPEN_M4B_EVENT, opened);
    expect(library.exportM4b).not.toHaveBeenCalled();
    const detail = (opened.mock.calls[0][0] as CustomEvent<M4bDialogDetail>).detail;
    expect(detail.state).toEqual({ available: true, enabled: true });
    expect(detail.book.id).toBe("sach");
  });

  it("không hỏi được trạng thái nhạc: xuất như trước", async () => {
    library.m4bMusicState.mockRejectedValueOnce(new Error("hỏng"));
    await chooseM4b(book);
    expect(library.exportM4b).toHaveBeenCalledWith(expect.objectContaining({ music: false }));
  });

  it("ô đã tích thì gửi `music` cho việc nền", async () => {
    await exportM4b(book, true);
    expect(library.exportM4b).toHaveBeenCalledWith({ bookId: "sach", cover: undefined, music: true });
  });

  it("hộp nhỏ: ô Kèm nhạc nền theo lựa chọn, lời nhắc trộn thẳng vào file, gợi ý cắm sạc khi cuốn dài", () => {
    const on = renderToString(<M4bMusicForm music onMusic={() => undefined} chapters={30} />);
    expect(text(on)).toContain("Kèm nhạc nền");
    expect(text(on)).toContain("Nhạc được trộn thẳng vào file, không tắt riêng được khi nghe.");
    expect(on).toMatch(/<input type="checkbox"[^>]*checked=""/);
    expect(text(on)).toContain("cắm sạc");
    const off = renderToString(<M4bMusicForm music={false} onMusic={() => undefined} chapters={30} />);
    expect(off).not.toMatch(/checked=""/);
    expect(text(off)).not.toContain("cắm sạc");
    expect(text(renderToString(<M4bMusicForm music onMusic={() => undefined} chapters={20} />))).not.toContain("cắm sạc");
  });

  it("tiến độ theo pha, cùng chữ máy tính", () => {
    expect(progressText({ phase: "music-fetch", done: 1, total: 3 }, 12)).toBe("Đang tải nhạc nền 2/3 bài");
    expect(progressText({ phase: "music", chapter: 3, chapters: 12 }, 12)).toBe("Đang trộn nhạc chương 3/12");
    expect(progressText({ phase: "peaks", peakRound: 0 }, 12)).toBe("Đang kiểm đỉnh âm…");
    expect(progressText({ phase: "reencode", peakRound: 2, peakOver: 3 }, 12)).toBe("Mã hoá lại vì 3 chương vượt đỉnh (lượt 2)");
    // pha "voice" không có trong M4B: không pha thì vẫn đếm chương như trước
    expect(progressText({ done: 3, total: 12, percent: 27 }, 12)).toBe("3/12 chương · 27%");
  });

  it("xong mà có đoạn thiếu nhạc: nói số đoạn", () => {
    expect(finishedView({ name: "Truyện.m4b", size: 3 * 1048576, chapters: 6, chaptersTotal: 6, musicMissing: 2 })).toMatchObject({
      description: "Truyện.m4b · 3 MB · 2 đoạn thiếu nhạc vì chưa tải được bài",
    });
  });
});
