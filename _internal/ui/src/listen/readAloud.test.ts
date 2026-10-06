import { describe, expect, it, vi } from "vitest";
import type { AudioEngine, EngineEvent, TrackInfo } from "./engine";
import type { Script } from "./model";
import {
  CLIP_RETRIES,
  ReadAloudEngine,
  RoutedEngine,
  estimateSeconds,
  estimatedStarts,
  isSpeakable,
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
  requests: { text: string; cachedOnly: boolean; resolve: (clip?: ReadAloudClip) => void; reject: (error: Error) => void }[];
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
        requests.push({ text, cachedOnly: false, resolve: (clip) => resolve(clip ?? clipOf(text)), reject });
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

  it("lỗi thoáng qua ở đoạn đang chờ: tự thử lại, không dừng; hỏng quá số lần thử thì mới dừng", async () => {
    vi.useFakeTimers();
    try {
      const s = setup();
      s.engine.load(s.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      const first = () => s.requests.filter((r) => r.text === TEXTS[0]);
      first()[0].reject(Object.assign(new Error("Bad Gateway"), { reason: "upstream" }));
      await vi.advanceTimersByTimeAsync(0);
      expect(s.events).not.toContain("error");
      await vi.advanceTimersByTimeAsync(1000);
      expect(first()).toHaveLength(2);
      first()[1].resolve();
      await vi.advanceTimersByTimeAsync(0);
      expect(audioOf(s, TEXTS[0])!.plays).toBe(1);
      expect(s.engine.error).toBe("");

      const t = setup();
      t.engine.load(t.trackInfo, 0, true);
      await vi.advanceTimersByTimeAsync(0);
      const firstT = () => t.requests.filter((r) => r.text === TEXTS[0]);
      for (let attempt = 0; attempt <= CLIP_RETRIES; attempt += 1) {
        firstT()[attempt].reject(Object.assign(new Error("Bad Gateway"), { reason: "upstream" }));
        await vi.advanceTimersByTimeAsync(1000 * (attempt + 1));
      }
      expect(firstT()).toHaveLength(CLIP_RETRIES + 1);
      expect(t.events).toContain("error");
      expect(t.engine.paused).toBe(true);
    } finally {
      vi.useRealTimers();
    }
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
