import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

// Trình phát clip ngắn: nghe thử giọng kể, nghe câu mẫu của một nhân vật. Tách khỏi trình phát chương để
// không làm mất vị trí đang nghe; bấm clip thì tạm dừng chương, clip hết thì thôi (không tự phát lại chương -
// người dùng đang so giọng, tự bật lại tiếng chương giữa chừng là làm phiền). Chương chỉ dừng khi clip THẬT SỰ phát:
// clip hỏng (câu mẫu chưa thu, 404) từng làm sách dừng im lặng mà không báo gì (soát UX 29-09).

/** Một clip: cả file, hay đoạn [start, end] giây trong một file dài (một câu nằm trong file chương). */
export interface ClipSource {
  src: string;
  start?: number;
  end?: number;
}

interface ClipContextValue {
  current: string | null;
  loading: boolean;
  toggle: (id: string, source: string | ClipSource) => void;
  stop: () => void;
}

type ClipElement = Pick<HTMLMediaElement, "currentTime" | "pause" | "addEventListener" | "removeEventListener">;

/** Dừng thẻ audio khi qua mốc `end` (sự kiện timeupdate) rồi gọi `onEnd`: đoạn một câu trong file chương không phát lan sang
 *  câu kế. Trả hàm gỡ theo dõi. */
export function stopAtEnd(element: ClipElement, end: number, onEnd: () => void): () => void {
  const check = () => {
    if (element.currentTime < end) return;
    release();
    element.pause();
    onEnd();
  };
  const release = () => element.removeEventListener("timeupdate", check);
  element.addEventListener("timeupdate", check);
  return release;
}

const ClipContext = createContext<ClipContextValue | null>(null);

export function useClip(): ClipContextValue {
  const value = useContext(ClipContext);
  if (!value) throw new Error("useClip ngoài ClipProvider");
  return value;
}

export function ClipProvider({ children, onStart }: { children: ReactNode; onStart?: () => void }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  if (audio.current === null && typeof Audio !== "undefined") {
    audio.current = new Audio();
    // ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng.
    audio.current.muted = new URLSearchParams(window.location.search).get("mute") === "1";
  }
  const [current, setCurrent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Mỗi lần bấm nghe thử có một số thứ tự: bấm nhanh sang clip khác thì play() của clip trước ném AbortError -
  // lỗi ấy không được xoá trạng thái của clip SAU (trước đây clip sau vẫn phát mà không nút nào hiện "đang phát").
  const request = useRef(0);
  // Gỡ theo dõi mốc `end` của clip đang phát (clip là một đoạn trong file dài).
  const releaseEnd = useRef<(() => void) | null>(null);
  const clearEnd = () => {
    releaseEnd.current?.();
    releaseEnd.current = null;
  };

  const stop = useCallback(() => {
    request.current += 1;
    clearEnd();
    audio.current?.pause();
    setCurrent(null);
    setLoading(false);
  }, []);

  const onStartRef = useRef(onStart);
  onStartRef.current = onStart;
  // Số thứ tự của lần bấm còn chờ clip phát được để dừng chương (0 = không chờ).
  const startPending = useRef(0);

  const ended = useCallback(() => {
    startPending.current = 0;
    clearEnd();
    setCurrent(null);
    setLoading(false);
  }, []);

  const failed = useCallback(() => {
    startPending.current = 0;
    setCurrent(null);
    setLoading(false);
    // Một id: sự kiện `error` và `play()` bị từ chối có thể cùng báo một lần bấm - hai toast giống hệt (soát UX 29-09). Không
    // hứa "sách vẫn phát tiếp": lúc bấm sách có thể đang dừng.
    toast("Chưa nghe thử được", { id: "clip-failed", description: "Câu mẫu này chưa có bản thu." });
  }, []);

  const toggle = useCallback((id: string, source: string | ClipSource) => {
    const element = audio.current;
    if (!element) return;
    if (current === id) {
      stop();
      return;
    }
    const clip = typeof source === "string" ? { src: source } : source;
    const mine = (request.current += 1);
    startPending.current = mine;
    clearEnd();
    element.pause();
    element.src = clip.src;
    // Đặt trước khi tải xong cũng được: trình duyệt nhớ làm vị trí bắt đầu phát.
    element.currentTime = clip.start ?? 0;
    if (clip.end !== undefined) releaseEnd.current = stopAtEnd(element, clip.end, ended);
    setCurrent(id);
    setLoading(true);
    void element.play().catch((error: unknown) => {
      // `startPending` đã về 0: sự kiện `error` của thẻ audio đã báo lần bấm này rồi.
      if (request.current !== mine || startPending.current !== mine || (error as { name?: string } | null)?.name === "AbortError") return;
      failed();
    });
  }, [current, ended, failed, stop]);

  useEffect(() => {
    const element = audio.current;
    if (!element) return;
    const error = () => {
      if (startPending.current && startPending.current === request.current) failed();
      else ended();
    };
    const playing = () => {
      setLoading(false);
      if (startPending.current && startPending.current === request.current) {
        startPending.current = 0;
        onStartRef.current?.();
      }
    };
    element.addEventListener("ended", ended);
    element.addEventListener("error", error);
    element.addEventListener("playing", playing);
    return () => {
      element.removeEventListener("ended", ended);
      element.removeEventListener("error", error);
      element.removeEventListener("playing", playing);
    };
  }, [ended, failed]);

  const value = useMemo(() => ({ current, loading, toggle, stop }), [current, loading, toggle, stop]);
  return <ClipContext.Provider value={value}>{children}</ClipContext.Provider>;
}
