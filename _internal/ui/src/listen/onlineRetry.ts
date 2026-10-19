import { useCallback, useEffect } from "react";

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

/** Việc làm khi mạng về: người nghe còn muốn nghe (đã bấm phát, chưa bấm dừng - lỗi xảy ra lúc đang phát / đang chờ phát) thì "Thử lại";
 *  lỗi sinh lúc mở app khi chưa bấm phát gì thì chỉ gỡ lời báo, không tự phát (soát a66: cuốn tự đọc tới hết khi người nghe đang ở Cài đặt). */
export function whenBackOnline(wantsPlay: () => boolean, retry: () => void, dismiss: () => void): () => void {
  return () => (wantsPlay() ? retry() : dismiss());
}

/** Chỉ khi đang báo mất mạng (`active`). */
export function useRetryWhenOnline(active: boolean, retry: () => void, dismiss: () => void, wantsPlay: () => boolean) {
  const back = useCallback(() => whenBackOnline(wantsPlay, retry, dismiss)(), [wantsPlay, retry, dismiss]);
  useEffect(() => (active ? retryWhenOnline(back) : undefined), [active, back]);
}
