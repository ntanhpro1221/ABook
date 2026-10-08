// "Thêm sách từ file…": đưa EPUB / DOCX / PDF / thư mục TXT vào thư viện thành sách CHỈ-CÓ-CHỮ (docs/LISTEN_ANYTHING.md mục 1 và 2).
// Máy tính: máy chủ cục bộ chạy `abook/importers.py` (webui/textbook.py). Điện thoại: `BookImport.kt` ở native; PDF thì pdf.js trong
// WebView lấy chữ từng trang rồi đưa sang Kotlin (android/textImport.ts).

import { formatNumber } from "@/shared/format";

/** Một hàng của danh sách chương xem trước. `index` là số thứ tự (từ 1) trong CHÍNH danh sách này - cũng là số mà `suggestions[].chapter`
 *  và `ChapterPick.index` dùng, không phải mã chương trong sách. */
export interface ImportPreviewChapter {
  index: number;
  title: string;
  firstLine: string;
  words: number;
  chars: number;
  /** Có vào sách theo mặc định không (không có khoá = có). Mục rất ngắn (bìa, trang bản quyền) hiện ra CHƯA tích. */
  included?: boolean;
  /** Mục rất ngắn: "có thể là bìa / trang bản quyền". */
  short?: boolean;
}

/** Danh sách chương của bước xem trước - cùng hàng chữ với danh sách chương của trình tạo sách Studio. */
export interface ImportPreview {
  title: string;
  author: string | null;
  chapters: ImportPreviewChapter[];
  /** Gợi ý của máy (vd dòng ghi công ở đầu chương): hiện ra, KHÔNG BAO GIỜ tự áp. */
  notes: string[];
  /** Gợi ý chọn được: dòng ghi công người nghe có thể bỏ khỏi phần đọc (mặc định không bỏ). `chapter`: mã chương trong sách. */
  suggestions?: ImportSuggestion[];
  /** Đúng bộ chữ này đã có trong thư viện: hỏi ngay ("Mở cuốn đó" / "Thêm bản riêng"). */
  existing?: { id: string; title: string } | null;
  /** Cuốn đã thêm từ CHÍNH file này (chọn chương khác, tách hay không tách): bộ chữ khác nên không phải `existing`, nhưng người nghe nên biết trước khi thành
   *  cuốn trùng tên. `chapters`: số chương của cuốn đó. */
  sameSource?: { id: string; title: string; chapters: number } | null;
  hasCover: boolean;
  totals: { chapters: number; words: number };
  /** File TXT cả truyện (>= 2 dòng "Chương N"): số chương nếu tách theo các dòng ấy. Giao diện đề xuất (ô KHÔNG tích sẵn); không có khoá = không có gì để tách. */
  splitOffer?: number;
  /** Số dòng "Chương N" ấy; ít hơn `splitOffer` khi chữ trước tiêu đề đầu thành chương "Mở đầu". */
  splitHeadings?: number;
}

/** Một chương người dùng giữ lại, kèm tên mới nếu họ đổi (chỉ đổi TÊN; chữ của chương không đổi). */
export interface ChapterPick {
  index: number;
  title?: string;
}

/** Lựa chọn của người dùng ở bước xem trước. */
export interface ImportOptions {
  /** Tích "Tách thành N chương theo các dòng “Chương N”" - gửi kèm cả lúc xem trước lẫn lúc thêm. */
  splitChapters?: boolean;
  /** Các chương được giữ (theo hàng của bước xem trước) và tên mới - chỉ lúc thêm; không có = các chương mặc định ([chapterPicks]). */
  chapters?: ChapterPick[];
}

export interface ImportSuggestion {
  chapter: number;
  line: string;
}

/** Thứ người dùng đã chọn: máy tính - đường dẫn; điện thoại - mã của bản sao tạm do native giữ. */
export interface ImportChoice {
  ref: string;
  /** Tên hiện cho người dùng (tên file hay thư mục). */
  name: string;
}

export type ImportKind = "file" | "folder";

export interface AddedBook {
  id: string;
  /** "new" (cuốn mới), "existing" (đúng cuốn này đã có trong thư viện), "updated". */
  how: "new" | "existing" | "updated";
  chapters: number;
}

export interface TextImport {
  /** Mở bộ chọn của máy; `null` khi người dùng bỏ qua. Máy tính không có hộp thoại (chạy trong trình duyệt): không có `choose`. */
  choose?(kind: ImportKind): Promise<ImportChoice | null>;
  /** Máy tính dán được đường dẫn thay cho hộp thoại. */
  typedPath?: boolean;
  preview(choice: ImportChoice, options?: ImportOptions): Promise<ImportPreview>;
  /** `separate`: "Thêm bản riêng" - cuốn mới dù thư viện đã có đúng bộ chữ này. `options`: như lúc xem trước (điện thoại giữ cuốn của lần xem
   *  trước cuối, nên thêm đúng thứ người dùng đã thấy). */
  add(choice: ImportChoice, title: string, separate?: boolean, options?: ImportOptions): Promise<AddedBook>;
  /** Bỏ thứ tạm đã giữ cho lần chọn này (điện thoại: bản sao file); nguồn nào không giữ gì thì không có. */
  discard?(choice: ImportChoice): Promise<void>;
}

