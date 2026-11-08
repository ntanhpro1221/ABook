import { S } from "../shared/strings.generated";
// Soát số chương ở bước 1 của trình tạo sách (soát UX a6 01-10, B4): tải truyện về hay gặp chương trùng (hai file cùng
// "Chương 12"), thiếu chương (14 rồi 18), xếp lùi (chương 9 sau chương 10), và phần nối tiếp không bắt đầu đúng chương kế
// của phần trước. Máy chỉ NÓI ra - người dùng tự quyết bỏ / thêm file (không bao giờ tự sửa nguồn).

const NUMBER = /(?:chương|chuong|hồi|hoi|chapter|tiết|第)\s*0*(\d{1,5})/i;
const BARE = /^0*(\d{1,5})(?!\d)/;

/** Số chương đọc từ dòng đầu, rồi tên file ("0012 Chương 12.txt", "012.txt"); không có thì null. */
export function chapterNumber(firstLine: string, name: string): number | null {
  const found = NUMBER.exec(firstLine) ?? NUMBER.exec(name) ?? BARE.exec(name);
  return found ? Number(found[1]) : null;
}

export interface NumberedFile {
  name: string;
  firstLine: string;
}

export function chapterNumberIssues(files: NumberedFile[], previousLast?: string): string[] {
  const numbered = files.map((file) => ({ name: file.name, number: chapterNumber(file.firstLine, file.name) }));
  const known = numbered.filter((file): file is { name: string; number: number } => file.number !== null);
  // Ít hơn một nửa số file có số chương: truyện không đánh số (EPUB theo tên chương) - không đoán.
  if (known.length < 2 || known.length * 2 < files.length) return [];
  const issues: string[] = [];
  const seen = new Map<number, string[]>();
  for (const file of known) seen.set(file.number, [...(seen.get(file.number) ?? []), file.name]);
  const duplicates = [...seen.entries()].filter(([, names]) => names.length > 1);
  for (const [number, names] of duplicates.slice(0, 3)) {
    issues.push(S.s_chuong_0_co_1_file_2_giu_mot_bo_cac_file_k_6dc27bbf(number, names.length, names.slice(0, 3).join(", ")));
  }
  if (duplicates.length > 3) issues.push(S.s_va_0_so_chuong_trung_khac_9560b0ea(duplicates.length - 3));
  const backwards: string[] = [];
  const gaps: string[] = [];
  for (let index = 1; index < known.length; index += 1) {
    const before = known[index - 1].number;
    const here = known[index].number;
    if (here < before) backwards.push(S.s_chuong_0_dung_sau_chuong_1_b38683fa(here, before));
    else if (here > before + 1) gaps.push(here === before + 2 ? S.s_chuong_0_55d256d1(before + 1) : S.s_chuong_0_1_31557138(before + 1, here - 1));
  }
  if (backwards.length) {
    issues.push(S.s_thu_tu_lech_0_1_ten_file_xep_khac_so_chuon_bc17e3d9(backwards.slice(0, 3).join("; "), backwards.length > 3 ? S.s_va_0_cho_khac_ea74c5e3(backwards.length - 3) : ""));
  }
  if (gaps.length) {
    issues.push(S.s_co_ve_thieu_0_1_3cfd1c2f(gaps.slice(0, 4).join(", "), gaps.length > 4 ? S.s_va_0_khoang_khac_fb999086(gaps.length - 4) : ""));
  }
  const last = previousLast ? chapterNumber(previousLast, previousLast) : null;
  const first = known[0].number;
  if (last !== null && first !== last + 1) {
    issues.push(
      first <= last
        ? S.s_phan_truoc_da_lam_toi_chuong_0_phan_nay_la_cdcc433a(last, first)
        : S.s_phan_truoc_dung_o_chuong_0_phan_nay_bat_da_43a5f44b(last, first, last + 1, first > last + 2 ? `–${first - 1}` : ""),
    );
  }
  return issues;
}
