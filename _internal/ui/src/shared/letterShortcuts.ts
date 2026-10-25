import { useSyncExternalStore } from "react";

// Phím tắt MỘT CHỮ CÁI của máy tính (M, [ ], ? ở trình phát; J/K/1-9 ở Việc cần duyệt; O/R ở Cần nghe lại) tắt được ở Cài đặt › Phím tắt
// (WCAG 2.1.4, soát a31): người dùng phần mềm nhập bằng giọng nói hay bàn phím dính lỡ "gõ" một chữ là app làm việc ấy. Mặc định bật như
// trước. Space, mũi tên, Esc và phím có Ctrl / Alt không thuộc nhóm này - vẫn chạy. Máy tính đọc cài đặt đã lưu (desktop/App.tsx); điện thoại
// không có bàn phím - không có công tắc, cờ luôn bật mà cũng không có phím nào bấm.

let enabled = true;
const listeners = new Set<() => void>();

/** Phím một chữ cái đang được dùng? Bộ bắt phím hỏi lúc có phím, nên đổi cài đặt có hiệu lực ngay. */
export function letterShortcutsOn(): boolean {
  return enabled;
}

export function setLetterShortcuts(value: boolean): void {
  if (value === enabled) return;
  enabled = value;
  for (const listener of listeners) listener();
}

/** Cho giao diện (hộp Phím tắt) vẽ lại khi cài đặt đổi. */
export function useLetterShortcuts(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    letterShortcutsOn,
    letterShortcutsOn,
  );
}
