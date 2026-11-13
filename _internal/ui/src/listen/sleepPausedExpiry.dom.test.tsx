// @vitest-environment happy-dom
// Soát Android 12-11 mục 2 (web): hẹn giờ đứng vì tạm dừng tới 30 phút thì tự tắt - buổi nghe sau không bị hẹn giờ cũ tắt tiếng. Cùng hạn với điện thoại / Qt.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";
import { SLEEP_PAUSED_EXPIRES_MS, sleepExpired, sleepPausedNote } from "./sleep";

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

async function pause() { await act(async () => { paused = true; fire("pause"); }); }
async function resume() { await act(async () => { paused = false; fire("play"); fire("playing"); }); }
async function later(ms: number) { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); }

it("cùng hạn, cùng chữ với điện thoại và Qt", () => {
  expect(SLEEP_PAUSED_EXPIRES_MS).toBe(30 * 60_000);
  expect(sleepPausedNote()).toBe("Đang tạm dừng - đồng hồ cũng dừng. Dừng quá 30 phút thì hẹn giờ tự tắt.");
  expect(sleepExpired({ kind: "off" }, 0, SLEEP_PAUSED_EXPIRES_MS)).toBe(false);
  expect(sleepExpired({ kind: "chapter", chapters: 1 }, null, SLEEP_PAUSED_EXPIRES_MS)).toBe(false);
  expect(sleepExpired({ kind: "chapter", chapters: 1 }, 5, 5 + SLEEP_PAUSED_EXPIRES_MS - 1)).toBe(false);
  expect(sleepExpired({ kind: "chapter", chapters: 1 }, 5, 5 + SLEEP_PAUSED_EXPIRES_MS)).toBe(true);
});

for (const request of [{ kind: "minutes", minutes: 30 } as const, { kind: "chapter" } as const]) {
  it(`hẹn ${request.kind} dừng 30 phút thì tắt, phát lại không còn hẹn giờ`, async () => {
    await mount();
    await act(async () => { actions.setSleep(request); });
    await pause();
    await later(SLEEP_PAUSED_EXPIRES_MS - 60_000);
    expect(actions.sleep.kind).toBe(request.kind);
    await later(60_000);
    expect(actions.sleep.kind).toBe("off");
    await resume();
    expect(actions.sleep.kind).toBe("off");
  });
}

it("nhịp hết hạn bị hoãn (máy ngủ): phát lại vẫn tắt hẹn giờ quá hạn trước khi đồng hồ chạy", async () => {
  await mount();
  await act(async () => { actions.setSleep({ kind: "minutes", minutes: 30 }); });
  await pause();
  vi.setSystemTime(Date.now() + 9 * 3_600_000); // đồng hồ thật trôi, nhịp setTimeout chưa chạy
  await resume();
  expect(actions.sleep.kind).toBe("off");
});

it("phát lại trước hạn giữ hẹn giờ; hẹn lại khi đang dừng tính hạn từ đầu", async () => {
  await mount();
  await act(async () => { actions.setSleep({ kind: "minutes", minutes: 30 }); });
  await pause();
  await later(20 * 60_000);
  await resume();
  expect(actions.sleep.kind).toBe("minutes");
  await pause();
  await later(20 * 60_000);
  await act(async () => { actions.setSleep({ kind: "minutes", minutes: 15 }); });
  await later(20 * 60_000);
  expect(actions.sleep.kind).toBe("minutes");
  await later(11 * 60_000);
  expect(actions.sleep.kind).toBe("off");
});
