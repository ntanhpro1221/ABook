import { useCachedBook } from "./data";
import { pollDelay } from "./polling";
import type { BookSummary } from "./api";

// Sách đang chạy thì máy liên tục tìm ra chỗ cần người duyệt (câu "Cần nghe lại", thẻ "Việc cần duyệt", số trên nhãn tab). Trước đây các danh sách
// ấy chỉ hỏi một lần khi mở trang nên người dùng ngồi xem một cuốn đang chạy mà không thấy việc mới nào, phải tự tải lại (soát a90 V4).

/** Nhịp hỏi lại danh sách khi sách đang chạy: danh sách việc có thể nặng (sách dài), việc mới sinh ra theo chương - không cần dồn dập. */
export const PRODUCING_REFRESH_MS = 15_000;

type Producing = Pick<BookSummary, "running" | "starting" | "paused"> | undefined;
type PollState = Parameters<typeof pollDelay>[1];

/** `refetchInterval` cho danh sách việc / duyệt của một cuốn: chỉ hỏi theo nhịp khi sách THẬT SỰ đang chạy (không tạm dừng - tạm dừng thì
 *  không có việc mới). Tab đang ẩn thì react-query bỏ qua nhịp (`refetchIntervalInBackground` mặc định false) và hiện lại là hỏi tiếp - đừng
 *  xét "tab ẩn" ở đây: trả false lúc ấy làm nhịp tắt hẳn tới khi có gì đặt lại. Lỗi máy chủ thì lùi dần như trang dự án (`pollDelay`). Dữ liệu giống hệt lần trước thì react-query giữ
 *  nguyên tham chiếu, nên danh sách không dựng lại - tiêu điểm và vị trí cuộn còn nguyên. */
export function producingRefetch(book: Producing): (query: { state: PollState }) => number | false {
  return (query) => {
    const live = Boolean(book && (book.running || book.starting) && !book.paused);
    return pollDelay(live ? PRODUCING_REFRESH_MS : false, query.state);
  };
}

/** `producingRefetch` theo sách trong bộ nhớ đệm của trang dự án (nhịp hỏi sách của `useBook` giữ nó luôn mới). */
export function useProducingRefetch(bookId: string) {
  return producingRefetch(useCachedBook(bookId || undefined).data?.book);
}
