/** "Kiểm tra bản mới" ở Cài đặt (vỏ Tauri: shell/src-tauri/src/main.rs `check_for_update`). Lần tự kiểm lúc mở app im lặng khi mất mạng,
 *  nên người dùng có nút kiểm lại, và nút luôn trả về một lời - kể cả khi vỏ không kịp trả lời. */
export const UPDATE_CHECKED_EVENT = "abook-update-checked";
/** Vỏ tự bỏ cuộc sau 30 giây; quá hạn này mà trang chưa nghe gì thì vỏ coi như không trả lời. */
export const UPDATE_CHECK_WAIT_MS = 45_000;

/** Sự kiện vỏ phát: `found` (bản mới đã có, trang đọc lại /api/app), `latest` (đang dùng bản mới nhất), `failed` (kèm lời đã viết sẵn). */
export interface UpdateChecked {
  state: "found" | "latest" | "failed";
  message?: string;
}

export interface CheckLine {
  tone: "ok" | "error";
  text: string;
}

/** Lời hiện dưới nút. `found` không cần lời (mục "bản mới đã có" hiện thay); không có sự kiện (vỏ im) là lỗi mạng. */
export function checkLine(detail: UpdateChecked | null | undefined, current: string): CheckLine | null {
  if (detail?.state === "found") return null;
  if (detail?.state === "latest") return { tone: "ok", text: `ABook${current ? ` ${current}` : ""} là bản mới nhất.` };
  return { tone: "error", text: detail?.message || "Chưa thấy trả lời từ trang phát hành - bạn kiểm tra mạng rồi thử lại." };
}
