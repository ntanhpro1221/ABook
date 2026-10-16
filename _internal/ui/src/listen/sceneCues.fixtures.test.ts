import { describe, expect, it } from "vitest";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { MusicCue } from "./musicBed";
import type { Script, ScriptSegment } from "./model";
import { SceneCues, anchorSceneCues, fromSegment, nextSegment, segmentStarts } from "./sceneCues";

// Bộ ví dụ chung cho phần đặt mốc nhạc theo cảnh: bản TS (sceneCues.ts) và bản Kotlin (SceneAnchor.kt, SceneAnchorTest) phải ra GIỐNG HỆT trên các file này
// (tests/fixtures/music/anchor/*.json, mọi chữ và mọi con số tự dựng). Chạy thường: so kết quả của sceneCues.ts với file. Muốn sinh lại sau khi đổi ví dụ hay đổi
// sceneCues.ts: WRITE_ANCHOR_FIXTURES=1 npx vitest run src/listen/sceneCues.fixtures.test.ts (rồi chạy SceneAnchorTest để chắc bản Kotlin còn khớp).
//
// Mỗi file: một chương (`script` = các đoạn của màn đọc, `cues` = mốc thô của máy theo giây ước, `estSeconds`) và
//  - `timing`: giây bắt đầu từng đoạn + tổng độ dài mà segmentStarts cho ra (đồng hồ đọc; Kotlin nhận thẳng, nó lấy từ ReadAloud.segmentTiming);
//  - `anchored`: anchorSceneCues; `from`: fromSegment cho vài chỉ số đoạn; `next`: nextSegment cho vài giây;
//  - `events`: chuỗi arrive / refresh / seeked của SceneCues, mỗi bước ghi mốc nó đặt (`set`) hay null nếu không đặt gì.

const FOLDER = fileURLToPath(new URL("../../../tests/fixtures/music/anchor/", import.meta.url));
const WRITE = process.env.WRITE_ANCHOR_FIXTURES === "1";

type Raw = Omit<MusicCue, "src">;

interface Seg {
  text: string;
  kind?: string;
  sceneBreak?: boolean;
  /** Giây thật (start, end) nếu đoạn đã đọc. */
  real?: [number, number];
}

interface Scenario {
  description: string;
  segments: Seg[];
  /** true: kịch bản có mốc cho MỌI đoạn (đoạn chưa đọc mang giây ước, như đồng hồ ảo của lõi native). false: chưa có mốc nào, đồng hồ ước thuần. */
  timed: boolean;
  duration?: number;
  cues: Raw[];
  estSeconds: number;
  from: number[];
  next: number[];
  events: Event[];
}

type Event =
  | { op: "arrive"; time: number; /** Kịch bản đổi sang bản này trước bước (đoạn đã đọc thêm). */ segments?: Seg[]; timed?: boolean }
  | { op: "refresh"; segments?: Seg[]; timed?: boolean }
  | { op: "seeked"; time: number };

const LONG = "Một đoạn chữ khá dài để người đọc phải mất vài giây mới đọc xong, câu này dài thêm chút nữa.";
const MID = "Một đoạn chữ vừa phải để đọc.";
const SHORT = "Ừ.";

function segmentOf(index: number, seg: Seg): ScriptSegment {
  return {
    id: index, paragraph: index, text: seg.text, kind: seg.kind ?? "narration", speaker: "NARRATOR",
    start: seg.real ? seg.real[0] : null, end: seg.real ? seg.real[1] : null, status: "pending", ...(seg.sceneBreak ? { sceneBreak: true } : {}),
  };
}

/** Kịch bản từ các đoạn: đoạn có giây thật thì dùng, `timed` thì đoạn chưa đọc nhận giây ước nối tiếp (như đồng hồ ảo của lõi native). */
function scriptOf(segments: Seg[], timed: boolean, duration?: number): Script {
  const built = segments.map((seg, index) => segmentOf(index, seg));
  if (timed) {
    let at = 0;
    segments.forEach((seg, index) => {
      if (seg.real) {
        built[index].start = seg.real[0];
        built[index].end = seg.real[1];
      } else {
        built[index].start = at;
        built[index].end = at + estimate(seg);
      }
      at = built[index].end as number;
    });
  }
  const last = built[built.length - 1];
  return { chapterId: 1, title: "T", timed, duration: duration ?? (timed ? ((last?.end as number | null) ?? 0) : 0), segments: built };
}

/** Giây ước của một đoạn chưa đọc (CHARS_PER_SECOND = 14, tối thiểu 0,6; dòng ngăn cảnh là quãng lặng cố định). */
function estimate(seg: Seg): number {
  if (seg.sceneBreak) return 1.4;
  return Math.max(0.6, seg.text.length / 14);
}

