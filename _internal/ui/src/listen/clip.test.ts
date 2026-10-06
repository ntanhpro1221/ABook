import { describe, expect, it } from "vitest";
import { stopAtEnd } from "./clip";

// Một câu nghe trong file chương ("Cần nghe lại" khi WAV riêng đã dọn): clip phải dừng ở mốc cuối câu, không lan sang câu kế.
class FakeAudio extends EventTarget {
  currentTime = 0;
  paused = false;
  pause() {
    this.paused = true;
  }
  tick(time: number) {
    this.currentTime = time;
    this.dispatchEvent(new Event("timeupdate"));
  }
}

describe("stopAtEnd", () => {
  it("dừng khi qua mốc end và báo đã hết một lần", () => {
    const audio = new FakeAudio();
    audio.currentTime = 5;
    let ended = 0;
    stopAtEnd(audio, 7, () => (ended += 1));
    audio.tick(6.5);
    expect([audio.paused, ended]).toEqual([false, 0]);
    audio.tick(7.1);
    expect([audio.paused, ended]).toEqual([true, 1]);
    audio.paused = false;
    audio.tick(9);
    expect([audio.paused, ended]).toEqual([false, 1]);
  });

  it("gỡ theo dõi thì không dừng nữa", () => {
    const audio = new FakeAudio();
    let ended = 0;
    const release = stopAtEnd(audio, 1, () => (ended += 1));
    release();
    audio.tick(2);
    expect([audio.paused, ended]).toEqual([false, 0]);
  });
});
