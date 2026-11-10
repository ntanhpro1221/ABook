// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";

type FakeAudio = { src: string; paused: boolean; volume: number; currentTime: number; released: boolean };
const h = vi.hoisted(() => ({ bed: null as import("./musicBed").MusicBed | null, audio: [] as FakeAudio[] }));
vi.mock("./musicBed", async (original) => {
  const actual = await original<typeof import("./musicBed")>();
  return { ...actual, MusicBed: class extends actual.MusicBed {
    constructor() {
      super((src) => {
        const audio = { src, paused: true, volume: 0, currentTime: 0, duration: 200, loop: false, released: false };
        h.audio.push(audio);
        return Object.assign(audio, { play: async () => { audio.paused = false; }, pause: () => { audio.paused = true; },
          // metadata arrives a moment later, as in a browser: the bed places the element then
          addEventListener: (kind: string, fn: () => void) => { if (kind === "loadedmetadata") setTimeout(fn, 0); }, removeAttribute: () => { audio.released = true; }, load() {} });
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

type Cue = { link: string; start?: number };
/** PlayerProvider + the real MusicBed on a scripted voice engine. `music[chapter]` = that chapter's cue (absent = quiet); `held` chapters answer only when released. */
async function rig(music: Record<number, Cue | undefined>, held: Set<number> = new Set()) {
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
  const pending: (() => void)[] = [];
  const source = { kind: "desktop", audioUrl: () => "/voice", saveProgress: async () => ({}), setRate: async () => undefined,
    musicCues: async (_book: string, chapter: number) => {
      const cue = music[chapter];
      const result = { cues: cue ? [{ start: cue.start ?? 0, end: 90, key: `${chapter}:0`, link: cue.link, src: `/${cue.link}` }] : [], levelDb: -20 };
      if (held.has(chapter)) return new Promise(resolve => { pending.push(() => resolve(result)); });
      return result;
    },
  } as unknown as ListenSource;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let player!: ReturnType<typeof usePlayer>;
  function Capture() { player = usePlayer(); return null; }
  const host = document.createElement("div"); const root = createRoot(host);
  const flush = async () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
  const wait = async (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
  await act(async () => root.render(<QueryClientProvider client={client}><SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Capture /></PlayerProvider></SourceProvider></QueryClientProvider>));
  await act(async () => player.play(book, chapters, 1, 0)); await flush();
  return {
    engine, state, fire, flush, wait, get player() { return player; },
    release: async () => { const list = pending.splice(0); await act(async () => { list.forEach(fn => fn()); }); await flush(); },
    sounding: () => h.audio.filter(a => !a.paused && a.volume > 0),
    close: async () => { await act(async () => root.unmount()); client.clear(); },
  };
}

const transitions = [["quiet-quiet", "", ""], ["quiet-music", "", "a"], ["music-quiet", "a", ""],
  ["music-other", "a", "b"], ["music-same", "a", "a"]] as const;
/** Same mode names on all three players (Android ChapterMusicTest, Qt MusicTests::chapterMusicMatrix): continuous = the voice runs into the
 *  next chapter; manual = next(); jump = jumpTo(n, 0); seek = jumpTo(n, 40), then seek inside the chapter past the cue end and back across
 *  it; resume = pause, next(), play; buffering = jumpTo(n, 0) while the voice stalls AND the cue answer is held. The step into chapter 3
 *  repeats the cell's mode. */
const modes = ["continuous", "manual", "jump", "seek", "resume", "buffering"] as const;

it.each(transitions.flatMap(([name, from, to]) => modes.map(mode => ({ name, from, to, mode }))))(
  "$name / $mode follows the new chapter through PlayerProvider", async ({ from, to, mode }) => {
    const r = await rig({ 1: from ? { link: from } : undefined, 2: to ? { link: to } : undefined, 3: { link: "a" } },
      mode === "buffering" ? new Set([2, 3]) : new Set());
    const go = async (target: number, link: string) => {
      await act(async () => {
        if (mode === "continuous") { Object.assign(r.state, { time: 100, paused: true, ended: true }); r.fire("ended"); }
        else if (mode === "manual") r.player.next();
        else if (mode === "jump" || mode === "buffering") r.player.jumpTo(target, 0);
        else if (mode === "seek") r.player.jumpTo(target, 40);
        else { r.player.pause(); r.player.next(); }
      });
      await r.flush();
      if (mode === "resume") {
        await r.wait(2500);
        expect(r.state.paused).toBe(true);
        expect(h.audio.every(a => a.paused)).toBe(true);
        await act(async () => r.player.resume());
      }
      if (mode === "buffering") {
        await act(async () => { r.fire("waiting"); }); // stream stalls: no time events from here
        await r.wait(2500);
        expect(h.bed!.activeLink).toBeNull();
        expect(r.sounding()).toEqual([]);
        await r.release();
        await r.wait(2500); // the stall ticker, not a time event, must start the bed
        expect(h.bed!.activeLink).toBe(link || null);
        expect(r.sounding().map(a => a.src)).toEqual(link ? [`/${link}`] : []);
        await act(async () => { r.fire("playing"); });
      }
      if (mode !== "buffering") await act(async () => { r.fire("time"); await vi.advanceTimersByTimeAsync(2500); });
      if (mode === "seek") {
        expect(r.state.time).toBe(40);
        await act(async () => { r.player.seek(95); await vi.advanceTimersByTimeAsync(2500); }); // past the cue end inside the chapter
        expect(h.bed!.activeLink).toBeNull();
        await act(async () => { r.player.seek(40); await vi.advanceTimersByTimeAsync(2500); }); // back across the cue edge
      }
      expect(r.player.track?.chapterId).toBe(target);
      expect(h.bed!.activeLink).toBe(link || null);
      expect(r.sounding().map(a => a.src)).toEqual(link ? [`/${link}`] : []);
      if (link) expect(r.sounding()[0].currentTime).toBe(mode === "seek" ? 40 : 0);
    };
    try {
      expect(h.bed!.activeLink).toBe(from || null);
      await act(async () => { r.state.time = 20; r.fire("time"); await vi.advanceTimersByTimeAsync(2500); });
      h.audio.forEach(audio => { audio.currentTime = 55; }); // a reused old element would still stand here
      await go(2, to);
      // A quiet chapter must never disable the next chapter's music clock.
      await go(3, "a");
    } finally { await r.close(); }
  });

it("next then previous inside the crossfade leaves one track and releases the rest", async () => {
  const r = await rig({ 1: { link: "a" }, 2: { link: "b" } });
  try {
    await r.wait(2500);
    await act(async () => r.player.next()); await r.flush();
    await r.wait(1000); // a -> b is half way (fadeSeconds = 2)
    await act(async () => r.player.previous()); await r.flush();
    await act(async () => { r.fire("time"); await vi.advanceTimersByTimeAsync(3000); });
    expect(r.player.track?.chapterId).toBe(1);
    expect(h.bed!.activeLink).toBe("a");
    const live = r.sounding();
    expect(live.map(a => a.src)).toEqual(["/a"]);
    expect(h.audio.filter(a => a !== live[0]).every(a => a.released)).toBe(true);
  } finally { await r.close(); }
});

it("a cue starting at 30 s comes in on the voice clock, not on the chapter change", async () => {
  const r = await rig({ 2: { link: "a", start: 30 } });
  try {
    await act(async () => { Object.assign(r.state, { time: 100, paused: true, ended: true }); r.fire("ended"); }); await r.flush();
    await act(async () => { r.fire("time"); await vi.advanceTimersByTimeAsync(2500); });
    expect(r.player.track?.chapterId).toBe(2);
    expect(h.bed!.activeLink).toBeNull();
    await act(async () => { r.state.time = 29; r.fire("time"); await vi.advanceTimersByTimeAsync(500); });
    expect(h.bed!.activeLink).toBeNull();
    await act(async () => { r.state.time = 31; r.fire("time"); await vi.advanceTimersByTimeAsync(2500); });
    expect(h.bed!.activeLink).toBe("a");
    expect(r.sounding().map(a => a.src)).toEqual(["/a"]);
    expect(r.sounding()[0].currentTime).toBe(1);
  } finally { await r.close(); }
});

it("a late cue answer while paused in the next chapter stays silent until play", async () => {
  const r = await rig({ 1: { link: "a" }, 2: { link: "b" } }, new Set([2]));
  try {
    await r.wait(2500);
    await act(async () => { r.player.pause(); r.player.next(); }); await r.flush();
    await r.wait(2500);
    await r.release();
    await r.wait(2500);
    // Checked after the answer arrived, not right after next().
    expect(r.state.paused).toBe(true);
    expect(h.audio.every(a => a.paused)).toBe(true);
    expect(h.bed!.activeLink).not.toBe("a");
    await act(async () => r.player.resume());
    await act(async () => { r.fire("time"); await vi.advanceTimersByTimeAsync(2500); });
    expect(h.bed!.activeLink).toBe("b");
    expect(r.sounding().map(a => a.src)).toEqual(["/b"]);
  } finally { await r.close(); }
});

it("a rate change inside the crossfade keeps one track", async () => {
  const r = await rig({ 1: { link: "a" }, 2: { link: "b" } });
  try {
    await r.wait(2500);
    await act(async () => r.player.next()); await r.flush();
    await r.wait(1000);
    await act(async () => r.player.setRate(1.5));
    await act(async () => { r.fire("time"); await vi.advanceTimersByTimeAsync(3000); });
    expect(h.bed!.activeLink).toBe("b");
    expect(r.sounding().map(a => a.src)).toEqual(["/b"]);
  } finally { await r.close(); }
});

it("paused in a quiet chapter, choosing a chapter with music stays silent until play", async () => {
  // The quiet chapter is reached while playing, so the bed last heard "playing"; only the pause in the quiet chapter says otherwise.
  const r = await rig({ 1: { link: "a" }, 3: { link: "b" } }, new Set([3]));
  try {
    await r.wait(2500);
    await act(async () => r.player.jumpTo(2, 0)); await r.flush();
    await act(async () => { r.fire("time"); await vi.advanceTimersByTimeAsync(2500); });
    expect(h.bed!.activeLink).toBeNull();
    await act(async () => { r.player.pause(); r.player.next(); }); await r.flush();
    await r.release();
    await r.wait(2500);
    expect(r.player.track?.chapterId).toBe(3);
    expect(r.state.paused).toBe(true);
    expect(h.audio.every(a => a.paused)).toBe(true);
    await act(async () => r.player.resume());
    await act(async () => { r.fire("time"); await vi.advanceTimersByTimeAsync(2500); });
    expect(r.sounding().map(a => a.src)).toEqual(["/b"]);
  } finally { await r.close(); }
});
