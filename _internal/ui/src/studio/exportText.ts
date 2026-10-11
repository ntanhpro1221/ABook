// Lời của hộp Xuất (studio/ExportBook.tsx) cần đúng sự thật mà không cần vẽ hộp để thử.

/** Chương chờ thu lại theo sửa của người nghe (soát UX a25 T9): bản xuất mang bản thu CŨ của chúng - chữ đọc theo đi cùng bản thu
 *  ấy, còn tên giọng trong danh sách nhân vật của file `.abook` đã theo sửa mới. `null` khi không có chương nào chờ. */
export function redoExportNote(redo: number, abook: boolean): string | null {
  if (redo <= 0) return null;
  const name = abook ? "; tên giọng ghi trong sách có thể đã là giọng mới" : "";
  return `${redo} chương đang chờ thu lại theo sửa của bạn - sách xuất dùng bản thu cũ của các chương ấy${name}.`;
}
