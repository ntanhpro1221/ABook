/** Nhập lại một cuốn đã có thay đổi của người nghe (tên, bìa, tên nhân vật/chương, nhạc): thay đổi ấy được giữ nguyên - nói
 *  cho người dùng biết. `null` khi máy này chưa có thay đổi nào (không có gì để nói). Dùng chung cho Android (imports.ts) và
 *  máy tính (desktop/App.tsx). */
export function keptEditsTitle(kept: number | null | undefined): string | null {
  return kept && kept > 0 ? `Đã cập nhật sách - giữ nguyên ${kept} chỉnh sửa của bạn` : null;
}

/** Mở file dự án của CÙNG dự án đã có ở máy này: sửa trong xưởng của file (cách đọc, ai nói câu nào, giọng, thu lại, phán quyết
 *  "Cần nghe lại") được gộp - bản mới hơn thắng (soát UX a25 T5). Nói đã gộp gì; `null` khi không có gì khác nhau. */
export function workshopMergeNote(merge: { merged: number; kept: number } | null | undefined): string | null {
  if (!merge || (!merge.merged && !merge.kept)) return null;
  const taken = merge.merged ? `Đã gộp ${merge.merged} sửa từ file` : "";
  const kept = merge.kept ? `${merge.kept} sửa giữ bản của máy này vì mới hơn` : "";
  return `${[taken, kept].filter(Boolean).join(", ")}.`;
}

/** File sách mang bài nhạc nền hỏng (chép dở, bị đổi byte): sách vẫn mở, bài ấy bị bỏ - nói MỘT câu (soát a26 L4). `null` khi không
 *  có bài nào hỏng. Dùng chung cho máy tính (desktop/App.tsx) và Android (imports.ts - BookFileImport.Imported.brokenMusic). */
export function brokenMusicNote(broken: number | null | undefined): string | null {
  if (!broken || broken <= 0) return null;
  return broken === 1
    ? "1 bài nhạc nền trong sách bị hỏng - đoạn ấy sẽ không có nhạc."
    : `${broken} bài nhạc nền trong sách bị hỏng - những đoạn ấy sẽ không có nhạc.`;
}
