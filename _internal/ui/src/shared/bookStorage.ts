/** Những gì máy này nhớ theo mã sách trong bộ nhớ trình duyệt (khoá `<tiền tố><mã sách>`), liệt kê ở MỘT chỗ: cuốn đổi mã (hoàn tác về
 *  "<tên> (2)" - mã sách là đường dẫn) mang theo được hết. Chỗ nhớ mới theo mã sách thì thêm tiền tố vào đây. */
export const BOOK_STORAGE = {
  /** Giọng đọc to chọn riêng cho cuốn (listen/readAloudVoice.ts). */
  readAloudVoice: "abook-readaloud-voice-",
  /** Lúc chọn giọng ấy, để so với lựa chọn đến từ máy kia. */
  readAloudVoiceAt: "abook-readaloud-voice-at-",
  /** Chỗ đang đọc ở màn đọc chữ (listen/ReaderScreen.tsx). */
  reading: "abook-reading-",
  /** Gợi ý bỏ qua (listen/ReadingSuggestions.tsx). */
  suggestionsDismissed: "abook.suggestionsDismissed.",
  /** Lần gửi sửa đã xem (listen/SendEdits.tsx). */
  editsSentSeen: "abook.editsSentSeen.",
} as const;

/** Chuyển mọi khoá nhớ theo mã `oldId` sang `newId` rồi bỏ khoá cũ. Không đọc / ghi được bộ nhớ thì thôi - chỉ là những điều nhỏ máy này nhớ. */
export function moveBookStorage(oldId: string, newId: string): void {
  if (!oldId || !newId || oldId === newId) return;
  try {
    for (const prefix of Object.values(BOOK_STORAGE)) {
      const value = localStorage.getItem(prefix + oldId);
      if (value === null) continue;
      localStorage.setItem(prefix + newId, value);
      localStorage.removeItem(prefix + oldId);
    }
  } catch {
    /* bộ nhớ bị chặn / đầy */
  }
}
