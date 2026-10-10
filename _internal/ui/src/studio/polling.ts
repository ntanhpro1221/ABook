import { useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { ApiError } from "./api";

// Nhịp hỏi máy chủ của trang dự án khi máy chủ trả lỗi (soát UX a18): sách đã mất (404) mà tab cũ vẫn hỏi lại hàng trăm lần, sổ làm
// việc hỏng (500) bị hỏi lại liên tục mà không ai được báo gì.

/** Lỗi "không còn nữa" (404): hỏi tiếp cũng vô ích. */
export const isGone = (error: unknown): boolean => error instanceof ApiError && error.status === 404;

/** Trần của nhịp lùi: lỗi kéo dài thì cứ hai phút hỏi một lần, đủ để trang tự khỏi khi máy chủ sống lại. */
const BACKOFF_CAP_MS = 120_000;

/** Nhịp hỏi kế tiếp của một truy vấn có nhịp cơ sở `base` (ms, hay false = không hỏi theo nhịp): 404 -> dừng hẳn; lỗi khác -> gấp đôi
 *  theo số lần lỗi liên tiếp, tới trần; không lỗi -> `base`. */
export function pollDelay(base: number | false, state: { error: unknown; fetchFailureCount?: number; errorUpdateCount: number }): number | false {
  if (isGone(state.error)) return false;
  if (!state.error || base === false) return base;
  return Math.min(base * 2 ** Math.min(state.errorUpdateCount, 8), BACKOFF_CAP_MS);
}

/** `retry` của truy vấn: 404 không thử lại; lỗi khác thử lại một lần như mặc định của app. */
export function retryUnlessGone(failureCount: number, error: unknown): boolean {
  return !isGone(error) && failureCount < 1;
}

/** Truy vấn phụ của trang dự án (sổ làm việc, hàng nghe lại, hộp thư điện thoại...): lỗi của chúng không làm mất cả trang nên
 *  trước đây im lặng. */
const SIDE_QUERIES = new Set(["review", "work", "cast", "edits-inbox", "precast", "activity"]);

/** Lời lỗi máy chủ trả của một truy vấn phụ đang hỏng ở sách `bookId`, hoặc "" khi không có (để trang hiện thay vì nuốt). */
export function useSideError(bookId: string): string {
  const cache = useQueryClient().getQueryCache();
  const read = () => {
    for (const query of cache.findAll()) {
      const [kind, id] = query.queryKey;
      if (id === bookId && typeof kind === "string" && SIDE_QUERIES.has(kind) && query.state.status === "error" && !isGone(query.state.error)) {
        return (query.state.error as Error | null)?.message ?? "";
      }
    }
    return "";
  };
  return useSyncExternalStore((notify) => cache.subscribe(notify), read);
}
