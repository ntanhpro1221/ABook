/** Offset đếm code point. FNV-1a 64 của các đoạn UTF-8 nối bằng LF, cùng ReadingAnchor.kt. */
export interface ReadingAnchor {
  segment: number;
  charOffset: number;
  textHash: string;
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
  return { segment, charOffset: [...text.slice(0, start)].length, textHash };
}

export function restoreAnchor(paragraphs: string[], anchor: ReadingAnchor | undefined, textHash = textFingerprint(paragraphs)): { segment: number; word: number } | undefined {
  if (!anchor || !Number.isInteger(anchor.segment) || !Number.isInteger(anchor.charOffset) || anchor.segment < 0 || anchor.charOffset < 0 ||
      anchor.segment > 2147483647 || anchor.charOffset > 2147483647 || anchor.textHash !== textHash) return undefined;
  const text = paragraphs[anchor.segment];
  if (text === undefined || anchor.charOffset > [...text].length) return undefined;
  const tokens = [...text.matchAll(/\S+/gu)];
  const word = tokens.findIndex((token) => [...text.slice(0, token.index + token[0].length)].length > anchor.charOffset);
  return { segment: anchor.segment, word: word >= 0 ? word : Math.max(0, tokens.length - 1) };
}
