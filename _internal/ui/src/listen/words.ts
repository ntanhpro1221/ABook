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

/** Phần câu từ chữ thứ `word` (0-based, đếm theo `\S+` như [countTokens]) tới hết; null khi không có chữ ấy. Clip đuôi ([ReadAloudClip.fromWord]) đọc đúng phần này. */
export function tailFromWord(text: string, word: number): string | null {
  if (!Number.isInteger(word) || word < 0) return null;
  let seen = 0;
  for (const match of text.matchAll(TOKEN)) {
    if (seen === word) return text.slice(match.index ?? 0);
    seen += 1;
  }
  return null;
}

/** Mốc chữ của cả đoạn từ mốc của clip đuôi: chữ trước `from` chưa đọc nên mốc [0, 0], chữ `from` trở đi theo clip. Chưa có mốc nào thì để rỗng.
 *  Chữ `from` (chữ người nghe bấm) coi như bắt đầu ngay đầu clip dù clip mở đầu bằng quãng lặng (~0,14 giây): không thì trong quãng ấy "chữ cuối cùng đã bắt đầu" là chữ liền trước
 *  (mốc [0, 0]) và nó sáng lóe lên (a58). Cùng luật với điện thoại (SeekPlan.tailWords). */
export function absoluteWords(from: number, words: WordSpan[]): WordSpan[] {
  if (from <= 0 || words.length === 0) return words;
  const [start, end] = words[0];
  return [...Array.from({ length: from }, (): WordSpan => [0, 0]), start > 0 ? [0, end] : words[0], ...words.slice(1)];
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

/** Câu đang đọc ở giây `seconds` (tìm nhị phân trên mốc bắt đầu). */
export function sentenceIndexAt(starts: number[], seconds: number): number {
  let low = 0;
  let high = starts.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (starts[middle] <= seconds + 0.05) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found;
}

/** Sáng sớm một chút (ms): mắt thấy chữ sáng trễ rõ hơn sáng sớm; cùng ý với 0,05 giây của `sentenceIndexAt`. */
export const WORD_LEAD_MS = 40;
/** Chữ cuối của câu tắt sau chừng này (ms) kể từ lúc nó kết thúc, nếu câu kế chưa bắt đầu. */
export const LAST_WORD_HOLD_MS = 400;

/** Chữ đang đọc ở `ms` (từ đầu chương): chữ cuối cùng đã bắt đầu (tìm nhị phân); -1 khi chưa tới chữ đầu hay chữ cuối đã qua lâu. Một chữ kết thúc
 *  đúng chỗ chữ sau bắt đầu nên khoảng ngắt giữa câu vẫn sáng chữ trước. */
export function wordIndexAt(words: readonly WordSpan[], ms: number): number {
  if (words.length === 0) return -1; // đoạn chưa đọc: chưa có mốc chữ nào để sáng
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
