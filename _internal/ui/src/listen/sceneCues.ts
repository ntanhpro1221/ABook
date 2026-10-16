import type { MusicCue } from "./musicBed";
import type { Script } from "./model";
import { estimatedStarts, estimateSeconds } from "./readAloud";

// Nhạc nền THEO CẢNH của sách chỉ có chữ (webui/music_nnscene.py). Máy chủ dựng mốc theo giây ƯỚC của kế hoạch (music_scenes._durations), mốc mở một cảnh
// mang `firstSegment` = mã đoạn của màn đọc nơi cảnh bắt đầu. Nghe ngay đọc to theo đồng hồ ảo của bộ máy đọc (readAloud.ts): đoạn nào cũng có giây bắt đầu
// (ước, rồi thật khi clip về). Ở đây mốc được đặt lại để bài đổi đúng lúc ĐOẠN ĐẦU CẢNH BẮT ĐẦU PHÁT - không giữa câu, không cần ước giây chính xác -
// còn mốc nối bài anh em và bước âm lượng trong cảnh co giãn theo các mốc đoạn ấy. Phần còn lại (mờ chéo, lặp, nhảy) là của MusicBed như sách Studio.

/** Giây bắt đầu từng đoạn của kịch bản (đồng hồ của bộ máy đọc) và tổng độ dài. Kịch bản đã có mốc thì dùng mốc; chưa thì ước như bộ máy sẽ ước. */
export function segmentStarts(script: Script): { starts: number[]; total: number } {
  const segments = script.segments;
  if (script.timed && segments.every((segment) => typeof segment.start === "number")) {
    const starts = segments.map((segment) => segment.start as number);
    const last = segments[segments.length - 1];
    return { starts, total: Math.max(script.duration, (last?.end as number | null) ?? 0, starts[starts.length - 1] ?? 0) };
  }
  const starts = estimatedStarts(segments);
  const last = segments[segments.length - 1];
  return { starts, total: last ? starts[starts.length - 1] + estimateSeconds(last.text) : 0 };
}

/** Hàm co giãn giây ước -> giây của đồng hồ đọc, tuyến tính từng khúc qua các mốc (giây ước mở cảnh, giây bắt đầu đoạn đầu cảnh). Ngoài khúc cuối thì dịch theo. */
export function warpOf(anchors: { est: number; real: number }[]): (est: number) => number {
  const points: { est: number; real: number }[] = [{ est: 0, real: 0 }];
  for (const anchor of [...anchors].sort((a, b) => a.est - b.est)) {
    const last = points[points.length - 1];
    if (anchor.est <= last.est) {
      if (anchor.est === last.est) last.real = Math.max(last.real, anchor.real);
      continue;
    }
    points.push({ est: anchor.est, real: Math.max(anchor.real, last.real) });
  }
  return (est) => {
    if (est <= 0) return Math.max(0, est);
    let at = 0;
    while (at + 1 < points.length && points[at + 1].est <= est) at += 1;
    const from = points[at];
    const to = points[at + 1];
    if (!to) return from.real + (est - from.est);
    return from.real + ((est - from.est) / (to.est - from.est)) * (to.real - from.real);
  };
}

/** Mốc của máy chủ có mốc mở cảnh nào mang `firstSegment` không (nhạc theo cảnh), hay chỉ là mốc giây thật của sách Studio. */
export function isSceneCues(cues: MusicCue[]): boolean {
  return cues.some((cue) => typeof cue.firstSegment === "number");
}

/** Đặt mốc theo đồng hồ đọc: mốc mở cảnh bắt đầu đúng lúc đoạn `firstSegment` bắt đầu phát; mọi giây khác trong mốc (kết, bước âm lượng, mốc nối bài
 *  anh em) co theo. `estSeconds`: độ dài chương theo giây ước của máy chủ. */
