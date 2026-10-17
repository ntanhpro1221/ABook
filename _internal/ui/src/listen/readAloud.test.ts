import { describe, expect, it, onTestFinished, vi } from "vitest";
import type { AudioEngine, EngineEvent, TrackInfo } from "./engine";
import type { Script } from "./model";
import {
  CLIP_RETRIES,
  clipRetryBefore,
  CLIP_MIN_ATTEMPT_MS,
  CLIP_RETRY_BUDGET_MS,
  CLIP_RETRY_DELAYS_MS,
  NEXT_CHAPTER_AHEAD,
  PROBE_MS,
  ReadAloudEngine,
  ReadAloudError,
  RoutedEngine,
  estimateSeconds,
  fetchClipBytes,
  estimatedStarts,
  isLongParagraph,
  isSpeakable,
  KEEP_BEHIND,
  isTransientClipError,
  MAX_WARM_RANK,
  readAheadCount,
  warmRankOf,
  WHOLE_CHARS,
  type AudioLike,
  type ReadAloudClip,
  type SpeechTrack,
} from "./readAloud";
import { LiveClip } from "./liveClip";
import { FakeSource } from "./liveTestKit";
import { textScript } from "./textScript";
import { tailFromWord, usableWords, wordIndexAt } from "./words";

class FakeAudio implements AudioLike {
  paused = true;
  duration = 0;
  playbackRate = 1;
  volume = 1;
  muted = false;
  preload = "";
  currentTime = 0;
  plays = 0;
  released = false;
  private listeners = new Map<string, Set<() => void>>();
  constructor(public src: string) {}
  play() {
    this.paused = false;
    this.plays += 1;
    return Promise.resolve();
  }
  pause() {
    this.paused = true;
  }
  removeAttribute() {
    this.released = true;
  }
  load() {}
  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: () => void) {
    this.listeners.get(type)?.delete(listener);
  }
  emit(type: string) {
    this.listeners.get(type)?.forEach((listener) => listener());
  }
  /** Hết clip: như trình duyệt - dừng rồi báo "ended". */
  finish() {
    this.paused = true;
    this.emit("ended");
  }
}

const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

/** Mỗi chữ 500 ms: clip của đoạn n chữ dài n/2 giây. */
function clipOf(text: string, gainDb?: number): ReadAloudClip {
  const count = text.split(/\s+/).filter(Boolean).length;
  return { url: `/clip/${encodeURIComponent(text)}`, durationMs: count * 500, words: Array.from({ length: count }, (_, i) => [i * 500, i * 500 + 450]), gainDb };
}

interface Setup {
  engine: ReadAloudEngine;
  audios: FakeAudio[];
  sources: FakeSource[];
  published: Script[];
  requests: { text: string; cachedOnly: boolean; willRetry?: boolean; retryBefore?: number; fresh?: boolean; rank?: number; whole?: boolean; tailFrom?: number; resolve: (clip?: ReadAloudClip) => void; reject: (error: Error) => void }[];
  events: string[];
  /** Cho clip của đoạn có chữ `text` về. */
  arrive: (text: string) => Promise<void>;
  track: SpeechTrack;
  trackInfo: TrackInfo;
}

// Chữ có 4 đoạn: 2, 4, 3 và 2 chữ (1,0 s; 2,0 s; 1,5 s; 1,0 s khi clip về). Ước tính ban đầu theo 14 ký tự mỗi giây.
const CHAPTER = "Một hai.\n\nBa bốn năm sáu.\n\nBảy tám chín.\n\nMười mười.";
const TEXTS = ["Một hai.", "Ba bốn năm sáu.", "Bảy tám chín.", "Mười mười."];

function setup(options: { chapter?: string; cached?: Record<string, ReadAloudClip>; script?: Script; muted?: boolean } = {}): Setup {
  const audios: FakeAudio[] = [];
  const sources: FakeSource[] = [];
  const published: Script[] = [];
  const requests: Setup["requests"] = [];
  const events: string[] = [];
  const track: SpeechTrack = {
    script: async () => options.script ?? textScript(1, "Chương", options.chapter ?? CHAPTER),
    voice: () => "edge:vi-VN-HoaiMyNeural",
    fetchClip: (_voice, text, o) =>
      new Promise((resolve, reject) => {
        const cached = options.cached?.[text];
        if (o?.cachedOnly) {
          if (cached) resolve(cached);
          else reject(Object.assign(new Error("uncached"), { reason: "uncached" }));
          return;
        }
        requests.push({ text, cachedOnly: false, willRetry: o?.willRetry, retryBefore: o?.retryBefore, fresh: o?.fresh, rank: o?.rank, whole: o?.whole, tailFrom: o?.tailFrom, resolve: (clip) => resolve(clip ?? clipOf(text)), reject });
      }),
    onScript: (script) => published.push(script),
  };
  const engine = new ReadAloudEngine({
    createAudio: (url) => {
      const audio = new FakeAudio(url);
      audios.push(audio);
      return audio;
    },
    createSource: () => {
      const source = new FakeSource();
      sources.push(source);
      return source;
    },
    muted: options.muted ?? false,
  });
  for (const name of ["time", "duration", "play", "pause", "ended", "error", "recovered", "waiting", "playing"] as EngineEvent[]) {
    engine.on(name, () => events.push(name));
  }
  return {
    engine,
    audios,
    sources,
    published,
    requests,
    events,
    arrive: async (text) => {
      requests.filter((r) => r.text === text).forEach((r) => r.resolve());
      await flush();
    },
    track,
    trackInfo: { url: "", title: "t", album: "a", artist: "x", speech: track },
  };
}

const audioOf = (s: Setup, text: string) => s.audios.find((a) => a.src === `/clip/${encodeURIComponent(text)}`);

describe("ước tính và đồng hồ ảo", () => {
  it("ước ~14 ký tự mỗi giây, đoạn không có chữ không tốn thời gian", () => {
    expect(isSpeakable("* * *")).toBe(false);
    expect(isSpeakable("Đã 1")).toBe(true);
    expect(estimateSeconds("* * *")).toBe(0);
    expect(estimateSeconds("x".repeat(140))).toBe(10);
    expect(estimateSeconds("Ừ.")).toBeGreaterThan(0);
    expect(estimatedStarts([{ text: "x".repeat(28) }, { text: "—" }, { text: "y".repeat(14) }])).toEqual([0, 2, 2]);
    // dòng ngăn cảnh chiếm quãng lặng 1,5 s (chỉ khi có đoạn đọc được ở cả hai bên)
    expect(estimatedStarts([{ text: "x".repeat(14) }, { text: "* * *" }, { text: "y".repeat(14) }, { text: "◆" }])).toEqual([0, 1, 2.5, 3.5]);
  });

  it("nạp xong thì tổng thời lượng là tổng các đoạn ước và kịch bản có mốc", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, false);
    await flush();
    const estimates = TEXTS.map(estimateSeconds);
    expect(s.engine.duration).toBeCloseTo(estimates.reduce((a, b) => a + b, 0), 6);
    expect(s.engine.time).toBe(0);
    expect(s.engine.paused).toBe(true);
    const script = s.published.at(-1)!;
    expect(script.timed).toBe(true);
    expect(script.segments.map((segment) => segment.start)).toEqual(estimatedStarts(TEXTS.map((text) => ({ text }))));
    expect(script.segments.every((segment) => segment.words === undefined)).toBe(true);
    expect(s.requests).toHaveLength(0); // chưa bấm phát thì chưa tải gì
  });
});

describe("phát, đọc trước và sửa thời gian", () => {
  it("bấm phát: chờ clip đầu, đọc trước ba đoạn kế (máy tính), không đọc xa hơn", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    expect(s.events.slice(0, 2)).toEqual(["play", "waiting"]);
    expect(s.requests.map((r) => r.text)).toEqual(TEXTS.slice(0, 4));
    const longer = setup({ chapter: `${CHAPTER}\n\nMười một.\n\nMười hai.` });
    longer.engine.load(longer.trackInfo, 0, true);
    await flush();
    expect(longer.requests.map((r) => r.text)).toEqual(TEXTS);
    await s.arrive(TEXTS[0]);
    const first = audioOf(s, TEXTS[0])!;
    expect(first.plays).toBe(1);
    expect(s.engine.duration).toBeCloseTo(1 + estimateSeconds(TEXTS[1]) + estimateSeconds(TEXTS[2]) + estimateSeconds(TEXTS[3]), 6);
  });

  it("đồng hồ = đầu đoạn + currentTime; clip về thì dời đầu các đoạn sau và ghi mốc chữ tính từ đầu chương", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await s.arrive(TEXTS[0]);
    await s.arrive(TEXTS[1]);
    audioOf(s, TEXTS[0])!.currentTime = 0.4;
    expect(s.engine.time).toBeCloseTo(0.4, 6);
    const script = s.published.at(-1)!;
    expect(script.segments[0].start).toBe(0);
    expect(script.segments[0].end).toBe(1);
    expect(script.segments[1].start).toBe(1);
    expect(script.segments[1].end).toBe(3);
    // chữ của đoạn 2 tính từ đầu chương (ms): đầu đoạn là 1 000 ms
    expect(script.segments[1].words).toEqual([[1000, 1450], [1500, 1950], [2000, 2450], [2500, 2950]]);
    expect(usableWords(script.segments[1].text, script.segments[1].words)).not.toBeNull();
    expect(script.segments[2].start).toBe(3);
    expect(script.segments[2].words).toBeUndefined(); // chưa có clip: chỉ sáng cả đoạn
    expect(script.duration).toBeCloseTo(3 + estimateSeconds(TEXTS[2]) + estimateSeconds(TEXTS[3]), 6);
  });

  it("hết đoạn thì sang đoạn kế liền mạch, đọc trước tiếp; hết chương thì pause rồi ended", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await s.arrive(text);
    audioOf(s, TEXTS[0])!.finish();
    expect(audioOf(s, TEXTS[1])!.plays).toBe(1);
    expect(s.engine.time).toBeCloseTo(1, 6);
    expect(s.requests.some((r) => r.text === TEXTS[3])).toBe(true); // đọc trước dịch theo
    await s.arrive(TEXTS[3]);
    audioOf(s, TEXTS[1])!.finish();
    audioOf(s, TEXTS[2])!.finish();
    expect(audioOf(s, TEXTS[3])!.plays).toBe(1);
    s.events.length = 0;
    audioOf(s, TEXTS[3])!.finish();
    expect(s.events.filter((e) => e === "pause" || e === "ended")).toEqual(["pause", "ended"]);
    expect(s.engine.ended).toBe(true);
    expect(s.engine.paused).toBe(true);
    expect(s.engine.time).toBeCloseTo(s.engine.duration, 6);
  });

  it("clip kế chưa về khi đoạn trước hết: báo waiting, về thì phát tiếp", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await s.arrive(TEXTS[0]);
    s.events.length = 0;
    audioOf(s, TEXTS[0])!.finish();
    expect(s.events).toContain("waiting");
    expect(audioOf(s, TEXTS[1])).toBeUndefined();
    await s.arrive(TEXTS[1]);
    expect(audioOf(s, TEXTS[1])!.plays).toBe(1);
  });

  it("tạm dừng rồi phát tiếp không về đầu đoạn; thả phần tử audio của các đoạn đã xa", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await s.arrive(text);
    const first = audioOf(s, TEXTS[0])!;
    first.currentTime = 0.7;
    s.engine.pause();
    expect(first.paused).toBe(true);
    s.engine.play();
    expect(first.currentTime).toBe(0.7);
    expect(first.plays).toBe(2);
    first.finish();
    audioOf(s, TEXTS[1])!.finish();
    audioOf(s, TEXTS[2])!.finish();
    expect(first.released).toBe(true);
  });

  it("tốc độ đi vào playbackRate (kể cả phần tử tạo sau), độ to nhân với độ chỉnh của giọng", async () => {
    const s = setup();
    s.engine.setRate(1.5);
    s.engine.setVolume(0.8);
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    s.requests[0].resolve(clipOf(TEXTS[0], -6));
    await flush();
    const first = audioOf(s, TEXTS[0])!;
    expect(first.playbackRate).toBe(1.5);
    expect(first.volume).toBeCloseTo(0.8 * Math.pow(10, -6 / 20), 6);
    s.engine.setRate(2);
    expect(first.playbackRate).toBe(2);
    await s.arrive(TEXTS[1]);
    expect(audioOf(s, TEXTS[1])!.playbackRate).toBe(2);
  });

  it("?mute=1 tắt tiếng phần tử audio", async () => {
    const s = setup({ muted: true });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await s.arrive(TEXTS[0]);
    expect(audioOf(s, TEXTS[0])!.muted).toBe(true);
  });
});