function scenarios(): Record<string, Scenario> {
  const eight: Seg[] = [LONG, MID, SHORT, LONG, LONG, MID, SHORT, LONG].map((text) => ({ text }));
  return {
    estimated_only: {
      description: "Chương chưa có clip nào: đồng hồ ước thuần (segmentStarts ước như bộ máy sẽ ước). Ba cảnh, một mốc nối bài anh em, một bước âm lượng, một mốc tail.",
      segments: eight,
      timed: false,
      cues: [
        { start: 0, end: 120, link: "https://x/a.mp3", key: "1:0", firstSegment: 0 },
        { start: 120, end: 210, link: "https://x/b.mp3", key: "1:1", firstSegment: 3, steps: [{ at: 150, db: -3 }, { at: 190, db: 0 }] },
        { start: 210, end: 260, link: "https://x/c.mp3", key: "1:1", sibling: true },
        { start: 260, end: 340, link: "https://x/d.mp3", key: "1:2", firstSegment: 6, tail: true },
      ],
      estSeconds: 340,
      from: [0, 1, 3, 6, 7, 8, 40],
      next: [-1, 0, 4.2, 19.5, 1000],
      events: [{ op: "arrive", time: 0 }, { op: "refresh" }],
    },
    partial_real: {
      description: "Bốn đoạn đầu đã đọc (giây thật, lệch ước), bốn đoạn sau còn ước nối tiếp - đồng hồ ảo của lõi native lúc đang nghe. Clip về thêm thì refresh đặt lại.",
      segments: [
        { text: LONG, real: [0, 4.1] },
        { text: MID, real: [4.1, 6.9] },
        { text: SHORT, real: [6.9, 7.5] },
        { text: LONG, real: [7.5, 13.2] },
        ...[LONG, MID, SHORT, LONG].map((text) => ({ text })),
      ],
      timed: true,
      cues: [
        { start: 0, end: 90, link: "https://x/a.mp3", key: "1:0", firstSegment: 0 },
        { start: 90, end: 200, link: "https://x/b.mp3", key: "1:1", firstSegment: 3, steps: [{ at: 120, db: -4.5 }] },
        { start: 200, end: 330, link: "https://x/c.mp3", key: "1:2", firstSegment: 5 },
      ],
      estSeconds: 330,
      from: [0, 3, 4, 5, 7],
      next: [0, 6.9, 7.5, 13.2, 14],
      events: [
        { op: "arrive", time: 3.3 },
        {
          op: "refresh",
          segments: [
            { text: LONG, real: [0, 4.1] },
            { text: MID, real: [4.1, 6.9] },
            { text: SHORT, real: [6.9, 7.5] },
            { text: LONG, real: [7.5, 13.2] },
            { text: LONG, real: [13.2, 20.45] },
            { text: MID, real: [20.45, 23.3] },
            ...[SHORT, LONG].map((text) => ({ text })),
          ],
          timed: true,
        },
      ],
    },
    arrives_mid_chapter: {
      description: "Mốc về khi giọng đã đọc dở (fromSegment / nextSegment): nhạc vào ở đầu câu kế; sau đó tua về trước chỗ ấy thì nhạc theo cảnh chứa chỗ mới.",
      segments: [
        { text: LONG, real: [0, 5] },
        { text: MID, real: [5, 8] },
        { text: LONG, real: [8, 14] },
        { text: LONG, real: [14, 20] },
        { text: MID, real: [20, 23] },
        { text: SHORT, real: [23, 24] },
        { text: LONG, real: [24, 30] },
      ],
      timed: true,
      cues: [
        { start: 0, end: 60, link: "https://x/a.mp3", key: "1:0", firstSegment: 0 },
        { start: 60, end: 130, link: "https://x/b.mp3", key: "1:1", firstSegment: 2, steps: [{ at: 100, db: -2 }] },
        { start: 130, end: 160, link: "https://x/c.mp3", key: "1:1", sibling: true },
        { start: 160, end: 220, link: "https://x/d.mp3", key: "1:2", firstSegment: 5, tail: true },
      ],
      estSeconds: 220,
      from: [0, 1, 2, 3, 4, 5, 6, 7],
      next: [0, 4.9999999, 5, 5.0000001, 16, 29.9, 30],
      events: [
        { op: "arrive", time: 16.5 },
        { op: "seeked", time: 30 },
        { op: "seeked", time: 6 },
        { op: "seeked", time: 2 },
        { op: "refresh" },
      ],
    },
    first_segment_out_of_range: {
      description: "firstSegment vượt số đoạn, âm, thiếu; mọi mốc ngoài khoảng thì không neo được: chỉ còn mốc cuối chương. Hai mốc trỏ cùng một đoạn, một mốc trỏ lùi (không lùi giây).",
      segments: eight,
      timed: false,
      cues: [
        { start: 0, end: 50, link: "https://x/a.mp3", key: "1:0", firstSegment: 0 },
        { start: 50, end: 90, link: "https://x/b.mp3", key: "1:1", firstSegment: 99 },
        { start: 90, end: 140, link: "https://x/c.mp3", key: "1:2", firstSegment: -1 },
        { start: 140, end: 200, link: "https://x/d.mp3", key: "1:3" },
        { start: 200, end: 250, link: "https://x/e.mp3", key: "1:4", firstSegment: 5 },
        { start: 250, end: 300, link: "https://x/f.mp3", key: "1:5", firstSegment: 5 },
        { start: 300, end: 320, link: "https://x/g.mp3", key: "1:6", firstSegment: 2 },
        { start: 320, end: 400, link: "https://x/h.mp3", key: "1:7", firstSegment: 8 },
      ],
      estSeconds: 400,
      from: [0, 2, 5, 8, 9],
      next: [0, 3, 50, 99],
      events: [{ op: "arrive", time: 0 }],
    },
    breaks_and_headings: {
      description: "Chương có tiêu đề và dòng ngăn cảnh (đoạn lặng cố định): cảnh bắt đầu ở đúng đoạn tiêu đề / ngăn cảnh; giây của các đoạn lặng nằm trong đồng hồ.",
      segments: [
        { text: "Chương một", kind: "heading" },
        { text: LONG },
        { text: MID },
        { text: "***", sceneBreak: true },
        { text: LONG },
        { text: "***", sceneBreak: true },
        { text: "Hai ngày sau", kind: "heading" },
        { text: MID },
        { text: LONG },
      ],
      timed: false,
      cues: [
        { start: 0, end: 70, link: "https://x/a.mp3", key: "1:0", firstSegment: 0 },
        { start: 70, end: 100, link: "https://x/b.mp3", key: "1:1", firstSegment: 3 },
        { start: 100, end: 190, link: "https://x/c.mp3", key: "1:2", firstSegment: 6, steps: [{ at: 140, db: -6 }] },
      ],
      estSeconds: 190,
      from: [0, 3, 4, 5, 6, 8],
      next: [0, 1, 2.5, 100],
      events: [{ op: "arrive", time: 9.5 }, { op: "refresh" }, { op: "seeked", time: 1 }],
    },
    no_segments: {
      description: "Màn đọc chưa có đoạn nào: không neo được gì, SceneCues không đặt mốc.",
      segments: [],
      timed: false,
      cues: [{ start: 0, end: 60, link: "https://x/a.mp3", key: "1:0", firstSegment: 0 }],
      estSeconds: 60,
      from: [0, 1],
      next: [0],
      events: [{ op: "arrive", time: 0 }, { op: "refresh" }, { op: "seeked", time: 3 }],
    },
  };
}

