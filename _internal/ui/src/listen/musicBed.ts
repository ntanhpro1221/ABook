// Lớp nhạc nền của trình phát máy tính: một (hai, khi chuyển cảnh) <audio> chạy song song với giọng đọc, theo các MỐC
// nhạc của chương (GET /api/books/<id>/music/chapters/<n> - webui/music_plan.py). Nhạc nền không cần khớp từng mili-giây
// như lời thoại với hình: chỉ cần đổi đúng bài khi sang đoạn mới, chuyển mờ dần, lặp liền, dừng / chạy theo giọng đọc,
// nhảy đúng chỗ khi người nghe tua. Âm lượng = âm lượng người nghe x `gainDb` của mốc (máy chủ tính từ `levelDb` = nhạc
// thấp hơn giọng bao nhiêu LU, độ to và độ lấn dải tiếng nói của từng bài - Pha 4 của docs/MUSIC_RESEARCH.md).
// Android: MusicBed.kt, cùng quy tắc.

export interface MusicCue {
  start: number;
  end: number;
  link: string;
  key: string;
  src: string;
  /** Độ khuếch đại (dB, <= 0) máy chủ đã tính cho bài này để nó nằm `levelDb` LU dưới giọng (music_plan.cue_gain_db):
   *  trình phát chỉ áp con số này, không tự tính. Thiếu (máy chủ cũ) -> mức chung `levelDb` của cuốn như trước. */
  gainDb?: number;
  /** Bước âm lượng trong cảnh (music_plan.chapter_cues): từ giây `at` của chương, mức là `gainDb + db` (dB, vẫn <= 0). Máy chủ
   *  tính, trình phát chỉ cộng; đổi bước thì trượt dần STEP_RAMP_SECONDS, tua thì vào thẳng mức tại chỗ tua. */
  steps?: MusicStep[];
  /** Mốc nối bài anh em ở điểm kết bài trong cùng cảnh: mờ chéo dài SIBLING_FADE_SECONDS, bài cũ chơi nốt phần còn lại rồi
   *  thôi (không quay lại đầu bài). */
  sibling?: boolean;
}

export interface MusicStep {
  at: number;
  db: number;
}

/** Ghi công tác giả một bài (CC BY đòi nêu tên ở nơi nhạc phát) - khoá theo `link` của mốc. */
export interface MusicCredit {
  title?: string;
  creator?: string;
  attribution?: string;
  landing?: string;
  license?: string;
  licenseUrl?: string;
}

/** MusicTab phát khi người dùng sửa / chọn lại nhạc của một cuốn (detail = mã sách): trình phát đang mở nạp lại mốc nhạc. */
export const MUSIC_CHANGED_EVENT = "abook:music-changed";

type BedAudio = Pick<HTMLAudioElement, "play" | "pause" | "paused" | "volume" | "loop" | "currentTime" | "duration"> & {
  /** `error`: bài không tải được (mất mạng, máy chủ không phát được). */
  addEventListener(type: "loadedmetadata" | "error", listener: () => void, options?: { once?: boolean }): void;
  /** Bài không lặp (bài cũ khi nối bài anh em) đã chơi hết: không phát lại. */
  readonly ended?: boolean;
};

/** <audio> thật; ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như engine.ts, clip.tsx). */
function browserAudio(src: string): BedAudio {
  const audio = new Audio(src);
  audio.muted = new URLSearchParams(window.location.search).get("mute") === "1";
  audio.preload = "auto";
  return audio;
}

const FADE_SECONDS = 2;
export const SIBLING_FADE_SECONDS = 6;
export const STEP_RAMP_SECONDS = 4;
const STEP_MS = 50;
/** Bài tải hỏng (mất mạng): đoạn của nó im lặng, chừng ấy sau mới thử lại - như RETRY_MS của MusicBed.kt. */
export const RETRY_MS = 5 * 60_000;

function cueAt(cues: MusicCue[], seconds: number): MusicCue | null {
  return cues.find((cue) => seconds >= cue.start && seconds < cue.end) ?? null;
}

/** Mức bước (dB) của mốc tại giây `seconds` của chương: bước cuối cùng đã tới, chưa tới bước nào thì 0. */
export function stepDbAt(cue: MusicCue, seconds: number): number {
  let db = 0;
  for (const step of cue.steps ?? []) {
    if (seconds < step.at) break;
    db = step.db;
  }
  return db;
}