describe("chương kế: xin trước tiêu đề + đoạn đầu khi chương này sắp hết", () => {
  const NEXT = ["Chương hai.", "Đoạn đầu của chương hai.", "Đoạn thứ hai của chương hai.", "Đoạn ba."];

  function withNext(options: Parameters<typeof setup>[0] = {}, serial = false) {
    const s = setup(options);
    const asked: string[] = [];
    s.track.after = async () => {
      asked.push("after");
      return NEXT;
    };
    if (serial) s.track.serial = () => true;
    return { s, asked };
  }
  const nextRequests = (s: Setup) => s.requests.filter((r) => NEXT.includes(r.text)).map((r) => r.text);

  it("cửa sổ đọc trước chạm cuối chương và mọi clip đã về: xin tiêu đề + đoạn đầu của chương kế, không xin xa hơn", async () => {
    const { s, asked } = withNext();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    expect(nextRequests(s)).toEqual([]); // clip của chương này còn đang làm: chưa xin chương kế
    for (const text of TEXTS) await s.arrive(text);
    await flush();
    expect(asked).toEqual(["after"]);
    expect(nextRequests(s)).toEqual(NEXT.slice(0, NEXT_CHAPTER_AHEAD));
    await s.arrive(NEXT[0]);
    await s.arrive(NEXT[1]);
    expect(nextRequests(s)).toHaveLength(NEXT_CHAPTER_AHEAD); // chỉ một lần cho mỗi lần nạp chương
  });

  // Đoạn dài (>= WHOLE_CHARS ký tự) mới tính vào rank của đoạn sau nó.
  const wide = (name: string) => `${name} ${"nói mãi không dứt ".repeat(8)}`.trim();
  const WIDE = [wide("Một"), wide("Hai"), wide("Ba"), wide("Bốn")];
  const WIDE_NEXT = ["Chương hai.", wide("Đoạn đầu của chương hai"), wide("Đoạn thứ hai của chương hai")];

  function withWideNext(serial = false) {
    const s = setup({ chapter: WIDE.join("\n\n") });
    s.track.after = async () => WIDE_NEXT;
    if (serial) s.track.serial = () => true;
    return s;
  }

  it("mỗi clip xin trước của chương kế mang rank = số đoạn DÀI người nghe còn phải nghe trước nó: sau mọi đoạn dài của chương này, trước việc nền (không rank)", async () => {
    const s = withWideNext();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    // đoạn của chính chương đang nghe: rank là số đoạn dài từ chỗ nghe tới nó (0 = đang chờ)
    expect(s.requests.map((r) => [r.text, r.rank])).toEqual(WIDE.map((text, i) => [text, i]));
    for (const text of WIDE) await s.arrive(text);
    await flush();
    const warm = s.requests.filter((r) => WIDE_NEXT.includes(r.text));
    expect(warm.map((r) => r.text)).toEqual(WIDE_NEXT.slice(0, NEXT_CHAPTER_AHEAD));
    // người nghe ở đoạn 0 của 4 đoạn dài: tiêu đề (ngắn) chương kế đứng sau 4 đoạn; đoạn đầu cũng sau 4 - tiêu đề ngắn đứng trước nó không tính
    expect(warm.map((r) => r.rank)).toEqual([WIDE.length, WIDE.length]);
    expect(warm.every((r) => r.rank! >= 1 && r.rank! <= MAX_WARM_RANK)).toBe(true);
  });

  it("giọng chạy trên máy cũng gửi rank cho từng clip xin lần lượt của chương kế", async () => {
    const s = withWideNext(true);
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of WIDE) await s.arrive(text);
    await flush();
    expect(s.requests.filter((r) => WIDE_NEXT.includes(r.text)).map((r) => r.rank)).toEqual([WIDE.length]);
    await s.arrive(WIDE_NEXT[0]);
    expect(s.requests.filter((r) => WIDE_NEXT.includes(r.text)).map((r) => r.rank)).toEqual([WIDE.length, WIDE.length]);
  });

  it("đoạn ngắn đứng trước không tính vào rank của đoạn kế (a56): cuối chương toàn đoạn ngắn thì đoạn dài của chương kế vẫn rank 1", async () => {
    const tail = ["Ừ.", "Vâng ạ.", "Thôi được."];
    const s = setup({ chapter: [WIDE[0], ...tail].join("\n\n") });
    s.track.after = async () => WIDE_NEXT;
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of [WIDE[0], ...tail]) await s.arrive(text);
    await flush();
    const warm = s.requests.filter((r) => WIDE_NEXT.includes(r.text));
    expect(warm.map((r) => r.rank)).toEqual([1, 1]); // chỉ đoạn dài đầu còn tính (người nghe ở đoạn 0); 3 đoạn ngắn không
  });

  it("rank xin trước chương kế: tối thiểu 1, tối đa MAX_WARM_RANK (98, thấp hơn rank việc nền 99 của máy chủ)", () => {
    expect(MAX_WARM_RANK).toBe(98);
    expect(warmRankOf(4, 0)).toBe(4);
    expect(warmRankOf(1, 0)).toBe(1);
    expect(warmRankOf(0, 0)).toBe(1);
    expect(warmRankOf(90, 20)).toBe(98);
    expect(warmRankOf(10_000, 3)).toBe(98);
  });

  it("giọng chậm: xin trước chương kế đủ số giây âm thanh như đọc trước giữa chương (không chỉ 2 clip), tối đa 4 lượt cùng lúc; giọng nhanh vẫn 2", async () => {
    const more = Array.from({ length: 10 }, (_, i) => `Câu số ${i + 1} của chương hai.`);
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      const { s, asked } = withNext();
      s.track.after = async () => {
        asked.push("after");
        return more;
      };
      const t0 = Date.now();
      s.engine.load(s.trackInfo, 0, true);
      await flush();
      // bốn clip của chương này mỗi cái mất 20 giây: đo được giọng chậm
      vi.setSystemTime(t0 + 20_000);
      for (const text of TEXTS) await s.arrive(text);
      await flush();
      expect(asked).toEqual(["after"]);
      const warm = () => s.requests.filter((r) => more.includes(r.text));
      // cần 40 s đệm (2 x 20 s), mỗi câu ước ~2 s -> cửa sổ tới trần 8 câu, nhưng chỉ 4 lượt đi cùng lúc (như đọc trước giữa chương)
      expect(warm().map((r) => r.text)).toEqual(more.slice(0, 4));
      await s.arrive(more[0]);
      expect(warm()).toHaveLength(5);
      for (const text of more.slice(1, 8)) await s.arrive(text);
      expect(warm().map((r) => r.text)).toEqual(more.slice(0, 8));
    } finally {
      vi.useRealTimers();
    }
    // đối chứng: clip về nhanh thì vẫn chỉ NEXT_CHAPTER_AHEAD
    const fast = withNext();
    fast.s.track.after = async () => more;
    fast.s.engine.load(fast.s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS) await fast.s.arrive(text);
    await flush();
    expect(fast.s.requests.filter((r) => more.includes(r.text))).toHaveLength(NEXT_CHAPTER_AHEAD);
  });

  it("chương còn dài: chưa xin chương kế khi cửa sổ đọc trước chưa tới cuối", async () => {
    const long = Array.from({ length: 8 }, (_, i) => `Đoạn số ${i + 1}.`).join("\n\n");
    const { s, asked } = withNext({ chapter: long });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await s.arrive("Đoạn số 1.");
    await s.arrive("Đoạn số 2.");
    await s.arrive("Đoạn số 3.");
    await s.arrive("Đoạn số 4.");
    expect(asked).toEqual([]);
    expect(nextRequests(s)).toEqual([]);
  });

  it("tạm dừng thì không gửi chữ chương kế đi; giọng chạy trên máy xin lần lượt từng clip", async () => {
    const paused = withNext();
    paused.s.engine.load(paused.s.trackInfo, 0, false);
    await flush();
    expect(paused.asked).toEqual([]);
    const { s } = withNext({}, true);
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS) await s.arrive(text);
    await flush();
    expect(nextRequests(s)).toEqual([NEXT[0]]);
    await s.arrive(NEXT[0]);
    expect(nextRequests(s)).toEqual([NEXT[0], NEXT[1]]);
  });

  it("chương kế lỗi hay không có thì bỏ qua, chương này vẫn phát bình thường", async () => {
    const { s } = withNext();
    s.track.after = async () => {
      throw new Error("không có chữ");
    };
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS) await s.arrive(text);
    await flush();
    expect(nextRequests(s)).toEqual([]);
    expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
  });
});

describe("tua", () => {
  async function playing(): Promise<Setup> {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await s.arrive(text);
    return s;
  }

  it("tua vào trong một clip đã biết rơi đúng chỗ trong clip, không về đầu đoạn", async () => {
    const s = await playing();
    // đoạn 2 bắt đầu ở 1 s, dài 2 s: giây 2,25 là 1,25 s trong clip
    s.engine.seek(2.25);
    const second = audioOf(s, TEXTS[1])!;
    expect(audioOf(s, TEXTS[0])!.paused).toBe(true);
    expect(second.currentTime).toBeCloseTo(1.25, 6);
    expect(second.plays).toBe(1);
    expect(s.engine.time).toBeCloseTo(2.25, 6);
  });

  it("tua vào đoạn chưa đọc: chờ, đọc, rồi vào theo tỉ lệ của đoạn", async () => {
    const s = await playing();
    const start = s.engine.duration - estimateSeconds(TEXTS[3]); // đầu đoạn 4 (chưa có clip)
    s.events.length = 0;
    s.engine.seek(start + estimateSeconds(TEXTS[3]) / 2);
    expect(s.events).toContain("waiting");
    expect(s.engine.time).toBeCloseTo(start + estimateSeconds(TEXTS[3]) / 2, 6); // nửa đoạn, theo ước
    expect(audioOf(s, TEXTS[3])).toBeUndefined();
    await s.arrive(TEXTS[3]); // clip thật dài 1 s
    expect(audioOf(s, TEXTS[3])!.currentTime).toBeCloseTo(0.5, 6);
    expect(s.engine.time).toBeCloseTo(3 + 1.5 + 0.5, 6);
  });

  it("seek ngoài chương được kẹp lại", async () => {
    const s = await playing();
    s.engine.seek(9999);
    expect(s.engine.time).toBeLessThanOrEqual(s.engine.duration);
    s.engine.seek(-5);
    expect(s.engine.time).toBe(0);
  });

  it("bấm vào chữ của đoạn đã có clip: nhảy vào đúng mốc chữ", async () => {
    const s = await playing();
    s.engine.seekWord(1, 2); // chữ thứ 3 của đoạn 2: mốc 1 000 ms trong clip
    const second = audioOf(s, TEXTS[1])!;
    expect(second.currentTime).toBeCloseTo(1, 6);
    expect(s.engine.time).toBeCloseTo(1 + 1, 6);
    expect(second.plays).toBe(1);
  });

  it("bấm vào chữ của đoạn chưa đọc: hiện chờ, đọc đoạn ấy, bắt đầu ở mốc chữ và dựng lại đồng hồ", async () => {
    const s = await playing();
    s.events.length = 0;
    s.engine.seekWord(3, 1); // đoạn 4 "Mười mười.", chữ thứ 2
    expect(s.events).toContain("waiting");
    expect(audioOf(s, TEXTS[3])).toBeUndefined();
    const before = s.engine.duration;
    await s.arrive(TEXTS[3]);
    const fourth = audioOf(s, TEXTS[3])!;
    expect(fourth.currentTime).toBeCloseTo(0.5, 6);
    expect(fourth.plays).toBe(1);
    expect(s.engine.time).toBeCloseTo(4.5 + 0.5, 6);
    expect(s.engine.duration).not.toBe(before); // ước -> thật
    const script = s.published.at(-1)!;
    expect(script.segments[3].start).toBe(4.5);
    expect(script.segments[3].words?.[1]).toEqual([5000, 5450]);
  });

  it("seekWord gọi lúc đang nạp thì áp dụng ngay khi nạp xong", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    s.engine.seekWord(2, 1);
    await flush();
    expect(s.requests.some((r) => r.text === TEXTS[2])).toBe(true);
    await s.arrive(TEXTS[2]);
    expect(audioOf(s, TEXTS[2])!.currentTime).toBeCloseTo(0.5, 6);
  });
});

