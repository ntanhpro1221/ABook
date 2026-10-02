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
  addEventListener(type: "loadedmetadata", listener: () => void, options?: { once?: boolean }): void;
};

/** <audio> thật; ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như engine.ts, clip.tsx). */
function browserAudio(src: string): BedAudio {
  const audio = new Audio(src);
  audio.muted = new URLSearchParams(window.location.search).get("mute") === "1";
  audio.preload = "auto";
  return audio;
}

const FADE_SECONDS = 2;
const STEP_MS = 50;

function cueAt(cues: MusicCue[], seconds: number): MusicCue | null {
  return cues.find((cue) => seconds >= cue.start && seconds < cue.end) ?? null;
}

export class MusicBed {
  constructor(private readonly createAudio: (src: string) => BedAudio = browserAudio) {}

  private cues: MusicCue[] = [];
  private gain = 0.1;
  private userVolume = 1;
  private playing = false;
  private current: { cue: MusicCue; audio: BedAudio } | null = null;
  private fading: BedAudio[] = [];
  private fadeFrom = new WeakMap<BedAudio, number>(); // âm lượng lúc bắt đầu mờ đi: bài to và bài nhỏ cùng tắt trong FADE_SECONDS
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastTime = 0;
  private listeners = new Set<(link: string | null) => void>();
  private announced: string | null = null;

  setCues(cues: MusicCue[], levelDb: number): void {
    this.cues = cues;
    this.gain = Math.pow(10, levelDb / 20);
    this.switchTo(cueAt(this.cues, this.lastTime), this.lastTime);
  }

  setVolume(volume: number): void {
    this.userVolume = Math.max(0, Math.min(1, volume));
    if (this.current) this.current.audio.volume = this.target();
  }

  /** Gọi mỗi khi thời gian giọng đọc đổi (`seeked` = người nghe vừa tua). */
  sync(seconds: number, playing: boolean, seeked = false): void {
    this.lastTime = seconds;
    this.playing = playing;
    const cue = cueAt(this.cues, seconds);
    if ((cue?.key ?? null) !== (this.current?.cue.key ?? null) || (seeked && cue)) {
      this.switchTo(cue, seconds);
    }
    for (const audio of [this.current?.audio, ...this.fading]) {
      if (!audio) continue;
      if (playing && audio.paused) void audio.play().catch(() => undefined);
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
    this.emitActive();
  }

  private emitActive(): void {
    const link = this.activeLink;
    if (link === this.announced) return;
    this.announced = link;
    for (const listener of [...this.listeners]) listener(link);
  }

  /** Âm lượng mục tiêu của bài đang phát: gainDb của chính mốc (bài to / nhỏ khác nhau), không có thì mức chung. */
  private target(): number {
    const gainDb = this.current?.cue.gainDb;
    const gain = typeof gainDb === "number" && Number.isFinite(gainDb) ? Math.pow(10, Math.min(0, gainDb) / 20) : this.gain;
    return Math.min(1, gain * this.userVolume);
  }

  private switchTo(cue: MusicCue | null, seconds: number): void {
    if (this.current && cue && this.current.cue.link === cue.link) {
      // Cùng bài (đoạn kề, hay vừa tua trong đoạn): chơi tiếp, không bắt đầu lại.
      this.current.cue = cue;
      return;
    }
    if (this.current) {
      this.fadeFrom.set(this.current.audio, Math.max(this.current.audio.volume, 0.01));
      this.fading.push(this.current.audio);
      this.current = null;
    }
    if (cue) {
      const audio = this.createAudio(cue.src);
      audio.loop = true;
      audio.volume = 0;
      audio.addEventListener("loadedmetadata", () => {
        if (audio.duration > 0) audio.currentTime = Math.max(0, seconds - cue.start) % audio.duration;
      }, { once: true });
      this.current = { cue, audio };
      if (this.playing) void audio.play().catch(() => undefined);
    }
    this.emitActive();
    this.startFade();
  }

  private startFade(): void {
    if (this.timer !== null) return;
    const step = STEP_MS / 1000 / FADE_SECONDS;
    this.timer = globalThis.setInterval(() => {
      let busy = false;
      if (this.current) {
        const goal = this.target();
        const audio = this.current.audio;
        if (audio.volume < goal) {
          audio.volume = Math.min(goal, audio.volume + step * goal);
          busy = busy || audio.volume < goal;
        }
      }
      this.fading = this.fading.filter((audio) => {
        audio.volume = Math.max(0, audio.volume - step * (this.fadeFrom.get(audio) ?? 0.1));
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
