import type { LiveClip } from "./liveClip";

// Nối các khúc MP3 của một clip đang về ([LiveClip]) vào một MediaSource để phần tử audio phát ngay từ khúc đầu. Phần dùng của MediaSource / SourceBuffer (để bài thử thay bằng đồ giả).

export interface SourceBufferLike {
  mode: string;
  readonly updating: boolean;
  appendBuffer(data: BufferSource): void;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

export interface MediaSourceLike {
  readonly readyState: string;
  addSourceBuffer(type: string): SourceBufferLike;
  endOfStream(): void;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

export const LIVE_MIME = "audio/mpeg";

/** Nối lần lượt từng khúc (chờ `updateend` mới nối khúc kế); clip xong và đã nối hết thì `endOfStream()` - từ đó phần tử audio mới báo "ended". Hết dữ liệu mà clip chưa xong thì
 *  phần tử tự dừng chờ ("waiting"). `broken`: nối lỗi (MediaSource không nhận) - bộ máy xử lý.
 *
 *  Clip đứt giữa chừng (uxfix58): phần đã nối vẫn phát nốt, MediaSource KHÔNG đóng - phần tiếp (clip đuôi của cùng đoạn, bắt đầu từ chữ đầu tiên chưa có tiếng) được [chain] vào sau khúc cuối
 *  của phần hỏng, phát liền một mạch trong cùng phần tử audio; không còn gì để nối thì [finish] cho phần tử audio báo "ended" ở cuối phần đã có. */
export class LiveFeed {
  private buffer: SourceBufferLike | null = null;
  private readonly lives: LiveClip[];
  private part = 0;
  private next = 0;
  private closed = false;
  private ended = false;
  private sealed = false;
  private readonly open = () => this.attach();
  private readonly pump = () => this.feed();
  private readonly offs: (() => void)[] = [];

  constructor(
    private readonly source: MediaSourceLike,
    live: LiveClip,
    private readonly broken: () => void,
  ) {
    this.lives = [live];
    source.addEventListener("sourceopen", this.open);
    this.watch(live);
  }

  private watch(live: LiveClip): void {
    this.offs.push(
      live.on((event) => {
        if (event === "audio" || event === "done" || event === "failed") this.feed();
      }),
    );
  }

  /** Phần tiếp sau phần cuối hiện có (phần cuối đã hỏng): nối khúc của nó sau khúc cuối của phần hỏng. */
  chain(live: LiveClip): void {
    this.lives.push(live);
    this.watch(live);
    this.feed();
  }

  /** Hết phần để nối: nối nốt khúc đã về rồi `endOfStream()` dù phần cuối không "xong" (hỏng). */
  finish(): void {
    this.sealed = true;
    this.feed();
  }

  private attach(): void {
    if (this.buffer || this.closed) return;
    try {
      this.buffer = this.source.addSourceBuffer(LIVE_MIME);
      this.buffer.mode = "sequence";
      this.buffer.addEventListener("updateend", this.pump);
    } catch {
      this.buffer = null;
      this.fault();
      return;
    }
    this.feed();
  }

  private feed(): void {
    const buffer = this.buffer;
    if (!buffer || this.closed || buffer.updating || this.source.readyState !== "open") return;
    try {
      for (;;) {
        const live = this.lives[this.part];
        if (this.next < live.chunks.length) {
          buffer.appendBuffer(live.chunks[this.next++] as BufferSource);
          return;
        }
        if (this.part + 1 < this.lives.length && live.state !== "open") {
          this.part += 1; // phần này hết (xong / hỏng) và đã nối hết khúc: sang phần tiếp
          this.next = 0;
          continue;
        }
        const last = this.part === this.lives.length - 1;
        if (last && !this.ended && (live.state === "done" || (this.sealed && live.state === "failed"))) {
          this.ended = true;
          this.source.endOfStream();
        }
        return;
      }
    } catch {
      this.fault();
    }
  }

  private fault(): void {
    if (this.closed) return;
    this.close();
    this.broken();
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.source.removeEventListener("sourceopen", this.open);
    for (const off of this.offs) off();
    this.buffer?.removeEventListener("updateend", this.pump);
  }
}
