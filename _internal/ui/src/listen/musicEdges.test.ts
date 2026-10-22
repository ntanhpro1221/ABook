import { readFileSync } from "node:fs";
import { afterEach, expect, it, vi } from "vitest";
import { MusicBed, loopBounds, type MusicCue } from "./musicBed";

const cases = JSON.parse(readFileSync(new URL("../../../tests/fixtures/music/edge_cases.json", import.meta.url), "utf8"));
afterEach(() => vi.useRealTimers());

function player(seconds: number) {
  const made: { src: string; currentTime: number; volume: number; paused: boolean; duration: number }[] = [];
  const bed = new MusicBed((src) => {
    const audio = { src, currentTime: 0, volume: 0, paused: true, loop: false, duration: src === "/pin" ? seconds : 200 };
    made.push(audio);
    return Object.assign(audio, { play: () => { audio.paused = false; return Promise.resolve(); }, pause: () => { audio.paused = true; }, addEventListener: () => undefined });
  });
  return { bed, made };
}

it.each(cases.pinCases as { seconds: number; expectedNext: number; applied: { chapters: Record<string, { track: string; start: number; end: number; gainDb: number }[]> } }[])("pin $seconds s: next track enters at its cue, after the server has removed tail", ({ seconds, expectedNext, applied }) => {
  vi.useFakeTimers();
  const { bed, made } = player(seconds);
  // Exact pinned package checked by Python apply_music and Kotlin applyMusic.
  bed.setCues(applied.chapters["1"].map((cue, i) => ({ ...cue, key: `1:${cue.start}`, link: i ? "next" : "pin", src: i ? "/next" : "/pin" })), -20);
  for (let t = 0; t < expectedNext; t += 0.5) {
    for (const audio of made) if (!audio.paused) audio.currentTime += 0.5;
    bed.sync(t, true);
    vi.advanceTimersByTime(500);
    expect(bed.activeLink).toBe("pin");
  }
  bed.sync(expectedNext, true);
  expect(bed.activeLink).toBe("next");
  vi.advanceTimersByTime(6000);
  expect(made.find((audio) => audio.src === "/next")!.volume).toBeCloseTo(0.1);
  bed.stop();
});

it("loopEnd past real EOF is clamped and playback opens the next loop before silence", () => {
  vi.useFakeTimers();
  const c = cases.loop;
  expect(loopBounds(c, c.seconds)).toMatchObject({ end: c.expectedEnd, loopEnd: c.expectedEnd, loopStart: c.loopStart });
  const { bed, made } = player(c.seconds);
  const cue: MusicCue = { ...c, start: 0, end: 300, key: "1:0", link: "pin", src: "/pin", gainDb: -20 };
  bed.setCues([cue], -20);
  bed.sync(0, true);
  vi.advanceTimersByTime(2000);
  made[0].currentTime = c.expectedPosition;
  bed.sync(c.expectedOpen, true);
  expect(made).toHaveLength(2);
  expect(made[1].currentTime).toBe(c.loopStart);
  vi.advanceTimersByTime(2000);
  expect(made[1].volume).toBeCloseTo(0.1);
  bed.stop();
});
