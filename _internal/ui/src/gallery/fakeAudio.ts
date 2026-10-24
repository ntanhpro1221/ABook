import { findBook } from "./data";
import { galleryState } from "./state";

// `<audio>` giả cho trình phát của máy tính (listen/engine.ts WebAudioEngine dùng `new Audio()`): không có file MP3 thật, không phát tiếng.
// Độ dài lấy từ chương trong thư viện giả theo địa chỉ `/media/books/<sách>/chapters/<chương>`; thời gian ĐỨNG YÊN ở chỗ nạp - ảnh chụp
// "đang phát" giống nhau mọi lần.

class GalleryAudio extends EventTarget {
  preload = "auto";
  muted = true;
  volume = 1;
  playbackRate = 1;
  defaultPlaybackRate = 1;
  paused = true;
  ended = false;
  readyState = 0;
  duration = Number.NaN;
  error: MediaError | null = null;
  crossOrigin: string | null = null;
  private position = 0;
  private source = "";

  get currentTime(): number {
    return this.position;
  }

  set currentTime(value: number) {
    this.position = value;
    queueMicrotask(() => {
      this.dispatchEvent(new Event("timeupdate"));
      this.dispatchEvent(new Event("seeked"));
    });
  }

  get src(): string {
    return this.source;
  }

  set src(value: string) {
    this.source = value;
    this.position = 0;
    this.readyState = 0;
    const match = value.match(/\/media\/books\/([^/]+)\/chapters\/(\d+)/);
    const chapter = match ? findBook(match[1])?.chapters.find((item) => item.id === Number(match[2])) : undefined;
    this.duration = chapter?.duration || 12;
    setTimeout(() => {
      this.readyState = 4;
      this.dispatchEvent(new Event("loadedmetadata"));
      this.dispatchEvent(new Event("durationchange"));
      this.dispatchEvent(new Event("canplay"));
    }, 0);
  }

  get currentSrc(): string {
    return this.source;
  }

  removeAttribute(name: string): void {
    if (name === "src") this.source = "";
  }

  setAttribute(name: string, value: string): void {
    if (name === "src") this.src = value;
  }

  load(): void {}

  pause(): void {
    if (this.paused) return;
    this.paused = true;
    this.dispatchEvent(new Event("pause"));
  }

  play(): Promise<void> {
    if (galleryState.scenario.playing === false) return Promise.resolve();
    this.paused = false;
    this.dispatchEvent(new Event("play"));
    this.dispatchEvent(new Event("playing"));
    return Promise.resolve();
  }

  canPlayType(): CanPlayTypeResult {
    return "probably";
  }
}

export function installFakeAudio(): void {
  (globalThis as { Audio: unknown }).Audio = GalleryAudio;
}
