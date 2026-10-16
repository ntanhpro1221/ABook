import { describe, expect, it } from "vitest";
import { MusicBed, type MusicCue } from "./musicBed";
import type { Script, ScriptSegment } from "./model";
import { SCENE_RETRY_MS, SceneCues, anchorSceneCues, fromSegment, isSceneCues, nextSegment, sceneRetryDelay, segmentStarts, warpOf } from "./sceneCues";

function segment(id: number, start: number | null, end: number | null, text = "Một đoạn chữ vừa đủ dài để đọc."): ScriptSegment {
  return { id, paragraph: id, text, kind: "narration", speaker: "NARRATOR", start, end, status: "pending" };
}

/** Chương 5 đoạn đã có giây thật: 0, 5, 12, 20, 31 (hết ở 40). */
const timed: Script = {
  chapterId: 1,
  title: "T",
  timed: true,
  duration: 40,
  segments: [segment(0, 0, 5), segment(1, 5, 12), segment(2, 12, 20), segment(3, 20, 31), segment(4, 31, 40)],
};

// Giây ƯỚC của máy chủ: cảnh A đoạn 0 (0-100), cảnh B đoạn 2 (100-250, có mốc nối bài anh em ở 170), cảnh C đoạn 4 (250-300).
const cues: MusicCue[] = [
  { start: 0, end: 100, link: "a", key: "1:0", src: "/a", firstSegment: 0 },
  { start: 100, end: 170, link: "b", key: "1:1", src: "/b", firstSegment: 2, steps: [{ at: 135, db: -3 }] },
  { start: 170, end: 250, link: "b2", key: "1:1", src: "/b2", sibling: true },
  { start: 250, end: 300, link: "c", key: "1:2", src: "/c", firstSegment: 4 },
];

function fakeBed() {
  return new MusicBed(() => {
    const fake = { paused: true, volume: 0, loop: false, currentTime: 0, duration: 200 };
    return Object.assign(fake, {
      play: () => {
        fake.paused = false;
        return Promise.resolve();
      },
      pause: () => {
        fake.paused = true;
      },
      addEventListener: () => undefined,
    });
  });
}

