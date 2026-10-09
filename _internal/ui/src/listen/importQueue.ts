// Hàng xem trước của "Thêm sách từ file…" khi chọn / kéo thả NHIỀU file một lúc: mỗi cuốn vẫn qua đúng bước xem trước của một file; hàng chỉ
// nhớ cuốn nào đã thêm, đã có, đã bỏ, hay không đọc được (lỗi của một file không chặn các file sau). Hàm thuần - AddBook.tsx giữ trạng thái.

import { defaultPicked, isBookFile, readPreview, type ImportChoice, type PickedItem, type TextImport } from "./textImport";

export type QueueState = "waiting" | "added" | "existing" | "skipped" | "error" | "opened";

export interface QueueItem {
  id: number;
  name: string;
  choice?: ImportChoice;
  state: QueueState;
  /** Lý do (lỗi) hay lời nhắn ngắn ("Đã có trong thư viện"). */
  note?: string;
  /** Cuốn đã vào thư viện (hay đã có sẵn): để mở trang sách. */
  bookId?: string;
  /** Số thứ tự trong "Sách 2/5": chỉ các file đọc được lúc chọn được đánh số; file không nhận được thì chỉ hiện trong danh sách. */
  number?: number;
}

const BOOK_TYPES = /\.(epub|docx|pdf|txt|abook|abookproj)$/i;

/** Một đường dẫn trên máy (hộp chọn file, hay file kéo thả vào cửa sổ app) thành [PickedItem]. Không có đuôi = có thể là thư mục TXT: để bước
 *  xem trước nói nếu hoá ra không phải. Đuôi khác (ảnh, .mobi...) thì nói rõ ngay, không đoán. */
export function itemFromPath(path: string): PickedItem {
  const clean = path.trim();
  const name = clean.split(/[\\/]/).filter(Boolean).pop() ?? clean;
  const last = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  if (last && !BOOK_TYPES.test(name)) {
    return { name, error: `ABook chưa đọc được file ${last.toLowerCase()} - chỉ nhận EPUB, Word (DOCX), PDF có chữ, TXT, hay file sách .abook.` };
  }
  return { name, choice: { ref: clean, name } };
}

/** Dựng hàng từ những thứ đã chọn; file sách .abook / .abookproj xếp CUỐI (mở chúng đưa app sang trang sách, nên làm sau khi xong các cuốn cần xem trước). */
export function buildQueue(picked: readonly PickedItem[]): QueueItem[] {
  const entries = picked.map((item, index) => ({ item, index }));
  const isBook = (item: PickedItem) => "choice" in item && isBookFile(item.choice.ref);
  entries.sort((a, b) => Number(isBook(a.item)) - Number(isBook(b.item)) || a.index - b.index);
  let number = 0;
  return entries.map(({ item }, id) => {
    if ("error" in item) return { id, name: item.name, state: "error", note: item.error };
    if ("opened" in item) return { id, name: item.name, state: "opened", note: "Đã mở" };
    number += 1;
    return { id, name: item.name, choice: item.choice, state: "waiting", number };
  });
}

/** Mấy cuốn trong hàng cần xem trước ("5" của "Sách 2/5"). */
export function queueTotal(items: readonly QueueItem[]): number {
  return items.filter((item) => item.number !== undefined).length;
}

/** "Sách 2/5" cho một cuốn; không đánh số (file không nhận được) thì không có nhãn. */
export function queueLabel(items: readonly QueueItem[], id: number): string {
  const item = items.find((entry) => entry.id === id);
  return item?.number === undefined ? "" : `Sách ${item.number}/${queueTotal(items)}`;
}

export const nextWaiting = (items: readonly QueueItem[]): QueueItem | undefined => items.find((item) => item.state === "waiting");

/** Các cuốn còn chờ SAU cuốn `id` (cuốn đang xem không tính). */
export function waitingAfter(items: readonly QueueItem[], id: number): QueueItem[] {
  return items.filter((item) => item.state === "waiting" && item.id !== id);
}

export function settle(items: readonly QueueItem[], id: number, patch: Pick<QueueItem, "state"> & Partial<Pick<QueueItem, "note" | "bookId">>): QueueItem[] {
  return items.map((item) => (item.id === id ? { ...item, note: undefined, ...patch } : item));
}

/** "Thêm tất cả phần còn lại": thêm một cuốn đúng như bước xem trước đề xuất, không hỏi gì - tên của file, các chương mặc định (trừ mục rất ngắn), tách
 *  chương khi máy chắc. Cuốn đã có trong thư viện thì không thêm (như hộp xem trước: ở đó nút chính cũng là "Mở cuốn đó"). Lỗi ném ra cho chỗ gọi ghi vào hàng. */
