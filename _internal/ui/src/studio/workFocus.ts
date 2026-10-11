// Tiêu điểm bàn phím trong hộp "Việc cần duyệt" (soát a31 K4): bấm "Nhận" / "Giữ" / "Hoàn tác" làm thẻ rời danh sách, nút đang giữ tiêu điểm
// mất theo và tiêu điểm rơi về BODY - người dùng bàn phím phải Tab lại từ đầu trang. Hàm thuần ở đây chọn chỗ đứng mới, WorkInbox đặt tiêu điểm.

/** Mã thẻ của hai danh sách: chờ duyệt (`open`) và đã quyết chờ áp dụng (`decided`). */
export interface WorkLists {
  open: string[];
  decided: string[];
}

/** "end": danh sách hết thẻ - tiêu điểm về dòng báo / tiêu đề danh sách. */
export type FocusAfter = string | "end" | null;

/** Thẻ nhận tiêu điểm sau khi danh sách đổi và tiêu điểm vừa mất (về BODY). `focused`: thẻ chứa tiêu điểm lần gần nhất (null: tiêu điểm
 *  không ở thẻ nào, vd ở nút "Hoàn tác" của thông báo).
 *  - Thẻ ấy rời danh sách của nó: thẻ KẾ ở đúng chỗ ấy trong cùng danh sách (hết thẻ phía sau thì thẻ trước); danh sách trống thì "end" -
 *    trừ hoàn tác thẻ đã quyết cuối cùng: chính thẻ ấy, vừa về lại chờ duyệt.
 *  - Thẻ ấy còn nguyên chỗ (vẽ lại mất tiêu điểm): chính nó.
 *  - Không có thẻ nào giữ tiêu điểm: thẻ vừa từ "đã quyết" trở lại "chờ duyệt" (Hoàn tác ở thông báo), nếu có. Thẻ vai phụ nằm ở "đã
 *    quyết" thành từng câu (mã khác), nên thẻ mới hiện ở "chờ duyệt" đúng lúc "đã quyết" bớt đi cũng tính là thẻ vừa trở lại. */
export function focusAfterChange(before: WorkLists, after: WorkLists, focused: string | null): FocusAfter {
  if (focused === null) {
    const back = after.open.filter((key) => !before.open.includes(key));
    return back.find((key) => before.decided.includes(key)) ?? (after.decided.length < before.decided.length ? back[0] : undefined) ?? null;
  }
  const list = before.open.includes(focused) ? "open" : before.decided.includes(focused) ? "decided" : null;
  if (!list) return null;
  const now = after[list];
  if (now.includes(focused)) return focused;
  if (now.length) return now[Math.min(before[list].indexOf(focused), now.length - 1)];
  // Thẻ đã quyết nằm trong mục thu gọn (có thể đang đóng) - không đưa tiêu điểm theo thẻ vừa quyết xuống đó.
  return list === "decided" && after.open.includes(focused) ? focused : "end";
}
