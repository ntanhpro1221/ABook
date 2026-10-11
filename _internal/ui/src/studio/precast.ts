import type { BookSummary, PrecastView } from "./api";

// "Duyệt trước khi thu" (webui/precast.py, docs/STUDIO_REVIEW.md): phân tích xong, trước khi thu những chương đầu - lúc sửa còn
// miễn phí. Màn duyệt dẫn qua đúng thứ tự người duyệt cần, mỗi bước là thẻ / dòng sẵn có của hộp việc và tab Nhân vật. Phần
// này chỉ chọn và đếm - không gì ở đây sửa chữ truyện.

export type PrecastStep = "cast" | "names" | "lines" | "done";
export const PRECAST_STEPS: PrecastStep[] = ["cast", "names", "lines", "done"];

/** Những người nói nhiều nhất: giọng của họ nghe suốt cuốn. */
export const TOP_PEOPLE = 6;
const CAST_KINDS = ["gender", "alias", "shared-voice"];
const LINE_KINDS = ["speaker", "turn", "vocative", "bracket", "unnamed"];

/** Phần của thẻ việc (webui/work_items.py) mà màn duyệt cần - để chọn thẻ không phải dựng cả thẻ. */
export interface WorkItemLike {
  kind: string;
  key: string;
  affected: number;
  doubt: number;
  requested?: string | null;
  redoOnly?: boolean | null;
  chapters?: number[];
}

/** Việc cần làm: chưa quyết, và quyết thì có tác dụng ngay - không tính việc đã quyết (chờ áp dụng) hay việc chỉ áp khi làm lại
 *  phân tích - thẻ người kể của đoạn đã phân tích xong (soát UX a23: lúc chờ duyệt "Việc cần duyệt 6" toàn là những thẻ ấy). Cùng
 *  phép đếm với work_items.open_count - con số điện thoại nhận. */
export function isOpenWork(item: Pick<WorkItemLike, "requested" | "redoOnly">): boolean {
  return !item.requested && !item.redoOnly;
}

const open = <T extends WorkItemLike>(items: T[]) => items.filter(isOpenWork);

/** (a) Việc về người và giọng: nam hay nữ, một người hai tên, hai người chung giọng. Giữ thứ tự lợi / lần bấm của hộp việc. */
export function castItems<T extends WorkItemLike>(items: T[]): T[] {
  return open(items).filter((item) => CAST_KINDS.includes(item.kind));
}

/** (b) Cách đọc tên máy tự đoán - tên máy kém chắc nhất trước, cùng mức thì tên gặp nhiều câu hơn trước. */
export function nameItems<T extends WorkItemLike>(items: T[]): T[] {
  return open(items)
    .filter((item) => item.kind === "pronunciation")
    .sort((a, b) => b.doubt - a.doubt || b.affected - a.affected);
}

/** (c) "Ai nói câu này" kém chắc ở các chương sắp thu - thu xong chương ấy thì sửa phải thu lại. */
export function lineItems<T extends WorkItemLike>(items: T[], upcoming: number[]): T[] {
  const ahead = new Set(upcoming);
  return open(items).filter((item) => LINE_KINDS.includes(item.kind) && (item.chapters ?? []).some((id) => ahead.has(id)));
}

/** Mã các thẻ việc nằm trong màn duyệt (ba bước trên). Tab "Duyệt trước khi thu" đếm chúng, "Việc cần duyệt" đếm phần còn lại -
 *  cộng hai nhãn đúng bằng số việc điện thoại nhận (soát UX a24, A7: điện thoại báo 29, máy tính không đâu có 29). */
export function precastKeys(items: WorkItemLike[], upcoming: number[]): Set<string> {
  return new Set([...castItems(items), ...nameItems(items), ...lineItems(items, upcoming)].map((item) => item.key));
}

export function lineCount(items: WorkItemLike[]): number {
  return items.reduce((total, item) => total + item.affected, 0);
}

/** "Chương 1" / "Chương 1 → Chương 3" cho các chương sắp thu (đã theo thứ tự đọc). */
export function chapterRange(chapters: { title: string }[]): string {
  if (!chapters.length) return "";
  const first = chapters[0].title;
  const last = chapters[chapters.length - 1].title;
  return chapters.length === 1 ? first : `${first} → ${last}`;
}

/** Sửa tới đâu thì miễn phí: chưa thu gì là mọi sửa; đã thu tới chương X thì sửa ở chương sau X không phải thu lại. */
export function freeNote(view: Pick<PrecastView, "recordedThrough">): string {
  return view.recordedThrough
    ? `Đã thu tới ${view.recordedThrough.title} - sửa ở chương sau đó không phải thu lại; sửa chỗ đã thu thì máy thu lại đúng các câu ấy.`
    : "Chưa thu chương nào - sửa bây giờ không phải thu lại câu nào.";
}

/** Có nên mở màn duyệt: phân tích xong, sách chưa xong. */
export function canReview(book: Pick<BookSummary, "phase" | "precast">): boolean {
  return Boolean(book.precast?.ready) && book.phase !== "done";
}

/** Lời mời "Phân tích xong - duyệt trước khi thu?" hiện một lần cho mỗi lần Studio báo mốc (`announcedAt`), và chỉ khi còn
 *  đúng lúc: sách đang được giữ chờ duyệt, hay chưa thu xong chương nào. `seen(id)`: mốc đã mời của cuốn ấy (bộ nhớ trình duyệt). */
export function precastInvites<B extends Pick<BookSummary, "id" | "phase" | "precast" | "chapters">>(
  books: B[],
  seen: (id: string) => string | null,
): B[] {
  return books.filter((book) => {
    const at = book.precast?.announcedAt;
    if (!at || !canReview(book)) return false;
    if (!book.precast?.held && book.chapters.completed > 0) return false;
    return seen(book.id) !== String(at);
  });
}
