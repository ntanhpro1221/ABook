import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import mix from "../../../abook/webui/assets/music_mix.json";
import {
  FADE_SECONDS,
  LOOP_CROSSFADE_SECONDS,
  MusicBed,
  NEXT_CHAPTER_WARM_SECONDS,
  NextChapterWarm,
  RETRY_MS,
  SIBLING_FADE_SECONDS,
  STEP_RAMP_SECONDS,
  alignedPosition,
  finalLoop,
  finished,
  loopBounds,
  loopDue,
  loopPosition,
  loopSchedule,
  siblingFadeSeconds,
  stepDbAt,
  type MusicCue,
  type MusicCues,
} from "./musicBed";

const cues: MusicCue[] = [
  { start: 0, end: 120, link: "a", key: "1:1", src: "/a" },
  { start: 180, end: 300, link: "b", key: "1:30", src: "/b" },
];

describe("nhạc nền theo mốc của chương", () => {
  it("đổi bài đúng đoạn, im lặng ở khoảng không có nhạc", () => {
    const made: string[] = [];
    const bed = new MusicBed((src) => {
      made.push(src);
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    bed.setCues(cues, -20);
    bed.sync(10, true);
    expect(bed.activeLink).toBe("a");
    bed.sync(150, true);
    expect(bed.activeLink).toBeNull();
    bed.sync(200, true);
    expect(bed.activeLink).toBe("b");
    bed.sync(20, true, true);
    expect(bed.activeLink).toBe("a");
    expect(made).toEqual(["/a", "/b", "/a"]);
    bed.stop();
    expect(bed.activeLink).toBeNull();
  });

  it("đổi cuốn lúc tạm dừng: bài của cuốn cũ (đang mờ đi) không bị chơi lại khi giọng mới chạy", () => {
    const plays: string[] = [];
    const bed = new MusicBed((src) => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
      return Object.assign(fake, {
        play: () => { plays.push(src); fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    bed.setCues(cues, -20);
    bed.sync(10, true);
    bed.sync(10, false); // người nghe tạm dừng
    plays.length = 0;
    bed.setCues([], -20); // chọn cuốn khác: bài cũ chuyển sang mờ đi
    bed.sync(0, true); // giọng của cuốn mới chạy
    expect(plays).toEqual([]);
    bed.stop();
  });

  it("báo khi bài đang phát đổi (cho dòng ghi công), không báo lặp khi cùng bài", () => {
    const bed = new MusicBed(() => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    const seen: (string | null)[] = [];
    const off = bed.onActiveChange((link) => seen.push(link));
    bed.setCues(cues, -20);
    bed.sync(10, true);
    bed.sync(11, true);
    bed.sync(150, true);
    bed.sync(200, true);
    expect(seen).toEqual(["a", null, "b"]);
    off();
    bed.stop();
    expect(seen).toEqual(["a", null, "b"]);
  });
});

describe("phần tử <audio> hết dùng thì nhả kết nối tải bài (uxfix54)", () => {
  afterEach(() => vi.useRealTimers());

  /** Mỗi phần tử ghi lại `removeAttribute` / `load` và các hàm nghe lỗi, như một <audio> thật còn đang tải. */
  function released() {
    const made: Record<string, { paused: boolean; removed: string[]; loads: number; onError: (() => void)[] }> = {};
    const bed = new MusicBed((src) => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200, removed: [] as string[], loads: 0, onError: [] as (() => void)[] };
      made[src] = fake;
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        removeAttribute: (name: string) => { fake.removed.push(name); },
        load: () => { fake.loads += 1; },
        addEventListener: (type: string, listener: () => void) => { if (type === "error") fake.onError.push(listener); },
      });
    });
    return { bed, made };
  }

  it("bài mờ hết (đổi bài / sang chương khác) thì bỏ nguồn và nạp lại - không chỉ tạm dừng", () => {
    vi.useFakeTimers();
    const { bed, made } = released();
    bed.setCues(cues, -20);
    bed.sync(10, true);
    expect(made["/a"].removed).toEqual([]); // đang kêu: còn dùng
    bed.sync(150, true); // khoảng không nhạc: bài a chuyển sang mờ đi
    expect(made["/a"].removed).toEqual([]);
    vi.advanceTimersByTime(FADE_SECONDS * 1000 + 2000);
    expect(made["/a"].paused).toBe(true);
    expect(made["/a"].removed).toEqual(["src"]);
    expect(made["/a"].loads).toBe(1);
    bed.stop();
  });

  it("dừng nhạc (rời chương, đổi cuốn): bài đang kêu lẫn bài đang mờ đều nhả kết nối", () => {
    vi.useFakeTimers();
    const { bed, made } = released();
    bed.setCues(cues, -20);
    bed.sync(10, true);
    bed.sync(150, true);
    bed.sync(200, true); // b đang kêu, a còn đang mờ
    vi.advanceTimersByTime(300);
    bed.stop();
    expect(made["/a"].removed).toEqual(["src"]);
    expect(made["/b"].removed).toEqual(["src"]);
    expect(made["/a"].loads).toBe(1);
    expect(made["/b"].loads).toBe(1);
  });

  it("bài tải hỏng: nhả kết nối, đoạn của nó im lặng chờ thử lại; lỗi muộn của phần tử đã nhả không tính là bài hỏng", () => {
    vi.useFakeTimers();
    const { bed, made } = released();
    bed.setCues(cues, -20);
    bed.sync(10, true);
    made["/a"].onError.forEach((listener) => listener());
    expect(made["/a"].removed).toEqual(["src"]);
    expect(bed.failing).toBe(true);
    // chương khác: bài b nhả bằng stop() rồi trình duyệt báo lỗi muộn - không được ghi bài b vào danh sách hỏng
    bed.sync(200, true);
    bed.stop();
    made["/b"].onError.forEach((listener) => listener());
    bed.setCues([cues[1]], -20);
    expect(bed.failing).toBe(false);
  });
});

describe("âm lượng nhạc theo gainDb của mốc", () => {
  afterEach(() => vi.useRealTimers());

  function bedWithVolumes() {
    const made: Record<string, { volume: number }> = {};
    const bed = new MusicBed((src) => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
      made[src] = fake;
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    return { bed, made };
  }

  it("mỗi bài lên đúng mức gainDb của nó, chuyển bài đổi sang mục tiêu của bài mới", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithVolumes();
    bed.setCues([
      { start: 0, end: 100, link: "a", key: "1:1", src: "/a", gainDb: -10 },
      { start: 100, end: 200, link: "b", key: "1:9", src: "/b", gainDb: -26 },
    ], -20);
    bed.sync(10, true);
    vi.advanceTimersByTime(3000);
    expect(made["/a"].volume).toBeCloseTo(Math.pow(10, -10 / 20), 3);
    bed.sync(110, true);
    vi.advanceTimersByTime(3000);
    expect(made["/b"].volume).toBeCloseTo(Math.pow(10, -26 / 20), 3);
    expect(made["/a"].volume).toBe(0);
  });

  it("nhân với âm lượng người nghe, và không bao giờ vượt 1", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithVolumes();
    bed.setCues([{ start: 0, end: 100, link: "a", key: "1:1", src: "/a", gainDb: -12 }], -20);
    bed.setVolume(0.5);
    bed.sync(10, true);
    vi.advanceTimersByTime(3000);
    expect(made["/a"].volume).toBeCloseTo(0.5 * Math.pow(10, -12 / 20), 3);
    bed.setCues([{ start: 0, end: 100, link: "a", key: "1:1", src: "/a", gainDb: 6 }], -20);
    bed.setVolume(1);
    expect(made["/a"].volume).toBe(1);
  });

  it("mốc không có gainDb (máy chủ cũ) dùng mức chung levelDb như trước", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithVolumes();
    bed.setCues([{ start: 0, end: 100, link: "a", key: "1:1", src: "/a" }], -24);
    bed.sync(10, true);
    vi.advanceTimersByTime(3000);
    expect(made["/a"].volume).toBeCloseTo(Math.pow(10, -24 / 20), 3);
  });
});

describe("bước âm lượng trong cảnh và nối bài anh em", () => {
  afterEach(() => vi.useRealTimers());

  type Fake = { volume: number; loop: boolean; paused: boolean };
  function bedWithAudios() {
    const made: Record<string, Fake> = {};
    const bed = new MusicBed((src) => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
      made[src] = fake;
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    return { bed, made };
  }
  const db = (value: number) => Math.pow(10, value / 20);
  const stepped: MusicCue = {
    start: 0, end: 400, link: "a", key: "1:1", src: "/a", gainDb: -10,
    steps: [{ at: 180, db: 2 }, { at: 300, db: -3 }],
  };

  it("bước đang hiệu lực là bước cuối cùng đã tới, chưa tới bước nào thì 0", () => {
    expect(stepDbAt(stepped, 10)).toBe(0);
    expect(stepDbAt(stepped, 180)).toBe(2);
    expect(stepDbAt(stepped, 299)).toBe(2);
    expect(stepDbAt(stepped, 350)).toBe(-3);
  });

  it("sang bước mới thì trượt dần trong STEP_RAMP_SECONDS, không nhảy", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithAudios();
    bed.setCues([stepped], -20);
    bed.sync(10, true);
    vi.advanceTimersByTime(3000);
    expect(made["/a"].volume).toBeCloseTo(db(-10), 3);
    bed.sync(181, true);
    vi.advanceTimersByTime((STEP_RAMP_SECONDS * 1000) / 2);
    const half = made["/a"].volume;
    expect(half).toBeGreaterThan(db(-10) + 0.01);
    expect(half).toBeLessThan(db(-8) - 0.01);
    vi.advanceTimersByTime((STEP_RAMP_SECONDS * 1000) / 2 + 200);
    expect(made["/a"].volume).toBeCloseTo(db(-8), 3);
    bed.sync(301, true);
    vi.advanceTimersByTime(STEP_RAMP_SECONDS * 1000 + 200);
    expect(made["/a"].volume).toBeCloseTo(db(-13), 3);
  });

  it("tua thì vào thẳng mức của bước tại chỗ tua", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithAudios();
    bed.setCues([stepped], -20);
    bed.sync(10, true);
    vi.advanceTimersByTime(3000);
    bed.sync(200, true, true);
    expect(made["/a"].volume).toBeCloseTo(db(-8), 3);
  });

  it("một mốc mới bắt đầu ngay ở mức bước của nó, và gainDb + bước không vượt 0 dB", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithAudios();
    bed.setCues([{ start: 0, end: 100, link: "b", key: "1:5", src: "/b", gainDb: -1, steps: [{ at: 0, db: 3 }] }], -20);
    bed.sync(5, true);
    vi.advanceTimersByTime(3000);
    expect(made["/b"].volume).toBe(1);
  });

  it("nối bài anh em: mờ chéo SIBLING_FADE_SECONDS, bài cũ chơi nốt không lặp lại, cùng khoá đoạn vẫn đổi bài", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithAudios();
    bed.setCues([
      { start: 0, end: 150, link: "a", key: "1:1", src: "/a", gainDb: -10 },
      { start: 150, end: 400, link: "c", key: "1:1", src: "/c", gainDb: -10, sibling: true },
    ], -20);
    bed.sync(10, true);
    vi.advanceTimersByTime(3000);
    bed.sync(151, true);
    expect(bed.activeLink).toBe("c");
    expect(made["/a"].loop).toBe(false);
    expect(made["/c"].loop, "bài đủ dài lặp bằng mờ chéo vào chính nó, không audio.loop").toBe(false);
    vi.advanceTimersByTime(3000); // nửa đường mờ chéo: cả hai còn kêu
    expect(made["/a"].volume).toBeGreaterThan(0.05);
    expect(made["/c"].volume).toBeGreaterThan(0.05);
    expect(made["/c"].volume).toBeLessThan(db(-10) - 0.05);
    vi.advanceTimersByTime(SIBLING_FADE_SECONDS * 1000 - 3000 + 200);
    expect(made["/a"].volume).toBe(0);
    expect(made["/c"].volume).toBeCloseTo(db(-10), 3);
  });
});

