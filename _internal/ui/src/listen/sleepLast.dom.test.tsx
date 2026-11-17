// @vitest-environment happy-dom
// Chủ sách 17-11: mốc mặc định của hẹn giờ ngủ là lần đặt cuối (lưu ở tuỳ chọn `lastSleep`), không cố định 30 phút.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import type { AudioEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import { SourceProvider, type ListenSource } from "./source";
import { PlayerProvider, usePlayer } from "./player";
import { SleepMenu } from "./PlayerViews";
import type { LastSleep } from "./sleep";

vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { dismiss: vi.fn(), success: vi.fn(), warning: vi.fn(), error: vi.fn() }) }));
vi.mock("./OnlineVoicePrompt", () => ({ OnlineVoicePrompt: () => null }));
vi.mock("./readAloudVoice", async original => ({ ...await original<typeof import("./readAloudVoice")>(), voicesOf: async () => [] }));

const chapters = [1, 2, 3].map(id => ({ id, title: `Chương ${id}`, fullTitle: `Chương ${id}`, available: true, duration: 100 })) as ListenChapter[];
const book = { id: "a", title: "A", narrator: "Giọng", complete: true, chapters, state: { chapters: {} } } as ListenBook;
let root: Root;
let actions: ReturnType<typeof usePlayer>;
let paused = true;
const listeners = new Map<string, Set<() => void>>();
const fire = (kind: string) => listeners.get(kind)?.forEach(listener => listener());
function Probe() { actions = usePlayer(); return null; }
const engine = {
  get time() { return 0; }, duration: 10_000, get paused() { return paused; }, ended: false,
  load: vi.fn(), play: vi.fn(() => { paused = false; fire("play"); }), pause: vi.fn(() => { paused = true; fire("pause"); }),
  stop: vi.fn(), seek: vi.fn(), setRate: vi.fn(), setVolume: vi.fn(),
  on: (kind: string, listener: () => void) => { const set = listeners.get(kind) ?? new Set(); set.add(listener); listeners.set(kind, set); return () => set.delete(listener); },
} as unknown as AudioEngine;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear(); listeners.clear(); paused = true;
  vi.stubGlobal("navigator", Object.assign(Object.create(navigator), { mediaSession: { setActionHandler: vi.fn() } }));
  vi.stubGlobal("MediaMetadata", class { constructor(data: object) { Object.assign(this, data); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, finished: Promise.resolve() }) as unknown as Animation);
  root = createRoot(document.body.appendChild(document.createElement("div")));
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

/** Một lần mở app: trình phát nhận `stored` (tuỳ chọn `lastSleep` đọc từ máy chủ, chưa làm sạch); `saved` gom những gì nó gửi đi lưu. */
async function openApp(stored: unknown, saved: LastSleep[] = []) {
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress: async () => {}, beginProgress: async () => {},
    setRate: async () => {}, book: async () => book } as unknown as ListenSource;
  await act(() => root.render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { queryFn: async () => [], retry: false } } })}>
    <SourceProvider source={source}><TooltipProvider><PlayerProvider engine={engine} keyboard={false} lastSleep={stored} onLastSleep={value => saved.push(value)}>
      <Probe /><SleepMenu />
    </PlayerProvider></TooltipProvider></SourceProvider>
  </QueryClientProvider>));
  await act(async () => { actions.prepare(book, chapters, 1, 0); });
  return saved;
}

async function reopen(stored: unknown) {
  await act(() => root.unmount());
  document.body.replaceChildren();
  root = createRoot(document.body.appendChild(document.createElement("div")));
  return openApp(stored);
}

async function openMenu() {
  const trigger = document.querySelector<HTMLButtonElement>("button[aria-haspopup], button[aria-expanded]")!;
  await act(async () => trigger.click());
}
const rulerValue = () => document.querySelector<HTMLElement>("[data-value-ruler]")!.getAttribute("aria-valuenow");
const chapterValue = () => document.querySelector<HTMLElement>("[data-sleep-chapters] [data-value-display]")?.textContent;

it("chưa từng đặt: mốc là 30 phút", async () => {
  await openApp(null);
  expect(actions.lastSleep).toEqual({ kind: "minutes", minutes: 30, chapters: 1 });
  await openMenu();
  expect(rulerValue()).toBe("30");
});

it("đặt 45 phút, mở lại app: mốc vẫn là 45", async () => {
  const saved = await openApp(null);
  await act(async () => actions.setSleep({ kind: "minutes", minutes: 45 }));
  expect(saved.at(-1)).toEqual({ kind: "minutes", minutes: 45, chapters: 1 });
  await act(async () => actions.setSleep({ kind: "off" }));
  expect(saved).toHaveLength(1); // tắt hẹn giờ không phải một lần đặt
  await reopen(saved.at(-1));
  expect(actions.lastSleep).toEqual({ kind: "minutes", minutes: 45, chapters: 1 });
  await openMenu();
  expect(rulerValue()).toBe("45");
});

