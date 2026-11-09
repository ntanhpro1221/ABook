import { S } from "./strings.generated";
/** Nhập lại một cuốn đã có thay đổi của người nghe (tên, bìa, tên nhân vật/chương, nhạc): thay đổi ấy được giữ nguyên - nói
 *  cho người dùng biết. `null` khi máy này chưa có thay đổi nào (không có gì để nói). Dùng chung cho Android (imports.ts) và
 *  máy tính (desktop/App.tsx). */
export function keptEditsTitle(kept: number | null | undefined): string | null {
  return kept && kept > 0 ? S.s_da_cap_nhat_sach_giu_nguyen_0_chinh_sua_cu_67ec8f98(kept) : null;
}

/** Mở file dự án của CÙNG dự án đã có ở máy này: sửa trong xưởng của file (cách đọc, ai nói câu nào, giọng, thu lại, phán quyết
 *  "Cần nghe lại") được gộp - bản mới hơn thắng (soát UX a25 T5). Nói đã gộp gì; `null` khi không có gì khác nhau. */
export function workshopMergeNote(merge: { merged: number; kept: number } | null | undefined): string | null {
  if (!merge || (!merge.merged && !merge.kept)) return null;
  const taken = merge.merged ? S.s_da_gop_0_sua_tu_file_41e5b5e2(merge.merged) : "";
  const kept = merge.kept ? S.s_0_sua_giu_ban_cua_may_nay_vi_moi_hon_bb407d4b(merge.kept) : "";
  return `${[taken, kept].filter(Boolean).join(", ")}.`;
}

/** File sách mang bài nhạc nền hỏng (chép dở, bị đổi byte): sách vẫn mở, bài ấy bị bỏ - nói MỘT câu (soát a26 L4). `null` khi không
 *  có bài nào hỏng. Dùng chung cho máy tính (desktop/App.tsx) và Android (imports.ts - BookFileImport.Imported.brokenMusic). */
export function brokenMusicNote(broken: number | null | undefined): string | null {
  if (!broken || broken <= 0) return null;
  return broken === 1
    ? S.s_1_bai_nhac_nen_trong_sach_bi_hong_doan_ay_0a679d5d
    : S.s_0_bai_nhac_nen_trong_sach_bi_hong_nhung_do_133fd5e7(broken);
}

/** Mở lại file cùng âm thanh với cuốn đã có nhưng mang TÊN khác: cuốn giữ tên cũ - nói tên trong file không được lấy (soát a81 lỗi 15).
 *  `null` khi tên như nhau. Dùng cho máy tính (desktop/App.tsx; `otherTitle` của `open_book_file`). */
export function otherTitleNote(title: string | null | undefined): string | null {
  return title ? S.s_ten_trong_file_la_0_khac_ten_dang_dung_f6042eec(title) : null;
}
