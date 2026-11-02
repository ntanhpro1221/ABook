// Trang sách đổi bố cục (một cột <-> hai cột) giữa chừng: khung cuộn danh sách chương đổi chỗ (cả trang <-> cột phải), nhưng chỗ đang xem phải
// đứng yên (DESIGN.md 5.5: giữ vị trí cuộn khi đổi khổ), không nhảy về chương đang nghe. Đo hàng đầu đang thấy TRƯỚC khi bố cục đổi, đặt lại SAU.
import { isPage, scrollParent } from "@/shared/scrollMemory";

export type ChapterAnchor = {
  /** Chương ở mép trên khung nhìn. */
  id: string;
  /** Mép trên hàng so với mép trên khung nhìn (âm: hàng bị cắt một phần). */
  offset: number;
  /** Mép trên hàng so với mép trên danh sách chương - giữ nguyên giữa hai bố cục khi hàng cao như nhau, dùng khi hàng chưa dựng (Windowed). */
  along: number;
};

const viewTop = (scroller: HTMLElement) => (isPage(scroller) ? 0 : scroller.getBoundingClientRect().top);

/** Khung cuộn của danh sách chương trong bố cục `split`: cột phải khi hai cột, còn lại là khung cuộn của cả trang. */
export function chapterScroller(frame: HTMLElement, split: boolean): HTMLElement {
  return (split && frame.querySelector<HTMLElement>("[data-book-list]")) || scrollParent(frame);
}

/** Hàng chương đầu tiên còn thấy trong khung của bố cục `split`; chưa có hàng nào (tab khác, danh sách trống) thì null. */
export function chapterAnchor(frame: HTMLElement, list: HTMLElement, split: boolean): ChapterAnchor | null {
  const top = viewTop(chapterScroller(frame, split));
  const listTop = list.getBoundingClientRect().top;
  for (const row of list.querySelectorAll<HTMLElement>("[data-chapter]")) {
    if (row.closest("[inert]")) continue;
    const box = row.getBoundingClientRect();
    if (box.bottom > top) return { id: row.dataset.chapter!, offset: box.top - top, along: box.top - listTop };
  }
  return null;
}

/** Cuộn khung của bố cục mới sao cho hàng neo đứng đúng chỗ cũ trên màn hình. Trả về khung đã cuộn. */
export function placeChapterAnchor(frame: HTMLElement, list: HTMLElement, split: boolean, anchor: ChapterAnchor): HTMLElement {
  const scroller = chapterScroller(frame, split);
  const top = viewTop(scroller);
  const row = list.querySelector<HTMLElement>(`[data-chapter="${CSS.escape(anchor.id)}"]`);
  const now = row ? row.getBoundingClientRect().top : list.getBoundingClientRect().top + anchor.along;
  scroller.scrollTop += now - top - anchor.offset;
  return scroller;
}