it("đặt hết 2 chương, mở lại: vẫn là 2 chương, số phút gần nhất vẫn giữ", async () => {
  const saved = await openApp({ kind: "minutes", minutes: 45, chapters: 1 });
  await act(async () => actions.setSleep({ kind: "chapter", chapters: 2 }));
  expect(saved.at(-1)).toEqual({ kind: "chapter", minutes: 45, chapters: 2 });
  await act(async () => actions.setSleep({ kind: "off" }));
  await reopen(saved.at(-1));
  expect(actions.lastSleep).toEqual({ kind: "chapter", minutes: 45, chapters: 2 });
  await openMenu();
  expect(chapterValue()).toBe("2");
  expect(rulerValue()).toBe("45");
});

for (const broken of [{ kind: "minutes", minutes: 999, chapters: 1 }, { kind: "chapter", minutes: 30, chapters: 0 }, { kind: "off" }, "45", 45, [45], {}]) {
  it(`giá trị lưu hỏng ${JSON.stringify(broken)}: rơi về 30, không văng`, async () => {
    await openApp(broken);
    expect(actions.lastSleep).toEqual({ kind: "minutes", minutes: 30, chapters: 1 });
    await openMenu();
    expect(rulerValue()).toBe("30");
  });
}

it("nút Bật lại đặt lại đúng lần cuối: số phút hay số chương", async () => {
  const { lastSleepRestartLabel, lastSleepRequest } = await import("./sleep");
  expect(lastSleepRestartLabel({ kind: "minutes", minutes: 45, chapters: 1 })).toBe("Bật lại 45\u00a0phút");
  expect(lastSleepRestartLabel({ kind: "chapter", minutes: 45, chapters: 1 })).toBe("Bật lại 1 chương");
  expect(lastSleepRestartLabel({ kind: "chapter", minutes: 45, chapters: 2 })).toBe("Bật lại 2 chương");
  expect(lastSleepRequest({ kind: "chapter", minutes: 45, chapters: 2 })).toEqual({ kind: "chapter", chapters: 2 });
  expect(lastSleepRequest({ kind: "minutes", minutes: 45, chapters: 2 })).toEqual({ kind: "minutes", minutes: 45 });
});

// Soát sleeplast 18-11 (lỗi 1): giữ +/- gửi nhiều lần lưu; bản máy chủ cũ về muộn không được kéo mốc vừa chọn lùi lại.
it("lần lưu còn bay: tuỳ chọn cũ về muộn không kéo mốc lùi; lưu xong thì lại theo máy chủ", async () => {
  const { latestSave } = await import("@/shared/latestSave");
  const answers: ((saved: LastSleep) => void)[] = [];
  const saver = latestSave((value: LastSleep) => new Promise<LastSleep>(resolve => answers.push(() => resolve(value))), { delay: 0 });
  const source = { kind: "desktop", audioUrl: () => "/audio", saveProgress: async () => {}, beginProgress: async () => {},
    setRate: async () => {}, book: async () => book } as unknown as ListenSource;
  const client = new QueryClient({ defaultOptions: { queries: { queryFn: async () => [], retry: false } } });
  const render = (stored: unknown) => act(() => root.render(<QueryClientProvider client={client}>
    <SourceProvider source={source}><TooltipProvider><PlayerProvider engine={engine} keyboard={false} lastSleep={stored} onLastSleep={value => saver.save(value)}>
      <Probe /><SleepMenu />
    </PlayerProvider></TooltipProvider></SourceProvider>
  </QueryClientProvider>));
  await render({ kind: "minutes", minutes: 30, chapters: 1 });
  await act(async () => actions.prepare(book, chapters, 1, 0));
  for (const minutes of [31, 32, 33]) await act(async () => actions.setSleep({ kind: "minutes", minutes }));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  // Phản hồi cũ (31 - lần gửi trước, hay một lần đọc lại tuỳ chọn) đến khi 33 còn chưa lưu xong.
  await render({ kind: "minutes", minutes: 31, chapters: 1 });
  expect(actions.lastSleep).toEqual({ kind: "minutes", minutes: 33, chapters: 1 });
  await act(async () => actions.setSleep({ kind: "chapter", chapters: 2 }));
  expect(actions.lastSleep).toEqual({ kind: "chapter", minutes: 33, chapters: 2 });
  // Lưu xong hết: tuỳ chọn mới của máy chủ (máy khác vừa đổi) lại được theo.
  for (let round = 0; round < 3 && answers.length; round++) {
    await act(async () => { answers.splice(0).forEach(answer => answer({} as LastSleep)); await new Promise(resolve => setTimeout(resolve, 0)); });
  }
  expect(saver.pending).toBe(false);
  await render({ kind: "minutes", minutes: 50, chapters: 1 });
  expect(actions.lastSleep).toEqual({ kind: "minutes", minutes: 50, chapters: 1 });
});
