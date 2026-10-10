import { renderToString } from "react-dom/server";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import type { ReadAloudVoice } from "@/listen/readAloud";
import { setApiTransport } from "@/studio/api";
import { AudiobookForm, FfmpegNeeded } from "./AudiobookDialog";
import { jobView, lastExportHint, type ExportJob } from "./bookFileExport";
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

  it("tells what happens to the chapters kept from an earlier run", () => {
    expect(resumeText(plan())).toBe("");
    expect(resumeText(plan({ readyChapters: 3 }))).toBe("Đã có sẵn 3/12 chương từ lần trước - làm tiếp từ đó.");
    expect(resumeText(plan({ readyChapters: 12 }))).toMatch(/chỉ còn ghép thành file/);
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
    expect(jobView({ state: "cancelled" }, 0, false).kind).toBe("none");
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
    const downloading = renderToString(
      <FfmpegNeeded status={{ ...ffmpegMissing, downloading: true, done: 40, total: 160 }} onDownload={noop} onStop={noop} />,
    );
    expect(downloading).toContain("25%");
    expect(downloading).toContain("Dừng");
    const blocked = renderToString(<FfmpegNeeded status={{ ...ffmpegMissing, blocked: "Máy này không tải được." }} onDownload={noop} onStop={noop} />);
    expect(blocked).toContain("Máy này không tải được.");
    expect(blocked).not.toContain("Tải công cụ");
  });
});
