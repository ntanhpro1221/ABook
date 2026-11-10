import { useCallback, useEffect, useRef, useState } from "react";
import { usePlayer } from "../listen/player";
import { mediaUrl } from "../studio/api";
import { previewPath } from "../studio/musicLocal";

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
  const current = useRef<string | null>(null);
  const stop = useCallback(() => {
    const element = audio.current;
    if (element) {
      element.pause();
      element.removeAttribute("src");
      element.load();
    }
    current.current = null;
    setPlaying(null);
  }, []);
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
        created.addEventListener("error", stop);
        audio.current = created;
      }
      const element = audio.current;
      const start = Math.max(0, track.audibleStart ?? 0);
      until.current = start + PREVIEW_SECONDS;
      element.src = mediaUrl(previewPath(track.link));
      element.volume = previewVolume(track.lufs);
      element.currentTime = start;
      if (start > 0) element.addEventListener("loadedmetadata", () => { element.currentTime = start; }, { once: true });
      current.current = track.link;
      setPlaying(track);
      void element.play().catch(() => {
        if (current.current === track.link) stop();
      });
    },
    [stop],
  );
  // Sách bắt đầu phát lại (người nghe bấm phát ở thanh dưới): bài nghe thử nhường.
  useEffect(() => {
    if (player.playing && current.current) stop();
  }, [player.playing, stop]);
  useEffect(() => stop, [stop]);
  return { playing, toggle, stop };
}

export type LibraryPreview = ReturnType<typeof useLibraryPreview>;
