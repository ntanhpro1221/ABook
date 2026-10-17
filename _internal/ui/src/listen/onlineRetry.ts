import { useEffect } from "react";

/** Mạng về -> chờ chừng này rồi tự "Thử lại": sự kiện "online" tới trước khi tra được tên máy chủ. */
export const ONLINE_RETRY_MS = 1500;

/**
 * Mạng về thì đọc tiếp luôn như bấm "Thử lại" - trước chỉ ẩn lời báo mất mạng, trình phát đứng yên, người nghe phải tự bấm Phát
 * (phoneui 18-10). Vẫn lỗi thì lời báo hiện lại với nút "Thử lại". Nhiều sự kiện "online" sát nhau chỉ thử một lần. Trả hàm gỡ.
 */
export function retryWhenOnline(retry: () => void, target: Pick<Window, "addEventListener" | "removeEventListener"> = window): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const back = () => {
    clearTimeout(timer);
    timer = setTimeout(retry, ONLINE_RETRY_MS);
  };
  target.addEventListener("online", back);
  return () => {
    clearTimeout(timer);
    target.removeEventListener("online", back);
  };
}

/** Chỉ khi đang báo mất mạng (`active`). */
export function useRetryWhenOnline(active: boolean, retry: () => void) {
  useEffect(() => (active ? retryWhenOnline(retry) : undefined), [active, retry]);
}