// ---- Chọn chương và đổi tên ở bước xem trước ---------------------------------------------------------------------------------
// Hàm thuần (AddBook.tsx giữ trạng thái): `picked` = số thứ tự các hàng đang tích; `names` = tên người dùng đã đổi (theo số thứ tự hàng).

/** Tên chương người dùng đã đổi, theo số thứ tự hàng; hàng không có trong đây giữ tên của file. */
export type ChapterNames = Readonly<Record<number, string>>;

/** Nhãn ô "Tách" của file TXT cả truyện: đếm các dòng "Chương N" người nghe thấy trong file, nói riêng phần "Mở đầu" thêm vào. */
export function splitLabel(preview: Pick<ImportPreview, "splitOffer" | "splitHeadings">): string {
  const offer = preview.splitOffer ?? 0;
  const headings = preview.splitHeadings ?? offer;
  const base = `Tách theo ${formatNumber(headings)} dòng “Chương N”`;
  return offer > headings ? `${base} (thêm phần Mở đầu - ${formatNumber(offer)} chương)` : base;
}

/** Từ chừng này dòng "Chương N" trong MỘT file TXT thì máy chắc đó là cả truyện: ô tách tích sẵn (soát UX a8 02-10 - truyện tải trên mạng
 *  phần lớn là một file, mặc định không tách ra "1 chương" dài hàng giờ). Hai dòng có thể chỉ là trùng hợp: dưới mức này vẫn chỉ đề xuất. */
export const SURE_SPLIT_HEADINGS = 3;

/** File TXT cả truyện mà máy chắc là nhiều chương: bản xem trước đầu tiên nên được đọc lại với "tách" đã tích. */
export function splitIsSure(preview: Pick<ImportPreview, "splitOffer" | "splitHeadings">): boolean {
  return Boolean(preview.splitOffer) && (preview.splitHeadings ?? preview.splitOffer ?? 0) >= SURE_SPLIT_HEADINGS;
}

/** Các hàng tích sẵn: mọi hàng trừ mục rất ngắn. */
export function defaultPicked(chapters: readonly ImportPreviewChapter[]): ReadonlySet<number> {
  return new Set(chapters.filter((chapter) => chapter.included !== false).map((chapter) => chapter.index));
}

/** Đang đúng như mặc định (chưa tích thêm / bỏ tích hàng nào)? */
export function isDefaultPick(chapters: readonly ImportPreviewChapter[], picked: ReadonlySet<number>): boolean {
  const wanted = defaultPicked(chapters);
  return wanted.size === picked.size && [...wanted].every((index) => picked.has(index));
}

/** Tên hiện cho hàng: tên người dùng đổi, không thì tên của file. */
export function shownTitle(chapter: ImportPreviewChapter, names: ChapterNames): string {
  return names[chapter.index] ?? chapter.title;
}

/** Người dùng gõ `value` làm tên mới cho hàng: rỗng hay đúng tên cũ là giữ tên cũ (bỏ đổi tên). */
export function renameChapter(names: ChapterNames, chapter: Pick<ImportPreviewChapter, "index" | "title">, value: string): ChapterNames {
  const next = { ...names };
  const clean = value.trim().replace(/\s+/g, " ");
  if (!clean || clean === chapter.title) delete next[chapter.index];
  else next[chapter.index] = clean;
  return next;
}

/** Số chương và số chữ của những hàng đang tích. */
export function pickedTotals(chapters: readonly ImportPreviewChapter[], picked: ReadonlySet<number>): { chapters: number; words: number } {
  const rows = chapters.filter((chapter) => picked.has(chapter.index));
  return { chapters: rows.length, words: rows.reduce((sum, chapter) => sum + chapter.words, 0) };
}

/** Lựa chọn gửi lúc thêm; `undefined` khi người dùng không đổi gì (các chương mặc định, tên của file) - máy chủ / điện thoại tự lấy mặc định. */
export function chapterPicks(chapters: readonly ImportPreviewChapter[], picked: ReadonlySet<number>, names: ChapterNames): ChapterPick[] | undefined {
  const renamed = chapters.some((chapter) => picked.has(chapter.index) && names[chapter.index]?.trim());
  if (!renamed && isDefaultPick(chapters, picked)) return undefined;
  return chapters
    .filter((chapter) => picked.has(chapter.index))
    .map((chapter) => {
      const title = names[chapter.index]?.trim();
      return title && title !== chapter.title ? { index: chapter.index, title } : { index: chapter.index };
    });
}

/** Gợi ý ghi công chỉ của các hàng đang tích, đánh số lại thành MÃ CHƯƠNG trong sách sẽ thêm (hàng thứ k trong số hàng tích = chương k). */
export function pickedSuggestions(
  suggestions: readonly ImportSuggestion[],
  chapters: readonly ImportPreviewChapter[],
  picked: ReadonlySet<number>,
): ImportSuggestion[] {
  const ids = new Map<number, number>();
  for (const chapter of chapters) if (picked.has(chapter.index)) ids.set(chapter.index, ids.size + 1);
  return suggestions.flatMap((suggestion) => {
    const id = ids.get(suggestion.chapter);
    return id === undefined ? [] : [{ ...suggestion, chapter: id }];
  });
}
