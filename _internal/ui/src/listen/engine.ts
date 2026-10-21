// Bộ máy phát. Máy tính dùng <audio> của trình duyệt; Android thay bằng bộ phát native (Media3/ExoPlayer) để
// phát khi tắt màn hình, hiện điều khiển ở màn hình khoá và nhận nút tai nghe. Trình phát (player.tsx) chỉ biết
// giao diện này.
//
// Bộ máy web chỉ phát MỘT chương; trình phát lo hàng đợi, hẹn giờ, lưu vị trí. Bộ máy native (`native: true`) giữ
// cả cuốn trong hàng đợi và tự lo hết những việc đó ở lõi - vì tắt màn hình thì JavaScript bị treo, nên những thứ
// phải chạy khi người nghe đã ngủ không được nằm ở JavaScript.

import type { Bookmark, BookmarkSentence, ListenBook, ListenChapter } from "./model";
import type { SpeechTrack } from "./readAloud";
import type { MusicCredit } from "./musicBed";
import type { SleepMode, SleepRequest } from "./sleep";

export interface TrackInfo {
  url: string;
  title: string;
  album: string;
  artist: string;
  artwork?: string;
  /** Chương chỉ-có-chữ (nghe ngay): bộ máy đọc to dựng chương từ các đoạn chữ; `url` bỏ trống (readAloud.ts). */
  speech?: SpeechTrack;
}

export type EngineEvent =
  | "time"
  | "duration"
  | "play"
  | "pause"
  | "ended"
  | "error"
  /** bộ máy đọc to: dịch vụ đã trả lời lại sau lỗi - thông báo lỗi cũ không còn đúng. */
  | "recovered"
  | "waiting"
  | "playing"
  /** chỉ bộ máy native: chương/cuốn đang phát đổi (tự sang chương, nút trên thông báo...). */
  | "chapter"
  /** chỉ bộ máy native: hẹn giờ ngủ đổi (đặt, gia hạn, lắc máy, tự tắt). */
  | "sleep";

export interface AudioEngine {
  load(track: TrackInfo, startAt: number, autoplay: boolean): void;
  play(): void;
  pause(): void;
  seek(seconds: number): void;
  setRate(rate: number): void;
  setVolume(volume: number): void;
  stop(): void;
  readonly time: number;
  readonly duration: number;
  readonly paused: boolean;
  readonly ended: boolean;
  /** Lý do lỗi gần nhất, nói bằng lời người nghe hiểu (bộ máy đọc to); không có thì trình phát dùng câu chung. */
  readonly error?: string;
  /** Bấm vào một chữ: nghe từ đúng chữ thứ `word` của đoạn `segment` (bộ máy đọc to; chương có audio đi bằng `seek`). */
  seekWord?(segment: number, word: number): void;
  on(event: EngineEvent, handler: () => void): () => void;
}

export interface NativeQueue {
  bookId: string;
  bookTitle: string;
  narrator: string;
  chapters: ListenChapter[];
  chapterId: number;
  at: number;
  rate: number;
  autoplay: boolean;
  /** Giọng đọc đã chọn cho cuốn chỉ-có-chữ (mã giọng của plugin ReadAloud); lõi native tự đọc chương chữ bằng giọng này. */
  readAloudVoice?: string;
}

export interface NativeEngine extends AudioEngine {
  readonly native: true;
  updateMetadata?(book: ListenBook): void;
  loadQueue(queue: NativeQueue): void;
  toggle(): void;
  skipBy(delta: number): void;
  next(): void;
  previous(): void;
  /** `word`: chữ bấm trong chương đọc to (đoạn + thứ tự chữ) - lõi native tự vào đúng mốc chữ. */
  jumpTo(chapterId: number, seconds: number, word?: { segment: number; word: number }): void;
  setSleep(request: SleepRequest): void;
  extendSleep(minutes?: number): void;
  /** `sentence`: chương đọc to - câu đang đọc (thứ tự + câu trích), như dấu đặt ở màn đọc. */
  addBookmark(note: string, sentence?: BookmarkSentence): Promise<Bookmark>;
  readonly sleep: SleepMode;
  readonly bookId: string;
  readonly bookTitle: string;
  readonly chapterId: number | null;
  readonly chapterTitle: string;
  /** Lỗi gần nhất của lõi native, nói đúng lý do (vd mất kết nối khi nghe thẳng); rỗng khi ổn. */
  readonly error: string;
  readonly rate: number;
  /** Ghi công bài nhạc nền lõi đang chơi; null khi im lặng. */
  readonly musicCredit: MusicCredit | null;
  /** Bài nhạc nền của chương đang nghe không phát được (MusicBed.kt brokenHere): đoạn ấy im lặng. */
  readonly musicBroken: boolean;
  /** Lời báo "mất mạng" khi nhạc nền đang bị giữ lại vì mạng (MusicBed.kt offlineNotice); rỗng khi ổn. */
  readonly musicOffline: string;
  /** Nhạc nền đang đổi theo cảnh của truyện (MusicBed.kt sceneMode), không phải danh sách phát người nghe chọn: để nhắc người nghe một lần (musicHint.ts). */
  readonly musicScene: boolean;
}

