// Phép tính thuần cho hàng tab cuộn ngang (TabsList trong ui.tsx) - tách ra để thử được không cần trình duyệt.

/** Vị trí cuộn mới để tab [left, left+width) hiện hẳn trong khung `viewWidth` (chừa `margin` cho vùng mờ ở mép); null = đã nằm trong tầm nhìn. */
export function revealedScroll(left: number, width: number, scrollLeft: number, viewWidth: number, margin: number): number | null {
  if (left < scrollLeft) return Math.max(0, left - margin);
  if (left + width > scrollLeft + viewWidth) return left + width - viewWidth + margin;
  return null;
}

/** Lăn chuột thường (dọc) trên hàng tab thành cuộn ngang. Trả vị trí cuộn mới, hay null khi KHÔNG nên chặn cú lăn: hàng vừa khung (không có gì để cuộn),
 *  cú lăn vốn đã ngang (bàn rê hai ngón, Shift+lăn), hoặc đã tới đầu/cuối hàng - lúc ấy để trang tự cuộn dọc, khỏi kẹt chuột trên hàng tab.
 *  `zoom` (Ctrl+lăn): đó là phóng to / thu nhỏ của trình duyệt, không được chặn. */
export function wheelScroll(deltaX: number, deltaY: number, scrollLeft: number, viewWidth: number, scrollWidth: number, zoom = false): number | null {
  const max = scrollWidth - viewWidth;
  if (zoom || max <= 1 || Math.abs(deltaX) >= Math.abs(deltaY) || deltaY === 0) return null;
  const next = Math.min(max, Math.max(0, scrollLeft + deltaY));
  // scrollLeft ở màn thu phóng là số lẻ (338,87 trong khi scrollWidth - clientWidth = 339) nên so có dung sai, không thì cuối hàng vẫn chặn trang cuộn.
  return Math.abs(next - scrollLeft) < 1 ? null : next;
}
