import { useCallback, useEffect, useRef, useState } from "react";
import { usePlayer } from "../listen/player";
import { mediaUrl } from "../studio/api";
import { previewPath } from "../studio/musicLocal";
import { S } from "../shared/strings.generated";

/** Nghe thử một bài của Kho nhạc: từ chỗ bắt đầu nghe được (`audibleStart`), tối đa 30 giây. */
export const PREVIEW_SECONDS = 30;
/** Độ to nghe thử: đưa bài về cùng một mức (LUFS danh mục đo) - bài to không giật tai, bài nhỏ không phải vặn loa. */
export const PREVIEW_LUFS = -18;

export interface PreviewTrack {
  link: string;
  title?: string;
  audibleStart?: number;
  lufs?: number;
}

/** Âm lượng 0-1 để bài có độ to `lufs` nghe ở PREVIEW_LUFS; danh mục chưa đo thì để nguyên. */
export function previewVolume(lufs: number | undefined): number {
  if (typeof lufs !== "number" || !Number.isFinite(lufs)) return 1;
  return Math.max(0.05, Math.min(1, 10 ** ((PREVIEW_LUFS - lufs) / 20)));
}

/** MỘT <audio> cho cả màn: bấm bài khác thì bài trước dừng; sách đang phát thì TẠM DỪNG sách (không tự phát lại khi thôi nghe thử);
 *  rời màn (unmount) là dừng. ?mute=1: kiểm thử tự động không phát tiếng ra loa (như musicBed.ts). */
export function useLibraryPreview() {
  const player = usePlayer();
  const playerRef = useRef(player);
  playerRef.current = player;
  const audio = useRef<HTMLAudioElement | null>(null);
  const until = useRef(0);
  const [playing, setPlaying] = useState<PreviewTrack | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const clearTimeoutRef = useCallback(() => { clearTimeout(timeout.current); timeout.current = undefined; }, []);
  const current = useRef<string | null>(null);
  const request = useRef(0);
  const metadataListener = useRef<(() => void) | null>(null);
  const clearMetadataListener = useCallback(() => {
    if (metadataListener.current) audio.current?.removeEventListener("loadedmetadata", metadataListener.current);
    metadataListener.current = null;
  }, []);
  const stop = useCallback(() => {
    request.current++;
    clearTimeoutRef();
    clearMetadataListener();
    const element = audio.current;
    if (element) {
      element.pause();
      element.removeAttribute("src");
      element.load();
    }
    current.current = null;
    setPlaying(null);
    setLoading(false);
  }, [clearMetadataListener, clearTimeoutRef]);
  const fail = useCallback((message: string) => { stop(); setError(message); }, [stop]);
  const toggle = useCallback(
    (track: PreviewTrack) => {
      if (current.current === track.link) {
        stop();
        return;
      }
      if (playerRef.current.playing) playerRef.current.pause();
      if (!audio.current) {
        const created = new Audio();
        created.preload = "auto";
        created.muted = new URLSearchParams(window.location.search).get("mute") === "1";
        created.addEventListener("timeupdate", () => {
          if (created.currentTime >= until.current) stop();
        });
        created.addEventListener("ended", stop);
        created.addEventListener("error", () => fail(S.s_chua_nghe_thu_duoc_luc_nay_58b11ef5));
        created.addEventListener("playing", () => { clearTimeoutRef(); setLoading(false); });
        created.addEventListener("waiting", () => {
          if (!current.current) return;
          setLoading(true);
          if (timeout.current === undefined) timeout.current = setTimeout(() => fail(S.s_preview_timeout), 30_000);
        });
        audio.current = created;
      }
      const element = audio.current;
      const token = ++request.current;
      clearTimeoutRef();
      clearMetadataListener();
      const start = Math.max(0, track.audibleStart ?? 0);
      until.current = start + PREVIEW_SECONDS;
      element.src = mediaUrl(previewPath(track.link));
      element.volume = previewVolume(track.lufs);
      element.currentTime = start;
      if (start > 0) {
        metadataListener.current = () => { metadataListener.current = null; element.currentTime = start; };
        element.addEventListener("loadedmetadata", metadataListener.current, { once: true });
      }
      current.current = track.link;
      setPlaying(track);
      setLoading(true);
      setError("");
      timeout.current = setTimeout(() => { if (request.current === token) fail(S.s_preview_timeout); }, 30_000);
      void element.play().catch(() => {
        if (request.current === token) fail(S.s_chua_nghe_thu_duoc_luc_nay_58b11ef5);
      });
    },
    [stop, fail, clearMetadataListener, clearTimeoutRef],
  );
  // Sách bắt đầu phát lại (người nghe bấm phát ở thanh dưới): bài nghe thử nhường.
  useEffect(() => {
    if (player.playing && current.current) stop();
  }, [player.playing, stop]);
  useEffect(() => stop, [stop]);
  return { playing, loading, error, toggle, stop };
}

export type LibraryPreview = ReturnType<typeof useLibraryPreview>;