interface Recorded {
  timing: { starts: number[]; total: number };
  anchored: MusicCue[];
  from: Record<string, MusicCue[]>;
  next: Record<string, number>;
  /** `timing`: đồng hồ đọc ngay trước bước (sau khi kịch bản đổi, nếu bước đổi nó) - bản Kotlin đặt nó làm đồng hồ hiện tại. */
  events: { op: string; timing: { starts: number[]; total: number }; set: MusicCue[] | null }[];
}

function run(scenario: Scenario): Recorded {
  let script = scriptOf(scenario.segments, scenario.timed, scenario.duration);
  const cues = scenario.cues as MusicCue[];
  const timing = segmentStarts(script);
  const anchored = anchorSceneCues(cues, scenario.estSeconds, script);
  const from = Object.fromEntries(scenario.from.map((index) => [String(index), fromSegment(anchored, script, index)]));
  const next = Object.fromEntries(scenario.next.map((time) => [String(time), nextSegment(script, time)]));
  let set: MusicCue[] | null = null;
  const scene = new SceneCues({ setCues: (placed) => void (set = placed) }, () => script);
  const events = scenario.events.map((event) => {
    set = null;
    if (event.op !== "seeked" && event.segments) script = scriptOf(event.segments, event.timed ?? scenario.timed);
    if (event.op === "arrive") scene.arrive(cues, scenario.estSeconds, undefined, event.time);
    else if (event.op === "refresh") scene.refresh(0);
    else scene.seeked(event.time);
    return { op: event.op, timing: segmentStarts(script), set };
  });
  return { timing, anchored, from, next, events };
}

function fixtureOf(name: string, scenario: Scenario) {
  return { name, ...scenario, script: scriptOf(scenario.segments, scenario.timed, scenario.duration), expected: run(scenario) };
}

describe("nhạc theo cảnh: bộ ví dụ chung với bản Kotlin", () => {
  for (const [name, scenario] of Object.entries(scenarios())) {
    it(name, () => {
      const fixture = JSON.parse(JSON.stringify(fixtureOf(name, scenario)));
      const file = `${FOLDER}${name}.json`;
      if (WRITE) {
        mkdirSync(FOLDER, { recursive: true });
        writeFileSync(file, JSON.stringify(fixture, null, 1) + "\n");
      }
      expect(existsSync(file)).toBe(true);
      expect(JSON.parse(readFileSync(file, "utf8"))).toEqual(fixture);
      // Sanity: ví dụ không rỗng ý nghĩa (mốc được neo) trừ ca không có đoạn nào.
      if (scenario.segments.length) expect(fixture.expected.anchored.length).toBe(scenario.cues.length);
    });
  }

  it("không file thừa trong thư mục ví dụ", () => {
    const names = Object.keys(scenarios()).map((name) => `${name}.json`).sort();
    expect(readdirSync(FOLDER).filter((file) => file.endsWith(".json")).sort()).toEqual(names);
  });
});
