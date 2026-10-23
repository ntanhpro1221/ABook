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
import type { ReadingAnchor } from "./readingAnchor";

export interface TrackInfo {
  url: string;
  title: string;
  album: string;
  artist: string;
  artwork?: string;
  /** Chương chỉ-có-chữ (nghe ngay): bộ máy đọc to dựng chương từ các đoạn chữ; `url` bỏ trống (readAloud.ts). */
  speech?: SpeechTrack;
  readingAnchor?: ReadingAnchor;
}

export type EngineEvent =
  | "time"
  | "seeked"
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
  /** chỉ bộ máy native: tên sách / tên chương đang phát đổi (sửa sách), vẫn cùng cuốn, cùng chương. */
  | "metadata"
  /** chỉ bộ máy native: hẹn giờ ngủ đổi (đặt, gia hạn, lắc máy, tự tắt). */
  | "sleep"
  /** chỉ bộ máy native: tốc độ đổi từ controller ngoài (xe, đồng hồ, Android Auto), lõi đã lưu vào sách. Nút tốc độ trong app không báo ngược. */
  | "rate";

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
  readonly readingAnchor?: ReadingAnchor;
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
  /** Hồ sơ nghe của `readAloudVoice`: giọng riêng nhớ theo (cuốn, hồ sơ). */
  readAloudRecord?: string;
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
  private generation = 0;
  private lastError = "";

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
    ++this.generation;
    this.lastError = "";
    this.pendingSeek = startAt > 0 ? startAt : null;
    this.landing = null;
    this.audio.src = track.url;
    if (autoplay) this.play();
  }

  play(): void {
    const generation = ++this.generation;
    this.lastError = "";
    void this.audio.play().catch((error: unknown) => {
      // Đổi nguồn / bấm dừng huỷ play đang chờ (thường là AbortError): không báo lỗi của nguồn cũ.
      if (generation !== this.generation) return;
      this.lastError = `Không phát được chương này. Bạn hãy bấm Phát để thử lại.${error instanceof Error ? ` (${error.message})` : ""}`;
      this.audio.pause();
      this.audio.dispatchEvent(new Event("pause"));
      this.audio.dispatchEvent(new Event("error"));
    });
  }

  pause(): void {
    ++this.generation;
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
    ++this.generation;
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

  get error(): string { return this.lastError; }

  on(event: EngineEvent, handler: () => void): () => void {
    const names: Partial<Record<EngineEvent, string>> = {
      time: "timeupdate",
      duration: "loadedmetadata",
      play: "play",
      seeked: "seeked",
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
