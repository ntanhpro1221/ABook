import { S } from "./strings.generated";
import { formatWhen } from "./format";

// Phần sửa của cuốn tải từ máy tính được gửi về máy tính (docs/EDITING.md, P2b; EditsSync.kt trên điện thoại, webui/edits_inbox.py
// trên máy tính). Giao diện chỉ nói tình trạng bằng lời người nghe nhận ra: chưa gửi, đã gửi, máy tính đã làm gì với nó.

/** Kết quả lần gửi gần nhất (EditsSync.kt). `error` có khi `state` là "error". */
export interface EditsSyncLast {
  state: "sent" | "error";
  at: number;
  error?: string;
  /** Sửa "áp ngay" máy tính đã áp. */
  applied?: number;
  /** Sửa không còn chỗ trên máy tính (nhân vật / chương đã không còn...) - bị bỏ qua. */
  skipped?: number;
  /** Ý muốn chờ Studio đã thành yêu cầu thật (thiết bị được điều khiển sản xuất từ xa). */
  requests?: number;
  /** Ý muốn đang nằm trong hộp thư chờ duyệt trên máy tính. */
  waiting?: number;
  /** Ý muốn máy tính đã nhận thẳng vào sách (cuốn nhập từ file, không có hộp duyệt) - chỉ còn chờ Studio thu lại giọng. */
  studio?: number;
  skippedWishes?: number;
  /** Khoá chủ máy đã đổi từ lần trước: bản gửi từ điện thoại vẫn thắng, nhưng người dùng được báo. */
  conflicts?: string[];
}

export interface EditsSyncState {
  /** Số thay đổi CHƯA gửi (gửi xong là gỡ khỏi lớp sửa của điện thoại). */
  pending: number;
  last: EditsSyncLast | null;
}

export type EditsSyncTone = "pending" | "error" | "sent";

export interface EditsSyncNote {
  tone: EditsSyncTone;
  title: string;
  /** Từng điều máy tính đã làm / còn chờ - mỗi điều một dòng. */
  lines: string[];
}

/** Tên máy giữ sách để nói trong lời báo: máy tính khác thì tên thật của nó (hai máy đều là máy tính, "máy tính" không nói máy nào), không thì "máy tính". */
export function holderName(remote: boolean | { computer: string } | undefined): string {
  return remote && typeof remote === "object" && remote.computer ? remote.computer : S.s_may_tinh_8eafc226;
}

/** Điều đáng nói về một cuốn tải từ máy tính: chưa gửi (kèm lý do nếu lần gửi trước hỏng), hay đã gửi và máy tính đã làm gì.
 *  `where`: tên máy giữ sách (`holderName`). `null` khi chưa có gì để nói (chưa sửa gì, chưa gửi bao giờ). */
export function editsSyncNote(state: EditsSyncState | null | undefined, where: string = S.s_may_tinh_8eafc226): EditsSyncNote | null {
  if (!state) return null;
  const { pending, last } = state;
  if (pending > 0) {
    if (last?.state === "error") {
      return { tone: "error", title: S.s_0_thay_doi_chua_gui_ve_1_ad25f59b(pending, where), lines: [last.error ?? S.s_chua_gui_duoc_se_thu_lai_b33d9601] };
    }
    return {
      tone: "pending",
      title: S.s_0_thay_doi_dang_cho_gui_ve_1_af5aef9d(pending, where),
      lines: [S.s_tu_gui_khi_toi_duoc_0_bam_gui_ve_1_de_gui_68533698(where, where)],
    };
  }
  if (last?.state !== "sent") return null;
  const lines: string[] = [];
  if (last.applied) lines.push(S.s_0_thay_doi_da_ap_ngay_tren_1_0baf0321(last.applied, where));
  if (last.studio) lines.push(S.s_0_viec_can_thu_lai_giong_da_ghi_tren_1_stu_3eb16c54(last.studio, where, where));
  if (last.requests) lines.push(S.s_0_viec_da_thanh_yeu_cau_tren_1_cho_ap_dung_8d86b57b(last.requests, where));
  if (last.waiting) lines.push(S.s_0_viec_dang_cho_duyet_tren_1_chua_lam_gi_c_71360040(last.waiting, where, where));
  const skipped = (last.skipped ?? 0) + (last.skippedWishes ?? 0);
  if (skipped) lines.push(S.s_0_thay_doi_khong_con_cho_trong_sach_tren_1_88b8a366(skipped, where));
  lines.push(...(last.conflicts ?? []));
  return { tone: "sent", title: S.s_da_gui_ve_0_1_f817fbb4(where, formatWhen(last.at)).trim(), lines };
}

/** Thông báo ngay sau khi bấm Gửi: MỘT dòng - "Đã gửi về X"; chi tiết đã áp / đang chờ nằm ở dòng tình trạng của sách (`editsSyncNote`). Còn thay đổi chưa gửi được
 *  thì `note` nói điều ấy (cảnh báo cùng dòng). */
export function sentToast(state: EditsSyncState, where: string = S.s_may_tinh_8eafc226): { title: string; note?: string } {
  return {
    title: S.s_da_gui_ve_0_c5d9f5e1(where),
    note: state.pending > 0 ? S.s_con_0_thay_doi_chua_gui_duoc_se_thu_lai_kh_a2ab7e32(state.pending, where) : undefined,
  };
}