describe("bài tải hỏng thử lại sau RETRY_MS (như MusicBed.kt)", () => {
  afterEach(() => vi.useRealTimers());

  type Fake = { volume: number; loop: boolean; paused: boolean; fire: (type: "loadedmetadata" | "error") => void };
  function bedWithEvents() {
    const made: Record<string, Fake[]> = {};
    const bed = new MusicBed((src) => {
      const listeners: Record<string, (() => void)[]> = {};
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
      const audio = Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: (type: string, listener: () => void) => { (listeners[type] ??= []).push(listener); },
        fire: (type: "loadedmetadata" | "error") => listeners[type]?.forEach((listener) => listener()),
      });
      (made[src] ??= []).push(audio);
      return audio;
    });
    return { bed, made };
  }

  it("hỏng thì im lặng, chưa tới 5 phút không thử lại, tới hạn thì thử lại; tải được thì xoá", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithEvents();
    bed.setCues([{ start: 0, end: 1000, link: "a", key: "1:1", src: "/a", gainDb: -10 }], -20);
    bed.sync(10, true);
    expect(bed.activeLink).toBe("a");
    made["/a"][0].fire("error");
    expect(bed.activeLink).toBeNull();
    expect(made["/a"][0].paused).toBe(true);
    vi.advanceTimersByTime(RETRY_MS - 1000);
    bed.sync(20, true);
    bed.sync(30, true, true);
    expect(bed.activeLink).toBeNull();
    expect(made["/a"]).toHaveLength(1);
    vi.advanceTimersByTime(1000);
    bed.sync(40, true);
    expect(bed.activeLink).toBe("a");
    expect(made["/a"]).toHaveLength(2);
    made["/a"][1].fire("loadedmetadata");
    // Đã tải được: lần hỏng sau lại chờ trọn RETRY_MS, đếm từ lúc ấy.
    vi.advanceTimersByTime(60_000);
    made["/a"][1].fire("error");
    vi.advanceTimersByTime(RETRY_MS - 1000);
    bed.sync(50, true);
    expect(bed.activeLink).toBeNull();
    vi.advanceTimersByTime(1000);
    bed.sync(51, true);
    expect(bed.activeLink).toBe("a");
    expect(made["/a"]).toHaveLength(3);
  });

  it("bài của chương không phát được thì nói ra (failing) - hết khi tải được hay sang chương khác (soát a26 L7)", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithEvents();
    bed.setCues([{ start: 0, end: 1000, link: "a", key: "1:1", src: "/a" }], -20);
    bed.sync(10, true);
    expect(bed.failing).toBe(false);
    made["/a"][0].fire("error");
    expect(bed.failing).toBe(true);
    bed.setCues([{ start: 0, end: 1000, link: "b", key: "2:1", src: "/b" }], -20);
    expect(bed.failing, "chương khác, bài khác").toBe(false);
    bed.setCues([{ start: 0, end: 1000, link: "a", key: "1:1", src: "/a" }], -20);
    expect(bed.failing).toBe(true);
    vi.advanceTimersByTime(RETRY_MS);
    bed.sync(20, true);
    made["/a"][1].fire("loadedmetadata");
    expect(bed.failing).toBe(false);
  });

  it("chỉ bài hỏng im lặng: mốc khác vẫn phát, nối bài anh em vẫn mờ chéo", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithEvents();
    bed.setCues([
      { start: 0, end: 100, link: "x", key: "1:1", src: "/x", gainDb: -10 },
      { start: 100, end: 250, link: "a", key: "1:5", src: "/a", gainDb: -10 },
      { start: 250, end: 400, link: "c", key: "1:5", src: "/c", gainDb: -10, sibling: true },
    ], -20);
    bed.sync(10, true);
    made["/x"][0].fire("error");
    bed.sync(110, true);
    expect(bed.activeLink).toBe("a");
    vi.advanceTimersByTime(3000);
    bed.sync(251, true);
    expect(bed.activeLink).toBe("c");
    expect(made["/a"][0].loop).toBe(false);
    vi.advanceTimersByTime(3000);
    expect(made["/a"][0].volume).toBeGreaterThan(0.05);
    expect(made["/c"][0].volume).toBeGreaterThan(0.05);
    // Bài cũ đang mờ đi mà hỏng: thôi hẳn, bài anh em vẫn lên đủ mức.
    made["/a"][0].fire("error");
    vi.advanceTimersByTime(SIBLING_FADE_SECONDS * 1000);
    expect(made["/a"][0].paused).toBe(true);
    expect(made["/c"][0].volume).toBeCloseTo(Math.pow(10, -10 / 20), 3);
    expect(bed.activeLink).toBe("c");
  });
});

