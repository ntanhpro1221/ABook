import { S } from "../shared/strings.generated";
// Lời của hộp Xuất (studio/ExportBook.tsx) cần đúng sự thật mà không cần vẽ hộp để thử.

/** Chương chờ thu lại theo sửa của người nghe (soát UX a25 T9): bản xuất mang bản thu CŨ của chúng - chữ đọc theo đi cùng bản thu
 *  ấy, còn tên giọng trong danh sách nhân vật của file `.abook` đã theo sửa mới. `null` khi không có chương nào chờ. */
export function redoExportNote(redo: number, abook: boolean): string | null {
  if (redo <= 0) return null;
  const name = abook ? S.s_ten_giong_ghi_trong_sach_co_the_da_la_gion_73247fe9 : "";
  return S.s_0_chuong_dang_cho_thu_lai_theo_sua_cua_ban_6e27f23a(redo, name);
}
