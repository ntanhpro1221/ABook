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
  const state = { time: 20, paused: false };
  const engine = { get time() { return state.time; }, duration: 100, get paused() { return state.paused; }, ended: false,
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
  return { actions, engine, fire };
}

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