describe("vị trí trong bài theo vị trí trong chương (soát a26 L8)", () => {
  function fakes() {
    const made: { currentTime: number; duration: number; fire: () => void }[] = [];
    const bed = new MusicBed(() => {
      let loaded: (() => void) | undefined;
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: Number.NaN };
      const audio = Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: (type: string, listener: () => void) => { if (type === "loadedmetadata") loaded = listener; },
        fire: () => { fake.duration = 200; loaded?.(); },
      });
      made.push(audio);
      return audio;
    });
    return { bed, made };
  }

  it("vào giữa chương: bài tải xong thì đứng ở giây mới nhất của chương, không phải từ đầu bài", () => {
    const { bed, made } = fakes();
    bed.setCues([{ start: 0, end: 600, link: "a", key: "1:1", src: "/a" }], -20, 0);
    bed.sync(95, true, true);
    made[0].fire();
    expect(made).toHaveLength(1);
    expect(made[0].currentTime).toBe(95);
  });

  it("tua trong cùng một bài thì nhạc dời theo (lặp bài thì theo chu kỳ độ dài - X); không tua thì chơi tiếp", () => {
    const { bed, made } = fakes();
    bed.setCues([{ start: 0, end: 600, link: "a", key: "1:1", src: "/a" }], -20, 0);
    bed.sync(0, true);
    made[0].fire();
    made[0].currentTime = 12;
    bed.sync(12.5, true);
    expect(made[0].currentTime, "không tua: không động vào nhạc").toBe(12);
    bed.sync(250, true, true);
    expect(made).toHaveLength(1);
    expect(made[0].currentTime).toBe(250 - (200 - LOOP_CROSSFADE_SECONDS));
  });
});

describe("đuôi bài: kết tự nhiên, bài kế vào ngay (MIX_QA 3.1, 3.3)", () => {
  afterEach(() => vi.useRealTimers());

  type Fake = { volume: number; loop: boolean; paused: boolean; currentTime: number; duration: number; ended: boolean };
  function bedWithClock() {
    const made: Record<string, Fake[]> = {};
    const bed = new MusicBed((src) => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200, ended: false };
      (made[src] ??= []).push(fake);
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    return { bed, made };
  }
  // Bài 200 s chơi hai vòng trong mốc 0-400, bài anh em vào đúng ở điểm kết bài.
  const tail: MusicCue[] = [
    { start: 0, end: 400, link: "a", key: "1:1", src: "/a", gainDb: -10, tail: true },
    { start: 400, end: 600, link: "c", key: "1:1", src: "/c", gainDb: -10, sibling: true },
  ];

  it("mốc tail: vòng trước mở phần tử lặp, vòng cuối thì không (theo độ dài thật của bài)", () => {
    const { bed, made } = bedWithClock();
    bed.setCues(tail, -20, 0);
    bed.sync(10, true);
    const a = made["/a"][0];
    a.currentTime = 200 - LOOP_CROSSFADE_SECONDS;
    bed.sync(198, true);
    expect(made["/a"], "vòng đầu: còn một vòng nữa").toHaveLength(2);
    const again = made["/a"][1];
    again.currentTime = 196;
    bed.sync(394, true);
    again.currentTime = 200 - LOOP_CROSSFADE_SECONDS;
    bed.sync(396, true);
    expect(made["/a"], "vòng cuối: chơi nốt rồi thôi").toHaveLength(2);
    bed.sync(20, true, true);
    again.currentTime = 200 - LOOP_CROSSFADE_SECONDS;
    bed.sync(21, true);
    expect(made["/a"], "tua về vòng đầu: lặp lại như cũ").toHaveLength(3);
  });

  it("mốc thường không bao giờ thôi lặp", () => {
    const { bed, made } = bedWithClock();
    bed.setCues([{ ...tail[0], tail: undefined }], -20, 0);
    bed.sync(10, true);
    made["/a"][0].currentTime = 200 - LOOP_CROSSFADE_SECONDS;
    bed.sync(396, true);
    expect(made["/a"]).toHaveLength(2);
  });

  it("bài cũ hết trước mốc: bài anh em vào ngay, không chuyển ngược trước đầu mốc của nó; tua thì theo mốc như thường", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithClock();
    bed.setCues(tail, -20, 0);
    bed.sync(10, true);
    const a = made["/a"][0];
    a.currentTime = 10;
    bed.sync(210, true);
    a.ended = true; // bài thật ngắn hơn số danh mục: hết ở 399,2
    bed.sync(399.25, true);
    expect(bed.activeLink).toBe("c");
    expect(made["/c"]).toHaveLength(1);
    expect(made["/c"][0].currentTime).toBe(0);
    vi.advanceTimersByTime(3000);
    expect(made["/c"][0].volume, "mờ vào như nối bài anh em (6 s)").toBeLessThan(Math.pow(10, -10 / 20) - 0.05);
    bed.sync(399.5, true);
    bed.sync(399.75, true);
    expect(bed.activeLink).toBe("c");
    expect(made["/a"]).toHaveLength(1);
    bed.sync(400.1, true);
    expect(bed.activeLink).toBe("c");
    expect(made["/c"]).toHaveLength(1);
    bed.sync(399.5, true, true);
    expect(bed.activeLink, "tua: bỏ vào sớm, theo mốc tại chỗ tua").toBe("a");
    expect(made["/a"]).toHaveLength(2);
  });

  it("bài kết ở stopAt (không có mốc kế): im tới hết mốc như cũ", () => {
    const { bed, made } = bedWithClock();
    bed.setCues([tail[0], { start: 420, end: 600, link: "c", key: "1:9", src: "/c" }], -20, 0);
    bed.sync(10, true);
    made["/a"][0].currentTime = 10;
    bed.sync(210, true);
    made["/a"][0].ended = true;
    bed.sync(399.5, true);
    expect(bed.activeLink).toBe("a");
    expect(made["/c"]).toBeUndefined();
  });

  it("đổi chương: xoá mốc cũ ở giây 0 thì bài cũ thôi, mốc mới cùng bài vẫn mở bài từ đầu", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithClock();
    bed.setCues([{ start: 0, end: 600, link: "b", key: "1:1", src: "/b", gainDb: -10 }], -20, 0);
    bed.sync(590, true);
    const old = made["/b"][0];
    bed.setCues([], undefined, 0);
    expect(bed.activeLink).toBeNull();
    bed.sync(0, true, true);
    expect(bed.activeLink, "giây 0 của chương mới: mốc cũ không còn").toBeNull();
    vi.advanceTimersByTime(3000);
    expect(old.paused).toBe(true);
    expect(old.volume).toBe(0);
    bed.setCues([{ start: 0, end: 500, link: "b", key: "2:1", src: "/b", gainDb: -10 }], -20);
    bed.sync(0.5, true);
    expect(made["/b"]).toHaveLength(2);
    expect(old.paused, "bài cũ không phát tiếp").toBe(true);
  });
});

