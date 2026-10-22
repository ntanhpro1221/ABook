import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import { MusicBed } from "./musicBed";
import * as apiModule from "@/studio/api";

const h = vi.hoisted(() => ({ effects: [] as { run: () => void | (() => void); deps: readonly unknown[] }[], dismiss: vi.fn(), playing: false, falseIndex: 0,
  back: () => undefined as void, stopWatch: vi.fn() }));
vi.mock("./peerBack", async (original) => ({ ...await original<typeof import("./peerBack")>(), watchUntilBack: (_probe: unknown, back: () => void) => { h.back = back; return h.stopWatch; } }));
vi.mock("react", async (original) => {
  const react = await original<typeof import("react")>();
  return { ...react, useEffect: (run: () => void, deps: readonly unknown[] = []) => h.effects.push({ run, deps }),
    useState: (initial: unknown) => react.useState(initial === false && h.falseIndex++ === 0 ? h.playing : h.playing && typeof initial === "object" && initial !== null && "kind" in initial && initial.kind === "off" ? { kind: "minutes", minutes: 1, leftMs: 60000, since: null } : initial) };
});
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { dismiss: h.dismiss, info: vi.fn(), success: vi.fn(), warning: vi.fn() }) }));
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./readAloudVoice", async (original) => ({ ...await original<typeof import("./readAloudVoice")>(), voicesOf: async () => [] }));
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";

