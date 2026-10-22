/** Offset đếm code point. FNV-1a 64 của các đoạn UTF-8 nối bằng LF, cùng ReadingAnchor.kt. */
export interface ReadingAnchor {
  segment: number;
  charOffset: number;
  /** Băm cả chương. */
  textHash: string;
  /** Băm riêng đoạn đang nghe: sửa chữ ở đoạn khác (băm chương lệch) mà đoạn này còn nguyên thì vẫn khôi phục đúng đoạn + chữ. */
  paragraphHash?: string;
}

const HASH = /^fnv1a64:[0-9a-f]{16}$/;

/** Vị trí chữ của máy phát, hay undefined nếu không lấy được: lỗi khi dựng mốc không được làm mất lưu tiến độ / chặn đóng sách (soát a79 lỗi 4). */
export function anchorOf(engine: { readonly readingAnchor?: ReadingAnchor }): ReadingAnchor | undefined {
  try {
    return engine.readingAnchor;
  } catch {
    return undefined;
  }
}

export function textFingerprint(paragraphs: string[]): string {
  let hash = 0xcbf29ce484222325n;
  for (const byte of new TextEncoder().encode(paragraphs.join("\n"))) hash = BigInt.asUintN(64, (hash ^ BigInt(byte)) * 0x100000001b3n);
  return `fnv1a64:${hash.toString(16).padStart(16, "0")}`;
}

export function makeAnchor(paragraphs: string[], segment: number, word: number, textHash = textFingerprint(paragraphs)): ReadingAnchor | undefined {
  const text = paragraphs[segment];
  if (text === undefined) return undefined;
  const tokens = [...text.matchAll(/\S+/gu)];
  const start = tokens[Math.max(0, Math.min(tokens.length - 1, word))]?.index ?? 0;
  return { segment, charOffset: [...text.slice(0, start)].length, textHash, paragraphHash: textFingerprint([text]) };
}

/** Đoạn của chương hiện tại mà anchor trỏ tới khi băm chương đã lệch: đoạn cũ nếu còn nguyên, không thì đoạn gần nó nhất có đúng băm đoạn. */
function movedSegment(paragraphs: string[], anchor: ReadingAnchor): number | undefined {
  const wanted = anchor.paragraphHash;
  if (typeof wanted !== "string" || !HASH.test(wanted)) return undefined;
  const same = (index: number) => paragraphs[index] !== undefined && textFingerprint([paragraphs[index]]) === wanted;
  if (same(anchor.segment)) return anchor.segment;
  let best: number | undefined;
  for (let index = 0; index < paragraphs.length; index += 1) {
    if (best !== undefined && Math.abs(index - anchor.segment) >= Math.abs(best - anchor.segment)) continue;
    if (same(index)) best = index;
  }
  return best;
}

export function restoreAnchor(paragraphs: string[], anchor: ReadingAnchor | undefined, textHash = textFingerprint(paragraphs)): { segment: number; word: number } | undefined {
  if (!anchor || !Number.isInteger(anchor.segment) || !Number.isInteger(anchor.charOffset) || anchor.segment < 0 || anchor.charOffset < 0 ||
      anchor.segment > 2147483647 || anchor.charOffset > 2147483647) return undefined;
  const segment = anchor.textHash === textHash ? anchor.segment : movedSegment(paragraphs, anchor);
  if (segment === undefined) return undefined;
  const text = paragraphs[segment];
  if (text === undefined || anchor.charOffset > [...text].length) return undefined;
  const tokens = [...text.matchAll(/\S+/gu)];
  const word = tokens.findIndex((token) => [...text.slice(0, token.index + token[0].length)].length > anchor.charOffset);
  return { segment, word: word >= 0 ? word : Math.max(0, tokens.length - 1) };
}