interface Playing {
  cue: MusicCue;
  audio: BedAudio;
  /** Âm lượng đang hướng tới, và mỗi nhịp STEP_MS nhích bao nhiêu. */
  goal: number;
  perTick: number;
  /** Đang mờ vào (bài mới): tua lúc này không nhảy thẳng tới mức. */
  entering: boolean;
}

export class MusicBed {
  constructor(private readonly createAudio: (src: string) => BedAudio = browserAudio) {}

  private cues: MusicCue[] = [];
  private gain = 0.1;
  private userVolume = 1;
  private playing = false;
  private current: Playing | null = null;
  private fading: BedAudio[] = [];
  // âm lượng bớt mỗi nhịp khi mờ đi: bài to và bài nhỏ cùng tắt trong FADE_SECONDS (SIBLING_FADE_SECONDS khi nối bài anh em)
  private fadeStep = new WeakMap<BedAudio, number>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastTime = 0;
  private listeners = new Set<(link: string | null) => void>();
  private announced: string | null = null;
  // Bài không phát được (`link` của mốc) -> lúc được thử lại (Date.now()); tải được thì xoá.
  private failed = new Map<string, number>();

  setCues(cues: MusicCue[], levelDb: number): void {
    this.cues = cues;
    this.gain = Math.pow(10, levelDb / 20);
    this.switchTo(this.playableAt(this.lastTime), this.lastTime);
  }

  setVolume(volume: number): void {
    this.userVolume = Math.max(0, Math.min(1, volume));
    if (this.current) this.current.audio.volume = this.current.goal = this.target();
  }

  /** Gọi mỗi khi thời gian giọng đọc đổi (`seeked` = người nghe vừa tua). */
  sync(seconds: number, playing: boolean, seeked = false): void {
    this.lastTime = seconds;
    this.playing = playing;
    // Mốc của bài vừa tải hỏng tính như khoảng không nhạc; tới hạn thử lại thì lần đồng bộ này vào bài như mốc mới.
    const cue = this.playableAt(seconds);
    const current = this.current?.cue;
    // Mốc anh em có thể cùng khoá đoạn với mốc trước (nối giữa một đoạn): phân biệt bằng cả giây bắt đầu.
    if (cue?.key !== current?.key || cue?.start !== current?.start || (seeked && cue)) {
      this.switchTo(cue, seconds);
    }
    this.retarget(seeked);
    for (const audio of [this.current?.audio, ...this.fading]) {
      if (!audio) continue;
      if (playing && audio.paused && !audio.ended) void audio.play().catch(() => undefined);
      if (!playing && !audio.paused) audio.pause();
    }
  }

  /** Bài đang phát (null = im lặng) - cho giao diện và bài thử. */
  get activeLink(): string | null {
    return this.current?.cue.link ?? null;
  }