export function anchorSceneCues(cues: MusicCue[], estSeconds: number, script: Script): MusicCue[] {
  const { starts, total } = segmentStarts(script);
  if (!starts.length) return [];
  const anchors = cues.flatMap((cue) =>
    typeof cue.firstSegment === "number" && cue.firstSegment >= 0 && cue.firstSegment < starts.length ? [{ est: cue.start, real: starts[cue.firstSegment] }] : [],
  );
  const end = Math.max(estSeconds, ...cues.map((cue) => cue.end));
  const warp = warpOf([...anchors, { est: end, real: Math.max(total, anchors.length ? anchors[anchors.length - 1].real : 0) }]);
  return cues.map((cue) => ({
    ...cue,
    start: warp(cue.start),
    end: warp(cue.end),
    ...(cue.steps ? { steps: cue.steps.map((step) => ({ ...step, at: warp(step.at) })) } : {}),
  }));
}

/** Chỉ giữ nhạc từ đoạn `index` trở đi (đã đặt theo đồng hồ đọc): mốc kết trước đó bỏ, mốc chứa chỗ ấy bắt đầu đúng ở đầu đoạn `index`. Mốc tới muộn - chương
 *  dựng xong khi giọng đã đọc dở - nhờ đây vào ở đầu câu kế, không xen giữa câu. */
export function fromSegment(cues: MusicCue[], script: Script, index: number): MusicCue[] {
  if (index <= 0) return cues;
  const { starts } = segmentStarts(script);
  const at = starts[index];
  if (at === undefined) return [];
  return cues.filter((cue) => cue.end > at).map((cue) => (cue.start < at ? { ...cue, start: at } : cue));
}

/** Chỉ số đoạn đầu tiên bắt đầu SAU giây `time` của đồng hồ đọc (câu kế), hay `starts.length` khi đang ở đoạn cuối. */
export function nextSegment(script: Script, time: number): number {
  const { starts } = segmentStarts(script);
  const found = starts.findIndex((start) => start > time + 1e-6);
  return found < 0 ? starts.length : found;
}

/** Bộ nhận mốc theo cảnh của một chương, đưa cho MusicBed. Giữ mốc thô của máy chủ rồi đặt lại mỗi khi kịch bản có giây mới (clip về) hay người nghe nhảy. */
export class SceneCues {
  private raw: MusicCue[] = [];
  private estSeconds = 0;
  private levelDb: number | undefined;
  /** Đoạn đầu tiên nhạc được phép vào (0 = từ đầu chương): mốc tới giữa chừng chờ câu kế. */
  private floor = 0;

  constructor(
    private readonly bed: { setCues(cues: MusicCue[], levelDb?: number, seconds?: number): void },
    private readonly script: () => Script | undefined,
  ) {}

  /** Chương khác: quên mốc cũ. */
  reset(): void {
    this.raw = [];
    this.floor = 0;
  }

  /** Mốc của chương vừa về lúc giọng đang ở giây `time`: nhạc vào ở đầu câu kế (không giữa câu). */
  arrive(cues: MusicCue[], estSeconds: number, levelDb: number | undefined, time: number): void {
    this.raw = cues;
    this.estSeconds = estSeconds;
    this.levelDb = levelDb;
    const script = this.script();
    this.floor = script && time > 0.25 ? nextSegment(script, time) : 0;
    this.push(time);
  }

  /** Kịch bản có giây mới (clip về, đổi giọng): đặt lại mốc cho khớp. */
  refresh(time: number): void {
    if (this.raw.length) this.push(time);
  }

  /** Người nghe nhảy tới giây `time`: về trước chỗ nhạc được phép vào thì nhạc theo cảnh chứa chỗ mới, như sách Studio. */
  seeked(time: number): void {
    const script = this.script();
    if (!this.raw.length || !script || this.floor === 0) return;
    const { starts } = segmentStarts(script);
    if (time < (starts[this.floor] ?? Infinity)) {
      this.floor = 0;
      this.push(time);
    }
  }

  private push(time: number): void {
    const script = this.script();
    if (!script || !script.segments.length) return;
    const placed = fromSegment(anchorSceneCues(this.raw, this.estSeconds, script), script, this.floor);
    this.bed.setCues(placed, this.levelDb, time);
  }
}
