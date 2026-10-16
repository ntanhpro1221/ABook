import type { MediaSourceLike, SourceBufferLike } from "./liveFeed";

// Đồ giả MediaSource / SourceBuffer cho bài thử phát dần (liveClip.test.ts, readAloud.test.ts): trình duyệt thật chỉ cần ở lúc chạy app.

export class FakeBuffer implements SourceBufferLike {
  mode = "";
  updating = false;
  appended: number[][] = [];
  fail = false;
  private listeners = new Map<string, Set<() => void>>();
  appendBuffer(data: BufferSource) {
    if (this.fail) throw new Error("QuotaExceeded");
    this.appended.push([...new Uint8Array(data as ArrayBuffer)]);
    this.updating = true;
  }
  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: () => void) {
    this.listeners.get(type)?.delete(listener);
  }
  /** Trình duyệt nối xong khúc đang nối. */
  finish() {
    this.updating = false;
    this.listeners.get("updateend")?.forEach((listener) => listener());
  }
}

export class FakeSource implements MediaSourceLike {
  readyState = "closed";
  buffer = new FakeBuffer();
  types: string[] = [];
  ended = false;
  private listeners = new Map<string, Set<() => void>>();
  addSourceBuffer(type: string) {
    this.types.push(type);
    return this.buffer;
  }
  endOfStream() {
    this.ended = true;
    this.readyState = "ended";
  }
  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: string, listener: () => void) {
    this.listeners.get(type)?.delete(listener);
  }
  open() {
    this.readyState = "open";
    this.listeners.get("sourceopen")?.forEach((listener) => listener());
  }
}