  /** Báo mỗi khi bài đang phát đổi (kể cả thành im lặng = null): giao diện vẽ dòng ghi công theo đó. */
  onActiveChange(listener: (link: string | null) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  stop(): void {
    for (const audio of [this.current?.audio, ...this.fading]) audio?.pause();
    this.current = null;
    this.fading = [];
    this.cues = [];
    this.failed.clear();
    this.emitActive();
  }

  /** Mốc tại giây `seconds`, trừ khi bài của nó đang chờ thử lại; bài đã tới hạn thì bỏ khỏi danh sách hỏng. */
  private playableAt(seconds: number): MusicCue | null {
    const cue = cueAt(this.cues, seconds);
    if (!cue) return null;
    const retryAt = this.failed.get(cue.link);
    if (retryAt === undefined) return cue;
    if (retryAt > Date.now()) return null;
    this.failed.delete(cue.link);
    return cue;
  }

  /** Bài `audio` của mốc `cue` không tải được: đoạn của nó im lặng, RETRY_MS sau mới thử lại. */
  private drop(cue: MusicCue, audio: BedAudio): void {
    this.failed.set(cue.link, Date.now() + RETRY_MS);
    audio.pause();
    this.fading = this.fading.filter((other) => other !== audio);
    if (this.current?.audio !== audio) return;
    this.current = null;
    this.emitActive();
  }

  private emitActive(): void {
    const link = this.activeLink;
    if (link === this.announced) return;
    this.announced = link;
    for (const listener of [...this.listeners]) listener(link);
  }

  /** Âm lượng mục tiêu của bài đang phát: gainDb của chính mốc (bài to / nhỏ khác nhau) cộng bước đang hiệu lực; không có
   *  gainDb thì mức chung. */
  private target(cue: MusicCue | undefined = this.current?.cue): number {
    const gainDb = cue?.gainDb;
    const step = cue ? stepDbAt(cue, this.lastTime) : 0;
    const gain = typeof gainDb === "number" && Number.isFinite(gainDb)
      ? Math.pow(10, Math.min(0, gainDb + step) / 20)
      : this.gain * Math.pow(10, step / 20);
    return Math.min(1, gain * this.userVolume);
  }

  /** Mức đích đổi (sang bước mới): trượt dần STEP_RAMP_SECONDS; vừa tua thì vào thẳng mức mới (trừ lúc bài đang mờ vào). */
  private retarget(seeked: boolean): void {
    const playing = this.current;
    if (!playing) return;
    const goal = this.target();
    if (Math.abs(goal - playing.goal) < 1e-6) return;
    playing.goal = goal;
    if (playing.entering) {
      playing.perTick = (goal * STEP_MS) / 1000 / (playing.cue.sibling ? SIBLING_FADE_SECONDS : FADE_SECONDS);
    } else if (seeked) {
      playing.audio.volume = goal;
      return;
    } else {
      playing.perTick = (Math.abs(goal - playing.audio.volume) * STEP_MS) / 1000 / STEP_RAMP_SECONDS;
    }
    this.startFade();
  }

  private switchTo(cue: MusicCue | null, seconds: number): void {
    if (this.current && cue && this.current.cue.link === cue.link) {
      // Cùng bài (đoạn kề, hay vừa tua trong đoạn): chơi tiếp, không bắt đầu lại.
      this.current.cue = cue;
      return;
    }
    const fadeSeconds = cue?.sibling ? SIBLING_FADE_SECONDS : FADE_SECONDS;
    if (this.current) {
      const old = this.current.audio;
      this.fadeStep.set(old, (Math.max(old.volume, 0.01) * STEP_MS) / 1000 / fadeSeconds);
      if (cue?.sibling) old.loop = false; // bài cũ vừa hết vòng: chơi nốt rồi thôi, không quay lại đầu bài
      this.fading.push(old);
      this.current = null;
    }
    if (cue) {
      const audio = this.createAudio(cue.src);
      audio.loop = true;
      audio.volume = 0;
      audio.addEventListener("loadedmetadata", () => {
        this.failed.delete(cue.link);
        if (audio.duration > 0) audio.currentTime = Math.max(0, seconds - cue.start) % audio.duration;
      }, { once: true });
      audio.addEventListener("error", () => this.drop(cue, audio), { once: true });
      const goal = this.target(cue);
      this.current = { cue, audio, goal, perTick: (goal * STEP_MS) / 1000 / fadeSeconds, entering: true };
      if (this.playing) void audio.play().catch(() => undefined);
    }
    this.emitActive();
    this.startFade();
  }

  private startFade(): void {
    if (this.timer !== null) return;
    this.timer = globalThis.setInterval(() => {
      let busy = false;
      const playing = this.current;
      if (playing) {
        const { audio, goal } = playing;
        const move = Math.max(playing.perTick, 1e-5);
        if (audio.volume < goal) audio.volume = Math.min(goal, audio.volume + move);
        else if (audio.volume > goal) audio.volume = Math.max(goal, audio.volume - move);
        if (Math.abs(audio.volume - goal) < 1e-4) playing.entering = false;
        else busy = true;
      }
      this.fading = this.fading.filter((audio) => {
        audio.volume = Math.max(0, audio.volume - (this.fadeStep.get(audio) ?? (0.1 * STEP_MS) / 1000 / FADE_SECONDS));
        if (audio.volume <= 0.001) {
          audio.pause();
          return false;
        }
        busy = true;
        return true;
      });
      if (!busy && this.timer !== null) {
        globalThis.clearInterval(this.timer);
        this.timer = null;
      }
    }, STEP_MS);
  }
}
