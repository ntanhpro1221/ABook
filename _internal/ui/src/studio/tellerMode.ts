import { S } from "../shared/strings.generated";
import { formatNumber } from "@/shared/format";
import { estimateText } from "./voiceTryText";

// Công tắc B "Ngôi tôi tự kể" (webui/teller_mode.py, abook/teller_voice.py): chữ và phép tính cái giá dùng chung cho
// trình tạo sách và trang dự án.

export interface TellerPlan {
  /** "on": bật sẽ đổi giọng những câu này; "off": tắt trả đúng những câu B đã chuyển. */
  direction: "on" | "off";
  /** Số câu đổi giọng, trong đó `recorded` câu đã thu nên phải thu lại. */
  lines: number;
  recorded: number;
  seconds: number;
  measured: boolean;
  tellers: string[];
}

export interface TellerModeView {
  available: boolean;
  mode: "narrator" | "teller";
  /** Đã phân vai: đổi là áp ngay. Chưa: chỉ ghi ý muốn, máy áp sau khi phân vai. */
  castLocked: boolean;
  applied: boolean;
  plan: TellerPlan | null;
  /** `false` ở điện thoại mở file dự án: chỉ xem được, đổi ở máy tính có Studio (cần thu lại). */
  editableHere?: boolean;
}

// "Ngôi tôi" là thuật ngữ - soát 24-10 T18: khó hiểu. Nói việc nghe thấy: nhân vật xưng "tôi" tự đọc lời kể của mình.
export const TELLER_TITLE = S.s_nhan_vat_tu_ke_b75121e9;

/** Câu thay cho nút đổi ở nơi không đổi được (điện thoại mở file dự án). */
export const TELLER_ELSEWHERE = S.s_doi_o_may_tinh_co_studio_can_thu_lai_d1f81a52;

export function tellerHint(on: boolean): string {
  return on
    ? S.s_nhan_vat_xung_toi_doc_ca_loi_ke_bang_giong_b51f6c3e
    : S.s_giong_dan_doc_loi_ke_nhan_vat_chi_doc_loi_51b22986;
}

/** Có cần hỏi lại trước khi đổi không: chỉ khi đã có câu thu sẽ bị bỏ. */
export function needsConfirm(view: TellerModeView | undefined): boolean {
  return Boolean(view?.castLocked && view.plan && view.plan.recorded > 0);
}

/** Cái giá của lần đổi, nói như người nghe thấy: bao nhiêu câu phải thu lại, mất khoảng bao lâu. */
export function costText(plan: TellerPlan | null | undefined, turningOn: boolean): string {
  if (!plan || !plan.lines) return turningOn ? S.s_chua_co_cau_loi_ke_nao_can_doi_giong_1713d093 : S.s_khong_con_cau_nao_de_tra_lai_giong_dan_b32638ee;
  const who = plan.tellers.length ? plan.tellers.join(", ") : S.s_nguoi_ke_50063a62;
  const what = turningOn
    ? S.s_0_cau_loi_ke_se_doc_bang_giong_cua_1_8b27b9f7(formatNumber(plan.lines), who)
    : S.s_0_cau_loi_ke_se_tro_ve_giong_dan_120544ea(formatNumber(plan.lines));
  if (!plan.recorded) return S.s_0_chua_cau_nao_trong_so_do_duoc_thu_nen_kh_e578daec(what);
  // Bản thu hiện có của những câu ấy bị bỏ, không lấy lại được: nói số ấy ra, ở cả hai chiều.
  return S.s_0_1_ban_thu_hien_co_cua_nhung_cau_ay_se_bi_bea67ccb(what, formatNumber(plan.recorded), estimateText(plan.seconds, plan.measured));
}
