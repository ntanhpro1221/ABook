import { foldVietnamese } from "./model";

// Tìm chữ trong sách (ô "Tìm trong sách"): khớp không phân biệt hoa thường và dấu, trên CHỮ GỐC của sách (`segment.text`, không phải chữ đem đọc),
// trả đoạn trích quanh chỗ khớp để tô đậm. Hàm thuần - việc đi qua các chương nằm ở bookSearch.ts.

/** Ít nhất chừng này ký tự mới tìm: một ký tự khớp gần như mọi câu. */
export const MIN_QUERY = 2;

/** Từ khoá đã chuẩn hoá để so khớp ("  Nguyễn   An " -> "nguyen an"); rỗng khi chưa đủ dài. */
export function foldedQuery(query: string): string {
  const folded = foldedText(query).replace(/ +/g, " ").trim();
  return folded.length >= MIN_QUERY ? folded : "";
}

/** Chữ của một đoạn đã chuẩn hoá để so khớp: foldVietnamese, mọi kiểu khoảng trắng (xuống dòng, khoảng trắng cứng…) thành dấu cách - độ dài giữ nguyên
 *  từng ký tự, nên chỗ khớp dò lại về chữ gốc được ([originalSpan]). */
export function foldedText(text: string): string {
  return foldVietnamese(text).replace(/\s/g, " ");
}

const cache = new Map<string, string>();

/** Chuẩn hoá một ký tự (có thể thành rỗng - dấu rời - hay vài ký tự), cùng kết quả với [foldedText]. Ký tự ASCII đi đường tắt. */
function foldChar(char: string): string {
  if (char < "\u0080") return /\s/.test(char) ? " " : char.toLowerCase();
  let folded = cache.get(char);
  if (folded === undefined) {
    folded = foldedText(char);
    if (cache.size < 4096) cache.set(char, folded);
  }
  return folded;
}

/** Đoạn [start, end) của `text` (chữ gốc) ứng với chỗ khớp ở vị trí `at` dài `length` của `foldedText(text)`. Chuẩn hoá từng ký tự để biết ký tự gốc nào
 *  sinh ra ký tự nào; lệch độ dài (chữ lạ) thì null và chỗ gọi tô cả đoạn trích. */
export function originalSpan(text: string, foldedHaystack: string, at: number, length: number): [number, number] | null {
  const starts: number[] = [];
  let built = "";
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const folded = foldChar(char);
    for (let k = 0; k < folded.length; k += 1) starts.push(i);
    built += folded;
  }
  if (built.length !== foldedHaystack.length) return null;
  if (at < 0 || at + length > starts.length || length <= 0) return null;
  const end = starts[at + length - 1] + 1;
  // Dấu rời đứng ngay sau chữ cái cuối vẫn thuộc về chữ ấy.
  let stop = end;
  while (stop < text.length && foldChar(text[stop]) === "") stop += 1;
  return [starts[at], stop];
}

/** Đoạn trích của kết quả: chữ trước / chỗ khớp / chữ sau. */
export interface Snippet {
  before: string;
  match: string;
  after: string;
}

const BEFORE = 40;
const AFTER = 70;

/** Cắt về ranh giới chữ (khoảng trắng) gần nhất để không bắt đầu / kết thúc giữa một chữ. */
function trimLeft(text: string): string {
  const space = text.search(/\s/);
  return space >= 0 && space < 12 ? text.slice(space + 1) : text;
}

function trimRight(text: string): string {
  const space = text.search(/\s\S*$/);
  return space >= text.length - 12 && space > 0 ? text.slice(0, space) : text;
}

/** Đoạn trích quanh `span` của `text`; "…" ở đầu / cuối khi đã cắt. `span` null (không dò được chỗ khớp) thì lấy đầu đoạn, không tô. */
export function snippetOf(text: string, span: [number, number] | null): Snippet {
  const flat = (value: string) => value.replace(/\s+/g, " ");
  if (!span) {
    const head = flat(text).trim();
    return { before: "", match: "", after: head.length > BEFORE + AFTER ? `${trimRight(head.slice(0, BEFORE + AFTER))}…` : head };
  }
  const [start, end] = span;
  let before = flat(text.slice(Math.max(0, start - BEFORE), start));
  let after = flat(text.slice(end, end + AFTER));
  if (start > BEFORE) before = `…${trimLeft(before)}`;
  if (end + AFTER < text.length) after = `${trimRight(after)}…`;
  return { before, match: flat(text.slice(start, end)), after };
}

/** Một kết quả: chương và câu (`?at=` của màn đọc) kèm đoạn trích. */
export interface FindHit {
  chapterId: number;
  /** Thứ tự câu trong kịch bản của chương (script.segments). */
  sentence: number;
  snippet: Snippet;
}

/** Kết quả đầu tiên của từ khoá trong từng đoạn của `segments`; `folded` đã qua [foldedQuery]. `foldedSegments` (nếu có) là chữ đã chuẩn hoá của từng đoạn,
 *  để tìm lại nhiều lần không phải chuẩn hoá lại. Dòng ngăn cảnh ("***") không tính. */
export function findInSegments(
  chapterId: number,
  segments: readonly { text: string; sceneBreak?: boolean }[],
  folded: string,
  foldedSegments?: readonly string[],
): FindHit[] {
  const hits: FindHit[] = [];
  segments.forEach((segment, sentence) => {
    if (segment.sceneBreak) return;
    const haystack = foldedSegments?.[sentence] ?? foldedText(segment.text);
    const at = haystack.indexOf(folded);
    if (at < 0) return;
    hits.push({ chapterId, sentence, snippet: snippetOf(segment.text, originalSpan(segment.text, haystack, at, folded.length)) });
  });
  return hits;
}
