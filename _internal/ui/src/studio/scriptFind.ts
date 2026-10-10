// Ô tìm chữ của tab Kịch bản: gõ "tuan" thấy "Tuấn", "dac lat" thấy "Đác-lát" (cùng cách bỏ dấu với ô tìm người), nhưng trả về VỊ TRÍ trong
// chữ gốc để tô đúng chỗ khớp (bỏ dấu cả chuỗi đổi độ dài, nên bỏ từng ký tự một và nhớ ký tự gốc của nó).

function foldChar(character: string): string {
  return character.normalize("NFD").replace(/\p{M}/gu, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}

/** Chuỗi đã bỏ dấu + hạ chữ, kèm vị trí ký tự gốc của từng ký tự. */
function folded(text: string): { text: string; origin: number[] } {
  let out = "";
  const origin: number[] = [];
  let index = 0;
  for (const character of text) {
    const piece = foldChar(character);
    for (const _ of piece) origin.push(index);
    out += piece;
    index += character.length;
  }
  return { text: out, origin };
}

/** Mọi chỗ `query` xuất hiện trong `text` (không phân biệt hoa thường và dấu), dạng [đầu, cuối) theo chữ gốc. Rỗng nếu `query` rỗng. */
export function findRanges(text: string, query: string): [number, number][] {
  const needle = folded(query.trim()).text;
  if (!needle) return [];
  const hay = folded(text);
  const ranges: [number, number][] = [];
  for (let at = hay.text.indexOf(needle); at >= 0; at = hay.text.indexOf(needle, at + needle.length)) {
    const start = hay.origin[at];
    const last = hay.origin[at + needle.length - 1];
    let end = last + 1;
    // Dấu rời (chữ NFD) đi sau ký tự cuối thuộc về nó.
    while (end < text.length && /\p{M}/u.test(text[end])) end += 1;
    ranges.push([start, end]);
  }
  return ranges;
}

/** Cắt `text` thành các đoạn theo `ranges` (đã sắp, không chồng): [chữ, có tô không]. */
export function splitByRanges(text: string, ranges: [number, number][]): [string, boolean][] {
  const parts: [string, boolean][] = [];
  let at = 0;
  for (const [start, end] of ranges) {
    if (start > at) parts.push([text.slice(at, start), false]);
    parts.push([text.slice(start, end), true]);
    at = end;
  }
  if (at < text.length) parts.push([text.slice(at), false]);
  return parts;
}

/** Chuyển vòng: mũi tên / Enter qua hết câu khớp cuối thì về câu đầu (và ngược lại). */
export function wrapIndex(at: number, count: number): number {
  return count ? ((at % count) + count) % count : 0;
}
