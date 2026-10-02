import { afterEach, describe, expect, it, vi } from "vitest";
import { MusicBed, type MusicCue } from "./musicBed";

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
