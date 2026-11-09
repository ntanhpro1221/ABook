// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";
import { AUTO_SLEEP_SCHEDULE } from "./sleepActivity";

const h = vi.hoisted(() => ({ feedback: vi.fn(), toast: Object.assign(vi.fn(), { dismiss: vi.fn(), success: vi.fn(), warning: vi.fn(), error: vi.fn() }) }));
vi.mock("@/shared/feedback", async original => ({ ...await original<typeof import("@/shared/feedback")>(), feedback: h.feedback }));
vi.mock("sonner", () => ({ toast: h.toast }));
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./readAloudVoice", async original => ({ ...await original<typeof import("./readAloudVoice")>(), voicesOf: async () => [] }));

const chapters = [1, 2].map(id => ({ id, title: `Chương ${id}`, fullTitle: `Chương ${id}`, available: true, duration: 100 })) as ListenChapter[];
const book = { id: "a", title: "A", narrator: "Giọng", complete: true, chapters, state: { chapters: {} } } as ListenBook;
let root: Root;
let actions: ReturnType<typeof usePlayer>;
let paused: boolean;
let osIdle: number | null;
let engine: AudioEngine;
const listeners = new Map<string, Set<() => void>>();
const fire = (kind: string) => listeners.get(kind)?.forEach(listener => listener());
function Probe() { actions = usePlayer(); return null; }

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  clock = new Date(2026, 10, 7, 23).getTime(); vi.setSystemTime(clock);
  vi.clearAllMocks(); listeners.clear(); paused = true; osIdle = 0;
  vi.stubGlobal("navigator", Object.assign(Object.create(navigator), { mediaSession: { setActionHandler: vi.fn() } }));
  vi.stubGlobal("MediaMetadata", class { constructor(data: object) { Object.assign(this, data); } });
  engine = { time: 12, duration: 100, get paused() { return paused; }, ended: false,
    load: vi.fn(), play: vi.fn(() => { paused = false; fire("play"); }), pause: vi.fn(() => { paused = true; fire("pause"); }),
    stop: vi.fn(), seek: vi.fn(), setRate: vi.fn(), setVolume: vi.fn(),
    on: (kind: string, listener: () => void) => { const set = listeners.get(kind) ?? new Set(); set.add(listener); listeners.set(kind, set); return () => set.delete(listener); },
  } as unknown as AudioEngine;
  root = createRoot(document.body.appendChild(document.createElement("div")));
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.useRealTimers(); vi.unstubAllGlobals(); });

async function mount(schedule = false, reader: (() => Promise<number | null>) | undefined = async () => osIdle) {
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress: async () => {}, beginProgress: async () => {},
    setRate: async () => {}, book: async () => book } as unknown as ListenSource;
  await act(() => root.render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { queryFn: async () => [], retry: false } } })}>
    <SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false} systemIdleReader={reader}
      sleepSchedule={schedule ? { from: "22:00", to: "06:00", minutes: 30 } : null}><Probe /></PlayerProvider></SourceProvider>
  </QueryClientProvider>));
  await act(async () => { actions.prepare(book, chapters, 1, 12); paused = false; fire("play"); fire("playing"); });
}
let clock = new Date(2026, 10, 7, 23).getTime();
async function elapsed(ms: number) {
  vi.setSystemTime(vi.getMockedSystemTime()!.getTime() + ms);
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
}

it("default playback stays without a timer after three idle hours", async () => {
  await mount();
  osIdle = 3 * 3_600_000;
  await elapsed(3 * 3_600_000);
  expect(actions.sleep.kind).toBe("off");
  expect(paused).toBe(false);
  expect(engine.pause).not.toHaveBeenCalled();
  expect(h.toast).not.toHaveBeenCalled();
});

it("the extend button makes exactly one timer confirmation and an off timer stays silent", async () => {
  await mount();
  await act(async () => actions.extendSleep());
  expect(h.feedback).not.toHaveBeenCalled();
  await act(async () => actions.setSleep({ kind: "minutes", minutes: 10 }));
  await act(async () => actions.extendSleep());
  expect(h.feedback).toHaveBeenCalledExactlyOnceWith("sleepExtend");
});

it("a key during chapter fade confirms once and stops the fade", async () => {
  await mount();
  await act(async () => actions.setSleep({ kind: "chapter" }));
  Object.assign(engine, { time: 95 });
  await elapsed(1000);
  expect(actions.fading).toBe(true);
  expect(h.feedback).toHaveBeenCalledExactlyOnceWith("sleepWarn");
  h.feedback.mockClear();
  await act(async () => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "+", cancelable: true })); });
  expect(h.feedback).toHaveBeenCalledExactlyOnceWith("sleepExtend");
  expect(actions.fading).toBe(false);
  expect(actions.sleep.kind).toBe("minutes");
});

it("three hours in another app cannot arm any timer", async () => {
  await mount(); osIdle = 500;
  await elapsed(3 * 3_600_000);
  expect(actions.sleep.kind).toBe("off");
});
it("unknown system evidence cannot arm the night schedule", async () => {
  await mount(true); osIdle = null;
  await elapsed(3 * 3_600_000);
  expect(actions.sleep.kind).toBe("off");
});
it("a delayed OS reply cannot arm a timer using stale evidence", async () => {
  let answer!: (value: number) => void;
  await mount(true, () => new Promise<number>(resolve => { answer = resolve; }));
  vi.setSystemTime(vi.getMockedSystemTime()!.getTime() + 2 * 3_600_000);
  await act(async () => { answer(2 * 3_600_000); });
  expect(actions.sleep.kind).toBe("off");
});
it("input in another app cancels an existing automatic timer, including a missed immediate event", async () => {
  await mount(true); osIdle = 121_000;
  await elapsed(121_000);
  expect(actions.sleep.kind).toBe("minutes");
  osIdle = 5000;
  await elapsed(5000);
  expect(actions.sleep.kind).toBe("off");
});
it("media seek and chapter controls count as awake without DOM input", async () => {
  await mount(true); osIdle = 121_000;
  await elapsed(121_000);
  expect(actions.sleep.kind).toBe("minutes");
  await act(async () => { actions.skip(15); actions.next(); });
  expect(actions.sleep.kind).toBe("off");
  await elapsed(1000);
  expect(actions.sleep.kind).toBe("off");
});
it("manual timers survive OS and app activity", async () => {
  await mount();
  await act(async () => { actions.setSleep({ kind: "minutes", minutes: 30 }); window.dispatchEvent(new Event("focus")); });
  osIdle = 100;
  await elapsed(1000);
  expect(actions.sleep.kind).toBe("minutes");
});
it("night schedule waits for idle evidence, gives its reason and respects cancellation for that night", async () => {
  await mount(true);
  expect(actions.sleep.kind).toBe("off");
  osIdle = 121_000;
  await elapsed(121_000);
  expect(actions.sleep.kind).toBe("minutes");
  expect(h.toast).toHaveBeenCalledWith(AUTO_SLEEP_SCHEDULE, expect.anything());
  await act(async () => actions.setSleep({ kind: "off" }));
  osIdle = 300_000;
  await elapsed(300_000);
  expect(actions.sleep.kind).toBe("off");
});
