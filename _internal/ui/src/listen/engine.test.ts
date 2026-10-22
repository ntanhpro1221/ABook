import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { missedSeek, WebAudioEngine } from "./engine";

// Bấm câu ở chương khác rồi bị dừng trước khi trình duyệt nhảy xong: Chrome bỏ dở lần nhảy và đặt về 0 - trình đọc nhảy về đầu chương
// (soát a27 X1). Bộ máy phải nhảy lại chỗ câu đã bấm.
class FakeAudio extends EventTarget {
  currentTime = 0;
  duration = Number.NaN;
  readyState = 0;
  paused = true;
  muted = false;
  preload = "";
  src = "";
  getAttribute(name: string) { return name === "src" ? this.src : null; }
  seeks: number[] = [];
  constructor() {
    super();
    let time = 0;
    Object.defineProperty(this, "currentTime", {
      get: () => time,
      set: (value: number) => {
        time = value;
        this.seeks.push(value);
      },
    });
  }
  play() {
    this.paused = false;
    return Promise.resolve();
  }
  pause() {
    this.paused = true;
  }
  metadata(duration: number) {
    this.duration = duration;
    this.readyState = 1;
    this.dispatchEvent(new Event("loadedmetadata"));
  }
  /** Trình duyệt báo nhảy xong ở `at` (không qua setter - đó là việc của trình duyệt, không phải bộ máy). */
  seeked(at: number) {
    this.seeks.length = 0;
    Object.getOwnPropertyDescriptor(this, "currentTime")?.set?.call(this, at);
    this.seeks.length = 0;
    this.dispatchEvent(new Event("seeked"));
  }
}

let audio: FakeAudio;
const track = { url: "/media/books/b/chapters/3", title: "Chương 3", album: "Sách", artist: "" };

beforeEach(() => {
  vi.stubGlobal("window", { location: { search: "?mute=1" } });
  vi.stubGlobal("navigator", {});
  vi.stubGlobal(
    "Audio",
    class {
      constructor() {
        audio = new FakeAudio();
        return audio;
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("play bị từ chối phát error/pause; AbortError do đổi nguồn không báo lỗi", async () => {
  const engine = new WebAudioEngine();
  const error = vi.fn(), pause = vi.fn();
  engine.on("error", error); engine.on("pause", pause);
  engine.load(track, 0, false);
  vi.spyOn(audio, "play").mockRejectedValueOnce(new DOMException("blocked", "NotAllowedError"));
  engine.play(); await Promise.resolve();
  expect(error).toHaveBeenCalledTimes(1);
  expect(pause).toHaveBeenCalledTimes(1);
  expect(engine.error).toContain("Không phát được");
  vi.mocked(audio.play).mockRejectedValueOnce(new DOMException("source changed", "AbortError"));
  engine.load(track, 0, true);
  engine.load({ ...track, url: "/other" }, 0, false); await Promise.resolve();
  expect(error).toHaveBeenCalledTimes(1);
});

describe("missedSeek", () => {
  it("chỉ nhảy lại khi lần nhảy bị đặt về đầu chương", () => {
    expect(missedSeek(16.9, 0)).toBe(16.9);
    expect(missedSeek(16.9, 16.9)).toBeNull();
    expect(missedSeek(null, 0)).toBeNull();
    expect(missedSeek(0.3, 0)).toBeNull();
  });
});

describe("WebAudioEngine nạp chương khác ở giữa", () => {
  it("dừng trước khi nhảy xong: vẫn ở câu đã bấm, không về đầu chương", () => {
    const engine = new WebAudioEngine();
    engine.load(track, 14.7, true);
    engine.pause();
    audio.metadata(194);
    expect(audio.currentTime).toBe(14.7);
    audio.seeked(0); // Chrome bỏ dở lần nhảy
    expect(engine.time).toBe(14.7);
    expect(audio.currentTime).toBe(14.7);
  });

  it("nhảy xong đúng chỗ thì không nhảy lại", () => {
    const engine = new WebAudioEngine();
    engine.load(track, 14.7, true);
    audio.metadata(194);
    audio.seeked(14.7);
    expect(audio.seeks).toEqual([]);
    expect(engine.time).toBe(14.7);
  });

  it("người nghe tự tua về đầu trong lúc ấy: giữ chỗ người nghe chọn", () => {
    const engine = new WebAudioEngine();
    engine.load(track, 14.7, true);
    audio.metadata(194);
    engine.seek(0);
    audio.seeked(0);
    expect(engine.time).toBe(0);
    expect(audio.currentTime).toBe(0);
  });
});