const chapters = [1, 2].map((id) => ({ id, title: `Chương ${id}`, fullTitle: `Chương ${id}`, available: true, duration: 100 })) as ListenChapter[];
const book = { id: "a", title: "A", narrator: "Giọng", complete: true, chapters, state: { chapters: {} } } as ListenBook;
const cleanups: (() => void)[] = [];
beforeEach(() => {
  vi.useFakeTimers(); h.effects = []; h.dismiss.mockClear(); h.playing = false; h.falseIndex = 0;
  vi.stubGlobal("window", Object.assign(new EventTarget(), { location: { href: "http://localhost/", search: "" },
    setInterval, clearInterval, setTimeout, clearTimeout, requestAnimationFrame: vi.fn(() => 1), cancelAnimationFrame: vi.fn() }));
  vi.stubGlobal("navigator", { mediaSession: {} });
  vi.stubGlobal("MediaMetadata", class { constructor(data: object) { Object.assign(this, data); } });
});
afterEach(() => { cleanups.splice(0).forEach((clean) => clean()); vi.useRealTimers(); vi.unstubAllGlobals(); });
async function settle() { for (let i = 0; i < 20; ++i) await Promise.resolve(); }
function mount(extra: Partial<ListenSource> = {}) {
  let actions!: ReturnType<typeof usePlayer>;
  const listeners = new Map<string, (() => void)[]>();
  const fire = (kind: string) => listeners.get(kind)?.forEach((listener) => listener());
  const state = { time: 12, paused: true };
  const engine = { get time() { return state.time; }, duration: 100, get paused() { return state.paused; }, ended: false,
    load: vi.fn((_track, at: number, autoplay: boolean) => { state.time = at; state.paused = !autoplay; }),
    play: vi.fn(() => { state.paused = false; fire("play"); }), pause: vi.fn(() => { state.paused = true; fire("pause"); }),
    stop: vi.fn(() => { state.paused = true; }), seek: vi.fn((at: number) => { state.time = at; }),
    setRate: vi.fn(), setVolume: vi.fn(), on: (kind: string, listener: () => void) => { listeners.set(kind, [...(listeners.get(kind) ?? []), listener]); return () => undefined; },
  } as unknown as AudioEngine;
  const saveProgress = vi.fn().mockResolvedValue(undefined);
  const beginProgress = vi.fn().mockResolvedValue(undefined);
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress, beginProgress, setRate: async () => undefined, book: async () => book, ...extra } as unknown as ListenSource;
  function Capture() { actions = usePlayer(); return null; }
  renderToString(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { queryFn: async () => [], retry: false } } })}><SourceProvider source={source}><PlayerProvider engine={engine} keyboard={false}><Capture /></PlayerProvider></SourceProvider></QueryClientProvider>);
  // Chạy các effect nối sự kiện của engine và đường đóng trang; không khởi động truy vấn/nhạc.
  for (const effect of h.effects.filter((effect) => effect.deps.includes(engine) || effect.run.toString().includes('"pagehide"'))) {
    const cleanup = effect.run(); if (cleanup) cleanups.push(cleanup);
  }
  actions.prepare(book, chapters, 1, 12);
  return { actions, engine, state, fire, saveProgress, beginProgress };
}
it("tab đang dừng không di chuyển thì pagehide không gửi progress", async () => {
  const { saveProgress, beginProgress } = mount();
  await settle();
  window.dispatchEvent(new Event("pagehide"));
  await settle();
  expect(beginProgress).toHaveBeenCalledWith("a", expect.any(String), undefined);
  expect(saveProgress).not.toHaveBeenCalled();
});
it("tua khi đang dừng lưu ngay lúc seeked, pagehide gửi keepalive và chỉ nhận chỗ sau ACK", async () => {
  const { actions, state, fire, saveProgress } = mount();
  await settle();
  actions.seek(40);
  fire("seeked");
  await settle();
  expect(saveProgress).toHaveBeenCalledWith("a", 1, 40, 100, undefined, undefined, expect.objectContaining({ revision: 1 }));
  let ack!: () => void;
  saveProgress.mockImplementationOnce(() => new Promise<void>((done) => { ack = done; }));
  const stamp = actions.positionStamp();
  vi.advanceTimersByTime(500);
  state.time = 55;
  window.dispatchEvent(new Event("pagehide"));
  await settle();
  expect(saveProgress).toHaveBeenLastCalledWith("a", 1, 55, 100, undefined, undefined, expect.objectContaining({ keepalive: true }));
  expect(actions.positionStamp()).toBe(stamp);
  ack(); await settle();
  expect(actions.positionStamp()).toBeGreaterThan(stamp);
});
it("nhịp đồng hồ lưu khi phát dù không có sự kiện time", async () => {
  const { state, fire, saveProgress } = mount();
  state.paused = false; fire("play"); state.time = 42;
  vi.advanceTimersByTime(10_000); await settle();
  expect(saveProgress).toHaveBeenCalledWith("a", 1, 42, 100, undefined, undefined, expect.any(Object));
});
it("đổi sách gỡ lịch sử và toast Quay lại", async () => {
  const { actions, engine } = mount();
  actions.next();
  actions.play({ ...book, id: "b", title: "B" }, chapters, 1, 0);
  expect(h.dismiss).toHaveBeenCalledWith("jump");
  const calls = vi.mocked(engine.load).mock.calls.length;
  vi.mocked(engine.seek).mockClear();
  actions.goBack();
  expect(engine.load).toHaveBeenCalledTimes(calls);
  expect(engine.seek).not.toHaveBeenCalled();
});
it("hẹn giờ nhỏ dần giọng và nhạc cùng hệ số, huỷ/gia hạn trả lại cả hai", async () => {
  h.playing = true;
  const musicVolume = vi.spyOn(MusicBed.prototype, "setVolume");
  const { actions, engine, state, fire } = mount({ musicCues: async () => ({ cues: [], levelDb: -20 }) });
  state.paused = false; fire("playing");
  actions.setSleep({ kind: "minutes", minutes: 1 });
  for (let i = 0; i < 450; ++i) { state.time += 0.1; vi.advanceTimersByTime(100); }
  const faded = vi.mocked(engine.setVolume).mock.lastCall![0];
  expect(faded).toBeLessThan(0.9);
  expect(musicVolume).toHaveBeenLastCalledWith(faded);
  actions.extendSleep();
  expect(musicVolume).toHaveBeenLastCalledWith(0.9);
  actions.setSleep({ kind: "off" });
  expect(engine.setVolume).toHaveBeenLastCalledWith(0.9);
  expect(musicVolume).toHaveBeenLastCalledWith(0.9);
  musicVolume.mockRestore();
});
it("hẹn giờ phút không trôi trong waiting hoặc khoảng ngủ máy không có tiếng", async () => {
  h.playing = true;
  const { actions, engine, state, fire } = mount();
  state.paused = false; fire("play"); fire("playing");
  actions.setSleep({ kind: "minutes", minutes: 1 });
  for (let i = 0; i < 10; ++i) { state.time += 0.1; vi.advanceTimersByTime(100); }
  fire("waiting");
  vi.advanceTimersByTime(120_000);
  expect(engine.pause).not.toHaveBeenCalled();
  fire("playing");
  vi.setSystemTime(Date.now() + 3_600_000);
  vi.advanceTimersByTime(100);
  expect(engine.pause).not.toHaveBeenCalled();
  for (let i = 0; i < 600; ++i) { state.time += 0.1; vi.advanceTimersByTime(100); }
  expect(engine.pause).toHaveBeenCalledTimes(1);
});
it("Pause đến sau thắng Media Play đang chờ kiểm tra chỗ mới", async () => {
  let answer!: (book: ListenBook) => void;
  const { actions, engine } = mount({ book: () => new Promise((done) => { answer = done; }) });
  actions.resume(); actions.pause();
  answer(book); await settle();
  expect(engine.play).not.toHaveBeenCalled();
  expect(actions.wantsPlay()).toBe(false);
});
it("Pause vô hiệu watcher máy nguồn quay lại", async () => {
  const api = vi.spyOn(apiModule, "api").mockResolvedValue({ reachable: false });
  const { actions, engine, fire } = mount();
  actions.play({ ...book, remote: { device: "peer", computer: "Máy kia" } } as ListenBook, chapters, 1, 0);
  fire("error"); await settle();
  const calls = vi.mocked(engine.load).mock.calls.length;
  actions.pause(); h.back(); await settle();
  expect(engine.load).toHaveBeenCalledTimes(calls);
  expect(h.stopWatch).toHaveBeenCalled();
  api.mockRestore();
});
it("metadata đặt ngay cả sách chữ, đổi từ audio và xoá khi đóng", async () => {
  const { actions } = mount();
  expect(navigator.mediaSession.metadata).toMatchObject({ album: "A", title: "Chương 1" });
  actions.play({ ...book, id: "text", title: "Sách chữ" }, chapters.map((chapter) => ({ ...chapter, state: "text" })), 2, 0);
  await settle();
  expect(navigator.mediaSession.metadata).toMatchObject({ album: "Sách chữ", title: "Chương 2" });
  actions.close();
  expect(navigator.mediaSession.metadata).toBeNull();
});
it("sang chương khi đang dừng vẫn lưu chương mới sau khi nguồn sẵn sàng", async () => {
  const { actions, fire, saveProgress } = mount();
  actions.next(); fire("duration"); await settle();
  expect(saveProgress).toHaveBeenCalledWith("a", 2, 0, 100, undefined, undefined, expect.any(Object));
});
