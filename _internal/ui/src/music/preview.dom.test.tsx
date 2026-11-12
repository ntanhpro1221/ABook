// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";

const player = vi.hoisted(() => ({ playing: false, pause: vi.fn() }));
vi.mock("../listen/player", () => ({ usePlayer: () => player }));
vi.mock("../studio/api", () => ({ mediaUrl: (path: string) => path }));
import { useLibraryPreview, type LibraryPreview } from "./preview";

class AudioStub extends EventTarget {
  static instances: AudioStub[] = [];
  src = "";
  currentTime = 0;
  preload = "";
  muted = false;
  volume = 1;
  pause = vi.fn();
  load = vi.fn();
  play = vi.fn(() => Promise.resolve());
  removeAttribute(name: string) { if (name === "src") this.src = ""; }
  constructor() { super(); AudioStub.instances.push(this); }
}

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); AudioStub.instances = []; });

async function mounted() {
  vi.stubGlobal("Audio", AudioStub);
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  let preview!: LibraryPreview;
  function Panel() { preview = useLibraryPreview(); return null; }
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  await act(async () => root.render(<Panel />));
  return { get preview() { return preview; }, close: async () => { await act(async () => root.unmount()); host.remove(); } };
}

it.each([0, 4])("drops the previous track's pending metadata seek when switching to start=%s", async start => {
  const view = await mounted();
  try {
    await act(async () => view.preview.toggle({ link: "https://a", audibleStart: 12 }));
    const audio = AudioStub.instances[0];
    await act(async () => view.preview.toggle({ link: "https://b", audibleStart: start }));
    audio.currentTime = 0; // The new source's metadata is only now arriving.
    await act(async () => audio.dispatchEvent(new Event("loadedmetadata")));
    expect(audio.currentTime).toBe(start);
    expect(AudioStub.instances).toHaveLength(1);
    expect(view.preview.playing?.link).toBe("https://b");
  } finally { await view.close(); }
});

it.each(["stop", "unmount"])("removes pending metadata on %s", async action => {
  const view = await mounted();
  await act(async () => view.preview.toggle({ link: "https://a", audibleStart: 12 }));
  const audio = AudioStub.instances[0];
  if (action === "stop") await act(async () => view.preview.stop());
  else await view.close();
  audio.currentTime = 0;
  audio.dispatchEvent(new Event("loadedmetadata"));
  expect(audio.currentTime).toBe(0);
  expect(audio.src).toBe("");
  if (action === "stop") await view.close();
});

it("ignores a stale play rejection even after returning to the same track", async () => {
  const view = await mounted();
  try {
    await act(async () => view.preview.toggle({ link: "https://b" }));
    const audio = AudioStub.instances[0];
    let reject!: (error: Error) => void;
    audio.play.mockImplementationOnce(() => new Promise<void>((_resolve, no) => { reject = no; }));
    await act(async () => view.preview.toggle({ link: "https://a" }));
    await act(async () => view.preview.toggle({ link: "https://b" }));
    await act(async () => view.preview.toggle({ link: "https://a" }));
    await act(async () => reject(new Error("old source interrupted")));
    expect(view.preview.playing?.link).toBe("https://a");
  } finally { await view.close(); }
});
