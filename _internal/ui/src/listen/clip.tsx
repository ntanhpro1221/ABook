import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

// Trình phát clip ngắn: nghe thử giọng kể, nghe câu mẫu của một nhân vật. Tách khỏi trình phát chương để
// không làm mất vị trí đang nghe; bấm clip thì tạm dừng chương, clip hết thì thôi (không tự phát lại chương -
// người dùng đang so giọng, tự bật lại tiếng chương giữa chừng là làm phiền). Chương chỉ dừng khi clip THẬT SỰ phát:
// clip hỏng (câu mẫu chưa thu, 404) từng làm sách dừng im lặng mà không báo gì (soát UX 29-09).

interface ClipContextValue {
  current: string | null;
  loading: boolean;
  toggle: (id: string, url: string) => void;
  stop: () => void;
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

  const stop = useCallback(() => {
    request.current += 1;
    audio.current?.pause();
    setCurrent(null);
    setLoading(false);
  }, []);

  const onStartRef = useRef(onStart);
  onStartRef.current = onStart;
  // Số thứ tự của lần bấm còn chờ clip phát được để dừng chương (0 = không chờ).
  const startPending = useRef(0);

  const failed = useCallback(() => {
    startPending.current = 0;
    setCurrent(null);
    setLoading(false);
    // Một id: sự kiện `error` và `play()` bị từ chối có thể cùng báo một lần bấm - hai toast giống hệt (soát UX 29-09). Không
    // hứa "sách vẫn phát tiếp": lúc bấm sách có thể đang dừng.
    toast("Chưa nghe thử được", { id: "clip-failed", description: "Câu mẫu này chưa có bản thu." });
  }, []);

  const toggle = useCallback((id: string, url: string) => {
    const element = audio.current;
    if (!element) return;
    if (current === id) {
      stop();
      return;
    }
    const mine = (request.current += 1);
    startPending.current = mine;
    element.pause();
    element.src = url;
    element.currentTime = 0;
    setCurrent(id);
    setLoading(true);
    void element.play().catch((error: unknown) => {
      // `startPending` đã về 0: sự kiện `error` của thẻ audio đã báo lần bấm này rồi.
      if (request.current !== mine || startPending.current !== mine || (error as { name?: string } | null)?.name === "AbortError") return;
      failed();
    });
  }, [current, failed, stop]);

  useEffect(() => {
    const element = audio.current;
    if (!element) return;
    const ended = () => {
      startPending.current = 0;
      setCurrent(null);
      setLoading(false);
    };
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
  }, [failed]);

  const value = useMemo(() => ({ current, loading, toggle, stop }), [current, loading, toggle, stop]);
  return <ClipContext.Provider value={value}>{children}</ClipContext.Provider>;
}
