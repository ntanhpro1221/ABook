import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Tự lùi khi nghe lại trên máy tính (soát a100 T1): có công tắc, tắt thì cả ba đường nghe tiếp (bấm phát lại, mở lại app, nghe tiếp từ chỗ lưu) không lùi.
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
// Lần nghe cuối cách đây một giờ, đúng chỗ 60 giây: mở lại app thì lùi theo lần nghe cuối.
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

async function session(autoRewind: boolean | undefined, book: never = fresh) {
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
  const props = autoRewind === undefined ? {} : { autoRewind };
  renderToString(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { queryFn: async () => [], retry: false } } })}>
      <SourceProvider source={source as never}>
        <PlayerProvider engine={engine as never} keyboard={false} {...props}><Capture /></PlayerProvider>
      </SourceProvider>
    </QueryClientProvider>,
  );
  const cleanups = h.effects.filter((e) => e.deps.includes(engine)).map((e) => e.run()).filter((x): x is () => void => typeof x === "function");
  const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
  return { actions, engine, settle, done: () => cleanups.forEach((c) => c()) };
}

describe("tự lùi khi nghe lại (máy tính)", () => {
  it("mặc định bật: nghe tiếp sau một phút dừng thì lùi 5 giây", async () => {
    const { actions, engine, settle, done } = await session(undefined);
    actions.prepare(fresh, chapters as never, 1, 60);
    await settle();
    engine.seek.mockClear();
    actions.pause();
    vi.advanceTimersByTime(60_000);
    actions.resume();
    await settle();
    expect(engine.seek).toHaveBeenCalledWith(55);
    expect(actions.options.autoRewind).toBe(true);
    done();
  });

  it("tắt: nghe tiếp sau dừng lâu không lùi", async () => {
    const { actions, engine, settle, done } = await session(false);
    actions.prepare(fresh, chapters as never, 1, 60);
    await settle();
    actions.pause();
    vi.advanceTimersByTime(60_000);
    actions.resume();
    await settle();
    expect(engine.seek).not.toHaveBeenCalled();
    expect(actions.options.autoRewind).toBe(false);
    done();
  });

  it("mở lại app (prepare) cũng theo công tắc: bật thì lùi theo lần nghe cuối, tắt thì đúng chỗ đã lưu", async () => {
    const on = await session(true, lastHeard);
    on.actions.prepare(lastHeard, chapters as never, 1, 60);
    await on.settle();
    expect(on.engine.load.mock.calls[0][1]).toBe(50); // dừng 1 giờ: lùi 10 giây
    on.done();
    h.effects = [];
    const off = await session(false, lastHeard);
    off.actions.prepare(lastHeard, chapters as never, 1, 60);
    await off.settle();
    expect(off.engine.load.mock.calls[0][1]).toBe(60);
    off.done();
  });

  it("bấm nghe tiếp đúng chỗ đã lưu (play) cũng theo công tắc", async () => {
    const on = await session(true, lastHeard);
    on.actions.play(lastHeard, chapters as never, 1, 60);
    await on.settle();
    expect(on.engine.load.mock.calls[0][1]).toBe(50);
    on.done();
    h.effects = [];
    const off = await session(false, lastHeard);
    off.actions.play(lastHeard, chapters as never, 1, 60);
    await off.settle();
    expect(off.engine.load.mock.calls[0][1]).toBe(60);
    off.done();
  });
});