describe("lặp mờ chéo trong đoạn nghe được (lô 2 mix-loop, MIX_QA 3.2, 3.5, 9)", () => {
  afterEach(() => vi.useRealTimers());

  type Fake = { volume: number; loop: boolean; paused: boolean; currentTime: number; duration: number; ended: boolean };
  function bedWithClock(duration = 120) {
    const made: Record<string, Fake[]> = {};
    const bed = new MusicBed((src) => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration, ended: false };
      (made[src] ??= []).push(fake);
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    return { bed, made };
  }
  // Bài 120 s, im 2 s đầu và 10 s cuối: A 2, E 110, chu kỳ P = 106.
  const a: MusicCue = { start: 0, end: 600, link: "a", key: "1:1", src: "/a", gainDb: -10, audibleStart: 2, audibleEnd: 110 };
  const db = (value: number) => Math.pow(10, value / 20);

  it("hằng số trộn đọc từ music_mix.json, không chép tay", () => {
    expect([FADE_SECONDS, SIBLING_FADE_SECONDS, STEP_RAMP_SECONDS, LOOP_CROSSFADE_SECONDS])
      .toEqual([mix.fadeSeconds, mix.siblingFadeSeconds, mix.stepRampSeconds, mix.loopCrossfadeSeconds]);
  });

  it("tới E - X thì một phần tử mới vào từ A, mờ chéo X giây; phần tử cũ dừng khi mờ xong", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithClock();
    bed.setCues([a], -20, 0);
    bed.sync(10, true);
    vi.advanceTimersByTime(3000);
    const first = made["/a"][0];
    expect(first.loop, "không lặp bằng audio.loop (nối thẳng có tách / lỗ im)").toBe(false);
    first.currentTime = 107.9;
    bed.sync(105.9, true);
    expect(made["/a"]).toHaveLength(1);
    first.currentTime = 110 - LOOP_CROSSFADE_SECONDS;
    bed.sync(106, true);
    expect(made["/a"]).toHaveLength(2);
    const second = made["/a"][1];
    expect(second.currentTime, "vào từ A").toBe(2);
    expect(bed.activeLink).toBe("a");
    vi.advanceTimersByTime((LOOP_CROSSFADE_SECONDS * 1000) / 2);
    expect(first.volume).toBeGreaterThan(0.05);
    expect(second.volume).toBeGreaterThan(0.05);
    vi.advanceTimersByTime((LOOP_CROSSFADE_SECONDS * 1000) / 2 + 200);
    expect(first.volume).toBe(0);
    expect(first.paused).toBe(true);
    expect(second.volume).toBeCloseTo(db(-10), 3);
  });

  it("thiếu A/E (sách đóng gói cũ): A = 0, E = độ dài thật", () => {
    const { bed, made } = bedWithClock();
    bed.setCues([{ ...a, audibleStart: undefined, audibleEnd: undefined }], -20, 0);
    bed.sync(10, true);
    made["/a"][0].currentTime = 120 - LOOP_CROSSFADE_SECONDS - 0.1;
    bed.sync(117.9, true);
    expect(made["/a"]).toHaveLength(1);
    made["/a"][0].currentTime = 120 - LOOP_CROSSFADE_SECONDS;
    bed.sync(118, true);
    expect(made["/a"]).toHaveLength(2);
    expect(made["/a"][1].currentTime).toBe(0);
  });

  it("bài quá ngắn để mờ chéo (E - A < 3X) lặp thường cả file như cũ", () => {
    const { bed, made } = bedWithClock(5);
    bed.setCues([{ ...a, audibleStart: 0.2, audibleEnd: 4.9 }], -20, 0);
    bed.sync(10, true);
    expect(made["/a"][0].loop).toBe(true);
    made["/a"][0].currentTime = 4.95;
    bed.sync(14.95, true);
    expect(made["/a"]).toHaveLength(1);
  });

  it("tua: vị trí A + ((giây - đầu mốc) mod P)", () => {
    const { bed, made } = bedWithClock();
    bed.setCues([a], -20, 0);
    bed.sync(0, true);
    bed.sync(250, true, true);
    expect(made["/a"]).toHaveLength(1);
    expect(made["/a"][0].currentTime).toBe(2 + (250 % 106));
  });

  it("vòng cuối của mốc tail không mở phần tử mới; bài chơi tới E thì mốc anh em kế vào sớm", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithClock();
    bed.setCues([
      { ...a, end: 214, tail: true },
      { start: 214, end: 400, link: "c", key: "1:1", src: "/c", gainDb: -10, sibling: true },
    ], -20, 0);
    bed.sync(1, true);
    made["/a"][0].currentTime = 108;
    bed.sync(106, true);
    expect(made["/a"], "vòng đầu: 108 s nữa mốc mới hết").toHaveLength(2);
    const last = made["/a"][1];
    last.currentTime = 108;
    bed.sync(212, true);
    expect(made["/a"], "vòng cuối: không mở phần tử mới").toHaveLength(2);
    last.currentTime = 109.9;
    bed.sync(213.5, true);
    expect(bed.activeLink).toBe("a");
    last.currentTime = 110; // tới E (bài thật lệch số danh mục 0,4 s): phần sau E là im
    bed.sync(213.6, true);
    expect(bed.activeLink, "vào sớm khi tới E, không chờ ended").toBe("c");
    expect(made["/c"][0].currentTime).toBe(0);
    bed.sync(213.8, true);
    expect(bed.activeLink, "không chuyển ngược trước đầu mốc").toBe("c");
  });

  it("nối bài anh em: bài cũ mờ ra trong phần còn lại thật của nó khi ngắn hơn SIBLING_FADE_SECONDS", () => {
    vi.useFakeTimers();
    const { bed, made } = bedWithClock();
    bed.setCues([
      { ...a, end: 212, tail: true },
      { start: 212, end: 400, link: "c", key: "1:1", src: "/c", gainDb: -10, sibling: true },
    ], -20, 0);
    bed.sync(1, true);
    vi.advanceTimersByTime(3000);
    const old = made["/a"][0];
    old.currentTime = 108; // còn 2 s tới E
    bed.sync(212, true);
    expect(bed.activeLink).toBe("c");
    vi.advanceTimersByTime(1000);
    expect(old.volume, "giữa đường mờ 2 s").toBeGreaterThan(0.05);
    expect(old.volume).toBeLessThan(db(-10) * 0.6);
    vi.advanceTimersByTime(1200);
    expect(old.volume, "hết mờ đúng lúc bài hết, không bị cắt khi còn kêu").toBe(0);
    expect(made["/c"][0].volume, "bài mới vẫn mờ vào 6 s").toBeLessThan(db(-10) - 0.05);
  });
});