describe("nhạc theo cảnh: mốc theo đồng hồ đọc", () => {
  it("co giãn tuyến tính từng khúc qua các mốc, dịch theo ở ngoài khúc cuối", () => {
    const warp = warpOf([{ est: 100, real: 12 }, { est: 250, real: 31 }]);
    expect([warp(0), warp(100), warp(250)]).toEqual([0, 12, 31]);
    expect(warp(50)).toBeCloseTo(6);
    expect(warp(175)).toBeCloseTo(21.5);
    expect(warp(260)).toBe(41);
    expect(warpOf([{ est: 10, real: 5 }, { est: 20, real: 2 }])(20)).toBe(5); // không lùi
  });

  it("mốc mở cảnh bắt đầu đúng giây đoạn đầu cảnh; mốc anh em và bước âm lượng co theo", () => {
    expect(isSceneCues(cues)).toBe(true);
    expect(isSceneCues(cues.map(({ firstSegment: _, ...cue }) => cue))).toBe(false);
    const placed = anchorSceneCues(cues, 300, timed);
    expect(placed.map((cue) => [cue.link, cue.start])).toEqual([["a", 0], ["b", 12], ["b2", expect.closeTo(20.87, 1)], ["c", 31]]);
    expect(placed[0].end).toBe(12);
    expect(placed[3].end).toBe(40);
    expect(placed[1].steps?.[0].at).toBeGreaterThan(12);
    expect(placed[1].steps?.[0].at).toBeLessThan(placed[1].end);
    expect(placed.every((cue, i) => i === 0 || cue.start >= placed[i - 1].start)).toBe(true);
  });

  it("kịch bản chưa có mốc thì dùng giây ước của bộ máy đọc", () => {
    const untimed: Script = { ...timed, timed: false, duration: 0, segments: timed.segments.map((s) => ({ ...s, start: null, end: null })) };
    const { starts, total } = segmentStarts(untimed);
    expect(starts[0]).toBe(0);
    expect(starts).toEqual([...starts].sort((a, b) => a - b));
    expect(total).toBeGreaterThan(starts[4]);
    expect(anchorSceneCues(cues, 300, untimed)[1].start).toBe(starts[2]);
  });

  it("bài đổi khi đoạn đầu cảnh bắt đầu phát, không giữa câu; nhảy thì về cảnh chứa chỗ mới", () => {
    const bed = fakeBed();
    bed.setCues(anchorSceneCues(cues, 300, timed), -20);
    bed.sync(0, true);
    expect(bed.activeLink).toBe("a");
    bed.sync(11.9, true);
    expect(bed.activeLink).toBe("a");
    bed.sync(12.0, true);
    expect(bed.activeLink).toBe("b");
    bed.sync(31.5, true);
    expect(bed.activeLink).toBe("c");
    bed.sync(3, true, true);
    expect(bed.activeLink).toBe("a");
    bed.sync(25, true, true);
    expect(bed.activeLink).toBe("b2");
    bed.stop();
  });

  it("giữ nhạc từ một đoạn trở đi: mốc chứa chỗ ấy bắt đầu ở đầu đoạn", () => {
    const placed = anchorSceneCues(cues, 300, timed);
    expect(fromSegment(placed, timed, 0)).toBe(placed);
    const later = fromSegment(placed, timed, 3);
    expect(later.map((cue) => [cue.link, cue.start])).toEqual([["b", 20], ["b2", expect.closeTo(20.87, 1)], ["c", 31]]);
    expect(fromSegment(placed, timed, 9)).toEqual([]);
    expect(nextSegment(timed, 7)).toBe(2);
    expect(nextSegment(timed, 12)).toBe(3);
    expect(nextSegment(timed, 35)).toBe(5);
  });

  it("mốc tới muộn (chương dựng xong khi giọng đã đọc dở) vào ở đầu câu kế; nhảy về trước thì như thường", () => {
    const bed = fakeBed();
    const scene = new SceneCues(bed, () => timed);
    scene.arrive(cues, 300, -20, 7); // đang ở giây 7 (đoạn 1): câu kế bắt đầu ở 12
    bed.sync(7, true);
    expect(bed.activeLink).toBeNull();
    bed.sync(11.9, true);
    expect(bed.activeLink).toBeNull();
    bed.sync(12.1, true);
    expect(bed.activeLink).toBe("b");
    scene.seeked(2);
    bed.sync(2, true, true);
    expect(bed.activeLink).toBe("a");
    bed.stop();
  });

  it("giây thật của đoạn về sau thì mốc dịch theo, bài đang phát không bắt đầu lại", () => {
    const bed = fakeBed();
    let script = timed;
    const scene = new SceneCues(bed, () => script);
    scene.arrive(cues, 300, -20, 0);
    bed.sync(14, true);
    expect(bed.activeLink).toBe("b");
    script = { ...timed, duration: 43, segments: timed.segments.map((s, i) => (i < 3 ? s : { ...s, start: (s.start ?? 0) + 3, end: (s.end ?? 0) + 3 })) };
    scene.refresh(14);
    bed.sync(14.5, true);
    expect(bed.activeLink).toBe("b");
    bed.sync(33, true);
    expect(bed.activeLink).toBe("b2");
    bed.sync(34.5, true);
    expect(bed.activeLink).toBe("c");
    bed.stop();
  });

  it("chưa có kịch bản thì chưa đặt mốc nào, có rồi thì đặt khi làm mới", () => {
    const bed = fakeBed();
    let script: Script | undefined;
    const scene = new SceneCues(bed, () => script);
    scene.arrive(cues, 300, -20, 0);
    bed.sync(1, true);
    expect(bed.activeLink).toBeNull();
    script = timed;
    scene.refresh(1);
    bed.sync(1, true);
    expect(bed.activeLink).toBe("a");
    bed.stop();
  });
});

describe("hỏi lại mốc nhạc theo cảnh khi chương trả 'chưa có' (soát a47 mục 7)", () => {
  it("lùi dần, có hạn: không dồn lượt hỏi và không hỏi mãi", () => {
    expect(sceneRetryDelay(0)).toBe(SCENE_RETRY_MS[0]);
    const delays = SCENE_RETRY_MS;
    for (let i = 1; i < delays.length; i += 1) expect(delays[i]).toBeGreaterThan(delays[i - 1]);
    expect(delays[0]).toBeGreaterThanOrEqual(10_000);
    expect(sceneRetryDelay(delays.length)).toBeNull();
  });
});
