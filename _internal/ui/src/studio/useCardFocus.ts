import { useEffect, useLayoutEffect, useRef, type MutableRefObject } from "react";
import { focusAfterChange, type WorkLists } from "./workFocus";

/** Nơi tiêu điểm về khi danh sách thẻ hết: `end` (dòng báo cuối danh sách), không có thì `lead` (lời mở đầu / vùng chứa danh sách). */
export interface CardFocusEnds {
  end: string;
  lead: string;
}

/** Đặt tiêu điểm vào thẻ (hay chỗ đứng khi hết thẻ) và cuộn cho thấy. */
export function focusCard(id: string, ends: CardFocusEnds): void {
  const element = document.getElementById(id) ?? (id === ends.end ? document.getElementById(ends.lead) : null);
  element?.focus({ preventScroll: true });
  element?.scrollIntoView({ block: "nearest" });
}

/** Quyết / hoàn tác làm thẻ đang giữ tiêu điểm rời danh sách: tiêu điểm sang thẻ kế thay vì rơi về BODY (soát a31 K4; luật ở workFocus.ts).
 *  Dùng chung cho hộp "Việc cần duyệt" và màn "Duyệt trước khi thu". `lists`: ref chứa mã các thẻ đang hiện, gán MỖI LẦN vẽ (sau khi
 *  đã biết danh sách); thẻ cần `id="work-<mã>"` và `data-work-key="<mã>"`.
 *  `lastCard`: thẻ chứa tiêu điểm lần gần nhất, "toast" nếu tiêu điểm ở thông báo (nút Hoàn tác), null nếu ở chỗ khác. */
export function useCardFocus(lists: MutableRefObject<WorkLists | null>, ends: CardFocusEnds): void {
  const lastCard = useRef<string | null>(null);
  const seen = useRef<WorkLists | null>(null);
  useEffect(() => {
    const onFocus = (event: FocusEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      const card = target?.closest<HTMLElement>("[data-work-key]");
      lastCard.current = card ? (card.dataset.workKey ?? null) : target?.closest("[data-sonner-toast]") ? "toast" : null;
    };
    document.addEventListener("focusin", onFocus);
    return () => document.removeEventListener("focusin", onFocus);
  }, []);
  useLayoutEffect(() => {
    const before = seen.current;
    const now = lists.current;
    seen.current = now;
    if (!before || !now || lastCard.current === null) return;
    const active = document.activeElement;
    // Nút Hoàn tác nằm trong thông báo sắp tắt: thẻ vừa quay lại nhận tiêu điểm luôn, không chờ thông báo tắt rồi rơi về BODY.
    const inToast = Boolean(active?.closest("[data-sonner-toast]"));
    if (active && active !== document.body && active.isConnected && !inToast) return;
    const target = focusAfterChange(before, now, lastCard.current === "toast" ? null : lastCard.current);
    if (target === null) return;
    const id = target === "end" ? ends.end : `work-${target}`;
    focusCard(id, ends);
    // Rời vùng thông báo thì sonner trả tiêu điểm về chỗ đứng TRƯỚC khi vào thông báo (thẻ cũ) - đặt lại một lần nữa sau đó.
    if (inToast) window.setTimeout(() => focusCard(id, ends), 0);
  });
}