describe("nghe dở và lỗi", () => {
  it("nạp ở giây đã lưu: tra bộ đệm để đồng hồ đúng như lần nghe trước, rơi đúng đoạn", async () => {
    // Giây 1,5 theo đồng hồ THẬT (đoạn 1 dài 1 s) nằm giữa đoạn 2; theo ước tính thuần thì rơi chỗ khác.
    const cached = { [TEXTS[0]]: clipOf(TEXTS[0]), [TEXTS[1]]: clipOf(TEXTS[1]) };
    const s = setup({ cached });
    s.engine.load(s.trackInfo, 1.5, false);
    await flush();
    expect(s.published.at(-1)!.segments[1].start).toBe(1);
    expect(s.engine.time).toBeCloseTo(1.5, 6);
    s.engine.play();
    await flush();
    expect(audioOf(s, TEXTS[1])!.currentTime).toBeCloseTo(0.5, 6);
  });

  it("kịch bản đã có mốc (lần nghe trước) giữ nguyên độ dài đã biết", async () => {
    const first = setup();
    first.engine.load(first.trackInfo, 0, true);
    await flush();
    await first.arrive(TEXTS[0]);
    await first.arrive(TEXTS[1]);
    const timed = first.published.at(-1)!;
    const again = setup({ script: timed });
    again.engine.load(again.trackInfo, 0, false);
    await flush();
    expect(again.published.at(-1)!.segments[1].start).toBe(1);
    expect(again.published.at(-1)!.segments[1].end).toBe(3);
    expect(again.published.at(-1)!.segments[1].words).toEqual(timed.segments[1].words);
  });

  it("đoạn không có chữ mà không phải ngăn cảnh ('...') được bỏ qua, không lặng", async () => {
    const s = setup({ chapter: "Một hai.\n\n...\n\nBa bốn." });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    expect(s.requests.map((r) => r.text)).toEqual(["Một hai.", "Ba bốn."]);
    await s.arrive("Một hai.");
    await s.arrive("Ba bốn.");
    audioOf(s, "Một hai.")!.finish();
    expect(audioOf(s, "Ba bốn.")!.plays).toBe(1);
  });

  it("lỗi thoáng qua ở đoạn đang chờ: tự thử lại sau quãng nghỉ lùi dần, không dừng; hỏng quá số lần thử thì mới dừng", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      const first = () => s.requests.filter((r) => r.text === TEXTS[0]);
      // hỏng hai lần liên tiếp (Edge 502, rồi chậm quá), lần thứ ba về: người nghe không bị dừng, chỉ chờ
      first()[0].reject(Object.assign(new Error("Bad Gateway"), { reason: "service" }));
      await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[0] - 1);
      expect(first()).toHaveLength(1);
      await vi.advanceTimersByTimeAsync(1);
      expect(first()).toHaveLength(2);
      first()[1].reject(Object.assign(new Error("Chậm quá"), { reason: "timeout" }));
      await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[1]);
      expect(first()).toHaveLength(3);
      expect(s.events).not.toContain("error");
      expect(s.engine.paused).toBe(false);
      first()[2].resolve();
      await vi.advanceTimersByTimeAsync(0);
      expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
      expect(s.engine.error).toBe("");

      // hết lần thử: dừng, báo lỗi; bộ lấy clip được báo "còn thử lại" ở mọi lần trừ lần cuối
      const t = setup();
      t.engine.load(t.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      const firstT = () => t.requests.filter((r) => r.text === TEXTS[0]);
      for (let attempt = 0; attempt <= CLIP_RETRIES; attempt += 1) {
        expect(t.events).not.toContain("error");
        firstT()[attempt].reject(Object.assign(new Error("Bad Gateway"), { reason: "service" }));
        await vi.advanceTimersByTimeAsync(attempt < CLIP_RETRIES ? CLIP_RETRY_DELAYS_MS[attempt] : 0);
      }
      expect(firstT()).toHaveLength(CLIP_RETRIES + 1);
      expect(firstT().map((r) => r.willRetry)).toEqual([...Array(CLIP_RETRIES).fill(true), false]);
      expect(t.events).toContain("error");
      expect(t.engine.paused).toBe(true);
      // bấm "Thử lại": được thử lại từ đầu
      t.engine.play();
      expect(firstT()).toHaveLength(CLIP_RETRIES + 2);
      expect(firstT().at(-1)!.willRetry).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("quỹ thời gian thử lại: lần hỏng đầu đã mất 16 giây (mạng còn nối mà im) thì không thử lại nữa - dừng ngay thay vì chờ cả phút", async () => {
    vi.useFakeTimers();
    try {
      const began = Date.now();
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      const first = () => s.requests.filter((r) => r.text === TEXTS[0]);
      // mốc truyền cho bộ lấy clip: sau mốc ấy lần thử lại không còn kịp (quỹ 20 giây - 5 giây - quãng nghỉ)
      expect(first()[0].retryBefore).toBe(clipRetryBefore(began, 0));
      expect(first()[0].retryBefore! - began).toBe(CLIP_RETRY_BUDGET_MS - CLIP_MIN_ATTEMPT_MS - CLIP_RETRY_DELAYS_MS[0]);
      await vi.advanceTimersByTimeAsync(16_000);
      first()[0].reject(Object.assign(new Error("Chậm quá"), { reason: "timeout" }));
      await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[0]);
      expect(first()).toHaveLength(1);
      expect(s.events).toContain("error");
      // lần hỏng nhanh thì vẫn được thử lại như trước
      const quick = setup();
      quick.engine.load(quick.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      const again = () => quick.requests.filter((r) => r.text === TEXTS[0]);
      again()[0].reject(Object.assign(new Error("Bad Gateway"), { reason: "service" }));
      await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[0]);
      expect(again()).toHaveLength(2);
      expect(quick.events).not.toContain("error");
    } finally {
      vi.useRealTimers();
    }
  });

  it("đoạn đọc sẵn hỏng thoáng qua lúc đang nghe đoạn trước: thử lại ở nền, âm thanh không ngắt, không dừng", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests.filter((r) => r.text === TEXTS[0]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      const second = () => s.requests.filter((r) => r.text === TEXTS[1]);
      second()[0].reject(Object.assign(new Error("Bad Gateway"), { reason: "service" }));
      await vi.advanceTimersByTimeAsync(0);
      expect(s.events).not.toContain("error");
      expect(audioOf(s, TEXTS[0])!.paused).toBe(false); // đoạn đầu vẫn đang nói
      await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[0]);
      expect(second()).toHaveLength(2);
      second()[1].resolve();
      await vi.advanceTimersByTimeAsync(0);
      audioOf(s, TEXTS[0])!.finish();
      expect(audioOf(s, TEXTS[1])!.plays).toBe(1);
      expect(s.events).not.toContain("error");
    } finally {
      vi.useRealTimers();
    }
  });

  /** Hỏng `CLIP_RETRIES + 1` lần liền (dịch vụ trục trặc) cho tới khi đoạn `text` hết lần thử lại. */
  async function exhaust(s: Setup, text: string) {
    const of = () => s.requests.filter((r) => r.text === text);
    for (let attempt = 0; attempt <= CLIP_RETRIES; attempt += 1) {
      of()[attempt].reject(Object.assign(new Error("Bad Gateway"), { reason: "service" }));
      await vi.advanceTimersByTimeAsync(attempt < CLIP_RETRIES ? CLIP_RETRY_DELAYS_MS[attempt] : 0);
    }
  }

  it("đoạn đọc sẵn hết lần thử lúc người nghe còn ở xa: không dừng; cứ ~10 giây hỏi thăm MỘT lượt (hỏi mới, không thử lại), được thì dùng luôn - người nghe tới nơi không bị dừng (a46)", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests.filter((r) => r.text === TEXTS[0]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      const second = () => s.requests.filter((r) => r.text === TEXTS[1]);
      await exhaust(s, TEXTS[1]);
      expect(second()).toHaveLength(CLIP_RETRIES + 1);
      expect(s.events).not.toContain("error"); // người nghe còn đang nói đoạn đầu
      expect(audioOf(s, TEXTS[0])!.paused).toBe(false);
      // mất mạng kéo dài: mỗi PROBE_MS đúng một lượt hỏi thăm cho đoạn gần nhất, lần hỏng nào cũng không thử lại
      for (let round = 1; round <= 3; round += 1) {
        await vi.advanceTimersByTimeAsync(PROBE_MS - 1);
        expect(second()).toHaveLength(CLIP_RETRIES + round);
        await vi.advanceTimersByTimeAsync(1);
        expect(second()).toHaveLength(CLIP_RETRIES + round + 1);
        const probe = second().at(-1)!;
        expect(probe.fresh).toBe(true);
        expect(probe.willRetry).toBe(false);
        probe.reject(Object.assign(new Error("Bad Gateway"), { reason: "service" }));
        await vi.advanceTimersByTimeAsync(0);
        expect(second()).toHaveLength(CLIP_RETRIES + round + 1); // hỏng thì chờ nhịp sau, không thử lại ngay
      }
      expect(s.events).not.toContain("error");
      // dịch vụ khoẻ lại: lượt hỏi thăm kế được, đoạn sẵn sàng trước khi người nghe tới
      await vi.advanceTimersByTimeAsync(PROBE_MS);
      second().at(-1)!.resolve();
      await vi.advanceTimersByTimeAsync(0);
      audioOf(s, TEXTS[0])!.finish();
      expect(audioOf(s, TEXTS[1])!.plays).toBe(1);
      expect(s.events).not.toContain("error");
    } finally {
      vi.useRealTimers();
    }
  });

  it("người nghe tới đoạn đã hết lần thử: hỏi MỚI một lần (quỹ thử lại tính lại, bộ lấy clip quên lệnh nghỉ) trước khi báo lỗi; được thì phát, hỏng hết quỹ mới dừng", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests.filter((r) => r.text === TEXTS[0]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      const second = () => s.requests.filter((r) => r.text === TEXTS[1]);
      await exhaust(s, TEXTS[1]);
      const asked = second().length;
      // đoạn đầu hết đúng lúc dịch vụ vừa khoẻ lại (trước nhịp hỏi thăm): lượt hỏi mới đi ngay khi người nghe tới
      audioOf(s, TEXTS[0])!.finish();
      await vi.advanceTimersByTimeAsync(0);
      expect(second()).toHaveLength(asked + 1);
      expect(second().at(-1)!.fresh).toBe(true);
      expect(second().at(-1)!.willRetry).toBe(true); // quỹ mới: lần này còn thử lại được
      expect(s.events).not.toContain("error");
      second().at(-1)!.resolve();
      await vi.advanceTimersByTimeAsync(0);
      expect(audioOf(s, TEXTS[1])!.plays).toBe(1);
      expect(s.engine.error).toBe("");

      // dịch vụ vẫn chết: lượt hỏi mới cũng hết quỹ thì mới dừng + báo
      const t = setup();
      t.engine.load(t.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      t.requests.filter((r) => r.text === TEXTS[0]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      await exhaust(t, TEXTS[1]);
      audioOf(t, TEXTS[0])!.finish();
      await vi.advanceTimersByTimeAsync(0);
      const again = () => t.requests.filter((r) => r.text === TEXTS[1]);
      expect(again().at(-1)!.fresh).toBe(true);
      for (let attempt = 0; attempt <= CLIP_RETRIES; attempt += 1) {
        expect(t.events).not.toContain("error");
        again().at(-1)!.reject(Object.assign(new Error("Bad Gateway"), { reason: "service" }));
        await vi.advanceTimersByTimeAsync(attempt < CLIP_RETRIES ? CLIP_RETRY_DELAYS_MS[attempt] : 0);
      }
      expect(t.events).toContain("error");
      expect(t.engine.paused).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("lỗi không phải của dịch vụ (mất mạng, từ chối) ở đoạn đọc sẵn: không hỏi thăm ngầm", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests.filter((r) => r.text === TEXTS[0]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      const second = () => s.requests.filter((r) => r.text === TEXTS[1]);
      second()[0].reject(Object.assign(new Error("Không có mạng"), { reason: "offline" }));
      await vi.advanceTimersByTimeAsync(PROBE_MS * 3);
      expect(second()).toHaveLength(1);
      expect(s.events).not.toContain("error");
      // người nghe tới đoạn ấy: vẫn được hỏi mới một lần trước khi báo (mạng có thể đã về)
      audioOf(s, TEXTS[0])!.finish();
      await vi.advanceTimersByTimeAsync(0);
      expect(second()).toHaveLength(2);
      expect(second()[1].fresh).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("một lượt clip THẬT (chậm hơn bộ đệm) thành công: đoạn đã bỏ cuộc được hỏi lại ngay, không đợi nhịp hỏi thăm", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests.filter((r) => r.text === TEXTS[0]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      const second = () => s.requests.filter((r) => r.text === TEXTS[1]);
      await exhaust(s, TEXTS[1]);
      const asked = second().length;
      // đoạn 3 về sau ~15 giây chờ (lượt gọi thật): dịch vụ khoẻ
      s.requests.filter((r) => r.text === TEXTS[2]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      expect(second()).toHaveLength(asked + 1);
      expect(second().at(-1)!.fresh).toBeUndefined(); // lượt thường, không phải hỏi thăm
      expect(second().at(-1)!.willRetry).toBe(true); // quỹ thử lại đầy
    } finally {
      vi.useRealTimers();
    }
  });

  it("lỗi không thoáng qua (mất mạng, bị từ chối, giọng hỏng, không rõ lý do): dừng ngay ở đoạn đang chờ, không thử lại", async () => {
    vi.useFakeTimers();
    try {
      for (const reason of ["offline", "rejected", "voice", "auth", "quota", "empty", undefined]) {
        const s = setup();
        s.engine.load(s.trackInfo, 0, true);
        await vi.advanceTimersByTimeAsync(0);
        s.requests[0].reject(Object.assign(new Error("hỏng"), { reason }));
        await vi.advanceTimersByTimeAsync(0);
        expect(s.events, String(reason)).toContain("error");
        expect(s.engine.paused).toBe(true);
        await vi.advanceTimersByTimeAsync(20_000);
        expect(s.requests.filter((r) => r.text === TEXTS[0]), String(reason)).toHaveLength(1);
      }
      // lời cuối của bộ lấy clip (đã thử hết giọng) cũng không bị thử lại thêm
      const t = setup();
      t.engine.load(t.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      t.requests[0].reject(Object.assign(new Error("Giọng Hoài My đang không dùng được."), { reason: "service", final: true }));
      await vi.advanceTimersByTimeAsync(20_000);
      expect(t.events).toContain("error");
      expect(t.requests.filter((r) => r.text === TEXTS[0])).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("lỗi đã báo mà dịch vụ trả lời lại (clip thật về): người nghe đã tự dừng (không còn gì để tự xin lại) thì bỏ lỗi và báo \"recovered\" để trình phát gỡ thông báo; clip từ bộ đệm (về tức thì) thì không", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests[0].reject(Object.assign(new Error("Giọng Hoài My đang không dùng được."), { reason: "service", final: true }));
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.error).toBe("Giọng Hoài My đang không dùng được.");
      // clip về tức thì (bộ đệm của máy chủ - về được cả khi Edge đang chết): lỗi còn nguyên
      s.requests.filter((r) => r.text === TEXTS[1]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.error).not.toBe("");
      expect(s.events).not.toContain("recovered");
      // clip qua dịch vụ thật (mất vài trăm ms) về: dịch vụ khoẻ lại
      s.engine.pause(); // người nghe tự dừng: lỗi gỡ đi thì ở yên dừng, không tự xin lại - lời báo gỡ ngay
      await vi.advanceTimersByTimeAsync(500);
      s.requests.filter((r) => r.text === TEXTS[2]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
      expect(s.events).toContain("recovered");
      expect(s.engine.error).toBe("");
    } finally {
      vi.useRealTimers();
    }
  });

  describe("tự phát tiếp khi lỗi gỡ đi (uxfix51)", () => {
    const stopped = async () => {
      vi.useFakeTimers();
      onTestFinished(() => void vi.useRealTimers());
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests[0].reject(Object.assign(new Error("Giọng Hoài My đang không dùng được."), { reason: "service", final: true }));
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.error).not.toBe("");
      expect(s.engine.paused).toBe(true);
      return s;
    };
    /** Một clip THẬT (qua dịch vụ, mất vài trăm ms) của đoạn đọc trước về. */
    const serviceAnswers = async (s: Setup) => {
      await vi.advanceTimersByTimeAsync(500);
      s.requests.filter((r) => r.text === TEXTS[1]).forEach((r) => r.resolve());
      await vi.advanceTimersByTimeAsync(0);
    };

    it("dừng VÌ lỗi: lỗi gỡ đi thì xin lại đoạn đang chờ và, clip về, tự phát tiếp - không chờ bấm phát", async () => {
      const s = await stopped();
      const before = s.requests.filter((r) => r.text === TEXTS[0]).length;
      await serviceAnswers(s);
      // sắp tự xin lại: lời báo đứng nguyên (không gỡ rồi dựng lại - a59d), gỡ khi lượt xin lại phát được
      expect(s.events).not.toContain("recovered");
      expect(s.engine.error).not.toBe("");
      expect(s.engine.paused).toBe(true); // clip chưa về: chưa phát
      const again = s.requests.filter((r) => r.text === TEXTS[0]);
      expect(again).toHaveLength(before + 1);
      expect(again.at(-1)!.rank).toBe(0);
      again.at(-1)!.resolve();
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.paused).toBe(false);
      expect(s.engine.error).toBe("");
      expect(s.events.slice(-1)[0]).not.toBe("error");
      expect(s.events.filter((e) => e === "play")).toHaveLength(2); // lần bấm đầu + lần tự phát tiếp
      expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
    });

    it("đoạn đang chờ đã có clip lúc lỗi gỡ (clip về trước cả lượt gỡ lỗi): phát luôn", async () => {
      const s = await stopped();
      // người nghe KHÔNG bấm gì; clip của đoạn đầu về qua một lượt xin khác (vd đổi giọng rồi đổi lại) - mô phỏng bằng cách để lượt xin lại về trước
      await serviceAnswers(s);
      s.requests.filter((r) => r.text === TEXTS[0]).at(-1)!.resolve();
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.paused).toBe(false);
    });

    it("người nghe tự dừng thì ở yên dừng: bấm dừng hay tua sau lỗi đều gỡ ý định tự phát, lỗi gỡ đi cũng không xin lại đoạn", async () => {
      for (const act of [(s: Setup) => s.engine.pause(), (s: Setup) => s.engine.seek(2.5)]) {
        const s = await stopped();
        act(s);
        const asked = s.requests.filter((r) => r.text === TEXTS[0]).length;
        await serviceAnswers(s);
        expect(s.events).toContain("recovered");
        expect(s.requests.filter((r) => r.text === TEXTS[0])).toHaveLength(asked);
        expect(s.engine.paused).toBe(true);
        vi.useRealTimers();
      }
    });

    it("đoạn xin lại sau khi gỡ lỗi mà hỏng nữa: báo lỗi lại (không để lỗi gỡ mất mà vẫn dừng không dấu hiệu), clip thật về sau lại thử tiếp", async () => {
      const s = await stopped();
      await serviceAnswers(s);
      s.requests.filter((r) => r.text === TEXTS[0]).at(-1)!.reject(Object.assign(new Error("Đoạn này không đọc được."), { reason: "empty" }));
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.error).toBe("Đoạn này không đọc được.");
      expect(s.engine.paused).toBe(true);
      expect(s.events.slice(-1)[0]).toBe("error");
    });

    it("hỏng kép cùng một chỗ (a59d): lượt tự xin lại hỏng nữa thì lời báo đang có được cập nhật - đúng MỘT lời báo, không gỡ rồi dựng lại", async () => {
      const s = await stopped();
      const shown: string[] = []; // chuỗi lời báo như trình phát thấy (setError ở mỗi sự kiện)
      let alerts = 0; // số lần lời báo hiện lên từ trống
      const sync = () => {
        const now = s.engine.error;
        if (now && !shown.at(-1)) alerts += 1;
        shown.push(now);
      };
      s.engine.on("error", sync);
      s.engine.on("recovered", () => shown.push(""));
      s.engine.on("play", () => shown.push(s.engine.error));
      shown.push(s.engine.error);
      alerts = 1; // lời báo đầu (từ lúc dừng)
      await serviceAnswers(s); // lookahead thật về: dịch vụ "khoẻ lại" -> tự xin lại đoạn đang chờ
      s.requests.filter((r) => r.text === TEXTS[0]).at(-1)!.reject(Object.assign(new Error("Giọng Hoài My đang không dùng được."), { reason: "service", final: true }));
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.error).toBe("Giọng Hoài My đang không dùng được.");
      expect(s.engine.paused).toBe(true);
      expect(alerts).toBe(1);
      expect(shown.every(Boolean)).toBe(true); // không có lúc nào lời báo bị gỡ giữa hai lần hỏng
      expect(s.events).not.toContain("recovered");
    });

    it("bấm phát sau lỗi vẫn thử lại như cũ và gỡ ý định tự phát (không phát đôi)", async () => {
      const s = await stopped();
      s.engine.play();
      await vi.advanceTimersByTimeAsync(0);
      s.requests.filter((r) => r.text === TEXTS[0]).at(-1)!.resolve();
      await vi.advanceTimersByTimeAsync(0);
      expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
      await serviceAnswers(s);
      expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
    });
  });

  it("phân loại lỗi thoáng qua theo lý do máy chủ thật sự trả (abook/readaloud/edge.py: cắt lượt / 429 / 5xx -> service, chậm -> timeout)", () => {
    expect(isTransientClipError({ reason: "service" })).toBe(true);
    expect(isTransientClipError({ reason: "timeout" })).toBe(true);
    for (const reason of ["offline", "rejected", "voice", "empty", "auth", "quota", "uncached", ""]) expect(isTransientClipError({ reason })).toBe(false);
    expect(isTransientClipError(new Error("không lý do"))).toBe(false);
    expect(isTransientClipError({ reason: "service", final: true })).toBe(false);
    expect(isTransientClipError(null)).toBe(false);
  });

  it("lấy clip lỗi: dừng, báo error với lý do; bấm phát lại thì thử lại", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    s.requests[0].reject(Object.assign(new Error("Không có mạng để dùng giọng trực tuyến."), { reason: "offline" }));
    await flush();
    expect(s.events).toContain("error");
    expect(s.events.at(-2)).toBe("pause");
    expect(s.engine.error).toBe("Không có mạng để dùng giọng trực tuyến.");
    expect(s.engine.paused).toBe(true);
    const before = s.requests.length;
    s.engine.play();
    expect(s.requests.length).toBeGreaterThan(before);
    await s.arrive(TEXTS[0]);
    expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
    expect(s.engine.error).toBe("");
  });

  it("đổi giọng giữa chừng: đoạn đang đọc nói nốt, từ đoạn sau lấy clip mới", async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await s.arrive(text);
    const requested = s.requests.length;
    (s.engine as unknown as { voiceChanged(): void }).voiceChanged();
    await flush();
    expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
    expect(audioOf(s, TEXTS[1])!.released).toBe(true);
    expect(s.requests.length).toBe(requested + 2); // đoạn 2 và 3 được xin lại (đoạn 4 chưa từng xin)
    expect(s.published.at(-1)!.segments[1].words).toBeUndefined();
  });
});

