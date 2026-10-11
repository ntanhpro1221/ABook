// Văn bản đi theo giọng đọc - màn đọc (ReaderScreen) và tab "Đọc theo" của trình phát dùng chung (ReadAlongText.tsx), cho cả sách nói của
// Studio lẫn "Nghe ngay".
//
// Luật (chọn 03-10):
// - Đang theo: câu đang nghe sắp khuất (chạm mép trên, hay xuống quá 85% chiều cao khung) thì cuộn nó lên khoảng một phần ba từ trên - không
//   cuộn theo từng câu, mắt không bị kéo liên tục.
// - Người tự cuộn (lăn chuột, vuốt, phím trang / mũi tên, kéo thanh cuộn) là thôi theo.
// - Theo lại khi: bấm "Tới câu đang nghe", bấm một chữ / một câu để nghe, hay người đọc tự cuộn về chỗ câu đang nghe (câu ấy nằm trong khung và
//   đã thôi cuộn SETTLE_MS). KHÔNG tự theo lại chỉ vì đứng yên vài giây: người đang đọc trước một đoạn sẽ bị giật trang mất chỗ.
// - "Tới câu đang nghe" hiện bất cứ khi nào câu đang nghe nằm ngoài khung (không còn ngưỡng "cách 12 câu").

export interface Box {
  top: number;
  bottom: number;
}

export type Placement = "above" | "inside" | "below";

/** Người thôi cuộn chừng này (ms) mà câu đang nghe nằm trong khung: theo lại. */
export const SETTLE_MS = 1500;
/** Câu đang nghe xuống quá phần này của khung thì cuộn (khi đang theo). */
const LOW_EDGE = 0.85;
/** Chỗ đặt câu đang nghe sau khi cuộn: phần này của chiều cao khung tính từ trên. */
const PLACE_AT = 0.3;
/** Câu chỉ còn ló chừng này px ở mép trên thì không tính là "thấy". */
const SLACK = 4;

/** Câu (`rect`) nằm đâu so với khung cuộn (`view`): thấy được một phần cũng là "inside". */
export function placementOf(rect: Box, view: Box): Placement {
  if (rect.bottom <= view.top + SLACK) return "above";
  if (rect.top >= view.bottom - SLACK) return "below";
  return "inside";
}

/** Đang theo mà câu đang nghe không còn nằm gọn trong vùng dễ đọc: cần cuộn. */
export function needsFollowScroll(rect: Box, view: Box): boolean {
  const height = view.bottom - view.top;
  return rect.top < view.top || rect.bottom > view.top + height * LOW_EDGE;
}

/** `scrollTop` mới để câu `rect` đứng ở khoảng một phần ba từ trên khung. */
export function followScrollTop(rect: Box, view: Box, scrollTop: number): number {
  const height = view.bottom - view.top;
  return Math.max(0, scrollTop + rect.top - view.top - height * PLACE_AT);
}

/** Thôi theo (người đã cuộn) mà câu đang nghe lại nằm trong khung, và người đã ngừng cuộn đủ lâu: theo lại. */
export function shouldResumeFollowing(following: boolean, placement: Placement | null, manualAt: number, now: number): boolean {
  return !following && placement === "inside" && now - manualAt >= SETTLE_MS;
}

/** Hiện "Tới câu đang nghe": có câu đang nghe mà nó nằm ngoài khung (đang theo thì app tự cuộn, nút không cần). */
export function showJumpToPlaying(following: boolean, placement: Placement | null): boolean {
  return !following && placement !== null && placement !== "inside";
}

/** Câu đầu tiên còn thấy trong khung (theo thứ tự trong chương): chỗ đọc, và chỗ "Nghe từ đây" bắt đầu. Không câu nào thấy: câu đầu (hay 0). */
export function firstVisibleIndex(items: readonly ({ index: number } & Box)[], view: Box): number {
  for (const item of items) {
    if (item.bottom > view.top + SLACK && item.top < view.bottom) return item.index;
  }
  return items[0]?.index ?? 0;
}

/** Phím mà người dùng cuộn trang bằng nó - bấm là thôi theo. (Space là phát / tạm dừng của trình phát, không cuộn.) */
export const SCROLL_KEYS = new Set(["PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown"]);

/** Giọng vừa sang chương `after` (đang nghe `before` trước đó): màn đọc đang mở đúng chương `before` thì đi theo sang `after`; đang mở chương khác thì để yên. */
export function chapterToFollow(before: number | null, after: number | null, shown: number): number | null {
  return before !== null && after !== null && before !== after && before === shown ? after : null;
}

/** Câu mà hộp "Sửa câu này" đang sửa: bản chữ của CHÍNH chương lúc mở và thứ tự câu trong đó - không phải "câu thứ N của chương đang hiện".
 *  Giọng tự sang chương sau thì màn đọc đi theo (`chapterToFollow`), hộp thì không: lưu lúc ấy vẫn sửa đúng câu đã mở (soát UX a24, A5:
 *  hộp đổi sang câu cùng thứ tự của chương mới, lưu là sửa nhầm câu). null: không có câu ấy. */
export interface LineToEdit<S> {
  script: S;
  index: number;
}

export function lineToEdit<S extends { segments: readonly unknown[] }>(script: S, index: number): LineToEdit<S> | null {
  return index >= 0 && index < script.segments.length ? { script, index } : null;
}