describe("dòng thời gian chung với máy chủ và Android (tests/fixtures/music_timeline)", () => {
  type Track = { seconds: number; audibleStart?: number; audibleEnd?: number; loopStart?: number; loopEnd?: number };
  type Cue = { start: number; end: number; track: string; gainDb: number; sibling?: boolean; tail?: boolean };
  type Element = { track: string; cue: number; enter: "start" | "loop" | "early"; from: number; to: number; position: number; loop?: boolean };
  type Case = { chapterSeconds: number; tracks: Record<string, Track>; cues: Cue[]; timeline: Element[] };
  const NAMES = ["loop_crossfade", "sibling_tail", "stop_at", "chapter_end", "short_track", "loop_points"];

  function load(name: string): Case {
    return JSON.parse(readFileSync(new URL(`../../../tests/fixtures/music_timeline/${name}.json`, import.meta.url)).toString("utf8")) as Case;
  }

  /** Mốc như trình phát nhận (máy chủ đã kẹp cuối chương - music_plan.clamp_to_chapter), dạng MusicCue. */
  function playerCues(data: Case): MusicCue[] {
    const limit = data.chapterSeconds - mix.chapterEndFadeSeconds;
    return data.cues
      .map((cue) => ({ ...cue, end: Math.min(cue.end, limit), tail: cue.end > limit ? undefined : cue.tail }))
      .filter((cue) => cue.end > cue.start)
      .map((cue) => ({ ...cue, link: cue.track, key: cue.track, src: `/${cue.track}`,
        audibleStart: data.tracks[cue.track].audibleStart, audibleEnd: data.tracks[cue.track].audibleEnd,
        loopStart: data.tracks[cue.track].loopStart, loopEnd: data.tracks[cue.track].loopEnd }));
  }

  for (const name of NAMES) {
    it(name, () => {
      const data = load(name);
      const cues = playerCues(data);
      data.timeline.forEach((element, index) => {
        const cue = cues[element.cue];
        const bounds = loopBounds(cue, data.tracks[element.track].seconds);
        const at = (other: Element, seconds: number) => other.position + seconds - other.from;
        expect(!!element.loop, `${name} #${index}: lặp thường hay mờ chéo`).toBe(!bounds.crossfade);
        if (element.enter !== "early") {
          expect(alignedPosition(cue, element.from, bounds), `${name} #${index}: vị trí căn`).toBeCloseTo(element.position, 6);
        }
        const before = data.timeline[index - 1];
        if (element.enter === "loop") {
          const position = at(before, element.from);
          expect(loopDue(bounds, position), `${name} #${index}: mở phần tử lặp ở loopEnd - X`).toBe(true);
          expect(loopDue(bounds, position - 0.05)).toBe(false);
          expect(finalLoop(cue, element.from, position, bounds), `${name} #${index}: chưa phải vòng cuối`).toBe(false);
          expect(element.position).toBe(bounds.loopStart);
        }
        if (element.enter === "early") {
          const previous = loopBounds(cues[before.cue], data.tracks[before.track].seconds);
          expect(finished(previous, at(before, element.from), false), `${name} #${index}: vào sớm khi bài trước tới E`).toBe(true);
          expect(finished(previous, at(before, element.from) - 0.05, false)).toBe(false);
          expect(cues[before.cue].end).toBe(cue.start);
          expect(element.from).toBeLessThan(cue.start);
          expect(element.position).toBe(bounds.start);
        }
        const looped = data.timeline.slice(index + 1).some((other) => other.cue === element.cue && other.enter === "loop");
        if (cue.tail && bounds.crossfade) {
          const position = bounds.loopEnd - LOOP_CROSSFADE_SECONDS;
          const seconds = element.from + position - element.position;
          expect(finalLoop(cue, seconds, position, bounds), `${name} #${index}: vòng cuối = không có phần tử lặp sau`).toBe(!looped);
        }
        if (cue.tail && !bounds.crossfade) {
          expect(finalLoop(cue, element.to - bounds.period, 0, bounds), `${name} #${index}: vòng cuối của lặp thường`).toBe(true);
          expect(finalLoop(cue, element.to - 2 * bounds.period, 0, bounds)).toBe(false);
        }
        const following = cues[element.cue + 1];
        if (following?.sibling && following.start === cue.end && element.to > cue.end && !looped) {
          expect(element.to - cue.end, `${name} #${index}: anh em cũ mờ trong phần còn lại`)
            .toBeCloseTo(siblingFadeSeconds(bounds, at(element, cue.end)), 6);
        }
        if (!following?.sibling && element.to > cue.end + 1e-9 && !looped) {
          expect(element.to - cue.end, `${name} #${index}: mờ ra cuối mốc`).toBeCloseTo(FADE_SECONDS, 6);
        }
        expect(element.to, `${name} #${index}: nhạc mờ xong trước khi giọng hết`).toBeLessThanOrEqual(data.chapterSeconds - 0.5);
      });
    });
  }
});

