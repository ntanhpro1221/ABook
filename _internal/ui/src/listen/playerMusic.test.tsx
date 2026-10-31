import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";

const h = vi.hoisted(() => ({
  effects: [] as { run: () => void | (() => void); deps: readonly unknown[] }[],
  seed: null as unknown, bed: null as import("./musicBed").MusicBed | null,
  audio: [] as { paused: boolean; volume: number; currentTime: number; duration: number; src: string; buffer: Uint8Array; disposed: boolean }[],
}));
vi.mock("react", async (original) => {
  const react = await original<typeof import("react")>();
  return { ...react, useEffect: (run: () => void | (() => void), deps: readonly unknown[] = []) => h.effects.push({ run, deps }),
    // Mount with an already opened book; real hooks and action callbacks remain in use.
    useState: (initial: unknown) => { const seed = initial === null && h.seed ? h.seed : initial; if (seed === h.seed) h.seed = null; return react.useState(seed); },
  };
});
vi.mock("./musicBed", async (original) => {
  const actual = await original<typeof import("./musicBed")>();
  return { ...actual, MusicBed: class extends actual.MusicBed {
    constructor() {
      super((src) => {
        const audio = { paused: true, volume: 0, currentTime: 0, duration: 200, loop: false, src, buffer: new Uint8Array(4096), disposed: false };
        h.audio.push(audio);
        return Object.assign(audio, { play: () => { audio.paused = false; return Promise.resolve(); }, pause: () => { audio.paused = true; },
          addEventListener: () => undefined, removeAttribute: () => { audio.src = ""; }, load: () => undefined,
          dispose: () => { audio.buffer = new Uint8Array(); audio.disposed = true; } });
      });
      h.bed = this;
    }
  } };
});
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { dismiss: vi.fn(), info: vi.fn(), success: vi.fn(), warning: vi.fn() }) }));
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./source", async (original) => ({ ...await original<typeof import("./source")>(), useListenBook: () => ({ data: undefined }) }));
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";
import { FADE_SECONDS } from "./musicBed";
import { VOICE_STALL_MS, VOICE_STALL_TICK_MS } from "./voiceStall";

beforeEach(() => {
  vi.useFakeTimers();
  h.effects = []; h.audio = []; h.bed = null;
  h.seed = { bookId: "music-test", chapterId: 1, bookTitle: "Sách", title: "Chương 1", url: "/audio" };
  vi.stubGlobal("window", Object.assign(new EventTarget(), { location: { href: "http://localhost/", search: "" } }));
  vi.stubGlobal("navigator", { mediaSession: {} });
});
afterEach(() => { h.bed?.stop(); vi.useRealTimers(); vi.unstubAllGlobals(); });

async function mount(silent = false) {
  const listeners = new Map<string, (() => void)[]>();
  const fire = (kind: string) => listeners.get(kind)?.forEach((listener) => listener());
  const state = { time: 20, paused: false, ended: false };
  const engine = { get time() { return state.time; }, duration: 100, get paused() { return state.paused; }, get ended() { return state.ended; },
    on: (kind: string, listener: () => void) => { listeners.set(kind, [...(listeners.get(kind) ?? []), listener]); return () => undefined; },
    seek: (t: number) => { state.time = t; fire("time"); }, stop: () => { state.paused = true; fire("pause"); },
    setVolume: vi.fn(), setRate: vi.fn(), load: vi.fn(),
  } as unknown as AudioEngine;
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress: async () => undefined, setRate: async () => undefined,
    musicCues: async () => silent
      ? JSON.parse(readFileSync(new URL("../../../tests/fixtures/music/edge_cases.json", import.meta.url), "utf8")).emptyResponse
      : ({ cues: [{ start: 0, end: 100, key: "1:0", link: "a", src: "/a", gainDb: -20 }], levelDb: -20 }),
  } as unknown as ListenSource;
  let actions!: ReturnType<typeof usePlayer>;
  function Capture() { actions = usePlayer(); return null; }
  renderToString(<QueryClientProvider client={new QueryClient()}><SourceProvider source={source}><PlayerProvider engine={engine}><Capture /></PlayerProvider></SourceProvider></QueryClientProvider>);
  for (const effect of h.effects.filter((effect) => effect.deps.includes(h.bed))) effect.run();
  for (let i = 0; i < 8; i++) await Promise.resolve();
  fire("time");
  vi.advanceTimersByTime(3000);
  expect(h.audio).toHaveLength(silent ? 0 : 1);
  return { actions, engine, fire, state };
}

