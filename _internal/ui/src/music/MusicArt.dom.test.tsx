// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MusicArt, loadArtwork } from "./MusicArt";

afterEach(() => vi.unstubAllGlobals());

it("renders a cover without network when no source artwork exists", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const div = document.createElement("div"); document.body.append(div);
  const root = createRoot(div);
  await act(async () => root.render(<MusicArt track={{ link: "local:offline", artSeed: 42 }} />));
  expect(div.querySelector("img")?.src).toMatch(/^data:image\/bmp;base64,/);
  expect(fetcher).not.toHaveBeenCalled();
  await act(async () => root.unmount()); div.remove();
});

it("reads verified disk cache offline and rejects a corrupted response", async () => {
  const bytes = new Uint8Array([1, 2, 3, 4]);
  const sha1 = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-1", bytes)), (v) => v.toString(16).padStart(2, "0")).join("");
  const cached = new Map<string, Response>();
  const cache = { match: async (key: string) => cached.get(key)?.clone(), put: async (key: string, response: Response) => { cached.set(key, response); }, delete: async (key: string) => cached.delete(key) };
  vi.stubGlobal("caches", { open: async () => cache });
  vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 512, height: 512, close() {} })));
  const fetcher = vi.fn(async () => new Response(bytes, { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const art = { url: "https://music.example/art/" + sha1 + ".jpg", sha1, w: 512, h: 512 };
  expect((await loadArtwork(art)).size).toBe(4);
  fetcher.mockImplementation(async () => { throw new Error(); });
  expect((await loadArtwork(art)).size).toBe(4);
  expect(fetcher).toHaveBeenCalledTimes(1);
  await expect(loadArtwork({ ...art, url: art.url + "-bad", sha1: "0".repeat(40) })).rejects.toThrow();
  fetcher.mockImplementation(async () => new Response(bytes));
  await expect(loadArtwork({ ...art, url: art.url + "-corrupt", sha1: "0".repeat(40) })).rejects.toThrow();
});
