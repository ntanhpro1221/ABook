// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.useFakeTimers();
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
});
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); });

const h = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("@/studio/api", () => ({ api: h.api }));
vi.mock("./MyMusic", () => ({ MY_MUSIC_KEY: ["mine"], useCanImportMusic: () => false }));
vi.mock("@/studio/musicImport", () => ({ importMusic: vi.fn() }));
vi.mock("@/shared/toast", () => ({ toast: Object.assign(vi.fn(), { error: vi.fn(), warning: vi.fn() }) }));
import { usePlaylistChoice } from "./PlaylistChoice";
import { MusicLevelSlider } from "@/shared/MusicLevelSlider";

it("queues reset after the pending write and keeps the final server value and thumb at default", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = (levelDb: number) => ({ package: true, hasMusic: true, enabled: true, levelDb, cues: [] });
  client.setQueryData(["listen", "edit-music", "book"], view(-20));
  const writes: { level: number; finish: () => void }[] = [];
  let server = -20;
  h.api.mockImplementation((_path, options) => new Promise((resolve) => {
    const level = options.body.levelDb;
    writes.push({ level, finish: () => { server = level; resolve(view(level)); } });
  }));
  function Panel() {
    const music = usePlaylistChoice("book", false);
    return <MusicLevelSlider value={music.levelDb} saving={music.levelBusy} onChange={music.setLevel} />;
  }
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const flush = async () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
  try {
    await act(async () => root.render(<QueryClientProvider client={client}><Panel /></QueryClientProvider>));
    await act(async () => { host.querySelector('[role="slider"]')!.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    await flush();
    await act(async () => host.querySelector("button")!.click());
    await flush();
    expect(writes.map((w) => w.level)).toEqual([-19]);
    await act(async () => writes[0].finish());
    await flush();
    expect(writes.map((w) => w.level)).toEqual([-19, -20]);
    expect(host.textContent).toContain("-20 dB (mặc định)");
    await act(async () => writes[1].finish());
    await flush();
    expect(server).toBe(-20);
    expect(client.getQueryData(["listen", "edit-music", "book"])).toMatchObject({ levelDb: -20 });
    expect(host.textContent).toContain("-20 dB (mặc định)");
  } finally {
    await act(async () => root.unmount());
    client.clear();
    host.remove();
  }
});
