import { useEffect, useRef, useState } from "react";
import { binary, fallbackSeed } from "../../../desktop_qt/qml/MusicArtRaster.mjs";
import { cn } from "../shared/cn";
import { useTrackDetail } from "./library";

export interface Artwork {
  url: string; sha1: string; w: number; h: number;
  source?: string; landing?: string; credit?: string; rights?: string;
}
export interface ArtTrack { link: string; artSeed?: number; art?: Artwork }

const generated = new Map<number, string>();
function placeholder(track: ArtTrack): string {
  const seed = track.artSeed ?? fallbackSeed(track.link);
  let image = generated.get(seed);
  if (!image) {
    image = `data:image/bmp;base64,${btoa(binary(seed))}`;
    generated.set(seed, image);
    if (generated.size > 96) generated.delete(generated.keys().next().value!);
  }
  return image;
}

// Shared queue: at most three image fetch/decode jobs, even when a list mounts at once.
let running = 0;
const waiting: (() => void)[] = [];
async function slot<T>(work: () => Promise<T>): Promise<T> {
  if (running >= 3) await new Promise<void>((resolve) => waiting.push(resolve));
  else running++;
  try { return await work(); } finally { const next = waiting.shift(); if (next) next(); else running--; }
}
const inflight = new Map<string, { job: Promise<Blob>; needed: Set<() => boolean> }>();
export function loadArtwork(art: Artwork, needed: () => boolean = () => true): Promise<Blob> {
  const key = art.url + "#" + art.sha1;
  const active = inflight.get(key);
  if (active) { active.needed.add(needed); return active.job; }
  const subscribers = new Set([needed]);
  const job = Promise.resolve().then(() => slot(async () => {
    if (![...subscribers].some((isNeeded) => isNeeded())) throw new Error();
    const cache = typeof caches === "undefined" ? undefined : await caches.open("abook-music-art-v1").catch(() => undefined);
    const cached = await cache?.match(key);
    const response = cached ?? await fetch(art.url, { credentials: "omit", signal: AbortSignal.timeout(12_000) });
    if (!response.ok) throw new Error();
    const blob = await response.blob();
    if (blob.size > 512 * 1024) throw new Error();
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-1", await blob.arrayBuffer()));
    const sha = Array.from(digest, (v) => v.toString(16).padStart(2, "0")).join("");
    if (sha !== art.sha1) { await cache?.delete(key); throw new Error(); }
    if (typeof createImageBitmap === "function") {
      const decoded = await createImageBitmap(blob);
      const valid = decoded.width > 0 && decoded.height > 0 && decoded.width <= 512 && decoded.height <= 512;
      decoded.close();
      if (!valid) throw new Error();
    }
    if (!cached) await cache?.put(key, new Response(blob));
    return blob;
  }));
  inflight.set(key, { job, needed: subscribers });
  void job.finally(() => inflight.delete(key)).catch(() => {});
  return job;
}

/** Decorative cover; the adjacent title supplies the accessible name. */
export function MusicArt({ track, className }: { track: ArtTrack; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [real, setReal] = useState<{ key: string; url: string }>();
  const key = track.link + (track.art?.sha1 ?? "");
  useEffect(() => {
    if (!track.art || !ref.current) return;
    let gone = false, url = "";
    const art = track.art;
    const load = () => { void loadArtwork(art, () => !gone).then((blob) => {
      if (gone) return;
      url = URL.createObjectURL(blob);
      setReal({ key, url });
    }).catch(() => {}); };
    const observer = typeof IntersectionObserver === "undefined" ? undefined : new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) { observer?.disconnect(); load(); }
    }, { rootMargin: "160px" });
    if (observer) observer.observe(ref.current); else load();
    return () => { gone = true; observer?.disconnect(); if (url) URL.revokeObjectURL(url); };
  }, [key, track.art]);
  return <span ref={ref} aria-hidden className={cn("block size-10 shrink-0 overflow-hidden rounded-cover", className)} data-music-art>
    <img alt="" decoding="async" loading="lazy" width={96} height={96} className="size-full object-cover" src={real?.key === key ? real.url : placeholder(track)} onError={() => setReal(undefined)} />
  </span>;
}

export function PlayingMusicArt({ link }: { link: string }) {
  const { data } = useTrackDetail(link);
  return <MusicArt track={data ?? { link }} className="size-8" />;
}
