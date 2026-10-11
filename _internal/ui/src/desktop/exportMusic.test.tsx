import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ReadAloudVoice } from "@/listen/readAloud";
import { AudiobookForm, MusicMixOption, musicChecked } from "./AudiobookDialog";
import { jobView, M4B_COPY, musicMissingNote, type ExportJob } from "./bookFileExport";
import { AUDIOBOOK_COPY, audiobookBody, MUSIC_MIX_HINT, type AudiobookPlan, type FfmpegStatus } from "./listenExport";

// Ô "Kèm nhạc nền" của hộp xuất sách nói (MP3 / M4B) và lời báo khi xuất kèm nhạc (abook/webui/music_export.py).

const ffmpeg: FfmpegStatus = { ready: true, downloading: false, done: 0, total: 0, error: "", bytes: 0, blocked: "" };
const plan = (over: Partial<AudiobookPlan> = {}): AudiobookPlan => ({
  chapters: 12,
  chars: 504000,
  audioSeconds: 36000,
  rtf: null,
  secondsEstimate: null,
  readyChapters: 0,
  ffmpeg,
  ...over,
});
const voice: ReadAloudVoice = { id: "vieneu:duc-tri", name: "Đức Trí", provider: "vieneu", online: false };
const noop = () => undefined;

describe("the Kèm nhạc nền box", () => {
  it("starts as the book's background-music switch is, until the listener ticks it, and only for that book", () => {
    const on = { available: true, enabled: true };
    const off = { available: true, enabled: false };
    expect(musicChecked(on, null, "a")).toBe(true);
    expect(musicChecked(off, null, "a")).toBe(false);
    expect(musicChecked(off, { bookId: "a", on: true }, "a")).toBe(true);
    expect(musicChecked(on, { bookId: "a", on: false }, "a")).toBe(false);
    expect(musicChecked(on, { bookId: "a", on: false }, "b")).toBe(true);
  });

  it("is never ticked for a book without a music plan", () => {
    expect(musicChecked(undefined, null, "a")).toBe(false);
    expect(musicChecked({ available: false, enabled: true }, { bookId: "a", on: true }, "a")).toBe(false);
  });

  it("says the music cannot be turned off later", () => {
    const html = renderToString(<MusicMixOption checked onChange={noop} />);
    expect(html).toContain("Kèm nhạc nền");
    expect(html).toContain(MUSIC_MIX_HINT);
    expect(MUSIC_MIX_HINT).toBe("Nhạc được trộn thẳng vào file, không tắt riêng được khi nghe.");
    expect(html).toMatch(/checked=""/);
    expect(renderToString(<MusicMixOption checked={false} onChange={noop} />)).not.toMatch(/checked=""/);
  });

  it("shows in the audiobook dialog only when the book has music for its chapters", () => {
    const form = (over: Partial<Parameters<typeof AudiobookForm>[0]>) =>
      renderToString(<AudiobookForm format="mp3" onFormat={noop} voice={voice} plan={plan()} planError="" ffmpeg={ffmpeg} onDownload={noop} onStopDownload={noop} onMusic={noop} {...over} />);
    expect(form({})).not.toContain("Kèm nhạc nền");
    expect(form({ plan: plan({ music: { available: false, enabled: false } }) })).not.toContain("Kèm nhạc nền");
    const shown = form({ plan: plan({ music: { available: true, enabled: true } }), music: true });
    expect(shown).toContain("Kèm nhạc nền");
    expect(shown).toMatch(/checked=""/);
  });

  it("asks the server for the music only when ticked", () => {
    expect(audiobookBody("mp3", "vieneu:duc-tri", true)).toEqual({ format: "mp3", voice: "vieneu:duc-tri", music: true });
    expect(audiobookBody("mp3", "vieneu:duc-tri", false)).toEqual({ format: "mp3", voice: "vieneu:duc-tri" });
  });
});

describe("progress and result of an export with music", () => {
  const running = (over: Partial<ExportJob>): ExportJob => ({ state: "running", elapsed: 5, ...over });

  it("says which chapter the music is being mixed into", () => {
    const m4b = jobView(running({ phase: "music", chapter: 2, chapters: 4 }), 4, false, M4B_COPY);
    expect(m4b).toMatchObject({ kind: "loading", description: "Đang trộn nhạc chương 2/4", progress: 0.25 });
    const audiobook = jobView(running({ phase: "music", chapter: 3, chapters: 12, percent: 30 }), 12, false, AUDIOBOOK_COPY);
    expect(audiobook).toMatchObject({ description: "Đang trộn nhạc chương 3/12", progress: 0.3 });
  });

  it("says when the m4b is checked for peaks and why it is encoded again", () => {
    expect(jobView(running({ phase: "peaks", peakRound: 0, peakOver: 0 }), 4, false, M4B_COPY)).toMatchObject({ kind: "loading", description: "Đang kiểm đỉnh âm…" });
    expect(jobView(running({ phase: "reencode", peakRound: 2, peakOver: 3 }), 4, false, M4B_COPY))
      .toMatchObject({ description: "Mã hoá lại vì 3 chương vượt đỉnh (lượt 2)" });
    const again = jobView(running({ phase: "music", chapter: 2, chapters: 4, peakRound: 1, peakOver: 1 }), 4, false, M4B_COPY);
    expect(again).toMatchObject({ description: "Mã hoá lại vì 1 chương vượt đỉnh (lượt 1) · Đang trộn nhạc chương 2/4" });
    const audiobook = jobView(running({ phase: "encode", chapter: 5, chapters: 12, peakRound: 1, peakOver: 2 }), 12, false, AUDIOBOOK_COPY);
    expect(audiobook).toMatchObject({ description: "Mã hoá lại vì 2 chương vượt đỉnh (lượt 1) · Chương 5/12" });
    const first = jobView(running({ phase: "encode", chapter: 5, chapters: 12, peakRound: 1, peakOver: 0 }), 12, false, AUDIOBOOK_COPY);
    expect(first).toMatchObject({ description: "Đang ghép file âm thanh · Chương 5/12" });
  });

  it("counts the parts left without music because a track could not be fetched", () => {
    expect(musicMissingNote({ folder: "x" })).toBe("");
    expect(musicMissingNote({ folder: "x", musicMissing: 3 })).toBe("3 đoạn thiếu nhạc vì chưa tải được bài");
    const done = jobView({ state: "done", result: { folder: "D:\\Sách", file: "D:\\Sách\\Truyện.m4b", size: 1000, musicMissing: 2 } }, 0, false, M4B_COPY);
    expect(done.kind === "success" && done.description).toContain("2 đoạn thiếu nhạc vì chưa tải được bài");
  });
});