describe("mất mạng giữa chừng với bộ lấy clip thật (soát a46)", () => {
  /** Chương 8 đoạn, mỗi đoạn người nghe nghe 12 giây (hết đoạn k ở giây 12 x (k + 1)). Edge chết từ giây 1 tới `recoverAt` (không bao giờ nếu null); chạy tới giây `until`. */
  async function outage(recoverAt: number | null, until: number) {
    vi.useFakeTimers();
    const paragraphs = Array.from({ length: 8 }, (_, i) => `Đoạn ${i + 1} ${Array(22).fill("từ").join(" ")}.`);
    const store = new Map<string, string>();
    const globals = globalThis as unknown as { window?: EventTarget; localStorage?: Storage };
    const saved = { window: globals.window, localStorage: globals.localStorage };
    globals.window = new EventTarget();
    globals.localStorage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) } as Storage;
    onTestFinished(() => {
      vi.useRealTimers();
      globals.window = saved.window;
      globals.localStorage = saved.localStorage;
    });
    vi.resetModules();
    const voice = await import("./readAloudVoice");
    const { ReadAloudError } = await import("./readAloud");
    const t0 = Date.now();
    const elapsed = () => (Date.now() - t0) / 1000;
    const asked: { text: string; at: number; ok: boolean }[] = [];
    const source = {
      readAloudVoices: async () => [{ id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My", provider: "edge", online: true, default: true }],
      readAloudClip: async (_voice: string, text: string) => {
        const dead = elapsed() >= 1 && (recoverAt === null || elapsed() < recoverAt);
        asked.push({ text, at: elapsed(), ok: !dead });
        if (dead) throw new ReadAloudError("Dịch vụ bận", "service");
        return clipOf(text);
      },
    };
    const s = setup({ chapter: paragraphs.join("\n\n") });
    s.track.fetchClip = voice.speechFetcher(source as never, "b1", vi.fn());
    s.engine.load(s.trackInfo, 0, true);
    const at = (seconds: number) => vi.advanceTimersByTimeAsync(Math.max(0, seconds * 1000 - (Date.now() - t0)));
    for (let end = 12, k = 0; end <= until; end += 12, k += 1) {
      await at(end);
      audioOf(s, paragraphs[k])?.finish();
      await at(end + 0.001);
    }
    await at(until);
    return { s, asked, paragraphs, forText: (text: string) => asked.filter((entry) => entry.text === text) };
  }

  it("Edge chết 28 giây (đoạn xa hết lần thử lúc ~27 giây) rồi sống lại: lượt hỏi thăm lấy đoạn trước khi người nghe tới (giây 48), không dừng", async () => {
    const { s, paragraphs, forText, asked } = await outage(28, 48.5);
    expect(s.events).not.toContain("error");
    expect(s.engine.paused).toBe(false);
    expect(audioOf(s, paragraphs[4])!.plays).toBe(1); // đoạn 5 đang phát lúc 48 giây
    const fifth = forText(paragraphs[4]);
    expect(fifth.some((entry) => entry.at >= 28 && entry.ok)).toBe(true);
    expect(fifth.find((entry) => entry.at >= 28)!.at).toBeLessThan(40); // nhịp hỏi thăm ~10 giây sau khi hết lần thử, không đợi tới lúc người nghe tới
    // số lượt gọi trong cả 48 giây có mất mạng 27 giây: thấp (a46 đo 13 lượt cho 74 giây không hỏi thăm)
    expect(asked.filter((entry) => !entry.ok).length).toBeLessThanOrEqual(12);
  });

  it("Edge sống lại sau nhịp hỏi thăm cuối nhưng trước lúc người nghe tới: người nghe tới nơi thì hỏi mới ngay, không dừng", async () => {
    const { s, paragraphs, forText } = await outage(47.5, 48.5);
    expect(s.events).not.toContain("error");
    expect(s.engine.paused).toBe(false);
    expect(audioOf(s, paragraphs[4])!.plays).toBe(1);
    const fifth = forText(paragraphs[4]);
    expect(fifth.at(-1)).toMatchObject({ ok: true });
    expect(fifth.at(-1)!.at).toBeGreaterThanOrEqual(47.5);
    expect(fifth.at(-1)!.at).toBeLessThan(49);
  });

  it("Edge chết suốt: tới nơi hỏi mới một lượt với quỹ thử lại đầy rồi mới dừng + báo; số lượt gọi vẫn thấp", async () => {
    const { s, asked } = await outage(null, 70);
    expect(s.events).toContain("error");
    expect(s.engine.paused).toBe(true);
    // 70 giây mất mạng liên tục, 4 đoạn trong cửa sổ: trần 40 lượt (không bão); ghi số thật ở báo cáo
    expect(asked.length).toBeLessThanOrEqual(40);
  });
});

