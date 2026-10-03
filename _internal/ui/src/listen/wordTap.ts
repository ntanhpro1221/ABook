import { splitPieces } from "./words";

// Bấm vào một chữ ở màn đọc (như Đọc to của Edge): từ chỗ chạm biết chữ thứ mấy của câu để nghe từ đúng chữ ấy.

/** Chữ (đơn vị `\S+`, như words.ts) chứa ký tự thứ `offset` của câu; rơi vào khoảng trắng thì chữ liền sau (chữ cuối nếu không còn); câu không có chữ: -1. */
export function wordAtOffset(text: string, offset: number): number {
  let position = 0;
  let last = -1;
  for (const piece of splitPieces(text)) {
    const end = position + piece.text.length;
    if (piece.word >= 0) {
      last = piece.word;
      if (offset < end) return piece.word;
    }
    position = end;
  }
  return last;
}

type CaretDocument = Document & {
  caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
  caretRangeFromPoint?: (x: number, y: number) => Range | null;
};

/** Ký tự thứ mấy của `element` (một câu) nằm dưới điểm chạm (x, y), hay null nếu trình duyệt không chỉ được / chạm ngoài câu. */
export function offsetAtPoint(element: HTMLElement, x: number, y: number): number | null {
  const doc = element.ownerDocument as CaretDocument;
  let node: Node | null = null;
  let offset = 0;
  const position = doc.caretPositionFromPoint?.(x, y);
  if (position) {
    node = position.offsetNode;
    offset = position.offset;
  } else {
    const range = doc.caretRangeFromPoint?.(x, y);
    if (range) {
      node = range.startContainer;
      offset = range.startOffset;
    }
  }
  if (!node || !element.contains(node)) return null;
  const range = doc.createRange();
  range.setStart(element, 0);
  range.setEnd(node, offset);
  return range.toString().length;
}

/** Chữ nằm dưới chỗ chạm trong câu `element` có chữ `text`; -1 khi không biết (rồi nghe từ đầu câu). */
export function wordAtPoint(element: HTMLElement, text: string, x: number, y: number): number {
  const offset = offsetAtPoint(element, x, y);
  return offset === null ? -1 : wordAtOffset(text, offset);
}
