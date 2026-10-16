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
  RoutedEngine,
  estimateSeconds,
  estimatedStarts,
  isSpeakable,
  isTransientClipError,
  readAheadCount,
  type AudioLike,
  type ReadAloudClip,
  type SpeechTrack,
} from "./readAloud";
import { textScript } from "./textScript";
import { usableWords } from "./words";

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
  published: Script[];
  requests: { text: string; cachedOnly: boolean; willRetry?: boolean; retryBefore?: number; fresh?: boolean; resolve: (clip?: ReadAloudClip) => void; reject: (error: Error) => void }[];
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
        requests.push({ text, cachedOnly: false, willRetry: o?.willRetry, retryBefore: o?.retryBefore, fresh: o?.fresh, resolve: (clip) => resolve(clip ?? clipOf(text)), reject });
      }),
    onScript: (script) => published.push(script),
  };
  const engine = new ReadAloudEngine({
    createAudio: (url) => {
      const audio = new FakeAudio(url);
      audios.push(audio);
      return audio;
    },
    muted: options.muted ?? false,
  });
  for (const name of ["time", "duration", "play", "pause", "ended", "error", "waiting", "playing"] as EngineEvent[]) {
    engine.on(name, () => events.push(name));
  }
  return {
    engine,
    audios,
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
