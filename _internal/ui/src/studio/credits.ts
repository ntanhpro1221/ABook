import { S } from "../shared/strings.generated";
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
    ...tails.map((line) => S.s_0_cuoi_chuong_eb53af5d(line)),
  ].slice(0, 3);
  return { lines: head + tail, head, tail, chapters, examples };
}

/** Gọi tên các dòng theo loại có trong sách: "dòng ghi công", "dòng xin ủng hộ, quảng cáo" hay cả hai. */
export function creditKind(credits: Credits): string {
  if (!credits.tail) return S.s_dong_ghi_cong_acaae945;
  if (!credits.head) return S.s_dong_xin_ung_ho_quang_cao_a4165e32;
  return S.s_dong_ghi_cong_xin_ung_ho_quang_cao_ffb87b29;
}

/** Chúng nằm ở đâu trong chương. */
export function creditWhere(credits: Credits): string {
  if (!credits.tail) return S.s_dong_ghi_cong_nguoi_dich_o_dau_chuong_c94cc054;
  if (!credits.head) return S.s_dong_xin_ung_ho_quang_cao_hay_nguon_o_cuoi_e826e333;
  return S.s_dong_ghi_cong_o_dau_chuong_hay_dong_xin_un_a0d7e71e;
}

/** Người dùng đồng ý bỏ dòng nào: đầu chương (`dropCreditLines`) và cuối chương (`dropTailCreditLines`) chọn riêng (soát UX a24, A9). */
export interface CreditDrop {
  head: boolean;
  tail: boolean;
}

export const KEEP_CREDITS: CreditDrop = { head: false, tail: false };

/** Số dòng sẽ bỏ theo lựa chọn - chỉ loại có trong sách. */
export function droppedLines(credits: Credits, drop: CreditDrop): number {
  return (drop.head ? credits.head : 0) + (drop.tail ? credits.tail : 0);
}

/** Mọi dòng gợi ý, theo chương - "Xem hết N dòng" trước khi bỏ. `label`: tên chương như danh sách chương hiện. */
export function creditRows<F extends { credits?: string[]; tailCredits?: string[] }>(
  files: F[],
  label: (file: F) => string,
): { chapter: string; head: string[]; tail: string[] }[] {
  return files
    .filter((file) => (file.credits?.length ?? 0) + (file.tailCredits?.length ?? 0) > 0)
    .map((file) => ({ chapter: label(file), head: file.credits ?? [], tail: file.tailCredits ?? [] }));
}

/** Một dòng trong danh sách "Xem hết": ở đâu trong chương, và - khi người dùng đã chọn bỏ một loại - dòng này bị bỏ hay vẫn được
 *  đọc (soát UX a25 T8: dưới "Sẽ bỏ 5 dòng" danh sách vẫn kể dòng đầu chương sẽ GIỮ như thể cũng bị bỏ). */
export function creditLine(line: string, place: "head" | "tail", drop: CreditDrop): { text: string; dropped: boolean } {
  const where = place === "head" ? S.s_dau_chuong_ef996d71 : S.s_cuoi_chuong_f95a0fda;
  if (!drop.head && !drop.tail) return { text: `“${line}” (${where})`, dropped: false };
  return drop[place] ? { text: S.s_0_1_bo_f774b2ee(line, where), dropped: true } : { text: S.s_0_1_van_doc_78cac460(line, where), dropped: false };
}
