import { formatClock } from "@/shared/format";

// "Xuất file sách" (menu "…" của trang sách): nói trước file sẽ nằm đâu, và trong lúc đóng gói nói điều đổi theo thời gian.
// Máy chủ đóng gói trong MỘT yêu cầu, không báo "chương n/N" - chỉ có thời gian trôi qua là thứ thật để nói.

/** Thư mục máy chủ lưu khi không có hộp chọn thư mục (trình duyệt, Studio từ xa): "Đã xuất" trong thư viện (webui/server.py post_bookfile).
 *  Giữ kiểu dấu ngăn của chính đường dẫn thư viện (Windows `\`, còn lại `/`). */
export function defaultExportFolder(libraryRoot: string | undefined): string | null {
  if (!libraryRoot) return null;
  const separator = libraryRoot.includes("\\") ? "\\" : "/";
  return `${libraryRoot.replace(/[\\/]+$/, "")}${separator}Đã xuất`;
}

/** Dòng phụ dưới "Xuất file sách": chọn thư mục (cửa sổ app) hay thư mục sẽ lưu (nơi khác). */
export function exportWhereHint(dialogs: boolean, libraryRoot: string | undefined): string {
  if (dialogs) return "Bạn chọn thư mục lưu ở bước kế";
  const folder = defaultExportFolder(libraryRoot);
  return folder ? `Lưu vào ${folder}` : "Lưu vào thư mục “Đã xuất” trong thư viện";
}

/** Chữ của thông báo đang đóng gói: số chương và thời gian đã trôi - đổi mỗi giây nên người xem biết máy chưa treo. */
export function packingText(chapters: number, elapsedSeconds: number): string {
  return `${chapters} chương · đã ${formatClock(elapsedSeconds)}`;
}