export function isNative(engine: AudioEngine): engine is NativeEngine {
  return (engine as Partial<NativeEngine>).native === true;
}

/** Lần nhảy tới chỗ bắt đầu của chương mới (bấm câu ở chương khác) mà trình duyệt bỏ dở và đặt về đầu chương (bị dừng giữa lúc đang
 *  nhảy - Chrome dừng tiếng tắt ở thẻ nền "để tiết kiệm pin"): trả lại chỗ cần nhảy lại, còn không thì null (soát a27 X1). */
export function missedSeek(target: number | null, landed: number): number | null {
  return target !== null && target >= 1 && landed < 0.5 ? target : null;
}

export class WebAudioEngine implements AudioEngine {
  private audio = new Audio();
  private pendingSeek: number | null = null;
  /** Chỗ vừa nhảy tới khi chương mới có độ dài, chờ `seeked` xác nhận (missedSeek). */
  private landing: number | null = null;

  constructor() {
    this.audio.preload = "auto";
    // ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng.
    this.audio.muted = new URLSearchParams(window.location.search).get("mute") === "1";
    this.audio.addEventListener("loadedmetadata", () => {
      if (this.pendingSeek !== null) {
        this.landing = Math.min(this.pendingSeek, Math.max(0, (this.audio.duration || 0) - 1));
        this.audio.currentTime = this.landing;
        this.pendingSeek = null;
      }
    });
    this.audio.addEventListener("seeked", () => {
      const again = missedSeek(this.landing, this.audio.currentTime);
      this.landing = null;
      if (again !== null) this.audio.currentTime = again;
    });
  }

  load(track: TrackInfo, startAt: number, autoplay: boolean): void {
    this.pendingSeek = startAt > 0 ? startAt : null;
    this.landing = null;
    this.audio.src = track.url;
    if ("mediaSession" in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: track.title,
        album: track.album,
        artist: track.artist,
        artwork: track.artwork ? [{ src: track.artwork, sizes: "512x512", type: "image/png" }] : [],
      });
    }
    if (autoplay) void this.audio.play().catch(() => undefined);
  }

  play(): void {
    void this.audio.play().catch(() => undefined);
  }

  pause(): void {
    this.audio.pause();
  }

  seek(seconds: number): void {
    const limit = Number.isFinite(this.audio.duration) ? this.audio.duration : seconds;
    const target = Math.max(0, Math.min(limit, seconds));
    this.landing = null; // người nghe tự tua: chỗ ấy thắng chỗ bắt đầu của lần nạp
    if (this.audio.readyState < 1) this.pendingSeek = target;
    else this.audio.currentTime = target;
  }

  setRate(rate: number): void {
    this.audio.playbackRate = rate;
    this.audio.defaultPlaybackRate = rate;
  }

  setVolume(volume: number): void {
    this.audio.volume = Math.max(0, Math.min(1, volume));
  }

  stop(): void {
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
  }

  get time(): number {
    const now = this.audio.currentTime || 0;
    return this.pendingSeek ?? missedSeek(this.landing, now) ?? now;
  }

  get duration(): number {
    return Number.isFinite(this.audio.duration) ? this.audio.duration : 0;
  }

  get paused(): boolean {
    return this.audio.paused;
  }

  get ended(): boolean {
    return this.audio.ended;
  }

  on(event: EngineEvent, handler: () => void): () => void {
    const names: Partial<Record<EngineEvent, string>> = {
      time: "timeupdate",
      duration: "loadedmetadata",
      play: "play",
      pause: "pause",
      ended: "ended",
      error: "error",
      waiting: "waiting",
      playing: "playing",
    };
    const name = names[event];
    if (!name) return () => undefined;
    const wrapped = event === "error" ? () => this.audio.getAttribute("src") && handler() : handler;
    this.audio.addEventListener(name, wrapped);
    return () => this.audio.removeEventListener(name, wrapped);
  }
}
