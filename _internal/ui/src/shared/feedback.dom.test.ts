// @vitest-environment happy-dom
// Phản hồi giác quan (DESIGN.md 5.3 / 5.4): tiếng im khi sách đang phát (trừ hẹn giờ ngủ), công tắc tắt = im hẳn, mỗi việc đúng hằng số rung.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { HAPTICS, SOUNDS, configureFeedback, crossedSeekMark, feedback, resetFeedbackForTest, setBookPlaying, withFeedback, type FeedbackKind } from "./feedback";

let oscillators: { frequency: { value: number }; start: ReturnType<typeof vi.fn> }[];

class FakeAudioContext {
  state = "running";
  currentTime = 0;
  destination = {};
  resume = vi.fn(() => Promise.resolve());
  createPeriodicWave = vi.fn(() => ({}));
  createOscillator() {
    const osc = { frequency: { value: 0 }, setPeriodicWave: vi.fn(), connect: (node: unknown) => node, start: vi.fn(), stop: vi.fn() };
    oscillators.push(osc);
    return osc;
  }
  createGain() {
    const ramp = { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() };
    return { gain: ramp, connect: (node: unknown) => node };
  }
}

beforeEach(() => {
  resetFeedbackForTest();
  oscillators = [];
  vi.stubGlobal("AudioContext", FakeAudioContext);
});
afterEach(() => vi.unstubAllGlobals());

it("xác nhận kêu hai nốt đi lên một quãng ba khi sách đang dừng", () => {
  feedback("confirm");
  expect(oscillators.map((osc) => Math.round(osc.frequency.value))).toEqual([1047, 1319]);
  expect(oscillators.every((osc) => osc.start.mock.calls.length === 1)).toBe(true);
});

it("đang phát thì mọi tiếng chạm im, trừ báo hẹn giờ ngủ", () => {
  setBookPlaying(true);
  for (const kind of ["toggle", "tick", "confirm", "done"] as FeedbackKind[]) feedback(kind);
  expect(oscillators).toHaveLength(0);
  feedback("sleepWarn");
  expect(oscillators).toHaveLength(1);
  setBookPlaying(false);
  feedback("toggle");
  expect(oscillators).toHaveLength(2);
});

it("tắt Âm thanh chạm thì im hẳn, cả báo hẹn giờ ngủ; rung vẫn theo công tắc riêng", () => {
  const haptic = vi.fn();
  configureFeedback({ sounds: false, haptic });
  for (const kind of Object.keys(SOUNDS) as FeedbackKind[]) feedback(kind);
  expect(oscillators).toHaveLength(0);
  expect(haptic).toHaveBeenCalled();
});

it("tắt Rung thì không gọi xuống lõi native", () => {
  const haptic = vi.fn();
  configureFeedback({ haptics: false, haptic });
  for (const kind of Object.keys(HAPTICS) as FeedbackKind[]) feedback(kind);
  expect(haptic).not.toHaveBeenCalled();
});

it("mỗi việc gửi đúng hằng số rung của bảng 5.4, cả khi sách đang phát", () => {
  const plugin = { haptic: vi.fn((_options: { effect: string }) => Promise.resolve()) };
  configureFeedback({ haptic: (effect) => plugin.haptic({ effect }) });
  setBookPlaying(true);
  const expected: Record<FeedbackKind, string | null> = {
    tap: "CONTEXT_CLICK",
    toggle: "SEGMENT_TICK",
    tick: "CLOCK_TICK",
    confirm: "CONFIRM",
    done: "CONFIRM",
    sleepWarn: null,
    reject: "REJECT",
    longPress: "LONG_PRESS",
    playPause: "CONTEXT_CLICK",
  };
  for (const [kind, effect] of Object.entries(expected)) {
    plugin.haptic.mockClear();
    feedback(kind as FeedbackKind);
    expect(plugin.haptic.mock.calls.map(([options]) => options.effect)).toEqual(effect ? [effect] : []);
  }
});

it("lỗi, chạm giữ, phát/dừng không có tiếng (chỉ rung); mọi tiếng ngắn <= 250 ms và không to hơn -22 dB", () => {
  for (const kind of ["reject", "longPress", "playPause", "tap"] as FeedbackKind[]) feedback(kind);
  expect(oscillators).toHaveLength(0);
  for (const notes of Object.values(SOUNDS)) {
    for (const note of notes ?? []) {
      expect(note.at + note.length).toBeLessThanOrEqual(0.25);
      expect(note.level).toBeLessThanOrEqual(-22);
    }
  }
});

it("không có Web Audio (WebView cũ, máy chủ thử) thì im lặng, không văng", () => {
  vi.stubGlobal("AudioContext", undefined);
  expect(() => feedback("confirm")).not.toThrow();
});

it("lõi native từ chối cú rung thì bỏ qua, không văng", async () => {
  configureFeedback({ haptic: () => Promise.reject(new Error("không có")) });
  expect(() => feedback("reject")).not.toThrow();
  await Promise.resolve();
});

it("thanh tua tích khi kéo qua mốc 15 giây hay chạm đầu / cuối chương, không tích khi đứng yên trong một khoảng", () => {
  expect(crossedSeekMark(10, 14, 600, 15)).toBe(false);
  expect(crossedSeekMark(14, 16, 600, 15)).toBe(true);
  expect(crossedSeekMark(31, 29, 600, 15)).toBe(true);
  expect(crossedSeekMark(20, 20, 600, 15)).toBe(false);
  expect(crossedSeekMark(5, 0, 600, 15)).toBe(true);
  expect(crossedSeekMark(593, 600, 600, 15)).toBe(true);
  expect(crossedSeekMark(600, 600, 600, 15)).toBe(false);
});

it("withFeedback phản hồi trước rồi mới làm việc được bọc", () => {
  const order: string[] = [];
  configureFeedback({ haptic: (effect) => order.push(effect) });
  withFeedback("playPause", (value: number) => order.push(`toggle ${value}`))(1);
  expect(order).toEqual(["CONTEXT_CLICK", "toggle 1"]);
});