describe("độ sâu đọc trước theo tốc độ giọng trực tuyến", () => {
  it("chưa đủ số đo hay clip về nhanh: đúng số đoạn tối thiểu; clip về chậm hơn thời gian nghe: dài ra tới trần; nhanh lại: co về", () => {
    const shortClips = Array(10).fill(1.5); // đoạn đối thoại ngắn: 1,5 giây mỗi đoạn
    expect(readAheadCount(3, [], shortClips)).toBe(3);
    expect(readAheadCount(3, [20], shortClips)).toBe(3); // một số đo chưa đủ
    expect(readAheadCount(3, [0.8, 1.1, 0.9, 1.2], shortClips)).toBe(8); // Edge nhanh nhưng đoạn ngắn: 20 s đệm tối thiểu cần hơn 8 đoạn -> trần
    expect(readAheadCount(3, [0.8, 1.1, 0.9, 1.2], Array(10).fill(12))).toBe(3); // đoạn dài: 2 đoạn đã đủ 20 s, giữ tối thiểu 3
    expect(readAheadCount(3, [20, 22, 9, 1, 1, 1, 1, 1], shortClips)).toBe(8); // p80 = 20 s -> cần 40 s đệm, đoạn ngắn nên chạm trần 8
    const longClips = Array(10).fill(12); // đoạn văn xuôi: 12 giây mỗi đoạn
    expect(readAheadCount(3, [9, 10, 11, 9, 10], longClips)).toBe(3); // cần 22 s, 3 đoạn đã có 36 s
    expect(readAheadCount(3, [20, 24, 18, 22, 19], longClips)).toBe(4); // cần 48 s: 4 đoạn
    // trần thời gian đệm: không đòi hơn 60 giây âm thanh dù Edge chậm tới đâu
    expect(readAheadCount(3, [100, 100, 100], Array(10).fill(10))).toBe(6);
    // hết chương: không đòi đoạn không có
    expect(readAheadCount(3, [20, 20], [1, 1])).toBe(3);
    // số đo chậm cũ trôi khỏi cửa sổ khi clip về nhanh trở lại: độ sâu co về tối thiểu
    expect(readAheadCount(3, [20, 22, 24, 21, 23, 22, 20, 21], shortClips)).toBe(8);
    expect(readAheadCount(3, [1, 1, 1, 1, 1, 1, 1, 1], Array(10).fill(12))).toBe(3);
  });

  it("bộ máy: clip về chậm thì đọc trước nhiều đoạn hơn (số lượt gọi cùng lúc vẫn như cũ), về nhanh lại thì co", async () => {
    vi.useFakeTimers({ toFake: ["Date"] }); // chỉ đồng hồ Date: để dời giờ giữa lúc gửi và lúc về mà vẫn dùng flush()
    try {
      // văn xuôi: 24 chữ mỗi đoạn = 12 s âm thanh khi clip về
      const chapter = Array.from({ length: 24 }, (_, i) => `Đoạn ${i + 1} ${Array(22).fill("từ").join(" ")}.`).join("\n\n");
      const s = setup({ chapter });
      const t0 = Date.now();
      s.engine.load(s.trackInfo, 0, true);
      await flush();
      expect(s.requests).toHaveLength(4); // đoạn đang nghe + 3 đoạn sau
      expect(s.engine.lookahead).toBe(3);
      // bốn clip đầu mỗi cái mất 20 giây
      vi.setSystemTime(t0 + 20_000);
      for (const request of s.requests.slice()) request.resolve();
      await flush();
      expect(s.engine.lookahead).toBe(4); // cần 40 s đệm (2 x 20 s): 3 đoạn = 36 s chưa đủ
      // cửa sổ dài ra: đoạn xa hơn đã được xin; số lượt đang chạy cùng lúc không quá 4 (như trước)
      const done = new Set(s.requests.slice(0, 4));
      const pending = () => s.requests.filter((r) => !done.has(r));
      expect(pending().length).toBeGreaterThan(0);
      expect(pending().length).toBeLessThanOrEqual(4);
      // các clip sau về nhanh (1 giây mỗi cái) và người nghe đi tiếp: số đo chậm trôi khỏi cửa sổ 8 mẫu
      for (let round = 0; round < 14; round += 1) {
        vi.setSystemTime(Date.now() + 1000);
        for (const request of pending()) {
          request.resolve();
          done.add(request);
        }
        await flush();
        expect(pending().length).toBeLessThanOrEqual(4);
        s.audios.find((audio) => !audio.paused)?.finish();
        await flush();
      }
      expect(s.engine.lookahead).toBe(3);
    } finally {
      vi.useRealTimers();
    }
  });

  it("đoạn ngắn (đối thoại): giọng trực tuyến đọc sẵn đủ ~20 giây âm thanh chứ không chỉ 3 đoạn; bộ đệm (clip về tức thì) thì không đổi", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      const chapter = Array.from({ length: 24 }, (_, i) => `Câu số ${i + 1} đây.`).join("\n\n");
      const cached = setup({ chapter });
      cached.engine.load(cached.trackInfo, 0, true);
      await flush();
      for (const request of cached.requests.slice()) request.resolve(); // 0 ms: lấy từ bộ đệm của máy chủ
      await flush();
      expect(cached.engine.lookahead).toBe(3);
      const t0 = Date.now();
      const s = setup({ chapter });
      s.engine.load(s.trackInfo, 0, true);
      await flush();
      vi.setSystemTime(t0 + 1000); // Edge nhanh nhưng thật: 1 giây mỗi clip
      for (const request of s.requests.slice()) request.resolve();
      await flush();
      expect(s.engine.lookahead).toBe(8); // 1,5 s mỗi đoạn: 20 s cần hơn 8 đoạn -> chạm trần
    } finally {
      vi.useRealTimers();
    }
  });

  it("lượt gọi chờ lâu chưa về cũng là số đo: cửa sổ dài ra ngay khi quãng chậm bắt đầu, không đợi clip chậm về xong", async () => {
    vi.useFakeTimers();
    try {
      const chapter = Array.from({ length: 24 }, (_, i) => `Đoạn ${i + 1} ${Array(22).fill("từ").join(" ")}.`).join("\n\n");
      const s = setup({ chapter });
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.lookahead).toBe(3);
      await vi.advanceTimersByTimeAsync(2000);
      expect(s.engine.lookahead).toBe(3); // mới chờ 2 giây: chưa nói lên gì
      await vi.advanceTimersByTimeAsync(10_000); // bốn lượt gọi đã chờ 12 s mà chưa clip nào về: cần 24 s đệm = 3 đoạn ước (10 s) -> 3; đoạn dài hơn thì nhiều hơn
      expect(s.engine.lookahead).toBeGreaterThanOrEqual(3);
      await vi.advanceTimersByTimeAsync(20_000); // đã chờ 32 s: cần 60 s đệm (trần)
      expect(s.engine.lookahead).toBeGreaterThanOrEqual(6);
    } finally {
      vi.useRealTimers();
    }
  });

  it("giọng chạy trên máy (serial): không đổi, dù đo được chậm", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      const chapter = Array.from({ length: 12 }, (_, i) => `Câu số ${i + 1} đây.`).join("\n\n");
      const s = setup({ chapter });
      (s.track as { serial?: () => boolean }).serial = () => true;
      const t0 = Date.now();
      s.engine.load(s.trackInfo, 0, true);
      await flush();
      vi.setSystemTime(t0 + 30_000);
      s.requests[0].resolve();
      await flush();
      vi.setSystemTime(t0 + 60_000);
      s.requests[1]?.resolve();
      await flush();
      expect(s.engine.lookahead).toBe(3);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("cách đọc riêng vừa đổi ('Đọc từ này là…')", () => {
  const changed = (s: Setup, surfaces: string[], bookId = "b1", all = false) =>
    (s.engine as unknown as { readingsChanged(detail: { bookId: string; surfaces: string[]; all?: boolean }): void }).readingsChanged({ bookId, surfaces, all });

  it("xoá bản đọc đã làm của cuốn (all): mọi đoạn đã đọc sẵn bị bỏ clip, đoạn đang nói nói nốt", async () => {
    const s = setup();
    s.track.bookId = "b1";
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await s.arrive(text);
    const requested = s.requests.length;
    changed(s, [], "b2", true); // cuốn khác: không đụng
    expect(audioOf(s, TEXTS[1])!.released).toBe(false);
    changed(s, [], "b1", true);
    await flush();
    expect(audioOf(s, TEXTS[0])!.released).toBe(false);
    expect(audioOf(s, TEXTS[1])!.released).toBe(true);
    expect(audioOf(s, TEXTS[2])!.released).toBe(true);
    const again = s.requests.slice(requested).map((request) => request.text);
    expect(again).toEqual(expect.arrayContaining([TEXTS[1], TEXTS[2]])); // xin lại để lần phát sau có clip mới
  });

  it("đoạn đã đọc sẵn có từ ấy bị bỏ clip và xin lại; đoạn không có từ ấy giữ nguyên; đoạn đang nói nói nốt", async () => {
    const s = setup();
    s.track.bookId = "b1";
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await s.arrive(text);
    const requested = s.requests.length;
    changed(s, ["năm"]); // đoạn 2 ("Ba bốn năm sáu.") đã đọc sẵn, chưa tới
    await flush();
    expect(audioOf(s, TEXTS[0])!.released).toBe(false);
    expect(audioOf(s, TEXTS[2])!.released).toBe(false);
    expect(audioOf(s, TEXTS[1])!.released).toBe(true);
    expect(s.requests.length).toBe(requested + 1);
    expect(s.requests.at(-1)!.text).toBe(TEXTS[1]);
    expect(s.published.at(-1)!.segments[1].words).toBeUndefined();
    // đoạn đang nói (đoạn 1) có từ ấy: không cắt ngang
    changed(s, ["hai"]);
    expect(audioOf(s, TEXTS[0])!.released).toBe(false);
    expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
  });

  it("nghe lại đúng đoạn đang nói (đã đổi cách đọc) thì xin clip mới thay vì phát lại clip cũ", async () => {
    const s = setup();
    s.track.bookId = "b1";
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await s.arrive(TEXTS[0]);
    const requested = s.requests.length;
    changed(s, ["hai"]);
    expect(s.requests.length).toBe(requested); // chưa xin: đoạn còn đang nói
    s.engine.seekWord(0, 0); // người nghe bấm lại đoạn ấy
    await flush();
    expect(s.requests.length).toBe(requested + 1);
    expect(s.requests.at(-1)!.text).toBe(TEXTS[0]);
  });

  it("clip về từ lượt hỏi cũ (trước khi đổi) bị bỏ, clip của lượt hỏi mới được dùng", async () => {
    const s = setup();
    s.track.bookId = "b1";
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    const first = s.requests.filter((r) => r.text === TEXTS[1]);
    expect(first.length).toBe(1); // đoạn 2 đang được đọc trước
    changed(s, ["năm"]);
    first[0].resolve(); // lượt cũ về sau khi đổi
    await flush();
    expect(audioOf(s, TEXTS[1])).toBeUndefined(); // không dựng audio từ clip theo cách đọc cũ
    expect(s.requests.filter((r) => r.text === TEXTS[1]).length).toBe(2); // đã xin lại
  });

  it("cuốn khác, hay chưa nạp xong, thì không làm gì", async () => {
    const s = setup();
    s.track.bookId = "b1";
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await s.arrive(text);
    const requested = s.requests.length;
    changed(s, ["năm"], "khác");
    await flush();
    expect(s.requests.length).toBe(requested);
    expect(audioOf(s, TEXTS[1])!.released).toBe(false);
  });
});

describe("clip người nghe đang chờ đi trước clip đọc trước (uxfix51)", () => {
  const LONG = Array.from({ length: 14 }, (_, n) => `Đoạn số ${n} ${"nói mãi không dứt ".repeat(8)}`.trim()); // >= WHOLE_CHARS: đoạn dài
  const chapter = LONG.join("\n\n");

  it("mỗi lượt xin mang rank = số đoạn dài người nghe phải nghe trước nó: đoạn đang chờ 0, đoạn kế 1, 2, 3", async () => {
    const s = setup({ chapter });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    expect(s.requests.map((r) => [r.text, r.rank])).toEqual([[LONG[0], 0], [LONG[1], 1], [LONG[2], 2], [LONG[3], 3]]);
  });

  it("nhảy tới đoạn xa: đoạn vừa nhảy tới mang rank 0 và đi ngay, kể cả khi cửa sổ cũ còn đủ lượt đang chạy", async () => {
    const s = setup({ chapter });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    s.engine.seekWord(9, 0);
    await flush();
    const jumped = s.requests.filter((r) => r.text === LONG[9]);
    expect(jumped).toHaveLength(1);
    expect(jumped[0].rank).toBe(0);
    expect(s.requests.filter((r) => r.rank === 0).map((r) => r.text)).toEqual([LONG[0], LONG[9]]);
  });

  it("tiêu đề ngắn đứng trước không tính (a56): tiêu đề và đoạn dài đầu cùng rank 0, các đoạn sau 1, 2", async () => {
    const heading = "Chương 8.";
    const s = setup({ chapter: [heading, ...LONG.slice(0, 5)].join("\n\n") });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    expect(s.requests.map((r) => [r.text, r.rank])).toEqual([[heading, 0], [LONG[0], 0], [LONG[1], 1], [LONG[2], 2]]);
  });

  it("đoạn ngắn xen giữa không tính, đoạn dài vẫn tính: dài, ngắn, dài, ngắn -> 0, 1, 1, 2", async () => {
    const parts = [LONG[0], "Ừ.", LONG[1], "Vâng ạ.", LONG[2]];
    const s = setup({ chapter: parts.join("\n\n") });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    expect(s.requests.map((r) => r.rank)).toEqual([0, 1, 1, 2]);
  });

  it("ranking đoạn dài: đúng ngưỡng WHOLE_CHARS", () => {
    expect(isLongParagraph("a".repeat(WHOLE_CHARS - 1))).toBe(false);
    expect(isLongParagraph("a".repeat(WHOLE_CHARS))).toBe(true);
  });
});

describe("nhảy tới câu xa: lượt xin cũ không chặn câu vừa nhảy tới", () => {
  const LONG = Array.from({ length: 14 }, (_, n) => `Đoạn số ${n} nói.`);
  const chapter = LONG.join("\n\n");
  const asked = (s: Setup) => s.requests.map((request) => request.text);

  it("giọng chạy trên máy: xin lần lượt, câu đang chờ trước; cách cũ (trực tuyến) xin cả cửa sổ cùng lúc", async () => {
    const online = setup({ chapter });
    online.engine.load(online.trackInfo, 0, true);
    await flush();
    expect(asked(online)).toEqual(LONG.slice(0, 4));

    const local = setup({ chapter });
    local.track.serial = () => true;
    local.engine.load(local.trackInfo, 0, true);
    await flush();
    expect(asked(local)).toEqual([LONG[0]]);
    await local.arrive(LONG[0]);
    expect(asked(local)).toEqual([LONG[0], LONG[1]]);
  });

  it("nhảy: các lượt chưa gửi của cửa sổ cũ bị bỏ, câu vừa nhảy tới đi ngay sau lượt đang chạy", async () => {
    vi.useFakeTimers({ toFake: ["Date"] }); // chỉ đồng hồ Date: để dời giờ giữa hai lần nhảy mà vẫn dùng flush()
    onTestFinished(() => void vi.useRealTimers());
    const s = setup({ chapter });
    s.track.serial = () => true;
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    expect(asked(s)).toEqual([LONG[0]]); // 1, 2, 3 đang xếp hàng
    s.engine.seekWord(9, 0); // nhảy xa trong lúc đoạn 0 còn đang được làm
    await flush();
    expect(asked(s)).toEqual([LONG[0]]); // đoạn 0 chiếm chỗ duy nhất, chưa gửi thêm gì
    await s.arrive(LONG[0]);
    expect(asked(s)).toEqual([LONG[0], LONG[9]]); // không phải đoạn 1 của cửa sổ cũ
    await s.arrive(LONG[9]);
    expect(asked(s)).toEqual([LONG[0], LONG[9], LONG[10]]);
    // nhảy về chỗ cũ (sau một quãng, không phải nhảy dồn): đoạn 0 đã có clip, đoạn 1 (đã bỏ khỏi hàng) được xin lại như mới
    await new Promise((resolve) => setTimeout(resolve, 20));
    vi.setSystemTime(Date.now() + 5000);
    s.engine.seekWord(0, 0);
    await s.arrive(LONG[10]);
    expect(asked(s)).toContain(LONG[1]);
  });

  it("nhảy dồn (giọng trên máy): chỉ lượt đầu đi ngay, các lần nhảy sau chờ người nghe ngừng nhảy rồi mới xin đích cuối", async () => {
    vi.useFakeTimers();
    try {
      const s = setup({ chapter });
      s.track.serial = () => true;
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      expect(asked(s)).toEqual([LONG[0]]);
      s.engine.seekWord(3, 0); // lần nhảy đầu: đi ngay (lượt đang chạy là đoạn 0)
      await vi.advanceTimersByTimeAsync(700);
      s.engine.seekWord(6, 0); // nhảy dồn
      await vi.advanceTimersByTimeAsync(700);
      s.engine.seekWord(9, 0);
      s.requests[0].resolve(); // đoạn 0 xong trong lúc còn đang nhảy: không được gửi đoạn của lần nhảy trước
      await vi.advanceTimersByTimeAsync(300);
      expect(asked(s)).toEqual([LONG[0]]);
      await vi.advanceTimersByTimeAsync(600); // ngừng nhảy đủ lâu
      expect(asked(s)).toEqual([LONG[0], LONG[9]]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("nhảy dồn nhưng giọng trên máy làm clip nhanh (dưới 1 giây): không giữ lượt xin, đích cuối đi ngay khi có chỗ", async () => {
    vi.useFakeTimers();
    try {
      const s = setup({ chapter });
      s.track.serial = () => true;
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(300);
      s.requests[0].resolve(); // clip đầu xong sau 0,3 giây: giọng nhanh
      await vi.advanceTimersByTimeAsync(0);
      s.engine.seekWord(5, 0);
      await vi.advanceTimersByTimeAsync(400);
      s.engine.seekWord(8, 0); // nhảy dồn
      s.requests[1].resolve(); // lượt đang chạy xong (mới 0,4 giây)
      await vi.advanceTimersByTimeAsync(50);
      expect(asked(s)).toContain(LONG[8]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("giọng trực tuyến: nhảy dồn không bị giữ lại", async () => {
    vi.useFakeTimers();
    try {
      const s = setup({ chapter });
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      s.requests.forEach((r) => r.resolve()); // chỗ trống cho lượt mới
      await vi.advanceTimersByTimeAsync(0);
      s.engine.seekWord(8, 0);
      await vi.advanceTimersByTimeAsync(50);
      s.engine.seekWord(11, 0);
      await vi.advanceTimersByTimeAsync(50);
      expect(asked(s)).toContain(LONG[11]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("nhảy sang đoạn kế (còn trong cửa sổ): lượt đã xếp hàng được giữ", async () => {
    const s = setup({ chapter });
    s.track.serial = () => true;
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    s.engine.seekWord(2, 0);
    await s.arrive(LONG[0]);
    expect(asked(s).slice(0, 2)).toEqual([LONG[0], LONG[2]]);
  });
});

describe("dòng ngăn cảnh: quãng lặng 1,5 giây", () => {
  const CHAPTER_WITH_BREAK = "Một hai.\n\n* * *\n\nBa bốn.";

  /** Nạp chương có dòng ngăn cảnh, đủ clip, đang nghe đoạn đầu (1 s), đồng hồ giả. */
  async function playing(chapter = CHAPTER_WITH_BREAK) {
    const s = setup({ chapter });
    s.engine.load(s.trackInfo, 0, true);
    await vi.advanceTimersByTimeAsync(0);
    s.requests.forEach((r) => r.resolve());
    await vi.advanceTimersByTimeAsync(0);
    return s;
  }

  it("is an item of 1.5 s with no clip and no voice request, between the two clips", async () => {
    vi.useFakeTimers();
    try {
      const s = await playing();
      expect(s.requests.map((r) => r.text)).toEqual(["Một hai.", "Ba bốn."]);
      expect(s.engine.duration).toBeCloseTo(1 + 1.5 + 1, 6);
      const script = s.published.at(-1)!;
      expect(script.segments.map((segment) => [segment.text, segment.start, segment.end])).toEqual([
        ["Một hai.", 0, 1],
        ["* * *", 1, 2.5],
        ["Ba bốn.", 2.5, 3.5],
      ]);
      expect(script.segments[1].words).toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });

  it("stays silent for 1.5 s, then plays the next paragraph; the clock runs through it", async () => {
    vi.useFakeTimers();
    try {
      const s = await playing();
      audioOf(s, "Một hai.")!.finish();
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(0);
      expect(s.engine.paused).toBe(false);
      expect(s.engine.time).toBeCloseTo(1, 6);
      await vi.advanceTimersByTimeAsync(700);
      expect(s.engine.time).toBeCloseTo(1.7, 1);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(0);
      await vi.advanceTimersByTimeAsync(900);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(1);
      expect(s.engine.time).toBeCloseTo(2.5, 1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps its place when paused in the silence and finishes the rest of it on play", async () => {
    vi.useFakeTimers();
    try {
      const s = await playing();
      audioOf(s, "Một hai.")!.finish();
      await vi.advanceTimersByTimeAsync(1000);
      s.engine.pause();
      const at = s.engine.time;
      expect(at).toBeCloseTo(2, 1);
      await vi.advanceTimersByTimeAsync(10_000);
      expect(s.engine.time).toBe(at);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(0);
      s.engine.play();
      await vi.advanceTimersByTimeAsync(300);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(0);
      await vi.advanceTimersByTimeAsync(300);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("runs faster at a faster listening rate, like every other paragraph", async () => {
    vi.useFakeTimers();
    try {
      const s = await playing();
      s.engine.setRate(2);
      audioOf(s, "Một hai.")!.finish();
      await vi.advanceTimersByTimeAsync(700);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(0);
      await vi.advanceTimersByTimeAsync(100);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("seeking into it, or past it, stops the silence and plays from there", async () => {
    vi.useFakeTimers();
    try {
      const s = await playing();
      audioOf(s, "Một hai.")!.finish();
      await vi.advanceTimersByTimeAsync(500);
      s.engine.seek(3);
      await vi.advanceTimersByTimeAsync(0);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(1);
      expect(audioOf(s, "Ba bốn.")!.currentTime).toBeCloseTo(0.5, 6);
      await vi.advanceTimersByTimeAsync(5000);
      expect(s.events.filter((name) => name === "ended")).toHaveLength(0);
      s.engine.seek(1.75); // lặng ở nửa chừng
      await vi.advanceTimersByTimeAsync(0);
      expect(s.engine.time).toBeCloseTo(1.75, 1);
      await vi.advanceTimersByTimeAsync(1000);
      expect(audioOf(s, "Ba bốn.")!.plays).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("is not played at the start or end of the chapter, nor twice for repeated lines", async () => {
    vi.useFakeTimers();
    try {
      const s = await playing("***\n\nMột hai.\n\n***");
      expect(s.requests.map((r) => r.text)).toEqual(["Một hai."]);
      expect(s.engine.duration).toBeCloseTo(1, 6);
      audioOf(s, "Một hai.")!.finish();
      expect(s.engine.ended).toBe(true);
      const t = await playing("Một hai.\n\n***\n\n***\n\nBa bốn.");
      expect(t.engine.duration).toBeCloseTo(3.5, 6);
      // một dấu "*" đứng riêng một đoạn cũng là ngăn cảnh; "—" một mình (lời thoại im lặng) thì không
      const lone = await playing("Một hai.\n\n*\n\nBa bốn.");
      expect(lone.engine.duration).toBeCloseTo(3.5, 6);
      const dash = await playing("Một hai.\n\n—\n\nBa bốn.");
      expect(dash.engine.duration).toBeCloseTo(2, 6);
    } finally {
      vi.useRealTimers();
    }
  });
});

class FakeWeb implements AudioEngine {
  time = 0;
  duration = 0;
  paused = true;
  ended = false;
  loads: string[] = [];
  stopped = 0;
  private handlers = new Map<EngineEvent, Set<() => void>>();
  load(track: TrackInfo) {
    this.loads.push(track.url);
  }
  play() {}
  pause() {}
  seek() {}
  setRate() {}
  setVolume() {}
  stop() {
    this.stopped += 1;
    this.fire("pause");
  }
  on(event: EngineEvent, handler: () => void) {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler);
    return () => this.handlers.get(event)!.delete(handler);
  }
  fire(event: EngineEvent) {
    this.handlers.get(event)?.forEach((handler) => handler());
  }
}

describe("RoutedEngine", () => {
  it("chương có audio đi qua bộ máy web, chương chỉ-có-chữ đi qua đọc to, và bộ cũ dừng im lặng", async () => {
    const web = new FakeWeb();
    const s = setup();
    const router = new RoutedEngine(web, () => s.engine);
    const seen: string[] = [];
    router.on("pause", () => seen.push("pause"));
    router.on("play", () => seen.push("play"));
    router.load({ url: "/a.mp3", title: "", album: "", artist: "" }, 5, true);
    expect(web.loads).toEqual(["/a.mp3"]);
    web.fire("pause");
    expect(seen).toEqual(["pause"]);
    seen.length = 0;
    router.setRate(1.25);
    router.load(s.trackInfo, 0, true);
    expect(web.stopped).toBe(1);
    expect(seen).toEqual(["play"]); // "pause" của web.stop() không lọt tới trình phát
    await flush();
    await s.arrive(TEXTS[0]);
    expect(audioOf(s, TEXTS[0])!.playbackRate).toBe(1.25);
    expect(router.speaking).toBe(true);
    router.seekWord(0, 1);
    expect(audioOf(s, TEXTS[0])!.currentTime).toBeCloseTo(0.5, 6);
    web.fire("pause"); // bộ máy web không còn là bộ đang chạy
    expect(seen).toEqual(["play"]);
    router.load({ url: "/b.mp3", title: "", album: "", artist: "" }, 0, true);
    expect(web.loads).toEqual(["/a.mp3", "/b.mp3"]);
    expect(router.speaking).toBe(false);
  });
});

/** jsdom không có URL.createObjectURL: đồ giả đếm blob: URL đã cấp / đã thu hồi. */
function blobUrls() {
  const made: string[] = [];
  const revoked: string[] = [];
  const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
  URL.createObjectURL = () => {
    made.push(`blob:abook/${made.length + 1}`);
    return made.at(-1)!;
  };
  URL.revokeObjectURL = (url: string) => void revoked.push(url);
  onTestFinished(() => {
    URL.createObjectURL = original.create;
    URL.revokeObjectURL = original.revoke;
  });
  return { made, revoked };
}

const withBytes = (text: string): ReadAloudClip => ({ ...clipOf(text), bytes: new Blob(["mp3"], { type: "audio/mpeg" }) });

describe("file audio của clip tải bằng fetch rồi phát từ blob: URL (uxfix53)", () => {
  const arriveWithBytes = async (s: Setup, text: string) => {
    s.requests.filter((r) => r.text === text).forEach((r) => r.resolve(withBytes(text)));
    await flush();
  };
  const readingsChanged = (s: Setup) =>
    (s.engine as unknown as { readingsChanged(detail: { bookId: string; surfaces: string[]; all?: boolean }): void }).readingsChanged({ bookId: "b1", surfaces: [], all: true });

  it("clip có file: phần tử audio nhận blob: URL, không nhận đường dẫn máy chủ; clip không có file vẫn dùng đường dẫn", async () => {
    const urls = blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await arriveWithBytes(s, TEXTS[0]);
    await s.arrive(TEXTS[1]);
    expect(urls.made).toEqual(["blob:abook/1"]);
    expect(s.audios[0].src).toBe("blob:abook/1");
    expect(audioOf(s, TEXTS[1])).toBeDefined(); // không có file -> đường dẫn như cũ
    expect(s.audios[0].plays).toBe(1);
  });

  it("thu hồi blob: URL khi bộ máy bị bỏ (stop / nạp chương khác), không thu hồi trước đó", async () => {
    const urls = blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await arriveWithBytes(s, text);
    expect(urls.made).toHaveLength(3);
    expect(urls.revoked).toEqual([]);
    s.engine.stop();
    expect(urls.revoked.sort()).toEqual([...urls.made].sort());
    // nạp lại chương: cái mới cấp, cái cũ không bị thu hồi lần hai
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await arriveWithBytes(s, TEXTS[0]);
    expect(urls.made).toHaveLength(4);
    s.engine.load(s.trackInfo, 0, true); // nạp đè: bộ máy cũ bị bỏ
    expect(urls.revoked).toHaveLength(4);
    expect(new Set(urls.revoked).size).toBe(4);
  });

  it("clip bị bỏ (đổi cách đọc) thì audio và blob: URL của nó cùng thả; clip mới về lại cấp blob: URL mới", async () => {
    const urls = blobUrls();
    const s = setup();
    s.track.bookId = "b1";
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS.slice(0, 3)) await arriveWithBytes(s, text);
    expect(urls.made).toHaveLength(3);
    readingsChanged(s);
    await flush();
    // đoạn đang nói (0) nói nốt; hai đoạn đọc sẵn bị thả
    expect(urls.revoked).toHaveLength(2);
    expect(urls.revoked).not.toContain(s.audios[0].src);
    expect(s.audios[1].released).toBe(true);
    await arriveWithBytes(s, TEXTS[1]);
    expect(urls.made).toHaveLength(4);
    expect(s.audios.at(-1)!.src).toBe("blob:abook/4");
  });

  it("nhảy xa: audio ngoài cửa sổ thả blob: URL và không giữ file trong bộ nhớ; quay lại thì phát từ đường dẫn", async () => {
    const urls = blobUrls();
    const chapter = Array.from({ length: 12 }, (_, i) => `Đoạn số ${i + 1}.`).join("\n\n");
    const s = setup({ chapter });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    const first = s.requests.slice(0, 3).map((r) => r.text);
    for (const text of first) await arriveWithBytes(s, text);
    expect(urls.made).toHaveLength(3);
    s.engine.seekWord(10, 0);
    await flush();
    expect(urls.revoked.sort()).toEqual([...urls.made].sort());
    const urlsBefore = urls.made.length;
    s.engine.seekWord(0, 0);
    await flush();
    expect(urls.made).toHaveLength(urlsBefore); // file đã bỏ khỏi bộ nhớ: không cấp blob: URL mới
    expect(s.audios.filter((audio) => audio.src === `/clip/${encodeURIComponent("Đoạn số 1.")}`)).toHaveLength(1);
  });
});

describe("giữ file của vài đoạn vừa nghe để nghe lại (uxfix54)", () => {
  const PARAS = Array.from({ length: 12 }, (_, i) => `Đoạn số ${i + 1} của chương.`);

  it("KEEP_BEHIND đoạn vừa nghe còn file: bấm lùi phát từ blob: URL mới, không đi tải lại đường dẫn; xa hơn thì phát từ đường dẫn", async () => {
    const urls = blobUrls();
    const s = setup({ chapter: PARAS.join("\n\n") });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    const resolveAll = async () => {
      s.requests.filter((r) => PARAS.includes(r.text)).forEach((r) => r.resolve(withBytes(r.text)));
      await flush();
    };
    // nghe liền tới đoạn 5 (chỉ số 4): mỗi đoạn xong thì đoạn kế bắt đầu
    for (let k = 0; k < 4; k += 1) {
      await resolveAll();
      const playing = s.audios.filter((audio) => !audio.paused && !audio.released);
      expect(playing).toHaveLength(1);
      playing[0].finish();
      await flush();
    }
    await resolveAll();
    const made = urls.made.length;
    // lùi 1 đoạn (chỉ số 3) và 2 đoạn (chỉ số 2): file còn, blob: URL mới cấp (chưa có audio nào dùng đường dẫn máy chủ)
    s.engine.seekWord(3, 0);
    await flush();
    expect(urls.made.length).toBeGreaterThanOrEqual(made); // đoạn 3 còn audio (hoặc cấp mới)
    s.engine.seekWord(2, 0);
    await flush();
    expect(s.audios.some((audio) => audio.src.startsWith("/clip/") && audio.src.includes(encodeURIComponent(PARAS[2])))).toBe(false);
    expect(s.audios.some((audio) => audio.src.startsWith("blob:") && !audio.released && audio.plays > 0)).toBe(true);
    // xa hơn KEEP_BEHIND (đoạn đầu, file đã bỏ): phát từ đường dẫn như thường
    s.engine.seekWord(0, 0);
    await flush();
    expect(s.audios.some((audio) => audio.src === `/clip/${encodeURIComponent(PARAS[0])}`)).toBe(true);
  });

  it("file ngoài KEEP_BEHIND đoạn vừa nghe bị bỏ, blob: URL thu hồi: bộ nhớ không lớn theo số đoạn đã nghe", async () => {
    const urls = blobUrls();
    const s = setup({ chapter: PARAS.join("\n\n") });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    const held = () => (s.engine as unknown as { slots: { clip: { bytes?: Blob } | null }[] }).slots.filter((slot) => slot.clip?.bytes).length;
    let peak = 0;
    for (let k = 0; k < 10; k += 1) {
      s.requests.filter((r) => PARAS.includes(r.text)).forEach((r) => r.resolve(withBytes(r.text)));
      await flush();
      const playing = s.audios.filter((audio) => !audio.paused && !audio.released);
      playing[0]?.finish();
      await flush();
      peak = Math.max(peak, held());
    }
    // cửa sổ: KEEP_BEHIND đoạn sau lưng + đoạn đang nghe + tối đa MAX_READ_AHEAD đoạn đọc trước
    expect(peak).toBeLessThanOrEqual(KEEP_BEHIND + 1 + 8);
    const slots = (s.engine as unknown as { slots: { clip: { bytes?: Blob } | null }[] }).slots;
    expect(slots.slice(0, 6).filter((slot) => slot.clip?.bytes)).toHaveLength(0);
    // mọi blob: URL đã cấp mà không còn audio giữ thì đã thu hồi: số còn sống <= số audio còn gắn
    const alive = urls.made.filter((url) => !urls.revoked.includes(url)).length;
    expect(alive).toBeLessThanOrEqual(s.audios.filter((audio) => !audio.released).length);
  });
});

describe("fetchClipBytes: tải file audio của clip", () => {
  it("lấy bằng fetch rồi trả blob", async () => {
    const seen: string[] = [];
    const blob = await fetchClipBytes("/media/clip.mp3?t=k", async (url) => {
      seen.push(url);
      return new Response(new Blob(["abc"], { type: "audio/mpeg" }), { status: 200 });
    });
    expect(seen).toEqual(["/media/clip.mp3?t=k"]);
    expect(await blob.text()).toBe("abc");
    expect(blob.type).toBe("audio/mpeg");
  });

  it("không tải được (HTTP 404/502 hay mất kết nối) = clip hỏng lỗi thoáng qua, đi đường thử lại như lúc máy chủ trả lỗi", async () => {
    for (const get of [async () => new Response("", { status: 404 }), async () => new Response("", { status: 502 }), async (): Promise<Response> => Promise.reject(new TypeError("Failed to fetch"))]) {
      const error = await fetchClipBytes("/media/clip.mp3", get).catch((e) => e);
      expect(error).toBeInstanceOf(ReadAloudError);
      expect(isTransientClipError(error)).toBe(true);
    }
  });

  it("clip hỏng vì file không tải được: bộ máy thử lại (cùng đường với lỗi máy chủ) rồi phát khi lần sau tải được", async () => {
    vi.useFakeTimers();
    onTestFinished(() => void vi.useRealTimers());
    blobUrls();
    let tries = 0;
    const s = setup({ chapter: "Một hai." });
    s.track.fetchClip = async (_voice, text) => {
      tries += 1;
      if (tries === 1) await fetchClipBytes("/media/x.mp3", async () => new Response("", { status: 502 }));
      return withBytes(text);
    };
    s.engine.load(s.trackInfo, 0, true);
    await vi.advanceTimersByTimeAsync(0);
    expect(s.audios).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[0] + 10);
    await vi.advanceTimersByTimeAsync(0);
    expect(tries).toBe(2);
    expect(s.audios).toHaveLength(1);
    expect(s.audios[0].plays).toBe(1);
    expect(s.engine.error).toBe("");
  });
});

/** Clip đang về (phát dần): chưa có url / độ dài / mốc - chỉ khúc đầu. */
function liveClipOf(first = [1, 2, 3]): { clip: ReadAloudClip; live: LiveClip } {
  const live = new LiveClip();
  live.push(new Uint8Array(first));
  return { clip: { url: "", durationMs: 0, words: [], live }, live };
}

const liveFinal = (text: string, bytes = "mp3") => {
  const done = clipOf(text);
  return { url: done.url, durationMs: done.durationMs, words: done.words, bytes: new Blob([bytes], { type: "audio/mpeg" }) };
};

describe("clip phát dần: nghe từ byte đầu, đồng hồ ảo không nhảy (uxfix56)", () => {
  const start = async () => {
    const urls = blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    return { s, urls };
  };

  it("clip về với byte đầu: phần tử audio phát từ MediaSource (blob: URL), mốc rỗng, độ dài vẫn là độ dài ước", async () => {
    const { s, urls } = await start();
    const estimated = s.engine.duration;
    const { clip, live } = liveClipOf();
    s.requests[0].resolve(clip);
    await flush();
    expect(s.sources).toHaveLength(1);
    expect(s.audios[0].src).toBe(urls.made[0]);
    expect(s.audios[0].plays).toBe(1);
    expect(s.engine.duration).toBeCloseTo(estimated, 6);
    expect(s.published.at(-1)!.segments[0].words).toEqual([]);
    s.sources[0].open();
    expect(s.sources[0].buffer.appended).toEqual([[1, 2, 3]]);
    live.push(new Uint8Array([4]));
    s.sources[0].buffer.finish();
    expect(s.sources[0].buffer.appended).toEqual([[1, 2, 3], [4]]);
    expect(s.sources[0].ended).toBe(false);
  });

  it("mốc tạm (W) cập nhật mốc chữ của đoạn; xong (E) thì đổi độ dài ước thành độ dài thật, dựng lại đồng hồ, giữ nguyên phần tử audio đang phát", async () => {
    const { s } = await start();
    const { clip, live } = liveClipOf();
    s.requests[0].resolve(clip);
    await flush();
    live.setWords([[0, 400], [400, 800]]);
    expect(s.published.at(-1)!.segments[0].words).toEqual([[0, 400], [400, 800]]);
    const durations: number[] = [];
    s.engine.on("duration", () => durations.push(s.engine.duration));
    live.finish(liveFinal(TEXTS[0]));
    expect(s.published.at(-1)!.segments[0].words).toEqual(clipOf(TEXTS[0]).words);
    const segments = s.published.at(-1)!.segments;
    expect(segments[0].end! - segments[0].start!).toBeCloseTo(1, 6); // 2 chữ x 0,5 s
    expect(segments[1].start).toBeCloseTo(1, 6); // đoạn sau dịch theo độ dài thật
    expect(durations).toHaveLength(1);
    expect(s.audios).toHaveLength(1); // không dựng lại phần tử audio giữa chừng
    expect(s.audios[0].released).toBe(false);
    s.sources[0].open();
    s.sources[0].buffer.finish();
    expect(s.sources[0].ended).toBe(true);
    s.audios[0].finish();
    await flush();
    expect(s.engine.time).toBeCloseTo(1, 6);
  });

  it("clip đã về đủ ngay lúc bộ máy nhận (A và E cùng khúc mạng): phát từ file như clip thường, không MediaSource", async () => {
    const { s, urls } = await start();
    const { clip, live } = liveClipOf();
    live.finish(liveFinal(TEXTS[0], "full"));
    s.requests[0].resolve(clip);
    await flush();
    expect(s.sources).toHaveLength(0);
    expect(urls.made).toHaveLength(1);
    expect(s.audios[0].plays).toBe(1);
    expect(s.published.at(-1)!.segments[0].words).toEqual(clipOf(TEXTS[0]).words);
  });

  it("hỏng giữa chừng (lỗi thoáng qua): phần đã về vẫn phát (phần tử MediaSource ở yên), xin phần tiếp NGAY không chờ quãng nghỉ, phần tiếp nối liền vào cùng phần tử (uxfix58)", async () => {
    vi.useFakeTimers();
    onTestFinished(() => void vi.useRealTimers());
    const urls = blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await vi.advanceTimersByTimeAsync(0);
    const { clip, live } = liveClipOf();
    s.requests[0].resolve(clip);
    await vi.advanceTimersByTimeAsync(0);
    s.audios[0].currentTime = 0.4;
    live.fail(new ReadAloudError("Mất kết nối giữa chừng", "service"));
    await vi.advanceTimersByTimeAsync(0);
    expect(s.audios[0].released).toBe(false);
    expect(urls.revoked).toEqual([]);
    expect(s.engine.error).toBe("");
    const again = s.requests.filter((r) => r.text === TEXTS[0]);
    expect(again).toHaveLength(2); // lượt xin tiếp đã đi, không chờ CLIP_RETRY_DELAYS_MS
    expect(again[1].whole).toBeUndefined();
    again[1].resolve(withBytes(TEXTS[0])); // chưa có mốc nào lúc đứt: xin lại từ đầu đoạn, về như clip đã xong
    await vi.advanceTimersByTimeAsync(0);
    expect(s.engine.error).toBe("");
    expect(s.audios).toHaveLength(1);
    s.sources[0].open();
    for (let i = 0; i < 10 && s.sources[0].buffer.updating; i += 1) s.sources[0].buffer.finish();
    expect(s.sources[0].buffer.appended.map((chunk) => chunk.length)).toEqual([3, 3]); // 3 byte phần đầu + "mp3" của phần tiếp
    expect(s.sources[0].ended).toBe(true);
  });

  it("hỏng giữa chừng vì lỗi không thử lại được (bị từ chối): phần tiếp cũng bị từ chối thì phát hết phần đã có rồi dừng và báo như clip hỏng", async () => {
    const { s } = await start();
    const { clip, live } = liveClipOf();
    s.requests[0].resolve(clip);
    await flush();
    live.fail(new ReadAloudError("Dịch vụ từ chối", "rejected"));
    await flush();
    expect(s.engine.error).toBe("");
    expect(s.audios[0].released).toBe(false);
    s.requests.filter((r) => r.text === TEXTS[0])[1].reject(new ReadAloudError("Dịch vụ từ chối", "rejected")); // lượt xin phần tiếp
    await flush();
    s.audios[0].finish();
    await flush();
    expect(s.engine.error).toBe("Dịch vụ từ chối");
    expect(s.engine.paused).toBe(true);
    expect(s.events.filter((e) => e === "error")).toHaveLength(1);
    expect(s.audios[0].released).toBe(true);
  });

  it("MediaSource không nhận khúc MP3 khi clip còn đang về: coi như clip hỏng (đi đường thử lại)", async () => {
    vi.useFakeTimers();
    onTestFinished(() => void vi.useRealTimers());
    blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await vi.advanceTimersByTimeAsync(0);
    const { clip } = liveClipOf();
    s.requests[0].resolve(clip);
    await vi.advanceTimersByTimeAsync(0);
    s.sources[0].buffer.fail = true;
    s.sources[0].open();
    expect(s.audios[0].released).toBe(true);
    await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[0] + 10);
    expect(s.requests.filter((r) => r.text === TEXTS[0])).toHaveLength(2);
  });

  it("MediaSource không nhận khúc khi clip đã về đủ: phát tiếp từ file (blob) ở chỗ đang nghe", async () => {
    const { s, urls } = await start();
    const { clip, live } = liveClipOf();
    s.requests[0].resolve(clip);
    await flush();
    s.audios[0].currentTime = 0.7;
    live.finish(liveFinal(TEXTS[0], "bytes"));
    s.sources[0].buffer.fail = true;
    s.sources[0].open();
    await flush();
    expect(s.audios[0].released).toBe(true);
    expect(s.audios).toHaveLength(2);
    expect(s.audios[1].src).toBe(urls.made[1]);
    expect(s.audios[1].currentTime).toBeCloseTo(0.7, 6);
    expect(s.audios[1].plays).toBe(1);
    expect(s.engine.error).toBe("");
  });

  it("bỏ clip (nạp chương khác) thu hồi blob: URL của MediaSource và thôi theo dõi clip", async () => {
    const { s, urls } = await start();
    const { clip, live } = liveClipOf();
    s.requests[0].resolve(clip);
    await flush();
    s.engine.stop();
    expect(urls.revoked).toEqual([urls.made[0]]);
    const published = s.published.length;
    live.setWords([[0, 1]]);
    live.finish(liveFinal(TEXTS[0]));
    expect(s.published).toHaveLength(published);
  });

  it("khoảng thời gian lấy clip tính tới lúc về đủ, không phải tới byte đầu", async () => {
    vi.useFakeTimers();
    onTestFinished(() => void vi.useRealTimers());
    blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await vi.advanceTimersByTimeAsync(0);
    const { clip, live } = liveClipOf();
    await vi.advanceTimersByTimeAsync(300);
    s.requests[0].resolve(clip);
    await vi.advanceTimersByTimeAsync(0);
    const seconds = () => (s.engine as unknown as { fetchSeconds: number[] }).fetchSeconds;
    expect(seconds()).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(2000);
    live.finish(liveFinal(TEXTS[0]));
    expect(seconds()).toHaveLength(1);
    expect(seconds()[0]).toBeGreaterThan(2);
  });
});

describe("chỗ chờ giữa đoạn không phát dần (whole) (uxfix56)", () => {
  const second = (s: Setup) => s.requests.find((r) => r.text === TEXTS[1])!;

  it("nghe từ đầu đoạn: không đặt gì; bấm chữ giữa đoạn: tailFrom (clip đuôi); theo tỉ lệ (thanh tua): whole", async () => {
    const plain = setup();
    plain.engine.load(plain.trackInfo, 0, true);
    await flush();
    expect(plain.requests[0].rank).toBe(0);
    expect(plain.requests[0].whole).toBeUndefined();

    const word = setup();
    word.engine.load(word.trackInfo, 0, false);
    await flush();
    word.engine.seekWord(1, 2);
    word.engine.play();
    await flush();
    expect(second(word).whole).toBeUndefined();
    expect(second(word).tailFrom).toBe(2);

    const fraction = setup();
    fraction.engine.load(fraction.trackInfo, 0, false);
    await flush();
    fraction.engine.seek(fraction.engine.duration * 0.6);
    fraction.engine.play();
    await flush();
    expect(fraction.requests.filter((r) => !r.cachedOnly).some((r) => r.whole === true)).toBe(true);

    const startOfWord = setup();
    startOfWord.engine.load(startOfWord.trackInfo, 0, false);
    await flush();
    startOfWord.engine.seekWord(1, 0);
    startOfWord.engine.play();
    await flush();
    expect(second(startOfWord).whole).toBeUndefined();
    expect(second(startOfWord).tailFrom).toBeUndefined();
  });
});

describe("clip đuôi: bấm chữ giữa đoạn chưa đọc (uxfix56)", () => {
  const TEXT = TEXTS[1]; // "Ba bốn năm sáu."
  /** Clip đuôi như httpSource trả: chỉ đọc từ chữ `from`; mỗi chữ 500 ms. */
  const tailClip = (from: number): ReadAloudClip => ({ ...clipOf(tailFromWord(TEXT, from)!), fromWord: from });
  const asked = (s: Setup) => s.requests.filter((r) => r.text === TEXT);
  const click = async (word: number) => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, false);
    await flush();
    s.engine.seekWord(1, word);
    s.engine.play();
    await flush();
    return s;
  };
  const shifted = (s: Setup, words: [number, number][]) => {
    const origin = s.published.at(-1)!.segments[1].start! * 1000;
    return words.map(([a, b]) => [Math.round(origin + a), Math.round(origin + b)]);
  };

  it("xin clip đuôi từ chữ vừa bấm; clip về thì nghe từ đầu clip, mốc theo chữ của đoạn (chữ trước đó [0,0]) và đoạn dài bằng clip đuôi", async () => {
    const s = await click(2);
    expect(asked(s)).toHaveLength(1);
    expect(asked(s)[0].tailFrom).toBe(2);
    expect(asked(s)[0].whole).toBeUndefined();
    asked(s)[0].resolve(tailClip(2));
    await flush();
    const audio = s.audios[0];
    expect(audio.currentTime).toBeCloseTo(0, 6);
    expect(audio.plays).toBe(1);
    const segment = s.published.at(-1)!.segments[1];
    expect(segment.end! - segment.start!).toBeCloseTo(1, 6); // 2 chữ x 0,5 s
    expect(segment.words).toEqual(shifted(s, [[0, 0], [0, 0], [0, 450], [500, 950]]));
  });

  it("bấm chữ tiếp theo trong clip đuôi nhảy trong clip; bấm chữ đứng trước nó bỏ clip đuôi và xin clip khác từ chữ ấy", async () => {
    const s = await click(2);
    asked(s)[0].resolve(tailClip(2));
    await flush();
    s.engine.seekWord(1, 3);
    expect(s.audios[0].currentTime).toBeCloseTo(0.5, 6);
    expect(asked(s)).toHaveLength(1); // không xin lại
    s.engine.seekWord(1, 2); // chữ đầu của clip đuôi vẫn nằm trong nó
    expect(s.audios[0].released).toBe(false);
    expect(asked(s)).toHaveLength(1);
    s.engine.seekWord(1, 1);
    await flush();
    expect(s.audios[0].released).toBe(true);
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBe(1);
    asked(s)[1].resolve(tailClip(1));
    await flush();
    expect(s.audios.at(-1)!.currentTime).toBeCloseTo(0, 6);
    expect(s.published.at(-1)!.segments[1].words).toHaveLength(4);
    // chữ đầu đoạn = nghe từ đầu đoạn: clip đủ cả đoạn, không whole, không tailFrom
    s.engine.seekWord(1, 0);
    await flush();
    expect(asked(s)).toHaveLength(3);
    expect(asked(s)[2].tailFrom).toBeUndefined();
    expect(asked(s)[2].whole).toBeUndefined();
    asked(s)[2].resolve();
    await flush();
    expect(s.published.at(-1)!.segments[1].words).toEqual(shifted(s, clipOf(TEXT).words as [number, number][]));
  });

  it("clip đuôi về khi người nghe đã chuyển sang chữ đứng trước nó: không dùng, xin lại từ chữ mới", async () => {
    const s = await click(3);
    expect(asked(s)[0].tailFrom).toBe(3);
    s.engine.seekWord(1, 1); // đang chờ: lượt cũ còn bay
    await flush();
    expect(asked(s)).toHaveLength(1);
    asked(s)[0].resolve(tailClip(3));
    await flush();
    expect(s.audios).toHaveLength(0);
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBe(1);
  });

  it("từ đoạn trước sang đoạn có clip đuôi (nghe liền): bỏ clip đuôi, xin clip đầy đủ", async () => {
    const s = await click(2);
    asked(s)[0].resolve(tailClip(2));
    await flush();
    s.engine.seekWord(0, 0);
    await flush();
    await s.arrive(TEXTS[0]);
    audioOf(s, TEXTS[0])!.finish();
    await flush();
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBeUndefined();
    expect(asked(s)[1].whole).toBeUndefined();
  });

  it("tua thanh thời gian về đầu đoạn có clip đuôi bỏ clip đuôi; tua vào giữa clip thì giữ", async () => {
    const s = await click(2);
    asked(s)[0].resolve(tailClip(2));
    await flush();
    const start = s.published.at(-1)!.segments[1].start!;
    s.engine.seek(start + 0.5);
    expect(s.audios[0].currentTime).toBeCloseTo(0.5, 6);
    expect(asked(s)).toHaveLength(1);
    s.engine.seek(start);
    await flush();
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBeUndefined();
  });

  it("clip đuôi đang về đứt giữa chừng: phần đã về phát hết, xin tiếp NGAY clip đuôi từ chữ đầu tiên chưa có tiếng (uxfix58)", async () => {
    blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, false);
    await flush();
    s.engine.seekWord(1, 1);
    s.engine.play();
    await flush();
    const live = new LiveClip();
    live.push(new Uint8Array(4800)); // 800 ms tiếng
    live.setWords([[0, 400], [400, 800]], 800); // chữ 1 và 2 của đoạn
    asked(s)[0].resolve({ url: "", durationMs: 0, words: [], live, fromWord: 1 });
    await flush();
    s.audios[0].currentTime = 0.5; // đang ở chữ thứ hai của clip đuôi
    live.fail(new ReadAloudError("Mất kết nối giữa chừng", "service"));
    await flush();
    expect(s.audios[0].released).toBe(false);
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBe(3); // chữ 1, 2 đã có tiếng; chữ 3 chưa
    expect(asked(s)[1].whole).toBeUndefined();
  });

  it("clip đủ cả đoạn đang về mà chữ vừa bấm chưa có mốc: xong thì nhảy tới chữ ấy", async () => {
    blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    const { clip, live } = liveClipOf();
    s.requests[0].resolve(clip);
    await flush();
    s.engine.seekWord(0, 1);
    expect(s.audios[0].currentTime).toBeCloseTo(0, 6);
    live.finish(liveFinal(TEXTS[0]));
    expect(s.audios[0].currentTime).toBeCloseTo(0.5, 6);
  });

  it("nguồn không có clip đuôi (trả cả đoạn): chữ đổi thành giây bằng mốc của clip như trước", async () => {
    const s = await click(2);
    asked(s)[0].resolve(); // clip đủ cả đoạn, không fromWord
    await flush();
    expect(s.audios[0].currentTime).toBeCloseTo(1, 6);
    expect(s.published.at(-1)!.segments[1].words).toHaveLength(4);
  });
});

describe("vào một đoạn đã phát dở: luôn từ đầu đoạn (uxfix58, a58 st2/st3)", () => {
  /** Phần tử audio đang giữ của đoạn (đoạn bị thả rồi dựng lại thì lấy cái mới nhất, còn sống). */
  const current = (s: Setup, text: string) => s.audios.filter((a) => a.src === `/clip/${encodeURIComponent(text)}` && !a.released).at(-1)!;
  /** Nạp, phát, cho mọi clip về; đoạn 0 đang phát. */
  const playing = async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    for (const text of TEXTS) await s.arrive(text);
    return s;
  };

  it("đoạn k+1 đã phát dở rồi người nghe bấm chỗ khác; sau đó vào nó bằng advance() từ đoạn k thì phát từ đầu, không ở chỗ cũ", async () => {
    const s = await playing();
    audioOf(s, TEXTS[0])!.finish(); // sang đoạn 1, phát từ đầu
    await flush();
    const second = audioOf(s, TEXTS[1])!;
    expect(second.currentTime).toBeCloseTo(0, 6);
    second.currentTime = 1.3; // đã nghe được 1,3 giây
    s.engine.seekWord(2, 0); // bấm chỗ khác (đoạn kế, vẫn trong cửa sổ giữ audio)
    await flush();
    s.engine.seekWord(0, 0); // quay lại đoạn 0 rồi nghe liền sang đoạn 1
    await flush();
    current(s, TEXTS[0]).finish();
    await flush();
    expect(second.currentTime).toBeCloseTo(0, 6);
    expect(s.engine.time).toBeCloseTo(1, 6); // đầu đoạn 1 (đoạn 0 dài 1 s)
  });

  it("đoạn bị rời giữa chừng (bấm sang đoạn khác) không giữ vị trí cũ: đi lại bằng bất kỳ đường nào cũng bắt đầu từ đầu", async () => {
    const s = await playing();
    audioOf(s, TEXTS[0])!.finish();
    await flush();
    const second = audioOf(s, TEXTS[1])!;
    second.currentTime = 0.9;
    s.engine.seek(s.engine.duration - 1.2); // nhảy sang đoạn sau, rời đoạn 1
    await flush();
    s.engine.seek(0.2); // về đoạn 0
    await flush();
    expect(second.released).toBe(false); // vẫn là phần tử audio cũ, còn giữ chỗ cũ
    current(s, TEXTS[0]).finish(); // advance vào đoạn 1
    await flush();
    expect(second.currentTime).toBeCloseTo(0, 6);
  });
});

describe("clip đuôi không chặn đọc trước (uxfix58, a58 b2)", () => {
  const TEXT = TEXTS[1];
  const tailClip = (from: number): ReadAloudClip => ({ ...clipOf(tailFromWord(TEXT, from)!), fromWord: from });
  const asked = (s: Setup) => s.requests.filter((r) => r.text === TEXT);
  const load = async () => {
    const s = setup();
    s.engine.load(s.trackInfo, 0, false);
    await flush();
    return s;
  };

  it("nhảy giữa đoạn P: các đoạn sau P được xin ngay trong lúc clip đuôi của P còn chưa về / đang phát", async () => {
    const s = await load();
    s.engine.seekWord(1, 2);
    s.engine.play();
    await flush();
    expect(s.requests.map((r) => r.text)).toEqual([TEXTS[1], TEXTS[2], TEXTS[3]]);
    asked(s)[0].resolve(tailClip(2));
    await flush();
    await s.arrive(TEXTS[2]);
    expect(s.audios.some((a) => a.src === `/clip/${encodeURIComponent(TEXTS[2])}`)).toBe(true); // đoạn sau đã sẵn audio khi P còn phát
  });

  it("đoạn k+1 đang giữ clip đuôi cũ (người nghe đã bỏ đi chỗ khác): lúc nghe đoạn k, cửa sổ đọc trước thay nó bằng clip đủ cả đoạn, không chờ tới khi vào đoạn ấy", async () => {
    const s = await load();
    s.engine.seekWord(1, 2);
    s.engine.play();
    await flush();
    asked(s)[0].resolve(tailClip(2));
    await flush();
    s.engine.seekWord(0, 0); // về đoạn 0: đoạn 1 vẫn giữ clip đuôi từ chữ 2
    await flush();
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBeUndefined();
    expect(asked(s)[1].whole).toBeUndefined();
    asked(s)[1].resolve();
    await flush();
    await s.arrive(TEXTS[0]);
    audioOf(s, TEXTS[0])!.finish(); // sang đoạn 1: đã có clip đủ, không còn lượt xin nào mới
    await flush();
    expect(asked(s)).toHaveLength(2);
    expect(s.published.at(-1)!.segments[1].words).toHaveLength(4);
  });

  it("clip đuôi mở đầu bằng quãng lặng: kịch bản công bố không có chữ trước chữ bấm nào đang đọc từ đầu clip (a58 d)", async () => {
    const s = await load();
    s.engine.seekWord(1, 2);
    s.engine.play();
    await flush();
    asked(s)[0].resolve({ ...tailClip(2), words: [[137, 500], [500, 950]] }); // 0,137 s lặng rồi chữ 2
    await flush();
    const segment = s.published.at(-1)!.segments[1];
    const origin = segment.start! * 1000;
    for (let ms = 0; ms <= 900; ms += 10) expect(wordIndexAt(segment.words!, origin + ms)).toBeGreaterThanOrEqual(2);
  });

  it("clip đuôi về khi người nghe đã đi tới đoạn đứng trước đoạn ấy: bỏ clip đuôi, xin clip đủ cả đoạn", async () => {
    const s = await load();
    s.engine.seekWord(1, 3);
    s.engine.play();
    await flush();
    s.engine.seekWord(0, 0); // đang chờ clip đuôi của đoạn 1 mà đi về đoạn 0
    await flush();
    asked(s)[0].resolve(tailClip(3));
    await flush();
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBeUndefined();
  });
});

describe("clip phát dần đứt giữa chừng: phần đã về phát hết, phần tiếp xin ngay (uxfix58, a58 e)", () => {
  const P = "Một hai ba bốn năm sáu bảy tám."; // 8 chữ, một đoạn
  const asked = (s: Setup) => s.requests.filter((r) => r.text === P);
  /** Mốc tạm như máy chủ: 4 chữ thật (250 ms mỗi chữ), 4 chữ chưa tới dồn về cuối phần đã có (1000 ms). */
  const FOUR_HEARD: [number, number][] = [[0, 250], [250, 500], [500, 750], [750, 1000], [1000, 1000], [1000, 1000], [1000, 1000], [1000, 1000]];
  const drain = (s: Setup) => {
    for (let i = 0; i < 50 && s.sources[0].buffer.updating; i += 1) s.sources[0].buffer.finish();
  };
  /** Đang nghe đoạn duy nhất bằng clip phát dần: 6000 byte (1000 ms) đã về, mốc tạm có 4 chữ thật. */
  const streaming = async (words: [number, number][] | null = FOUR_HEARD, heard: number | null = 1000) => {
    blobUrls();
    const s = setup({ chapter: P });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    const live = new LiveClip();
    live.push(new Uint8Array(6000));
    asked(s)[0].resolve({ url: "", durationMs: 0, words: [], live });
    await flush();
    s.sources[0].open();
    drain(s);
    if (words) live.setWords(words, heard);
    return { s, live };
  };
  const BROKEN = () => new ReadAloudError("Mất kết nối giữa chừng", "service");

  it("đứt giữa chừng: phần tử audio không bị thả, không báo lỗi, MediaSource chưa đóng; xin NGAY clip đuôi từ chữ đầu tiên chưa có tiếng (rank 0, phát luồng)", async () => {
    const { s, live } = await streaming();
    s.audios[0].currentTime = 0.4;
    live.fail(BROKEN());
    await flush();
    expect(s.audios[0].released).toBe(false);
    expect(s.engine.error).toBe("");
    expect(s.events).not.toContain("error");
    expect(s.events).not.toContain("pause");
    expect(s.sources[0].ended).toBe(false);
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBe(4);
    expect(asked(s)[1].rank).toBe(0);
    expect(asked(s)[1].whole).toBeUndefined();
    // chữ chưa tới không sáng trong lúc phát phần đã có
    const segment = s.published.at(-1)!.segments[0];
    const origin = segment.start! * 1000;
    expect(segment.words!.slice(0, 4)).toEqual([[0, 250], [250, 500], [500, 750], [750, 1000]].map(([a, b]) => [origin + a, origin + b]));
    expect(wordIndexAt(segment.words!, origin + 990)).toBeLessThanOrEqual(3);
  });

  it("lóe chữ cuối đoạn (a59d): âm thanh chạm hết phần có mốc tạm mà bản W kế chưa tới - tô đứng yên ở chữ cuối ĐÃ CÓ TIẾNG, không nhảy sang chữ cuối đoạn", async () => {
    const { s } = await streaming();
    const segment = s.published.at(-1)!.segments[0];
    const origin = segment.start! * 1000;
    for (const ms of [0, 500, 960, 1000, 1030, 1400, 2500]) {
      const word = wordIndexAt(segment.words!, origin + ms);
      expect(word).toBeLessThanOrEqual(3);
      if (ms >= 960) expect(word).toBe(3);
    }
    expect(segment.words).toHaveLength(8);
  });

  it("lóe chữ cuối đoạn: máy chủ cũ không gửi heard_ms thì mốc tạm giữ nguyên như trước", async () => {
    const { s } = await streaming(FOUR_HEARD, null);
    const segment = s.published.at(-1)!.segments[0];
    expect(segment.words!.slice(4)).toEqual([1, 2, 3, 4].map(() => [segment.start! * 1000 + 1000, segment.start! * 1000 + 1000]));
  });

  it("phần tiếp (live) nối thẳng sau khúc cuối của phần đứt trong CÙNG phần tử audio; mốc chữ ghép; xong thì độ dài = phần đầu + phần tiếp, hết thì không lỗi", async () => {
    const { s, live } = await streaming();
    live.fail(BROKEN());
    await flush();
    const next = new LiveClip();
    next.push(new Uint8Array([9, 9, 9]));
    asked(s)[1].resolve({ url: "", durationMs: 0, words: [], live: next, fromWord: 4 });
    await flush();
    expect(s.audios).toHaveLength(1); // không dựng phần tử audio mới
    drain(s);
    expect(s.sources[0].buffer.appended.map((chunk) => chunk.length)).toEqual([6000, 3]);
    next.setWords([[0, 200], [200, 450], [450, 700], [700, 900]], 900);
    const origin = () => s.published.at(-1)!.segments[0].start! * 1000;
    expect(s.published.at(-1)!.segments[0].words!.slice(4)).toEqual([[1000, 1200], [1200, 1450], [1450, 1700], [1700, 1900]].map(([a, b]) => [origin() + a, origin() + b]));
    next.finish({ url: "/media/x.mp3", durationMs: 900, words: [[0, 200], [200, 450], [450, 700], [700, 900]], bytes: new Blob([new Uint8Array([9, 9, 9])], { type: "audio/mpeg" }) });
    drain(s);
    expect(s.sources[0].ended).toBe(true);
    const segment = s.published.at(-1)!.segments[0];
    expect(segment.end! - segment.start!).toBeCloseTo(1.9, 6);
    expect(segment.words).toHaveLength(8);
    s.audios[0].finish();
    await flush();
    expect(s.events).not.toContain("error");
    expect(s.engine.ended).toBe(true);
    expect(asked(s)).toHaveLength(2);
  });

  it("lượt xin phần tiếp cũng hỏng: phần đã về phát HẾT (MediaSource đóng ở cuối phần ấy) rồi mới báo lỗi, MỘT lần; Thử lại xin lại từ chữ chưa nghe", async () => {
    const { s, live } = await streaming();
    live.fail(BROKEN());
    await flush();
    asked(s)[1].reject(new ReadAloudError("Mất mạng", "offline"));
    await flush();
    expect(s.sources[0].ended).toBe(true);
    expect(s.events.filter((e) => e === "error")).toHaveLength(0); // chưa nghe hết phần đã có: chưa báo
    expect(s.audios[0].released).toBe(false);
    s.audios[0].finish(); // phát hết phần đã về
    await flush();
    expect(s.events.filter((e) => e === "error")).toHaveLength(1);
    expect(s.engine.error).toBe("Mất mạng");
    expect(s.engine.paused).toBe(true);
    s.engine.play();
    await flush();
    expect(asked(s)).toHaveLength(3);
    expect(asked(s)[2].tailFrom).toBe(4);
  });

  it("lỗi thoáng qua của lượt xin phần tiếp: thử lại sau quãng nghỉ như mọi clip, vẫn từ chữ đó", async () => {
    vi.useFakeTimers();
    onTestFinished(() => void vi.useRealTimers());
    blobUrls();
    const s = setup({ chapter: P });
    s.engine.load(s.trackInfo, 0, true);
    await vi.advanceTimersByTimeAsync(0);
    const live = new LiveClip();
    live.push(new Uint8Array(6000));
    asked(s)[0].resolve({ url: "", durationMs: 0, words: [], live });
    await vi.advanceTimersByTimeAsync(0);
    live.setWords(FOUR_HEARD, 1000);
    live.fail(BROKEN());
    await vi.advanceTimersByTimeAsync(0);
    asked(s)[1].reject(new ReadAloudError("Edge bận", "service"));
    await vi.advanceTimersByTimeAsync(CLIP_RETRY_DELAYS_MS[0] + 10);
    expect(asked(s)).toHaveLength(3);
    expect(asked(s)[2].tailFrom).toBe(4);
    expect(s.events).not.toContain("error");
  });

  it("chưa có bản ghi W nào lúc đứt: xin lại từ đầu đoạn (không tailFrom)", async () => {
    const { s, live } = await streaming(null);
    live.fail(BROKEN());
    await flush();
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBeUndefined();
    expect(asked(s)[1].whole).toBeUndefined();
    expect(asked(s)[1].rank).toBe(0);
  });

  it("chữ chưa có tiếng tính theo phần ĐÃ VỀ khi nó ngắn hơn mốc chữ thật Edge đã báo", async () => {
    blobUrls();
    const s = setup({ chapter: P });
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    const live = new LiveClip();
    live.push(new Uint8Array(3000)); // chỉ 500 ms tiếng về, dù mốc chữ đã báo tới 1000 ms
    asked(s)[0].resolve({ url: "", durationMs: 0, words: [], live });
    await flush();
    live.setWords(FOUR_HEARD, 1000);
    live.fail(BROKEN());
    await flush();
    expect(asked(s)[1].tailFrom).toBe(2); // chữ 0, 1 hết ở 250 và 500: đủ tiếng; chữ 2 (500-750) chưa
  });

  it("clip đuôi (fromWord 2) đứt giữa chừng: chữ xin tiếp tính theo chữ của đoạn", async () => {
    blobUrls();
    const s = setup({ chapter: P });
    s.engine.load(s.trackInfo, 0, false);
    await flush();
    s.engine.seekWord(0, 2);
    s.engine.play();
    await flush();
    const live = new LiveClip();
    live.push(new Uint8Array(6000));
    asked(s)[0].resolve({ url: "", durationMs: 0, words: [], live, fromWord: 2 });
    await flush();
    s.sources[0].open();
    drain(s);
    live.setWords([[0, 300], [300, 600], [600, 1000], [1000, 1000], [1000, 1000], [1000, 1000]], 1000); // chữ 2, 3, 4 có tiếng; 5, 6, 7 chưa
    live.fail(BROKEN());
    await flush();
    expect(asked(s)).toHaveLength(2);
    expect(asked(s)[1].tailFrom).toBe(5);
  });

  it("nguồn trả cả đoạn thay vì clip đuôi (nó đã sẵn trong bộ đệm): bỏ phần đã có, nghe tiếp từ chữ đang nghe trong clip đủ", async () => {
    const { s, live } = await streaming();
    s.audios[0].currentTime = 0.8; // đang ở chữ 3 (750-1000 ms) của phần đã về
    live.fail(BROKEN());
    await flush();
    asked(s)[1].resolve(); // clip đủ cả đoạn (mỗi chữ 500 ms), không fromWord
    await flush();
    const audio = s.audios.at(-1)!;
    expect(s.audios[0].released).toBe(true);
    expect(audio.currentTime).toBeCloseTo(1.5, 6); // chữ 3 bắt đầu ở 1,5 s của clip đủ: nghe tiếp từ chữ đang nghe, không từ chữ chưa nghe
    expect(audio.plays).toBe(1);
    expect(s.events).not.toContain("error");
    expect(s.published.at(-1)!.segments[0].words).toHaveLength(8);
  });

  it("đoạn không phải đoạn đang nghe: đứt giữa chừng không báo lỗi", async () => {
    blobUrls();
    const s = setup();
    s.engine.load(s.trackInfo, 0, true);
    await flush();
    await s.arrive(TEXTS[0]);
    const live = new LiveClip();
    live.push(new Uint8Array(6000));
    s.requests.find((r) => r.text === TEXTS[1])!.resolve({ url: "", durationMs: 0, words: [], live });
    await flush();
    s.engine.seekWord(3, 0); // người nghe đi chỗ khác
    await flush();
    live.fail(BROKEN());
    await flush();
    expect(s.events).not.toContain("error");
  });
});
