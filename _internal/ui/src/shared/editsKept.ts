/** Nhập lại một cuốn đã có thay đổi của người nghe (tên, bìa, tên nhân vật/chương, nhạc): thay đổi ấy được giữ nguyên - nói
 *  cho người dùng biết. `null` khi máy này chưa có thay đổi nào (không có gì để nói). Dùng chung cho Android (imports.ts) và
 *  máy tính (desktop/App.tsx). */
export function keptEditsTitle(kept: number | null | undefined): string | null {
  return kept && kept > 0 ? `Đã cập nhật sách - giữ nguyên ${kept} chỉnh sửa của bạn` : null;
}
