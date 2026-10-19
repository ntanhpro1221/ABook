// Lời đọc của một việc có tiến độ cho trình đọc màn hình (soát a31 A6): chữ trên màn đổi mỗi giây (đồng hồ, MB, %) mà nằm trong vùng
// aria-live / role=status thì bị đọc lại mỗi giây. Chữ nhìn vẫn cập nhật (LiveText, shared/ui.tsx); lời đọc chỉ đổi khi đổi PHA hay qua
// mốc 25 % - những lúc người nghe thật sự cần biết.

/** Mốc đã qua của phần đã xong (0-1): 0, 25, 50, 75, 100. Không biết tiến độ: null. */
export function progressMilestone(fraction: number | null | undefined): number | null {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return null;
  return Math.floor(Math.max(0, Math.min(1, fraction)) * 4) * 25;
}

/** "Đang tải sẵn nhạc nền · 50%": pha + mốc 25 % (pha đã có dấu "…" thì bỏ dấu ấy). Không biết tiến độ, hay chưa qua mốc 25 % đầu, thì chỉ nói pha:
 *  "· 0%" đứng cạnh số thật trên màn ("Đang tải … 6%") là hai số mâu thuẫn (soát a69, Cài đặt điện thoại). */
export function spokenProgress(phase: string, fraction?: number | null): string {
  const at = progressMilestone(fraction);
  const name = phase.replace(/…$/, "");
  return at === null || at === 0 ? phase : `${name} · ${at}%`;
}
