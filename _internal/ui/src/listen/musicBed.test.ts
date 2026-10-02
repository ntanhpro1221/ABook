import { describe, expect, it } from "vitest";
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
