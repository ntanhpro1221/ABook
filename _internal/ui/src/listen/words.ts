// Mốc từng CHỮ của một câu (`words` trong scripts/<n>.json, abook/webui/word_timing.py; docs/ABOOK_FILE_FORMAT.md): mỗi chữ hiện - đơn vị
// cách nhau bằng khoảng trắng - một cặp [bắt đầu_ms, kết thúc_ms] tính từ đầu MP3 chương, cùng đồng hồ với `start`/`end` của câu.
// Thiếu `words`, hay số cặp không bằng số chữ (sách cũ, chữ bị sửa sau khi căn): bỏ qua, chỉ sáng cả câu như trước.

export type WordSpan = [number, number];

/** Một mảnh của câu: một chữ hiện (`word` = thứ tự chữ) hay khoảng trắng giữa các chữ (`word` = -1). Ghép các mảnh lại ra đúng chữ của câu. */
export interface Piece {
  text: string;
  word: number;
}

const TOKEN = /\S+/g;

/** Số chữ hiện của một câu (= `tokens()` của word_timing.py). */
export function countTokens(text: string): number {
  return (text.match(TOKEN) ?? []).length;
}

/** Tách câu thành chữ và khoảng trắng, giữ nguyên từng ký tự - render lại không đổi cách câu xuống dòng. */
export function splitPieces(text: string): Piece[] {
  const pieces: Piece[] = [];
  let position = 0;
  let word = 0;
  for (const match of text.matchAll(TOKEN)) {
    const at = match.index ?? 0;
    if (at > position) pieces.push({ text: text.slice(position, at), word: -1 });
    pieces.push({ text: match[0], word: word++ });
    position = at + match[0].length;
  }
  if (position < text.length) pieces.push({ text: text.slice(position), word: -1 });
  return pieces;
}

/** `words` của câu nếu dùng được (đúng hình, tăng dần, đúng số chữ hiện), không thì null. */
export function usableWords(text: string, words: unknown): WordSpan[] | null {
  if (!Array.isArray(words) || words.length === 0 || words.length !== countTokens(text)) return null;
  let last = 0;
  for (const span of words) {
    if (!Array.isArray(span) || span.length !== 2) return null;
    const [start, end] = span;
    if (typeof start !== "number" || typeof end !== "number" || !Number.isFinite(start) || !Number.isFinite(end) || start < last || end < start) return null;
    last = start;
  }
  return words as WordSpan[];
}

/** Sáng sớm một chút (ms): mắt thấy chữ sáng trễ rõ hơn sáng sớm; cùng ý với 0,05 giây của `sentenceIndexAt`. */
export const WORD_LEAD_MS = 40;
/** Chữ cuối của câu tắt sau chừng này (ms) kể từ lúc nó kết thúc, nếu câu kế chưa bắt đầu. */
export const LAST_WORD_HOLD_MS = 400;

/** Chữ đang đọc ở `ms` (từ đầu chương): chữ cuối cùng đã bắt đầu (tìm nhị phân); -1 khi chưa tới chữ đầu hay chữ cuối đã qua lâu. Một chữ kết thúc
 *  đúng chỗ chữ sau bắt đầu nên khoảng ngắt giữa câu vẫn sáng chữ trước. */
export function wordIndexAt(words: readonly WordSpan[], ms: number): number {
  const at = ms + WORD_LEAD_MS;
  let low = 0;
  let high = words.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (words[middle][0] <= at) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  if (found === words.length - 1 && ms > words[found][1] + LAST_WORD_HOLD_MS) return -1;
  return found;
}
