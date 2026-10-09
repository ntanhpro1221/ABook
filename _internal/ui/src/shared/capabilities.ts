/** Máy này làm được gì với một cuốn sách (docs/EDITING.md) - giao diện chỉ hỏi qua đây, không tự suy ra từ nền tảng.
 *
 * - `toolchain`: Studio dùng được trên máy này (bản dev luôn có; app Windows đóng gói khi đã cài và không cũ; điện thoại không).
 * - `workshop`: cuốn có dự án sản xuất trên máy này (điện thoại không bao giờ có - nó không mở sổ dự án).
 * - `link`: cuốn không sửa được ở đây - máy tính: cuốn của điện thoại chia sẻ thư viện (sửa ở điện thoại ấy). Điện thoại không còn cuốn nào như vậy.
 * - `sync`: cuốn của máy tính khác - điện thoại: của máy tính chính (đã tải hay nghe thẳng) hay một máy tính khác đã ghép; máy tính: cuốn
 *   "Trên máy khác" của một máy tính đã ghép (webui/remote_books.py). Sửa được ngay ở đây, và phần sửa gửi về máy ấy (EditsSync.kt, docs/EDITING.md P2b).
 * - `local`: cuốn của điện thoại khác đã ghép (điện thoại): sửa được ngay ở đây nhưng máy kia không nhận phần sửa - nó chỉ nằm trên máy này (docs/EDITING.md P2d).
 *
 * Máy tính trả ở `/api/app` và trên từng sách (`ListenBook.capabilities`); Android ở `EbookLibrary.capabilities` và trên từng
 * sách plugin trả về. */
export interface Capabilities {
  toolchain: boolean;
  workshop: boolean;
  link: boolean;
  sync?: boolean;
  local?: boolean;
}

/** Sửa "áp ngay" (tên sách, bìa, tên nhân vật, tên chương, nhạc nền) không cần Studio: làm được trên mọi cuốn của máy này,
 *  có xưởng hay không. Cuốn của điện thoại chia sẻ thư viện (`link`, máy tính) thì không. */
export function canEditLayer(caps: Capabilities | null | undefined): boolean {
  return Boolean(caps) && (caps!.workshop || !caps!.link);
}

/** Việc cần Studio (đổi giọng, sửa lời đọc, thu lại chương...): `null` khi làm được ngay (có Studio VÀ cuốn có xưởng), không thì
 *  câu nói thiếu gì - nút vẫn hiện, bấm không được, kèm câu này. Cuốn nghe thẳng từ máy khác: không có gì để nói ở đây. */
export function studioNeed(caps: Capabilities | null | undefined): string | null {
  if (!caps || caps.link) return null;
  if (caps.workshop && caps.toolchain) return null;
  if (!caps.toolchain) return "cần cài Studio";
  return "cuốn này chưa có dự án Studio";
}

/** Việc cần Studio có nên hiện (bị mờ) không: mọi cuốn của máy này trừ cuốn đã làm được ngay. */
export function showsStudioOnly(caps: Capabilities | null | undefined): boolean {
  return studioNeed(caps) !== null;
}

/** Cuốn tải từ máy tính chính: phần sửa (và ý muốn chờ Studio) gửi về máy tính - nút "Gửi về máy tính", dòng trạng thái. */
export function syncsToComputer(caps: Capabilities | null | undefined): boolean {
  return Boolean(caps?.sync) && !caps?.workshop;
}

/** Lý do không sửa được cuốn của điện thoại chia sẻ thư viện (máy tính) - cùng câu với 409 của máy tính. */
export const LINK_BOOK = "Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy";

/** Cuốn của điện thoại khác: sửa được, nhưng phần sửa chỉ nằm trên máy này - câu nói điều đó cho người nghe. */
export const LOCAL_EDITS = "Sách này nằm trên điện thoại khác nên các thay đổi chỉ có trên máy này - máy kia vẫn giữ sách như cũ";

/** Phần sửa của cuốn này chỉ ở lại máy này (cuốn của điện thoại khác): `LOCAL_EDITS`, không thì `null`. */
export function localEditsNote(caps: Capabilities | null | undefined): string | null {
  return caps?.local && !caps.workshop ? LOCAL_EDITS : null;
}

/** Sửa "áp ngay" bị chặn vì cuốn nghe thẳng từ máy khác: câu nói lý do, không thì `null` (sửa được, hay không có gì để nói).
 *  Menu vẫn hiện mục sửa, mờ đi kèm câu này - như việc cần Studio ("explain, never hide"). */
export function editBlockedNote(caps: Capabilities | null | undefined): string | null {
  return caps?.link && !caps.workshop ? LINK_BOOK : null;
}

/** Sửa MỘT CÂU từ trang đọc (người nói, loại câu / cảm xúc / chữ đem đọc, cách đọc tên, thu lại) - docs/EDITING.md, P2a:
 *  - `wish`: cuốn không có xưởng - ghi ý muốn "đang chờ Studio" ngay trên trang đọc;
 *  - `studio`: cuốn có xưởng và có Studio - sửa thật ở tab Kịch bản của Studio;
 *  - `blocked`: chưa làm được ở đây - nút vẫn hiện, mờ đi, kèm `note` (cuốn nghe thẳng từ máy khác, hay xưởng chưa dùng được).
 *  `null`: chưa biết máy làm được gì. */
export type LineEditing = { mode: "wish" } | { mode: "studio" } | { mode: "blocked"; note: string };

export function lineEditing(caps: Capabilities | null | undefined): LineEditing | null {
  if (!caps) return null;
  if (caps.link && !caps.workshop) return { mode: "blocked", note: LINK_BOOK };
  // Việc chờ Studio cần một máy làm sách nhận được; điện thoại khác không phải máy ấy.
  if (caps.local && !caps.workshop) return { mode: "blocked", note: "Sách này nằm trên điện thoại khác - sửa từng câu phải làm ở máy ấy" };
  if (caps.workshop) return caps.toolchain ? { mode: "studio" } : { mode: "blocked", note: studioNeed(caps) ?? "cần cài Studio" };
  return { mode: "wish" };
}
