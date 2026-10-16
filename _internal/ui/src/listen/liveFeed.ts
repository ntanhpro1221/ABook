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
 *  phần tử tự dừng chờ ("waiting"). `broken`: nối lỗi (MediaSource không nhận) - bộ máy xử lý. */
export class LiveFeed {
  private buffer: SourceBufferLike | null = null;
  private next = 0;
  private closed = false;
  private ended = false;
  private readonly open = () => this.attach();
  private readonly pump = () => this.feed();
  private readonly unlisten: () => void;

  constructor(
    private readonly source: MediaSourceLike,
    private readonly live: LiveClip,
    private readonly broken: () => void,
  ) {
    source.addEventListener("sourceopen", this.open);
    const off = live.on((event) => {
      if (event === "audio" || event === "done") this.feed();
    });
    this.unlisten = () => {
      source.removeEventListener("sourceopen", this.open);
      off();
    };
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
      if (this.next < this.live.chunks.length) {
        buffer.appendBuffer(this.live.chunks[this.next++] as BufferSource);
      } else if (this.live.state === "done" && !this.ended) {
        this.ended = true;
        this.source.endOfStream();
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
    this.unlisten();
    this.buffer?.removeEventListener("updateend", this.pump);
  }
}