export async function addWithDefaults(
  importer: Pick<TextImport, "preview" | "add">,
  choice: ImportChoice,
): Promise<Pick<QueueItem, "state" | "note" | "bookId">> {
  const { preview, split } = await readPreview(importer, choice);
  if (preview.existing) return { state: "existing", note: "Đã có trong thư viện", bookId: preview.existing.id };
  if (preview.sameSource) return { state: "existing", note: "Đã thêm từ file này rồi", bookId: preview.sameSource.id };
  const title = preview.title.trim();
  if (!title) throw new Error("File này chưa có tên sách - thêm riêng để đặt tên.");
  if (defaultPicked(preview.chapters).size === 0) throw new Error("File này chưa có chương nào để thêm.");
  const added = await importer.add(choice, title, false, { splitChapters: split });
  return { state: added.how === "existing" ? "existing" : "added", note: added.how === "existing" ? "Đã có trong thư viện" : undefined, bookId: added.id };
}

export interface QueueSummary {
  added: number;
  existing: number;
  skipped: number;
  failed: number;
  opened: number;
}

export function summarize(items: readonly QueueItem[]): QueueSummary {
  const count = (state: QueueState) => items.filter((item) => item.state === state).length;
  return { added: count("added"), existing: count("existing"), skipped: count("skipped"), failed: count("error"), opened: count("opened") };
}

/** Một câu cho người nghe sau khi hàng xong: "Đã thêm 3 sách · 1 cuốn đã có trong thư viện · 1 file chưa đọc được". */
export function summaryText(summary: QueueSummary): string {
  const parts = [
    summary.added ? `Đã thêm ${summary.added} sách` : "",
    summary.opened ? `đã mở ${summary.opened} file sách` : "",
    summary.existing ? `${summary.existing} cuốn đã có trong thư viện` : "",
    summary.skipped ? `bỏ qua ${summary.skipped} cuốn` : "",
    summary.failed ? `${summary.failed} file chưa đọc được` : "",
  ].filter(Boolean);
  const text = parts.join(" · ");
  return text ? text[0].toUpperCase() + text.slice(1) : "Không thêm cuốn nào";
}

/** Chọn / kéo thả xong: một file thì y như trước (bước xem trước, hay lý do không nhận được); nhiều file thì thành hàng. */
export type PickPlan = { kind: "none" } | { kind: "single"; item: PickedItem } | { kind: "queue"; items: QueueItem[] };

export function planPick(picked: readonly PickedItem[]): PickPlan {
  if (picked.length === 0) return { kind: "none" };
  if (picked.length === 1) return { kind: "single", item: picked[0] };
  return { kind: "queue", items: buildQueue(picked) };
}

/** Sang cuốn kế trong hàng. `load` đọc một file cho bước xem trước (ném lỗi nếu không đọc được: ghi vào hàng, đi tiếp - không chặn các cuốn sau); file sách
 *  .abook (xếp cuối hàng) đi `openBooks`. Trả hàng mới và cuốn vừa đọc xong (`null` = hàng đã hết). */
export async function advanceQueue(
  start: readonly QueueItem[],
  load: (item: QueueItem, items: QueueItem[]) => Promise<void>,
  openBooks: (items: QueueItem[]) => Promise<QueueItem[]>,
  failed?: (item: QueueItem) => void,
): Promise<{ items: QueueItem[]; current: QueueItem | null }> {
  let items = [...start];
  for (;;) {
    const next = nextWaiting(items);
    if (!next?.choice) return { items, current: null };
    if (isBookFile(next.choice.ref)) return { items: await openBooks(items), current: null };
    try {
      await load(next, items);
      return { items, current: next };
    } catch (error) {
      failed?.(next);
      items = settle(items, next.id, { state: "error", note: (error as Error).message });
    }
  }
}

/** "Thêm tất cả phần còn lại": `current` là kết quả của cuốn đang xem (người dùng đã thêm hay bỏ qua nó đúng như đang hiện - chỗ gọi lo); các cuốn chờ SAU nó
 *  đi `addWithDefaults`, lỗi ghi vào hàng và đi tiếp. File sách .abook để `openBooks` làm sau cùng. */
export async function addRest(
  importer: Pick<TextImport, "preview" | "add" | "discard">,
  start: readonly QueueItem[],
  currentId: number,
  current: Pick<QueueItem, "state" | "note" | "bookId">,
  hooks: { working?: (name: string) => void; changed?: (items: QueueItem[]) => void; openBooks: (items: QueueItem[]) => Promise<QueueItem[]> },
): Promise<QueueItem[]> {
  let items = settle(start, currentId, current);
  hooks.changed?.(items);
  for (const item of waitingAfter(items, currentId)) {
    if (!item.choice || isBookFile(item.choice.ref)) continue;
    hooks.working?.(item.name);
    try {
      items = settle(items, item.id, await addWithDefaults(importer, item.choice));
    } catch (error) {
      void importer.discard?.(item.choice).catch(() => undefined);
      items = settle(items, item.id, { state: "error", note: (error as Error).message });
    }
    hooks.changed?.(items);
  }
  return hooks.openBooks(items);
}