describe("điểm vòng của bài có đoạn kết (PLAN_loop §10, tests/fixtures/music_loop)", () => {
  afterEach(() => vi.useRealTimers());

  type Track = { seconds: number; audibleStart?: number; audibleEnd?: number; loopStart?: number; loopEnd?: number };
  type Schedule = { opens: number[]; tail: { opens: number[]; seconds: number } };
  type Case = {
    track: Track;
    bounds: { start: number; end: number; period: number; crossfade: boolean; loopStart: number; loopEnd: number };
    invalidVariants?: Partial<Track>[];
    ts: number[];
    positions: number[];
    cues: (Schedule & { seconds: number })[];
    legacy?: { positions: number[]; cues: (Schedule & { seconds: number })[] };
  };
  const MS = 3; // lệch <= 1 ms: toBeCloseTo(x, 3) = |lệch| < 0,5 ms

  function load(name: string): Case {
    return JSON.parse(readFileSync(new URL(`../../../tests/fixtures/music_loop/${name}.json`, import.meta.url)).toString("utf8")) as Case;
  }

  function same(got: number[], want: number[], label: string) {
    expect(got.length, label).toBe(want.length);
    got.forEach((value, index) => expect(value, `${label} #${index}`).toBeCloseTo(want[index], MS));
  }

  for (const name of ["with_points", "without_points", "invalid_points"]) {
    it(`${name}: cùng vị trí, lịch mở phần tử và chỗ hết vòng cuối với máy chủ`, () => {
      const data = load(name);
      const bounds = loopBounds(data.track, data.track.seconds);
      expect(bounds).toEqual(data.bounds);
      for (const variant of data.invalidVariants ?? []) {
        const { loopStart: _start, loopEnd: _end, ...plain } = data.track;
        expect(loopBounds({ ...plain, ...variant }, data.track.seconds), JSON.stringify(variant)).toEqual(loopBounds(plain, data.track.seconds));
      }
      same(data.ts.map((t) => loopPosition(bounds, t)), data.positions, `${name}: vị trí`);
      for (const cue of data.cues) {
        same(loopSchedule(bounds, cue.seconds).opens, cue.opens, `${name} ${cue.seconds}: mở phần tử`);
        const tail = loopSchedule(bounds, cue.seconds, true);
        same(tail.opens, cue.tail.opens, `${name} ${cue.seconds} tail: mở phần tử`);
        expect(tail.end, `${name} ${cue.seconds}: hết vòng cuối`).toBeCloseTo(cue.tail.seconds, MS);
      }
      if (data.legacy) {
        // Không có điểm vòng (hay không hợp lệ): trùng từng số với 0.4.89.
        expect(data.ts.map((t) => loopPosition(bounds, t))).toEqual(data.legacy.positions);
        data.legacy.cues.forEach((old) => {
          same(loopSchedule(bounds, old.seconds).opens, old.opens, `${name} ${old.seconds}: như 0.4.89`);
          same(loopSchedule(bounds, old.seconds, true).opens, old.tail.opens, `${name} ${old.seconds} tail: như 0.4.89`);
          expect(loopSchedule(bounds, old.seconds, true).end).toBeCloseTo(old.tail.seconds, MS);
        });
      }
    });
  }

  type Fake = { volume: number; loop: boolean; paused: boolean; currentTime: number; duration: number; ended: boolean };
  function bed() {
    const made: Fake[] = [];
    const music = new MusicBed(() => {
      const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200, ended: false };
      made.push(fake);
      return Object.assign(fake, {
        play: () => { fake.paused = false; return Promise.resolve(); },
        pause: () => { fake.paused = true; },
        addEventListener: () => undefined,
      });
    });
    return { bed: music, made };
  }
  // Bài 200 s: A 1,5, E 190,25, điểm vòng 12,5 / 160,75 -> phần tử lặp mở ở 158,75 (giây 157,25 của mốc), P = 146,25.
  const track = load("with_points").track;
  const looped: MusicCue = { start: 0, end: 600, link: "a", key: "1:1", src: "/a", gainDb: -10, audibleStart: track.audibleStart,
    audibleEnd: track.audibleEnd, loopStart: track.loopStart, loopEnd: track.loopEnd };

  it("phần tử mới mở ở loopEnd - X và phát từ loopStart, không về A", () => {
    vi.useFakeTimers();
    const { bed: music, made } = bed();
    music.setCues([looped], -20, 0);
    music.sync(10, true);
    made[0].currentTime = 158.7;
    music.sync(157.2, true);
    expect(made, "chưa tới loopEnd - X").toHaveLength(1);
    made[0].currentTime = 160.75 - LOOP_CROSSFADE_SECONDS;
    music.sync(157.25, true);
    expect(made).toHaveLength(2);
    expect(made[1].currentTime, "vào từ loopStart").toBe(12.5);
    made[1].currentTime = 158.75;
    music.sync(303.5, true);
    expect(made, "vòng sau: cũng ở loopEnd - X").toHaveLength(3);
    expect(made[2].currentTime).toBe(12.5);
  });

  it("vòng cuối của mốc tail chơi qua loopEnd tới E (đoạn kết soạn sẵn), mốc anh em vào lúc bài hết", () => {
    vi.useFakeTimers();
    const { bed: music, made } = bed();
    music.setCues([
      { ...looped, end: 335, tail: true },
      { start: 335, end: 600, link: "c", key: "1:2", src: "/c", gainDb: -10, sibling: true },
    ], -20, 0);
    music.sync(1, true);
    made[0].currentTime = 158.75;
    music.sync(157.25, true);
    expect(made, "vòng đầu: còn 178 s mốc, mở phần tử lặp").toHaveLength(2);
    const last = made[1];
    last.currentTime = 158.75; // loopEnd - X của vòng cuối
    music.sync(303.5, true);
    expect(made, "vòng cuối: không mở phần tử mới ở loopEnd - X").toHaveLength(2);
    last.currentTime = 175;
    music.sync(319.75, true);
    expect(music.activeLink, "qua loopEnd vẫn là bài này").toBe("a");
    last.currentTime = 190.25;
    music.sync(334.9, true);
    expect(music.activeLink, "tới E: bài anh em vào").toBe("c");
  });

  it("tua: vòng đầu A + t, sau đó loopStart + ((t - (loopStart - A)) mod P)", () => {
    const { bed: music, made } = bed();
    music.setCues([looped], -20, 0);
    music.sync(0, true);
    music.sync(100, true, true);
    expect(made[0].currentTime).toBe(1.5 + 100);
    music.sync(200, true, true);
    expect(made).toHaveLength(1);
    expect(made[0].currentTime).toBeCloseTo(12.5 + ((200 - 11) % 146.25), 9);
  });
});

/** PLAN_lx F1 (musicwarm): tải sẵn bài kế + bài mới chỉ mờ vào từ lúc CÓ TIẾNG. <audio> giả có trễ tải như đĩa thật: `loadedmetadata` + `playing` chỉ tới sau
 *  `delayOf(src)` giây (cỡ bài / 0,64 MB mỗi giây); bài đã được warm xong trước thì tới gần như ngay (bộ đệm máy chủ). */
