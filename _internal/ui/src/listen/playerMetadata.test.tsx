import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";

const h = vi.hoisted(() => ({ effects: [] as { run: () => void; deps: readonly unknown[] }[], book: undefined as unknown, dismiss: vi.fn(), bedStops: vi.fn() }));
vi.mock("./musicBed", async (original) => ({
  ...await original<typeof import("./musicBed")>(),
  MusicBed: class { stop = h.bedStops; setVolume = vi.fn(); onActiveChange = () => () => undefined; onLoadResult = () => () => undefined; failing = false; },
}));
vi.mock("react", async (original) => ({ ...await original<typeof import("react")>(), useEffect: (run: () => void, deps: readonly unknown[] = []) => h.effects.push({ run, deps }) }));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { dismiss: h.dismiss, info: vi.fn(), success: vi.fn() }) }));
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./source", async (original) => ({ ...await original<typeof import("./source")>(), useListenBook: () => ({ data: h.book }) }));
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";

const chapters = [1, 2].map((id) => ({ id, title: `Chương ${id}`, fullTitle: `Chương ${id}`, available: true, duration: 100 })) as ListenChapter[];
const old = { id: "test-book", title: "Tên cũ", narrator: "Giọng cũ", complete: true, chapters, state: { rate: 1, chapters: {} } } as ListenBook;
beforeEach(() => {
  h.effects = []; h.dismiss.mockClear();
  h.book = { ...old, title: "Tên mới", narrator: "Giọng mới", cover: { url: "/new.png", color: "#000" }, chapters: chapters.map((chapter) => ({ ...chapter, fullTitle: `${chapter.fullTitle} mới` })) };
  vi.stubGlobal("window", Object.assign(new EventTarget(), { location: { href: "http://localhost/", search: "" } }));
  vi.stubGlobal("navigator", { mediaSession: {} });
  vi.stubGlobal("MediaMetadata", class { constructor(data: object) { Object.assign(this, data); } });
});
afterEach(() => vi.unstubAllGlobals());

function player(extra: Partial<ListenSource> = {}) {
  let actions!: ReturnType<typeof usePlayer>;
  const engine = { load: vi.fn(), stop: vi.fn(), setVolume: vi.fn(), setRate: vi.fn(), time: 12, duration: 100, paused: true, ended: false, on: () => () => undefined } as unknown as AudioEngine;
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress: async () => undefined, setRate: async () => undefined, ...extra } as unknown as ListenSource;
  function Capture() { actions = usePlayer(); return null; }
  renderToString(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { queryFn: async () => [] } } })}><SourceProvider source={source}><PlayerProvider engine={engine}><Capture /></PlayerProvider></SourceProvider></QueryClientProvider>);
  actions.prepare(old, chapters, 1, 12);
  return { actions, engine };
}

it("sửa sách đang phát cập nhật media session và dữ liệu dùng khi sang chương", () => {
  const { actions, engine } = player();
  for (const effect of h.effects.filter((effect) => effect.deps.includes(h.book))) effect.run();
  expect(navigator.mediaSession.metadata).toMatchObject({ album: "Tên mới", title: "Chương 1 mới", artist: "Giọng mới", artwork: [{ src: "http://localhost/new.png", sizes: "512x512", type: "image/png" }] });
  actions.next();
  expect(engine.load).toHaveBeenLastCalledWith(expect.objectContaining({ album: "Tên mới", title: "Chương 2 mới", artist: "Giọng mới", artwork: "http://localhost/new.png" }), 0, false);
});

it("đóng cuốn đang phát gỡ toast Quay lại chỗ cũ", () => {
  const { actions } = player();
  actions.next();
  actions.close();
  expect(h.dismiss).toHaveBeenCalledWith("jump");
});

it("đổi riêng tên chương sau vẫn cập nhật hàng đợi mà không nạp lại chương đang nghe", () => {
  h.book = { ...old, chapters: [chapters[0], { ...chapters[1], fullTitle: "Tên chương sau mới" }] };
  const { actions, engine } = player();
  for (const effect of h.effects.filter((effect) => effect.deps.includes(h.book))) effect.run();
  expect(engine.load).toHaveBeenCalledTimes(1);
  actions.next();
  expect(engine.load).toHaveBeenLastCalledWith(expect.objectContaining({ title: "Tên chương sau mới" }), 0, false);
});

it("câu trả lời trễ của cuốn khác không đổi nhãn cuốn đang nghe", () => {
  h.book = { ...old, id: "other", title: "Cuốn khác" };
  const { actions, engine } = player();
  for (const effect of h.effects.filter((effect) => effect.deps.includes(h.book))) effect.run();
  actions.next();
  expect(engine.load).toHaveBeenLastCalledWith(expect.objectContaining({ album: "Tên cũ", title: "Chương 2" }), 0, false);
});

it("đóng cuốn nhả hẳn bộ phát nhạc nền, không chỉ tạm dừng nó", () => {
  h.bedStops.mockClear();
  const { actions } = player({ musicCues: async () => ({ cues: [], levelDb: -20 }) });
  actions.close();
  expect(h.bedStops).toHaveBeenCalled();
});
