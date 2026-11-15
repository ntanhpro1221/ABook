// @vitest-environment happy-dom
// A selected sleep timer stays enabled until the listener switches it off.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";
import { sleepPausedNote } from "./sleep";

const h = vi.hoisted(() => ({ feedback: vi.fn(), toast: Object.assign(vi.fn(), { dismiss: vi.fn(), success: vi.fn(), warning: vi.fn(), error: vi.fn() }) }));
vi.mock("@/shared/feedback", async original => ({ ...await original<typeof import("@/shared/feedback")>(), feedback: h.feedback }));
vi.mock("sonner", () => ({ toast: h.toast }));
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./readAloudVoice", async original => ({ ...await original<typeof import("./readAloudVoice")>(), voicesOf: async () => [] }));

const chapters = [1, 2].map(id => ({ id, title: `Chương ${id}`, fullTitle: `Chương ${id}`, available: true, duration: 100 })) as ListenChapter[];
const book = { id: "a", title: "A", narrator: "Giọng", complete: true, chapters, state: { chapters: {} } } as ListenBook;
let root: Root;
let actions: ReturnType<typeof usePlayer>;
let soundTime = 12;
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
  vi.clearAllMocks(); localStorage.clear(); listeners.clear(); paused = true; osIdle = 0;
  vi.stubGlobal("navigator", Object.assign(Object.create(navigator), { mediaSession: { setActionHandler: vi.fn() } }));
  vi.stubGlobal("MediaMetadata", class { constructor(data: object) { Object.assign(this, data); } });
  soundTime = 12;
  engine = { get time() { return soundTime; }, duration: 10_000, get paused() { return paused; }, ended: false,
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

async function pause() { await act(async () => { paused = true; fire("pause"); }); }
async function resume() { await act(async () => { paused = false; fire("play"); fire("playing"); }); }

it("uses the same paused wording on all platforms", () => {
  expect(sleepPausedNote()).toBe("Đang tạm dừng - đồng hồ cũng dừng.");
});

for (const request of [{ kind: "minutes", minutes: 30 } as const, { kind: "chapter", chapters: 2 } as const]) {
  it(`keeps ${request.kind} enabled through an overnight pause`, async () => {
    await mount();
    await act(async () => { actions.setSleep(request); });
    await pause();
    vi.setSystemTime(clock + 12 * 3_600_000);
    await resume();
    expect(actions.sleep.kind).toBe(request.kind);
    await act(async () => { actions.setSleep({ kind: "off" }); });
    expect(actions.sleep.kind).toBe("off");
  });
}

async function hear(seconds: number) {
  await act(async () => {
    for (let i = 0; i < seconds * 10; i++) { soundTime += 0.1; vi.advanceTimersByTime(100); }
  });
}

it("expires twice with a full selected cycle between stops", async () => {
  await mount();
  await act(async () => { actions.setSleep({ kind: "minutes", minutes: 1 }); });
  await hear(61);
  expect(paused).toBe(true);
  expect(actions.sleep).toMatchObject({ kind: "minutes", minutes: 1, leftMs: 60_000, since: null });
  expect(actions.sleepStoppedAt).not.toBeNull();
  await resume();
  await hear(58);
  expect(paused).toBe(false);
  await hear(3);
  expect(paused).toBe(true);
  expect(actions.sleep).toMatchObject({ kind: "minutes", leftMs: 60_000 });
});

for (const name of ["focus", "pointerdown", "pointermove", "wheel", "keydown", "touchmove"]) {
  it(`resets on ${name} after six minutes`, async () => {
    await mount();
    await act(async () => { actions.setSleep({ kind: "minutes", minutes: 10 }); });
    await hear(360);
    expect(actions.sleep.kind === "minutes" && actions.sleep.leftMs).toBeLessThan(241_000);
    await act(async () => { window.dispatchEvent(new Event(name)); });
    expect(actions.sleep).toMatchObject({ kind: "minutes", minutes: 10, leftMs: 600_000 });
  });
}

it("changing chapter and minute picks never fabricates an end event", async () => {
  await mount();
  for (const chapters of [2, 1, 2, 3, 2, 1, 2]) {
    await act(async () => { actions.setSleep({ kind: "chapter", chapters }); });
    expect(actions.sleep).toEqual({ kind: "chapter", chapters });
    expect(paused).toBe(false);
  }
  for (const minutes of [2, 1, 2, 3, 2, 1, 2]) {
    await act(async () => { actions.setSleep({ kind: "minutes", minutes }); });
    expect(actions.sleep).toMatchObject({ kind: "minutes", minutes });
    expect(paused).toBe(false);
  }
  expect(h.feedback).not.toHaveBeenCalledWith("sleepExtend");
});

it("chapter expiry retains the original count; extension only changes this cycle", async () => {
  await mount();
  await act(async () => { actions.setSleep({ kind: "chapter", chapters: 2 }); actions.extendSleep(); });
  expect(actions.sleep.kind).toBe("minutes");
  await hear(601);
  expect(paused).toBe(true);
  expect(actions.sleep).toEqual({ kind: "chapter", chapters: 2 });
  await act(async () => { actions.extendSleep(); });
  await act(async () => { window.dispatchEvent(new Event("focus")); });
  await resume();
  expect(actions.sleep.kind).toBe("minutes");
  await hear(601);
  expect(paused).toBe(true);
  expect(actions.sleep).toEqual({ kind: "chapter", chapters: 2 });
});