describe("tải sẵn bài kế và mờ vào từ lúc có tiếng (musicwarm, PLAN_lx F1)", () => {
  afterEach(() => vi.useRealTimers());

  const MB_PER_SECOND = 0.64;
  const TRACK_MB = 7.4; // trung vị danh mục
  const LOAD_SECONDS = TRACK_MB / MB_PER_SECOND; // ~11,6 giây
  const TICK = 0.5;
  const GOAL = Math.pow(10, -20 / 20); // mốc không có gainDb: mức chung -20 dB, âm lượng người nghe 1
  const slow: MusicCue[] = [
    { start: 0, end: 100, link: "https://x/a.mp3", key: "1:1", src: "/a" },
    { start: 100, end: 200, link: "https://x/b.mp3", key: "1:2", src: "/b" },
    { start: 200, end: 300, link: "https://x/c.mp3", key: "1:3", src: "/c" },
  ];

  type FakeAudio = { paused: boolean; volume: number; loop: boolean; currentTime: number; duration: number; readyState?: number; sounded?: boolean };
  interface Slow {
    bed: MusicBed;
    warmed: string[];
    made: { src: string; audio: FakeAudio }[];
  }

  /** `withWarm` false: không có hàng tải sẵn (0.4.89). `withState` false: bản giả không khai báo readyState / playing (hành vi cũ). */
  function slowBed(delayOf: (src: string) => number, options: { withWarm?: boolean; withState?: boolean } = {}): Slow {
    const withWarm = options.withWarm ?? true;
    const withState = options.withState ?? true;
    const ready = new Set<string>(); // bài đã nằm trong bộ đệm máy chủ
    const warmed: string[] = [];
    const made: Slow["made"] = [];
    const srcOf = (link: string) => "/" + link.split("/").pop()!.replace(".mp3", "");
    const warm = (link: string) => {
      warmed.push(link);
      setTimeout(() => ready.add(srcOf(link)), LOAD_SECONDS * 1000);
    };
    const bed = new MusicBed((src) => {
      const listeners: Record<string, (() => void)[]> = {};
      const fire = (type: string) => (listeners[type] ?? []).splice(0).forEach((listener) => listener());
      const fake: FakeAudio = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
      if (withState) fake.readyState = 0;
      let loaded = false;
      setTimeout(() => {
        loaded = true;
        if (withState) fake.readyState = 4;
        fire("loadedmetadata");
        if (!fake.paused) {
          fake.sounded = true; // từ đây bài thật sự kêu
          fire("playing");
        }
      }, (ready.has(src) ? 0.1 : delayOf(src)) * 1000);
      made.push({ src, audio: fake });
      return Object.assign(fake, {
        play: () => {
          const wasPaused = fake.paused;
          fake.paused = false;
          if (loaded && wasPaused) {
            fake.sounded = true;
            fire("playing");
          }
          return Promise.resolve();
        },
        pause: () => { fake.paused = true; },
        removeAttribute: () => undefined,
        load: () => undefined,
        addEventListener: (type: string, listener: () => void) => { (listeners[type] ??= []).push(listener); },
      });
    }, withWarm ? warm : undefined);
    return { bed, warmed, made };
  }

  /** Nghe tuần tự `seconds` giây của chương, mỗi TICK giây một nhịp `sync`, đồng hồ nhạc chạy từng 50 ms.
   *  silent = giây im hẳn (không phần tử nào có âm lượng) trong các mốc sau mốc đầu; abrupt = số phần tử mà ở nhịp 50 ms ĐẦU TIÊN sau khi thật sự kêu đã quá nửa mức đích (vào đột ngột, J). */
  function listen(sim: Slow, seconds: number): { silent: number; abrupt: number } {
    let silent = 0;
    let abrupt = 0;
    const seen = new Set<FakeAudio>();
    for (let t = 0; t < seconds; t += TICK) {
      sim.bed.sync(t, true);
      for (let step = 0; step < TICK * 20; step += 1) {
        vi.advanceTimersByTime(50);
        const live = sim.made.filter((item) => item.audio.volume > 0.001);
        if (live.length === 0 && t >= slow[0].end && t < slow[2].end) silent += 0.05;
        for (const item of sim.made) {
          if (!item.audio.sounded || seen.has(item.audio)) continue;
          seen.add(item.audio);
          if (item.audio.volume > 0.5 * GOAL) abrupt += 1;
        }
      }
    }
    return { silent, abrupt };
  }

  it("mốc i mở thì bài của mốc kế (khác bài đang kêu) được xin tải sẵn, mỗi bài một lần", () => {
    vi.useFakeTimers();
    const sim = slowBed(() => 0);
    sim.bed.setCues([
      { ...slow[0] },
      { ...slow[0], start: 50, end: 100, key: "1:1b" }, // cùng bài: không phải bài kế
      { ...slow[1], start: 100, end: 200 },
      { ...slow[2], start: 200, end: 300 },
    ], -20);
    sim.bed.sync(1, true);
    expect(sim.warmed).toEqual(["https://x/b.mp3"]);
    sim.bed.sync(2, true);
    sim.bed.sync(60, true); // sang mốc cùng bài
    expect(sim.warmed).toEqual(["https://x/b.mp3"]);
    sim.bed.sync(120, true);
    expect(sim.warmed).toEqual(["https://x/b.mp3", "https://x/c.mp3"]);
    sim.bed.sync(20, true, true); // tua về: b đã xin rồi, không xin lại
    expect(sim.warmed).toEqual(["https://x/b.mp3", "https://x/c.mp3"]);
    sim.bed.stop();
  });

  it("chỉ bài danh mục (https) mới được xin tải sẵn; không có hàng tải sẵn thì thôi", () => {
    vi.useFakeTimers();
    const sim = slowBed(() => 0);
    sim.bed.setCues([{ ...slow[0] }, { start: 100, end: 200, link: "local:abc", key: "1:2", src: "/l" }], -20);
    sim.bed.sync(1, true);
    expect(sim.warmed).toEqual([]);
    sim.bed.stop();
    const none = slowBed(() => 0, { withWarm: false });
    none.bed.setCues(slow, -20);
    expect(() => none.bed.sync(1, true)).not.toThrow();
    none.bed.stop();
  });

  it("bài nằm sẵn trong file .abook (máy chủ đưa qua /music/files/) không được xin tải lại (soát a61)", () => {
    vi.useFakeTimers();
    const sim = slowBed(() => 0);
    const packaged = (cue: MusicCue) => ({ ...cue, src: `http://127.0.0.1:8870/api/books/b1/music/files/${cue.key}.mp3` });
    sim.bed.setCues([packaged(slow[0]), packaged(slow[1]), slow[2]], -20);
    sim.bed.sync(1, true);
    expect(sim.warmed).toEqual([]);
    sim.bed.sync(120, true);
    expect(sim.warmed).toEqual(["https://x/c.mp3"]); // bài thiếu thật (đường tải của máy chủ) vẫn được tải sẵn
    sim.bed.stop();
  });

  it("bài mới chưa có tiếng thì âm lượng giữ 0 (bài cũ mờ như cũ); có tiếng rồi mới mờ vào trong FADE_SECONDS", () => {
    vi.useFakeTimers();
    const sim = slowBed((src) => (src === "/a" ? 0 : 16));
    sim.bed.setCues(slow, -20);
    sim.bed.sync(0, true);
    vi.advanceTimersByTime(3_000); // a có tiếng ngay và mờ vào xong
    const a = sim.made[0].audio;
    expect(a.volume).toBeCloseTo(GOAL, 3);
    sim.bed.sync(100, true); // sang b: tải 16 giây
    const b = sim.made[1].audio;
    vi.advanceTimersByTime(15_000);
    expect(b.volume).toBe(0);
    expect(a.volume).toBe(0); // bài cũ mờ hết trong 2 giây: im lặng bằng thời gian tải, nhưng bài mới KHÔNG vào đột ngột
    vi.advanceTimersByTime(1_100); // b có tiếng
    expect(b.readyState).toBe(4);
    vi.advanceTimersByTime(FADE_SECONDS * 500);
    expect(b.volume).toBeGreaterThan(0.3 * GOAL);
    expect(b.volume).toBeLessThan(0.7 * GOAL); // đang ở giữa dốc, chưa tới mức đích
    vi.advanceTimersByTime(FADE_SECONDS * 600);
    expect(b.volume).toBeCloseTo(GOAL, 3);
    sim.bed.stop();
  });

  it("trễ tải 16 giây: không lần vào nào đột ngột (J = 0); bản giả không khai báo trạng thái (hành vi cũ) thì có - bài thử đủ chặt", () => {
    vi.useFakeTimers();
    const gated = slowBed(() => 16, { withWarm: false });
    gated.bed.setCues(slow, -20);
    expect(listen(gated, 330).abrupt).toBe(0);
    gated.bed.stop();
    vi.useRealTimers();
    vi.useFakeTimers();
    const old = slowBed(() => 16, { withWarm: false, withState: false });
    old.bed.setCues(slow, -20);
    expect(listen(old, 330).abrupt).toBeGreaterThan(0);
    old.bed.stop();
  });

  it("G: im lặng vì chờ tải còn <= 10% khi có tải sẵn (bài đã warm xong thì tới gần như ngay)", () => {
    vi.useFakeTimers();
    const without = slowBed(() => LOAD_SECONDS, { withWarm: false });
    without.bed.setCues(slow, -20);
    const base = listen(without, 330);
    without.bed.stop();
    vi.useRealTimers();
    vi.useFakeTimers();
    const withWarm = slowBed(() => LOAD_SECONDS);
    withWarm.bed.setCues(slow, -20);
    const warmed = listen(withWarm, 330);
    expect(withWarm.warmed).toEqual(["https://x/b.mp3", "https://x/c.mp3"]);
    withWarm.bed.stop();
    expect(base.silent).toBeGreaterThan(15); // hai lần đổi bài, mỗi lần ~10 giây im sau khi bài cũ mờ hết
    expect(warmed.silent).toBeLessThanOrEqual(0.1 * base.silent);
    expect(warmed.abrupt).toBe(0);
  });

  it("đổi âm lượng lúc bài mới còn chờ tải thì vẫn giữ 0", () => {
    vi.useFakeTimers();
    const sim = slowBed(() => 16, { withWarm: false });
    sim.bed.setCues(slow, -20);
    sim.bed.sync(0, true);
    sim.bed.setVolume(0.8);
    vi.advanceTimersByTime(10_000);
    expect(sim.made[0].audio.volume).toBe(0);
    vi.advanceTimersByTime(8_000);
    expect(sim.made[0].audio.volume).toBeCloseTo(0.8 * GOAL, 3);
    sim.bed.stop();
  });
});

