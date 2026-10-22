/** Mỗi lúc chỉ MỘT yêu cầu còn sống: yêu cầu mới (hay đóng hộp: [cancel]) huỷ yêu cầu cũ - kết nối đóng, máy chủ thôi chờ - để lời đáp
 *  về muộn của lượt cũ không hiện đè lên lượt mới (kết quả tìm bìa, ảnh bìa chọn trước đã bỏ). */
export function latestRequest() {
  let current: AbortController | null = null;
  return {
    next(): AbortSignal {
      current?.abort();
      current = new AbortController();
      return current.signal;
    },
    cancel(): void {
      current?.abort();
      current = null;
    },
  };
}

/** Lỗi do chính ta huỷ (đóng hộp, hỏi lượt khác): không phải lỗi để báo người dùng. */
export function wasAborted(error: unknown): boolean {
  return (error as { name?: string } | null)?.name === "AbortError";
}
