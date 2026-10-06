import { afterEach, describe, expect, it, vi } from "vitest";
import { MusicBed, SIBLING_FADE_SECONDS, STEP_RAMP_SECONDS, stepDbAt, type MusicCue } from "./musicBed";

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
    expect(made["/c"].loop).toBe(true);
    vi.advanceTimersByTime(3000); // nửa đường mờ chéo: cả hai còn kêu
    expect(made["/a"].volume).toBeGreaterThan(0.05);
    expect(made["/c"].volume).toBeGreaterThan(0.05);
    expect(made["/c"].volume).toBeLessThan(db(-10) - 0.05);
    vi.advanceTimersByTime(SIBLING_FADE_SECONDS * 1000 - 3000 + 200);
    expect(made["/a"].volume).toBe(0);
    expect(made["/c"].volume).toBeCloseTo(db(-10), 3);
  });
});
