import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "@/listen/engine";

// Danh sách phát người nghe đã chọn mà lần hỏi đầu lỗi (mất mạng, danh mục chưa tải được): lỗi phải được báo và hỏi lại có khoảng chờ, khi mạng về, khi đổi chương
// (soát a103 F5; Android: MusicBed.retryCatalogLater).
const h = vi.hoisted(() => ({
  effects: [] as { run: () => void | (() => void); deps: readonly unknown[] }[],
  seed: null as unknown, bed: null as import("@/listen/musicBed").MusicBed | null,
}));
vi.mock("react", async (original) => {
  const react = await original<typeof import("react")>();
  return { ...react, useEffect: (run: () => void | (() => void), deps: readonly unknown[] = []) => h.effects.push({ run, deps }),
    // Mount with an already opened book; real hooks and action callbacks remain in use.
    useState: (initial: unknown) => { const seed = initial === null && h.seed ? h.seed : initial; if (seed === h.seed) h.seed = null; return react.useState(seed); },
  };
});
vi.mock("@/listen/musicBed", async (original) => {
  const actual = await original<typeof import("@/listen/musicBed")>();
  return { ...actual, MusicBed: class extends actual.MusicBed {
    constructor() {
      super((src) => Object.assign({ paused: true, volume: 0, currentTime: 0, duration: 200, loop: false, src }, {
        play: () => Promise.resolve(), pause: () => undefined, addEventListener: () => undefined, removeAttribute: () => undefined, load: () => undefined }) as never);
      h.bed = this;
    }
  } };
});
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { dismiss: vi.fn(), info: vi.fn(), success: vi.fn(), warning: vi.fn() }) }));
vi.mock("@/listen/OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("@/listen/source", async (original) => ({ ...await original<typeof import("@/listen/source")>(), useListenBook: () => ({ data: undefined }) }));
import { SourceProvider, type ListenSource } from "@/listen/source";
import { PlayerProvider, usePlayer } from "@/listen/player";

let page: EventTarget & { location: unknown };
beforeEach(() => {
  vi.useFakeTimers();
  h.effects = []; h.bed = null;
  h.seed = { bookId: "music-test", chapterId: 1, bookTitle: "Sách", title: "Chương 1", url: "/audio" };
  page = Object.assign(new EventTarget(), { location: { href: "http://localhost/", search: "" } });
  vi.stubGlobal("window", page);
  vi.stubGlobal("navigator", { mediaSession: {} });
});
afterEach(() => { h.bed?.stop(); vi.useRealTimers(); vi.unstubAllGlobals(); });

const failed = { playlist: "calm", tracks: [], levelDb: -20, error: "Mất mạng" };
const recovered = { playlist: "calm", tracks: [{ link: "cached", src: "/cached", duration: 180, gainDb: -20 }], levelDb: -20, error: "" };

async function flush(rounds = 8) { for (let i = 0; i < rounds; i++) await Promise.resolve(); }

async function mount(answers: unknown[]) {
  const listeners = new Map<string, (() => void)[]>();
  const fire = (kind: string) => listeners.get(kind)?.forEach((listener) => listener());
  const engine = { get time() { return 20; }, duration: 100, get paused() { return false; }, ended: false,
    on: (kind: string, listener: () => void) => { listeners.set(kind, [...(listeners.get(kind) ?? []), listener]); return () => undefined; },
    seek: vi.fn(), stop: vi.fn(), setVolume: vi.fn(), setRate: vi.fn(), load: vi.fn(),
  } as unknown as AudioEngine;
  const askPlaylist = vi.fn(async () => answers.length > 1 ? answers.shift() : answers[0]);
  const source = { musicPlaylist: askPlaylist, kind: "desktop", audioUrl: () => "/audio", saveProgress: async () => undefined, setRate: async () => undefined,
    musicCues: async () => JSON.parse(readFileSync(new URL("../../../tests/fixtures/music/edge_cases.json", import.meta.url), "utf8")).emptyResponse,
  } as unknown as ListenSource;
  function Capture() { usePlayer(); return null; }
  renderToString(<QueryClientProvider client={new QueryClient()}><SourceProvider source={source}><PlayerProvider engine={engine}><Capture /></PlayerProvider></SourceProvider></QueryClientProvider>);
  for (const effect of h.effects.filter((effect) => effect.deps.includes(h.bed))) effect.run();
  await flush();
  fire("time");
  vi.advanceTimersByTime(3000);
  return { askPlaylist, rerun: () => h.effects.find((effect) => effect.deps.includes(h.bed) && effect.deps.length === 4)!.run() };
}

it("a chosen playlist that failed is asked again after a wait, without choosing again", async () => {
  const { askPlaylist } = await mount([failed, recovered]);
  expect(askPlaylist).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(20_000);
  await flush();
  expect(askPlaylist).toHaveBeenCalledTimes(2);
  await vi.advanceTimersByTimeAsync(10 * 60_000); // đã có bài: không hỏi nữa
  await flush();
  expect(askPlaylist).toHaveBeenCalledTimes(2);
});

it("the network coming back asks the failed playlist again at once", async () => {
  const { askPlaylist } = await mount([failed, recovered]);
  page.dispatchEvent(new Event("online"));
  await flush();
  expect(askPlaylist).toHaveBeenCalledTimes(2);
});

it("a chapter change asks a failed playlist again, but reuses a good answer", async () => {
  const bad = await mount([failed, failed, recovered]);
  bad.rerun();
  await flush();
  expect(bad.askPlaylist).toHaveBeenCalledTimes(2);
});

it("a good answer is kept across a chapter change", async () => {
  h.bed?.stop();
  const good = await mount([recovered]);
  good.rerun();
  await flush();
  expect(good.askPlaylist).toHaveBeenCalledTimes(1);
});
