// Cách gia hạn hẹn giờ trên máy tính: bắt phím/chuột, hay chạm màn hình khi máy cảm ứng. Một nơi cho hộp hẹn giờ của trình phát
// và trang Cài đặt, để hai nơi không nói khác nhau (soát UX 05-10).

/** Máy chủ yếu là cảm ứng (máy tính bảng, màn cảm ứng): không có phím/chuột để "chạm". */
export const COARSE = typeof window !== "undefined" && Boolean(window.matchMedia?.("(pointer: coarse)").matches);

export function extendGestureText(coarse: boolean): string {
  return coarse ? "chạm màn hình" : "chạm phím hoặc chuột";
}

export const EXTEND_GESTURE = extendGestureText(COARSE);