describe("tải sẵn bài đầu chương kế khi chương còn <= 120 giây (NextChapterWarm)", () => {
  const next = (link: string): MusicCues => ({
    cues: [{ start: 0, end: 50, link, key: "1:1", src: "/n" }, { start: 50, end: 90, link: "https://x/z.mp3", key: "1:2", src: "/z" }],
    levelDb: -20,
  });
  const settle = async () => {
    for (let i = 0; i < 4; i += 1) await Promise.resolve();
  };

  it("chương kế của file .abook mang bài trong gói: không xin máy chủ tải gì (soát a61)", async () => {
    const warmed: string[] = [];
    const packaged = next("https://x/n.mp3");
    packaged.cues = packaged.cues.map((cue) => ({ ...cue, src: `/api/books/b1/music/files/${cue.key}.mp3` }));
    const watch = new NextChapterWarm(async () => packaged, (link) => warmed.push(link));
    watch.update("1:1", 2, 60);
    await settle();
    watch.update("1:1", 2, 30);
    await settle();
    expect(warmed).toEqual([]);
  });

  it("còn > 120 giây hay chưa biết độ dài thì chưa hỏi; tới ngưỡng thì xin bài MỐC ĐẦU của chương kế, một lần", async () => {
    const asked: number[] = [];
    const warmed: string[] = [];
    const watch = new NextChapterWarm(async (id) => { asked.push(id); return next("https://x/n.mp3"); }, (link) => warmed.push(link));
    watch.update("1:1", 2, NEXT_CHAPTER_WARM_SECONDS + 1);
    watch.update("1:1", 2, 0);
    watch.update("1:1", 2, -5);
    watch.update("1:1", null, 30);
    expect(asked).toEqual([]);
    watch.update("1:1", 2, NEXT_CHAPTER_WARM_SECONDS);
    await settle();
    expect(asked).toEqual([2]);
    expect(warmed).toEqual(["https://x/n.mp3"]);
    watch.update("1:1", 2, 100);
    await settle();
    expect(asked).toEqual([2]);
  });

  it("chương kế chưa dựng xong (pending) hay hỏi hỏng thì bỏ qua, hỏi lại sau 15 giây; không nhạc thì thôi hẳn", async () => {
    let clock = 1_000;
    const answers: (MusicCues | Error)[] = [{ cues: [], levelDb: -20, pending: true }, new Error("mạng"), next("https://x/n.mp3")];
    const warmed: string[] = [];
    let asks = 0;
    const watch = new NextChapterWarm(async () => {
      const answer = answers[asks++];
      if (answer instanceof Error) throw answer;
      return answer;
    }, (link) => warmed.push(link), () => clock);
    watch.update("1:1", 2, 100);
    await settle();
    expect(asks).toBe(1);
    watch.update("1:1", 2, 99);
    await settle();
    expect(asks).toBe(1); // chưa tới hạn hỏi lại
    clock += 15_000;
    watch.update("1:1", 2, 80);
    await settle();
    expect(asks).toBe(2);
    clock += 15_000;
    watch.update("1:1", 2, 60);
    await settle();
    expect(asks).toBe(3);
    expect(warmed).toEqual(["https://x/n.mp3"]);
    let silentAsks = 0;
    const silent = new NextChapterWarm(async () => { silentAsks += 1; return { cues: [], levelDb: -20 }; }, (link) => warmed.push(link), () => clock);
    silent.update("1:1", 3, 60);
    await settle();
    silent.update("1:1", 3, 59);
    await settle();
    expect(silentAsks).toBe(1);
    expect(warmed).toEqual(["https://x/n.mp3"]);
  });
});
