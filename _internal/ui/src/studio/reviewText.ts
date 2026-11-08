import { S } from "../shared/strings.generated";
// Chữ của tab "Cần nghe lại" (soát UX a8 07-10), tách ra để kiểm bằng test.

/** "máy nghe khớp 15%" không nói khớp với cái gì - đây là độ khớp giữa điều máy nghe lại được và CHỮ CỦA CÂU. */
/** Cuốn chưa thu câu nào: "không còn câu nào cần xem" là nói dối (chưa có câu nào để kiểm), phải nói là sẽ có sau khi thu âm. */
export function notRecordedYet(segments: { recorded: number } | null | undefined): boolean {
  return Boolean(segments) && segments!.recorded === 0;
}

export function matchPhrase(percent: string): string {
  return S.s_may_nghe_lai_khop_0_voi_chu_cua_cau_59610ae2(percent);
}

/** Bản ngắn của matchPhrase cho dòng "Máy nghe ra": đứng ngay cạnh điều máy nghe được nên không cần nói lại "với chữ của câu" (đó là tooltip). */
export function matchShort(percent: string): string {
  return S.s_khop_0_b5c9f23d(percent);
}

/** Chữ của nút / ô sửa cách máy đọc một câu (không đụng chữ của sách) - "chữ đem đọc" là tiếng của người làm máy. */
export function spokenEditLabel(twins: number): string {
  return twins > 0 ? S.s_sua_0_cau_8fa47e43(twins + 1) : S.s_sua_cach_doc_d67b7a7b;
}

/** Dòng phím tắt chỉ có nghĩa khi đang nghe liền: ngoài lúc ấy O / R không làm gì nên không hiện. */
export function shortcutHint(continuous: boolean): string | null {
  return continuous ? S.s_dang_nghe_lien_bam_o_neu_on_r_neu_can_thu_4e3d0d8d : null;
}
