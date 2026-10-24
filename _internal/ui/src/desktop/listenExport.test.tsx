import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import type { ReadAloudVoice } from "@/listen/readAloud";
import { setApiTransport } from "@/studio/api";
import { AudiobookForm, FfmpegNeeded } from "./AudiobookDialog";
import { jobView, lastExportHint, M4B_COPY, type ExportJob } from "./bookFileExport";
import {
  AUDIOBOOK_COPY,
  audiobookBody,
  audiobookCancel,
  fetchPlan,
  ffmpegPercent,
  ffmpegStart,
  FORMAT_CHOICES,
  planText,
  resumeText,
  wholeBookNotice,
  type AudiobookPlan,
  type FfmpegStatus,
} from "./listenExport";

// "Xuất sách nói (MP3 / M4B)" của sách Nghe ngay: lời trong hộp, tiến độ trong thông báo, và các lệnh gọi máy chủ (abook/webui/listen_export.py).

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

afterEach(() => setApiTransport(null));

const ffmpegReady: FfmpegStatus = { ready: true, downloading: false, done: 0, total: 0, error: "", bytes: 0, blocked: "" };
const ffmpegMissing: FfmpegStatus = { ...ffmpegReady, ready: false, bytes: 80 * 1024 * 1024 };
const plan = (over: Partial<AudiobookPlan> = {}): AudiobookPlan => ({
  chapters: 12,
  chars: 504000,
  audioSeconds: 36000,
  rtf: null,
  secondsEstimate: null,
  readyChapters: 0,
  ffmpeg: ffmpegReady,
  ...over,
});
const local: ReadAloudVoice = { id: "vieneu:duc-tri", name: "Đức Trí", provider: "vieneu", online: false };
const edge: ReadAloudVoice = { id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My", provider: "edge", online: true };

describe("planText / resumeText", () => {
  it("says how long the book is, and how long the machine needs only when the voice was measured", () => {
    expect(planText(plan())).toMatch(/^12 chương · .*nghe\.$/);
    expect(planText(plan())).not.toMatch(/máy cần/);
    expect(planText(plan({ rtf: 0.5, secondsEstimate: 18000 }))).toMatch(/nghe · máy cần .+\.$/);
  });

  it("tells what is already read (heard, prepared, an earlier export) and exports at once", () => {
    expect(resumeText(plan())).toBe("");
    expect(resumeText(plan({ readyChapters: 12 }))).toBe("Đã đọc sẵn cả cuốn - chỉ còn ghép thành file, không đọc lại.");
    // soát a63: huỷ khi chương 2/3 đã đọc 57% - nói phần đã đọc trên cả cuốn, không "1/3 chương"
    expect(resumeText(plan({ chapters: 3, readyChapters: 1, readySeconds: 187, audioSeconds: 360 }))).toBe("Đã đọc sẵn khoảng 52% - phần này xuất ngay, không đọc lại.");
    // vài đoạn đã nghe, chưa đủ chương nào: vẫn nói phần ấy; dưới một phút thì thôi; chưa đủ cả cuốn thì không nói 100%
    expect(resumeText(plan({ readySeconds: 400 }))).toBe("Đã đọc sẵn khoảng 1% - phần này xuất ngay, không đọc lại.");
    expect(resumeText(plan({ readySeconds: 40 }))).toBe("");
    expect(resumeText(plan({ chapters: 3, readyChapters: 2, readySeconds: 359, audioSeconds: 360 }))).toBe("Đã đọc sẵn khoảng 99% - phần này xuất ngay, không đọc lại.");
  });
});

describe("wholeBookNotice", () => {
  it("is silent for a voice that runs on the machine", () => {
    expect(wholeBookNotice(local)).toBe("");
  });

  it("names where the whole book goes for an online voice", () => {
    expect(wholeBookNotice(edge)).toMatch(/cả cuốn.*Microsoft/);
    expect(wholeBookNotice({ provider: "azure", online: true })).toMatch(/Azure Speech.*khóa của bạn/);
    expect(wholeBookNotice({ provider: "khac", online: true })).toMatch(/dịch vụ ngoài/);
  });
});

describe("ffmpegPercent", () => {
  it("is 0 before the size is known and never passes 100", () => {
    expect(ffmpegPercent({ done: 5, total: 0 })).toBe(0);
    expect(ffmpegPercent({ done: 40, total: 160 })).toBe(25);
    expect(ffmpegPercent({ done: 200, total: 160 })).toBe(100);
  });
});

describe("jobView for the audiobook", () => {
  const running = (over: Partial<ExportJob>): ExportJob => ({ state: "running", elapsed: 5, ...over });

  it("shows chapter, percent and time left, with the bar fraction", () => {
    const view = jobView(running({ phase: "voice", chapter: 3, chapters: 12, percent: 25, secondsLeft: 3600 }), 12, false, AUDIOBOOK_COPY);
    expect(view).toMatchObject({ kind: "loading", title: AUDIOBOOK_COPY.busy, progress: 0.25 });
    expect(view.kind === "loading" && view.description).toMatch(/^Chương 3\/12 · 25% · còn /);
  });

  it("says it is making room for the chapter being listened to", () => {
    const view = jobView(running({ phase: "voice", chapter: 3, chapters: 12, percent: 25, waiting: "listening" }), 12, false, AUDIOBOOK_COPY);
    expect(view.kind === "loading" && view.description).toMatch(/nhường cho chương đang nghe/);
  });

  it("says it is waiting for the network instead of a time left", () => {
    const view = jobView(running({ phase: "voice", chapter: 3, chapters: 12, percent: 25, secondsLeft: 600, waiting: "network" }), 12, false, AUDIOBOOK_COPY);
    expect(view.kind === "loading" && view.description).toBe("Chương 3/12 · 25% · Đang chờ mạng…");
    expect(view.kind === "loading" && view.spoken).toMatch(/chờ mạng/);
  });

  it("shows no time left until the server has measured enough", () => {
    const view = jobView(running({ phase: "voice", chapter: 1, chapters: 12, percent: 6, secondsLeft: null }), 12, false, AUDIOBOOK_COPY);
    expect(view.kind === "loading" && view.description).toBe("Chương 1/12 · 6%");
  });

  it("says it is joining the files at the end", () => {
    const view = jobView(running({ phase: "encode", chapter: 12, chapters: 12, percent: 100 }), 12, false, AUDIOBOOK_COPY);
    expect(view).toMatchObject({ kind: "loading", progress: 1 });
    expect(view.kind === "loading" && view.description).toMatch(/Đang ghép file âm thanh/);
  });

  it("falls back to the plain elapsed line before the first report", () => {
    const view = jobView(running({}), 12, false, AUDIOBOOK_COPY);
    expect(view.kind === "loading" && view.progress).toBeUndefined();
  });

  it("reports a stopped run as information that keeps the finished part", () => {
    const view = jobView({ state: "cancelled", id: "x", finishedAgo: 3 }, 12, true, AUDIOBOOK_COPY);
    expect(view).toEqual({ kind: "info", title: AUDIOBOOK_COPY.stopped, description: AUDIOBOOK_COPY.stoppedNote });
  });

  it("says nothing about a stopped run for an export that cannot be stopped", () => {
    expect(jobView({ state: "cancelled" }, 0, false, { busy: "Đang làm…", done: "Xong", failed: "Hỏng" }).kind).toBe("none");
  });

  it("an M4B stopped with Huỷ says nothing was written (soát a61: trước đây M4B không huỷ được)", () => {
    expect(jobView({ state: "cancelled" }, 0, false, M4B_COPY)).toEqual({ kind: "info", title: "Đã huỷ xuất", description: "Chưa có file M4B nào được ghi." });
  });

  it("an M4B downloading its background music says which track (k/n)", () => {
    const view = jobView({ state: "running", phase: "music-fetch", done: 1, total: 3, elapsed: 5 }, 0, false, M4B_COPY);
    expect(view.kind === "loading" && view.description).toBe("Đang tải nhạc nền 2/3 bài");
  });

  it("hints at the last file after a finished run", () => {
    const job: ExportJob = { state: "done", id: "a", result: { folder: "D:\\Sách", files: 12, size: 1000 } as never };
    expect(lastExportHint(job, AUDIOBOOK_COPY)).toMatch(/^Lần xuất gần nhất/);
  });
});

describe("the calls to the server", () => {
  function record(reply: unknown) {
    const calls: { path: string; init?: { method?: string; body?: unknown } }[] = [];
    setApiTransport(async (path, init) => {
      calls.push({ path, init });
      return reply;
    });
    return calls;
  }

  it("asks for the plan of this voice, encoded", async () => {
    const calls = record(plan());
    await fetchPlan("abc", "edge:vi-VN-HoaiMyNeural");
    expect(calls[0].path).toBe("/api/listen/books/abc/audiobook/plan?voice=edge%3Avi-VN-HoaiMyNeural");
  });

  it("starts with the format and the voice the dialog chose", () => {
    expect(audiobookBody("m4b", "vieneu:duc-tri")).toEqual({ format: "m4b", voice: "vieneu:duc-tri" });
  });

  it("cancels the run of the book and starts the ffmpeg download", async () => {
    const calls = record({ state: "running" });
    await audiobookCancel("abc");
    await ffmpegStart();
    expect(calls.map((call) => [call.init?.method, call.path])).toEqual([
      ["POST", "/api/listen/books/abc/audiobook/cancel"],
      ["POST", "/api/ffmpeg"],
    ]);
  });
});

describe("the dialog body", () => {
  const noop = () => undefined;
  const form = (over: Partial<Parameters<typeof AudiobookForm>[0]> = {}) =>
    renderToString(
      <AudiobookForm format="mp3" onFormat={noop} voice={local} plan={plan()} planError="" ffmpeg={ffmpegReady} onDownload={noop} onStopDownload={noop} {...over} />,
    );

  it("offers both formats with one line each, and marks the chosen one", () => {
    const html = form({ format: "m4b" });
    for (const choice of FORMAT_CHOICES) expect(html).toContain(choice.label.replace("-", "-"));
    expect(html).toMatch(/aria-checked="true"[^>]*>(?:(?!<button).)*M4B/);
    expect(html).toContain("12 chương");
  });

  it("names the voice and warns before sending the whole book to an online voice", () => {
    expect(form()).not.toContain('role="note"');
    const online = form({ voice: edge });
    expect(online).toContain("Hoài My");
    expect(online).toContain('role="note"');
    expect(online).toContain("Microsoft");
  });

  it("says so when there is no voice", () => {
    expect(form({ voice: undefined, plan: undefined })).toContain("chưa có giọng đọc nào");
  });

  it("shows the reason the plan was refused instead of the length", () => {
    expect(form({ plan: undefined, planError: "Sách này đã có âm thanh" })).toContain("Sách này đã có âm thanh");
  });

  it("invites to download ffmpeg when it is missing, and shows the progress while it comes", () => {
    expect(form({ ffmpeg: ffmpegReady })).not.toContain("Tải công cụ");
    expect(form({ ffmpeg: ffmpegMissing })).toContain("Tải công cụ");
    const update = form({ ffmpeg: { ...ffmpegReady, outdated: true } });
    expect(update).toContain("Cập nhật công cụ");
    expect(update).toContain("Cập nhật công cụ");
    const downloading = renderToString(
      <FfmpegNeeded status={{ ...ffmpegMissing, downloading: true, done: 40, total: 160 }} onDownload={noop} onStop={noop} />,
    );
    expect(downloading).toContain("25%");
    expect(downloading).toContain("Dừng");
    const blocked = renderToString(<FfmpegNeeded status={{ ...ffmpegMissing, blocked: "Máy này không tải được." }} onDownload={noop} onStop={noop} />);
    expect(blocked).toContain("Máy này không tải được.");
    expect(blocked).not.toContain("Tải công cụ");
  });

  it("from another device says the computer lacks ffmpeg and where to install it, with no download button that would be refused", () => {
    const remote = renderToString(
      <QueryClientProvider client={new QueryClient()}>
        <FfmpegNeeded status={ffmpegMissing} remote onDownload={noop} onStop={noop} />
      </QueryClientProvider>,
    );
    expect(remote).toContain("Thiếu công cụ ghép");
    expect(remote).toContain("ở máy tính");
    expect(remote).not.toContain("Tải công cụ<");
  });
});
