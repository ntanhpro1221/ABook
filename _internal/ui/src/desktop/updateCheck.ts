import { S } from "../shared/strings.generated";
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
  if (detail?.state === "latest") return { tone: "ok", text: S.s_abook_0_la_ban_moi_nhat_a57654b0(current ? ` ${current}` : "") };
  return { tone: "error", text: detail?.message || S.s_chua_thay_tra_loi_tu_trang_phat_hanh_ban_k_437de1e1 };
}
