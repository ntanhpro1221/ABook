// @vitest-environment happy-dom
// Chốt chặn cuối của trình phát (bản Qt: Player::checkStall): chờ âm thanh quá STALL_MS (215 s) trên bất kỳ nguồn nào thì thành đúng lỗi của một nguồn hỏng,
// kèm "Thử lại" ở PlayerAlert (nhận ra giọng hỏng nhờ isVoiceStuck).
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import { STALL_MS } from "@/shared/hostWait";
import { NO_USABLE_VOICE, isVoiceStuck } from "./readAloudVoice";
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";

vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./readAloudVoice", async (original) => ({ ...(await original<typeof import("./readAloudVoice")>()), voicesOf: async () => [] }));

const PLAY_ERROR = "Không phát được chương này - file có thể đã bị xoá hoặc đang được ghi lại.";
const audio = [1, 2].map((id) => ({ id, title: `Chương ${id}`, fullTitle: `Chương ${id}`, available: true, duration: 100 })) as ListenChapter[];
const text = audio.map((chapter) => ({ ...chapter, state: "text" })) as ListenChapter[];
const bookOf = (chapters: ListenChapter[]) => ({ id: "a", title: "A", narrator: "Giọng", complete: true, chapters, state: { chapters: {} } }) as ListenBook;

let root: Root;
let actions: ReturnType<typeof usePlayer>;
let engine: AudioEngine;
let paused: boolean;
const listeners = new Map<string, (() => void)[]>();
const fire = (kind: string) => listeners.get(kind)?.forEach((listener) => listener());

function Probe() {
  actions = usePlayer();
  return <p data-error={actions.error} data-buffering={String(actions.buffering)} data-playing={String(actions.playing)} />;
}
const shown = () => document.querySelector("p")!;

async function mount(chapters: ListenChapter[]) {
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress: vi.fn().mockResolvedValue(undefined), beginProgress: vi.fn().mockResolvedValue(undefined),
    setRate: async () => undefined, book: async () => bookOf(chapters) } as unknown as ListenSource;
  await act(() => root.render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { queryFn: async () => [], retry: false } } })}>
      <SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Probe /></PlayerProvider></SourceProvider>
    </QueryClientProvider>,
  ));
  await act(async () => actions.prepare(bookOf(chapters), chapters, 1, 12));
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  listeners.clear();
  paused = true;
  engine = { time: 12, duration: 100, get paused() { return paused; }, ended: false, error: "",
    load: vi.fn((_track, _at: number, autoplay: boolean) => { paused = !autoplay; }),
    play: vi.fn(() => { paused = false; fire("play"); }), pause: vi.fn(() => { paused = true; fire("pause"); }),
    stop: vi.fn(), seek: vi.fn(), setRate: vi.fn(), setVolume: vi.fn(),
    on: (kind: string, listener: () => void) => { listeners.set(kind, [...(listeners.get(kind) ?? []), listener]); return () => undefined; },
  } as unknown as AudioEngine;
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  vi.stubGlobal("navigator", Object.assign(Object.create(navigator), { mediaSession: {} }));
  vi.stubGlobal("MediaMetadata", class { constructor(data: object) { Object.assign(this, data); } });
  root = createRoot(document.body.appendChild(document.createElement("div")));
});
afterEach(async () => {
  await act(() => root.unmount());
  document.body.replaceChildren();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const startWaiting = async () => { await act(async () => { paused = false; fire("play"); fire("waiting"); }); };

it("giọng đọc chờ quá 215 s: lỗi giọng không dùng được (PlayerAlert đưa Thử lại), nút Phát trở lại", async () => {
  await mount(text);
  await startWaiting();
  expect(shown().dataset.buffering).toBe("true");
  await act(async () => { vi.advanceTimersByTime(STALL_MS - 1); });
  expect(shown().dataset.error).toBe("");
  await act(async () => { vi.advanceTimersByTime(1); });
  expect(STALL_MS).toBe(215_000);
  expect(shown().dataset.error).toBe(NO_USABLE_VOICE);
  expect(isVoiceStuck(shown().dataset.error!)).toBe(true);
  expect(shown().dataset.buffering).toBe("false");
  expect(shown().dataset.playing).toBe("false");
  expect(engine.pause).toHaveBeenCalled();
});

it("file audio chờ quá 215 s: cùng lỗi như nguồn hỏng", async () => {
  await mount(audio);
  await startWaiting();
  await act(async () => { vi.advanceTimersByTime(STALL_MS); });
  expect(shown().dataset.error).toBe(PLAY_ERROR);
});

it("có tiếng trước hạn thì không lỗi; chờ lại thì đếm lại từ đầu", async () => {
  await mount(text);
  await startWaiting();
  await act(async () => { vi.advanceTimersByTime(STALL_MS - 5_000); });
  await act(async () => { fire("playing"); });
  await act(async () => { vi.advanceTimersByTime(STALL_MS); });
  expect(shown().dataset.error).toBe("");
  await act(async () => { fire("waiting"); vi.advanceTimersByTime(STALL_MS - 1); });
  expect(shown().dataset.error).toBe("");
  await act(async () => { vi.advanceTimersByTime(1); });
  expect(shown().dataset.error).toBe(NO_USABLE_VOICE);
});

it("người nghe tạm dừng khi đang chờ thì không báo lỗi sau đó", async () => {
  await mount(text);
  await startWaiting();
  await act(async () => { engine.pause(); });
  await act(async () => { vi.advanceTimersByTime(STALL_MS * 2); });
  expect(shown().dataset.error).toBe("");
});

it("Thử lại sau lỗi chờ quá lâu nạp lại đúng chương, đúng chỗ", async () => {
  await mount(text);
  await startWaiting();
  await act(async () => { vi.advanceTimersByTime(STALL_MS); });
  const loads = vi.mocked(engine.load).mock.calls.length;
  await act(async () => { actions.retry(); });
  expect(vi.mocked(engine.load).mock.calls.length).toBe(loads + 1);
  expect(vi.mocked(engine.load).mock.lastCall![2]).toBe(true);
});
