import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Resume must hold the exact cursor, including when reopening a book.
const h = vi.hoisted(() => ({ effects: [] as { run: () => unknown; deps: unknown[] }[] }));
vi.mock("react", async (original) => {
  const react = await original<typeof import("react")>();
  return { ...react, useEffect: (run: () => unknown, deps: unknown[] = []) => h.effects.push({ run, deps }) };
});
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./readAloudVoice", async (original) => ({ ...(await original<typeof import("./readAloudVoice")>()), voicesOf: async () => [] }));
import { SourceProvider } from "./source";
import { PlayerProvider, usePlayer } from "./player";

const chapters = [{ id: 1, title: "Chương 1", fullTitle: "Chương 1", available: true, duration: 100 }];
const fresh = { id: "test", title: "Sách", complete: true, chapters, state: { chapters: {} } } as never;
// Last listened an hour ago, at exactly sixty seconds.
const lastHeard = { id: "test", title: "Sách", complete: true, chapters, state: { chapters: {}, last: { chapterId: 1, seconds: 60, at: Date.now() / 1000 - 3600 } } } as never;

beforeEach(() => {
  vi.useFakeTimers();
  h.effects = [];
  Object.assign(globalThis, {
    window: Object.assign(new EventTarget(), {
      location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
      matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
      setInterval: (...args: Parameters<typeof setInterval>) => setInterval(...args),
      clearInterval: (id: Parameters<typeof clearInterval>[0]) => clearInterval(id),
      setTimeout: (...args: Parameters<typeof setTimeout>) => setTimeout(...args),
      clearTimeout: (id: Parameters<typeof clearTimeout>[0]) => clearTimeout(id),
    }),
  });
  vi.stubGlobal("navigator", { mediaSession: {} });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function session(book: never = fresh) {
  let actions!: ReturnType<typeof usePlayer>;
  const events = new Map<string, (() => void)[]>();
  const state = { time: 60, paused: true };
  const fire = (kind: string) => events.get(kind)?.forEach((f) => f());
  const engine = {
    get time() { return state.time; },
    duration: 100,
    get paused() { return state.paused; },
    ended: false,
    load: vi.fn((_track: unknown, at: number, autoplay: boolean) => { state.time = at; state.paused = !autoplay; }),
    play: vi.fn(() => { state.paused = false; fire("play"); }),
    pause: vi.fn(() => { state.paused = true; fire("pause"); }),
    stop: vi.fn(),
    seek: vi.fn((at: number) => { state.time = at; }),
    setRate: vi.fn(),
    setVolume: vi.fn(),
    on: (kind: string, f: () => void) => { events.set(kind, [...(events.get(kind) ?? []), f]); return () => undefined; },
  };
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress: async () => undefined, beginProgress: async () => undefined, setRate: async () => undefined, book: async () => book };
  function Capture() { actions = usePlayer(); return null; }
  renderToString(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { queryFn: async () => [], retry: false } } })}>
      <SourceProvider source={source as never}>
        <PlayerProvider engine={engine as never} keyboard={false}><Capture /></PlayerProvider>
      </SourceProvider>
    </QueryClientProvider>,
  );
  const cleanups = h.effects.filter((e) => e.deps.includes(engine)).map((e) => e.run()).filter((x): x is () => void => typeof x === "function");
  const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
  return { actions, engine, settle, done: () => cleanups.forEach((c) => c()) };
}

describe("resume preserves heard content", () => {
  it.each([5_000, 60_000, 3_600_000])("keeps the cursor after a %i ms pause", async (pauseMs) => {
    const { actions, engine, settle, done } = await session();
    actions.prepare(fresh, chapters as never, 1, 60);
    await settle();
    engine.seek.mockClear();
    actions.pause();
    vi.advanceTimersByTime(pauseMs);
    actions.resume();
    await settle();
    expect(engine.time).toBe(60);
    expect(engine.seek).not.toHaveBeenCalled();
    done();
  });

  it.each(["prepare", "play"] as const)("%s holds the saved cursor on reopen", async (action) => {
    const { actions, engine, settle, done } = await session(lastHeard);
    actions[action](lastHeard, chapters as never, 1, 60);
    await settle();
    expect(engine.load.mock.calls[0][1]).toBe(60);
    done();
  });

  it("still permits an explicit backward seek", async () => {
    const { actions, engine, settle, done } = await session();
    actions.prepare(fresh, chapters as never, 1, 60);
    await settle();
    actions.seek(55);
    expect(engine.time).toBe(55);
    done();
  });
});
