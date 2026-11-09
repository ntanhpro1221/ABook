// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";

const h = vi.hoisted(() => ({ bed: null as import("./musicBed").MusicBed | null,
  audio: [] as { src: string; paused: boolean; volume: number; currentTime: number }[] }));
vi.mock("./musicBed", async (original) => {
  const actual = await original<typeof import("./musicBed")>();
  return { ...actual, MusicBed: class extends actual.MusicBed {
    constructor() {
      super((src) => {
        const audio = { src, paused: true, volume: 0, currentTime: 0, duration: 200, loop: false };
        h.audio.push(audio);
        return Object.assign(audio, { play: async () => { audio.paused = false; }, pause: () => { audio.paused = true; },
          addEventListener() {}, removeAttribute() {}, load() {} });
      });
      h.bed = this;
    }
  } };
});
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./source", async (original) => ({ ...await original<typeof import("./source")>(), useListenBook: () => ({ data: undefined }) }));
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";

beforeEach(() => {
  vi.useFakeTimers(); h.audio = []; h.bed = null;
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
});
afterEach(() => { h.bed?.stop(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });

const transitions = [["quiet-quiet", "", ""], ["quiet-music", "", "a"], ["music-quiet", "a", ""],
  ["music-other", "a", "b"], ["music-same", "a", "a"]] as const;
const modes = ["continuous", "manual", "seek", "resume", "buffering"] as const;

it.each(transitions.flatMap(([name, from, to]) => modes.map(mode => ({ name, from, to, mode }))))(
  "$name / $mode follows the new chapter through PlayerProvider", async ({ from, to, mode }) => {
    const listeners = new Map<string, Set<() => void>>();
    const fire = (kind: string) => [...listeners.get(kind) ?? []].forEach(fn => fn());
    const state = { time: 0, paused: true, ended: false };
    const engine = { get time() { return state.time; }, duration: 100, get paused() { return state.paused; }, get ended() { return state.ended; },
      on: (kind: string, fn: () => void) => { if (!listeners.has(kind)) listeners.set(kind, new Set()); listeners.get(kind)!.add(fn); return () => { listeners.get(kind)?.delete(fn); }; },
      load: (_track: unknown, at: number, autoplay: boolean) => { Object.assign(state, { time: at, paused: !autoplay, ended: false }); fire("time"); if (autoplay) fire("play"); },
      play: () => { state.paused = false; fire("play"); }, pause: () => { state.paused = true; fire("pause"); },
      stop: () => { state.paused = true; }, seek: (at: number) => { state.time = at; fire("time"); },
      setVolume() {}, setRate() {},
    } as unknown as AudioEngine;
    const chapters = [1, 2, 3].map(id => ({ id, index: id, title: `Chapter ${id}`, fullTitle: `Chapter ${id}`, subtitle: "", duration: 100, available: true })) as ListenChapter[];
    const book = { id: "matrix", title: "Matrix", narrator: "Voice", chapters, state: { chapters: {} } } as ListenBook;
    let answer: (() => void) | undefined;
    const source = { kind: "desktop", audioUrl: () => "/voice", saveProgress: async () => ({}), setRate: async () => undefined,
      musicCues: async (_book: string, chapter: number) => {
        const link = chapter === 1 ? from : chapter === 2 ? to : "a";
        const result = { cues: link ? [{ start: 0, end: 90, key: `${chapter}:0`, link, src: `/${link}` }] : [], levelDb: -20 };
        if (mode === "buffering" && chapter === 2) return new Promise(resolve => { answer = () => resolve(result); });
        return result;
      },
    } as unknown as ListenSource;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let player!: ReturnType<typeof usePlayer>;
    function Capture() { player = usePlayer(); return null; }
    const host = document.createElement("div"); const root = createRoot(host);
    const flush = async () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
    try {
      await act(async () => root.render(<QueryClientProvider client={client}><SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Capture /></PlayerProvider></SourceProvider></QueryClientProvider>));
      await act(async () => player.play(book, chapters, 1, 0)); await flush();
      expect(h.bed!.activeLink).toBe(from || null);
      await act(async () => { state.time = 20; fire("time"); await vi.advanceTimersByTimeAsync(2500); });
      h.audio.forEach(audio => { audio.currentTime = 55; });
      await act(async () => {
        if (mode === "resume") engine.pause();
        if (mode === "continuous") { Object.assign(state, { time: 100, paused: true, ended: true }); fire("ended"); }
        else if (mode === "resume") player.next();
        else player.jumpTo(2, mode === "seek" ? 40 : 0);
      });
      await flush();
      if (mode === "buffering") {
        await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
        expect(h.bed!.activeLink).toBeNull();
        expect(h.audio.every(a => a.paused || a.volume === 0)).toBe(true);
        await act(async () => { answer!(); }); await flush();
      }
      if (mode === "resume") {
        expect(state.paused).toBe(true);
        expect(h.audio.every(a => a.paused)).toBe(true);
        await act(async () => engine.play());
      }
      // A buffering voice has no time events; cue arrival must still start the bed.
      await act(async () => { if (mode !== "buffering") fire("time"); await vi.advanceTimersByTimeAsync(2500); });
      expect(h.bed!.activeLink).toBe(to || null);
      expect(h.audio.filter(a => !a.paused && a.volume > 0).map(a => a.src)).toEqual(to ? [`/${to}`] : []);
      if (to) expect(h.audio.at(-1)!.currentTime).toBe(mode === "seek" ? 40 : 0);
      // A quiet chapter must never disable the next chapter's music clock.
      await act(async () => player.jumpTo(3)); await flush();
      await act(async () => { state.time = 0.5; fire("time"); await vi.advanceTimersByTimeAsync(2500); });
      expect(h.bed!.activeLink).toBe("a");
    } finally { await act(async () => root.unmount()); client.clear(); }
  });
