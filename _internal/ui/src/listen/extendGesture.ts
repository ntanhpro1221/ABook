import { Capacitor } from "@capacitor/core";

// Cách gia hạn hẹn giờ khác nhau theo máy: máy tính bắt phím/chuột; điện thoại bắt cú LẮC (SleepTimer.kt) và nút "Nghe thêm"
// trên thông báo - chạm màn hình ở đó chỉ ghi nhận cho tính năng tự dừng, không gia hạn (27-09, thấy trên máy ảo). Một nơi cho
// hộp hẹn giờ của trình phát và trang Cài đặt, để hai nơi không nói khác nhau (soát UX 05-10).

/** Máy chủ yếu là cảm ứng (máy tính bảng, màn cảm ứng): không có phím/chuột để "chạm". */
export const COARSE = typeof window !== "undefined" && Boolean(window.matchMedia?.("(pointer: coarse)").matches);

export function extendGestureText(native: boolean, coarse: boolean): string {
  if (native) return "lắc máy hoặc bấm “Nghe thêm” trên thông báo";
  return coarse ? "chạm màn hình" : "chạm phím hoặc chuột";
}

export const EXTEND_GESTURE = extendGestureText(Capacitor.isNativePlatform(), COARSE);
