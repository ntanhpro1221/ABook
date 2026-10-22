import { afterEach, expect, it, vi } from "vitest";
import { MusicBed, browserAudio } from "./musicBed";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

// Phần tử <audio> + MediaSource + fetch giả: tải bài chậm (đường mseAudio) để thấy ý định phát đang chờ tải.
function rig() {
  const made: FakeAudio[] = [];
  const downloads: ((value: unknown) => void)[] = [];
  class FakeAudio extends EventTarget {
    paused = true; volume = 0; loop = false; currentTime = 0; duration = 200; readyState = 4; ended = false; muted = false; preload = ""; src = "";
    constructor() { super(); made.push(this); }
    play() { this.paused = false; this.dispatchEvent(new Event("playing")); return Promise.resolve(); }
    pause() { this.paused = true; }
    removeAttribute() { this.src = ""; }
    load() { /* giả */ }
  }
  class FakeMediaSource extends EventTarget {
    static isTypeSupported() { return true; }
    constructor() { super(); queueMicrotask(() => this.dispatchEvent(new Event("sourceopen"))); }
    addSourceBuffer() { const b = new EventTarget(); return Object.assign(b, { appendBuffer: () => queueMicrotask(() => b.dispatchEvent(new Event("updateend"))) }); }
    endOfStream() { /* giả */ }
  }
  vi.stubGlobal("fetch", vi.fn(() => new Promise((resolve) => downloads.push(resolve))));
  vi.stubGlobal("Audio", FakeAudio);
  vi.stubGlobal("MediaSource", FakeMediaSource);
  vi.stubGlobal("window", { location: { search: "" } });
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  const finish = async (n: number) => {
    downloads[n]({ ok: true, headers: { get: () => "audio/mpeg" }, arrayBuffer: async () => new ArrayBuffer(100) });
    for (let i = 0; i < 30; i++) await Promise.resolve();
  };
  return { made, finish };
}
const cue = (link: string, start: number, end: number) => ({ start, end, key: `1:${start}`, link, src: `/${link}`, gainDb: -20 });

it("a music download finishing after voice Pause does not start the music", async () => {
  vi.useFakeTimers();
  const { made, finish } = rig();
  const bed = new MusicBed(browserAudio);
  try {
    bed.setCues([cue("song", 0, 100)], -20);
    bed.sync(0, true); // ý định phát nằm chờ, phần tử vẫn paused
    expect(made[0].paused).toBe(true);
    bed.sync(0, false); // bạn tạm dừng giọng khi file nhạc còn đang tải
    await finish(0);
    expect(made[0].paused).toBe(true);
  } finally { bed.stop(); }
});

it("a pending play intention on a track that is already fading out is cancelled by Pause too", async () => {
  vi.useFakeTimers();
  const { made, finish } = rig();
  const bed = new MusicBed(browserAudio);
  try {
    bed.setCues([cue("a", 0, 50), cue("b", 50, 100)], -20);
    bed.sync(0, true);
    bed.sync(60, true); // sang mốc b: a còn chờ tải thì đang mờ đi
    bed.sync(60, false);
    await finish(0);
    await finish(1);
    expect(made.every((audio) => audio.paused)).toBe(true);
  } finally { bed.stop(); }
});

it("seeking or changing track while the voice is paused never revives an old play intention", async () => {
  vi.useFakeTimers();
  const { made, finish } = rig();
  const bed = new MusicBed(browserAudio);
  try {
    bed.setCues([cue("a", 0, 50), cue("b", 50, 100)], -20);
    bed.sync(0, true);
    bed.sync(0, false);
    bed.sync(70, false, true); // tua sang mốc b lúc đang dừng
    bed.setCues([cue("a", 0, 50), cue("b", 50, 100)], -20, 10); // dựng lại hàng bài: về mốc a
    await finish(0);
    await finish(1);
    expect(made.every((audio) => audio.paused)).toBe(true);
    bed.sync(10, true); // bấm phát lại: lúc này mới có tiếng, khi bài tải xong
    await finish(2);
    expect(made.some((audio) => !audio.paused)).toBe(true);
  } finally { bed.stop(); }
});
