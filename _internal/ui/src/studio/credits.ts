// Dòng ghi công người dịch ở ĐẦU chương và dòng xin ủng hộ / quảng cáo / nguồn ở CUỐI chương mà trình tạo sách ĐỀ XUẤT bỏ
// khỏi phần đọc (webui/actions.scan_inputs: `credits`, `tailCredits` - luật chung với sách nhập, text_processing). Một lần đồng
// ý bỏ cả hai loại; sách lưu hai khoá riêng (`dropCreditLines`, `dropTailCreditLines`) để sách tạo trước vẫn tách như cũ.

export interface Credits {
  /** Số dòng sẽ bỏ nếu đồng ý (đầu + cuối chương). */
  lines: number;
  head: number;
  tail: number;
  /** Số chương có ít nhất một dòng như thế. */
  chapters: number;
  /** Tối đa ba dòng mẫu trong ngoặc kép; dòng cuối chương ghi thêm "(cuối chương)". */
  examples: string[];
}

/** Đếm trên các chương ĐANG CHỌN (bỏ chương hay giới hạn số chương thì đếm lại). */
export function creditSummary(files: { credits?: string[]; tailCredits?: string[] }[]): Credits {
  const heads: string[] = [];
  const tails: string[] = [];
  let head = 0;
  let tail = 0;
  let chapters = 0;
  for (const file of files) {
    const top = file.credits ?? [];
    const end = file.tailCredits ?? [];
    if (!top.length && !end.length) continue;
    head += top.length;
    tail += end.length;
    chapters += 1;
    for (const line of top) if (heads.length < 3 && !heads.includes(line)) heads.push(line);
    for (const line of end) if (tails.length < 3 && !tails.includes(line)) tails.push(line);
  }
  const examples = [
    ...heads.slice(0, tails.length ? 2 : 3).map((line) => `“${line}”`),
    ...tails.map((line) => `“${line}” (cuối chương)`),
  ].slice(0, 3);
  return { lines: head + tail, head, tail, chapters, examples };
}

/** Gọi tên các dòng theo loại có trong sách: "dòng ghi công", "dòng xin ủng hộ, quảng cáo" hay cả hai. */
export function creditKind(credits: Credits): string {
  if (!credits.tail) return "dòng ghi công";
  if (!credits.head) return "dòng xin ủng hộ, quảng cáo";
  return "dòng ghi công, xin ủng hộ, quảng cáo";
}

/** Chúng nằm ở đâu trong chương. */
export function creditWhere(credits: Credits): string {
  if (!credits.tail) return "dòng ghi công người dịch ở đầu chương";
  if (!credits.head) return "dòng xin ủng hộ, quảng cáo hay nguồn ở cuối chương";
  return "dòng ghi công ở đầu chương hay dòng xin ủng hộ, quảng cáo ở cuối chương";
}
