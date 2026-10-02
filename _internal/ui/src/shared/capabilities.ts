/** Máy này làm được gì với một cuốn sách (docs/EDITING.md) - giao diện chỉ hỏi qua đây, không tự suy ra từ nền tảng.
 *
 * - `toolchain`: Studio dùng được trên máy này (bản dev luôn có; app Windows đóng gói khi đã cài và không cũ; điện thoại không).
 * - `workshop`: cuốn có dự án sản xuất trên máy này (điện thoại không bao giờ có - nó không mở sổ dự án).
 * - `link`: cuốn nghe thẳng từ máy tính khác ("Trên máy khác") - chưa phải của máy này, sửa ở máy ấy.
 *
 * Máy tính trả ở `/api/app` và trên từng sách (`ListenBook.capabilities`); Android ở `EbookLibrary.capabilities` và trên từng
 * sách plugin trả về. */
export interface Capabilities {
  toolchain: boolean;
  workshop: boolean;
  link: boolean;
}

/** Sửa "áp ngay" (tên sách, bìa, tên nhân vật, tên chương, nhạc nền) không cần Studio: làm được trên mọi cuốn của máy này,
 *  có xưởng hay không. Cuốn nghe thẳng từ máy khác thì không. */
export function canEditLayer(caps: Capabilities | null | undefined): boolean {
  return Boolean(caps) && (caps!.workshop || !caps!.link);
}

/** Việc cần Studio (đổi giọng, sửa lời đọc, thu lại chương...): `null` khi làm được ngay (có Studio VÀ cuốn có xưởng), không thì
 *  câu nói thiếu gì - nút vẫn hiện, bấm không được, kèm câu này. Cuốn nghe thẳng từ máy khác: không có gì để nói ở đây. */
export function studioNeed(caps: Capabilities | null | undefined): string | null {
  if (!caps || caps.link) return null;
  if (caps.workshop && caps.toolchain) return null;
  if (!caps.toolchain) return "cần cài Studio";
  return "cần dựng xưởng cho cuốn này (sắp có)";
}

/** Việc cần Studio có nên hiện (bị mờ) không: mọi cuốn của máy này trừ cuốn đã làm được ngay. */
export function showsStudioOnly(caps: Capabilities | null | undefined): boolean {
  return studioNeed(caps) !== null;
}

/** Lý do không sửa được cuốn nghe thẳng từ máy khác - cùng câu với 409 của LocalStudio.kt (Android) và của máy tính. */
export const LINK_BOOK = "Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy";

/** Sửa "áp ngay" bị chặn vì cuốn nghe thẳng từ máy khác: câu nói lý do, không thì `null` (sửa được, hay không có gì để nói).
 *  Menu vẫn hiện mục sửa, mờ đi kèm câu này - như việc cần Studio ("explain, never hide"). */
export function editBlockedNote(caps: Capabilities | null | undefined): string | null {
  return caps?.link && !caps.workshop ? LINK_BOOK : null;
}