it("the voice ending by itself fades the music out through player.tsx instead of cutting it with the voice", async () => {
  // 01-11 audio_sink on Qt 0.4.152: chapter end dropped the music -30 -> -91 dB in 6 ms; web had the same pause-with-the-voice shape.
  const { fire, state } = await mount();
  const audio = h.audio[0];
  const level = audio.volume;
  Object.assign(state, { time: 100, paused: true, ended: true });
  fire("pause"); // <audio> fires pause before ended, with ended already true
  fire("ended");
  expect(audio.paused).toBe(false);
  vi.advanceTimersByTime(500);
  expect(audio.volume).toBeLessThan(level);
  expect(audio.volume).toBeGreaterThan(0);
  Object.assign(state, { time: 0, ended: false }); // next chapter loading, voice still silent
  fire("time");
  expect(audio.paused).toBe(false);
});

it("a voice stalled past voiceStallFadeAfterSeconds fades the music down through player.tsx and lets it back when the voice moves", async () => {
  // Network gone for good: the voice waits up to STALL_MS (215 s) - the music must not play alone all that time. No time events fire
  // while stalled, so player.tsx asks on its own ticker.
  const { fire, state } = await mount();
  const audio = h.audio[0];
  const level = audio.volume;
  vi.advanceTimersByTime(VOICE_STALL_MS - 3000 - VOICE_STALL_TICK_MS - 100); // mount() already spent 3 s with the voice still
  expect(audio.volume).toBe(level); // an ordinary gap: nothing changes
  vi.advanceTimersByTime(VOICE_STALL_TICK_MS + 500);
  expect(audio.paused).toBe(false);
  expect(audio.volume).toBeLessThan(level);
  expect(audio.volume).toBeGreaterThan(0);
  vi.advanceTimersByTime(FADE_SECONDS * 1000 + 500);
  expect(audio.paused || audio.volume === 0).toBe(true);
  state.time = 21; // the voice is back
  fire("time");
  for (let i = 0; i < 8; i++) await Promise.resolve();
  vi.advanceTimersByTime(1000);
  const back = h.audio.at(-1)!;
  expect(back.paused).toBe(false);
  expect(back.volume).toBeGreaterThan(0);
});

it("a listener Pause still stops the music at once (control for the chapter-end fade)", async () => {
  const { fire, state } = await mount();
  state.paused = true;
  fire("pause");
  expect(h.audio[0].paused).toBe(true);
});

it.each([0.5, 3, -3])("seek %s seconds through player.tsx keeps the track, position and completed fade", async (delta) => {
  const { actions, engine } = await mount();
  const audio = h.audio[0];
  audio.currentTime = 50;
  const level = audio.volume;
  expect(level).toBeGreaterThan(0);
  actions.seek(engine.time + delta);
  expect(h.audio).toHaveLength(1);
  expect(audio.currentTime).toBe(50);
  expect(audio.volume).toBe(level);
  vi.advanceTimersByTime(500);
  expect(audio.volume).toBe(level);
});

it("a seek over three seconds through player.tsx aligns the same music player (positive control)", async () => {
  const { actions } = await mount();
  h.audio[0].currentTime = 50;
  actions.seek(24);
  expect(h.audio).toHaveLength(1);
  expect(h.audio[0].currentTime).toBe(24);
});

it("the close action releases the real MusicBed player and its audio buffer", async () => {
  const { actions } = await mount();
  const audio = h.audio[0];
  expect(audio.buffer.length).toBe(4096);
  actions.close();
  expect(h.bed!.activeLink).toBeNull();
  expect(audio.paused).toBe(true);
  expect(audio.src).toBe("");
  expect(audio.buffer.length).toBe(0);
  expect(audio.disposed).toBe(true);
  vi.advanceTimersByTime(5000);
  expect(h.audio).toHaveLength(1);
});

it("a valid catalog with no candidates reaches player.tsx as silent cues and creates no audio player", async () => {
  const { actions, fire } = await mount(true);
  expect(h.bed!.activeLink).toBeNull();
  actions.seek(23);
  fire("play");
  vi.advanceTimersByTime(10_000);
  expect(h.audio).toHaveLength(0);
  expect(h.bed!.failing).toBe(false);
  actions.close();
});
