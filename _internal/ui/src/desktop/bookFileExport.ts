import { formatClock, formatSize } from "@/shared/format";

// "Xuất file sách" (menu "…" của trang sách): nói trước file sẽ nằm đâu, và trong lúc đóng gói nói điều đổi theo thời gian.
// Máy chủ không báo "chương n/N" khi đóng gói - chỉ có thời gian trôi qua là thứ thật để nói.

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

// ---- việc xuất chạy nền (webui/export_jobs.py: GET /api/books/<id>/bookfile-job) ----------------------------------------------
// Máy chủ nhớ lần xuất gần nhất của mỗi cuốn: tải lại trang giữa chừng hay sau khi xong, giao diện hỏi lại và hiện đúng chỗ ấy.

/** Kết quả của một lượt xuất: một file (`file`), hay cả bộ mỗi phần một file (chỉ có `folder` + `parts`). */
export interface ExportResult {
  folder: string;
  file?: string;
  size?: number;
  parts?: unknown[];
}

export interface ExportJob {
  state: "idle" | "running" | "done" | "error";
  id?: string;
  /** Giây đã đóng gói (đang chạy). */
  elapsed?: number;
  /** Giây kể từ lúc xong / hỏng. */
  finishedAgo?: number;
  result?: ExportResult;
  error?: string;
}

/** Xong cách đây không quá chừng này thì mở trang sách là báo lại; xa hơn thì chỉ còn dòng "lần xuất gần nhất" trong menu. */
export const RECENT_SECONDS = 30 * 60;

export type JobView =
  | { kind: "none" }
  | { kind: "loading" | "success" | "error"; title: string; description: string };

/** Nơi file nằm: file sách, hay thư mục khi cả bộ mỗi phần một file. */
export function exportedPlace(result: ExportResult): string {
  return result.file ?? result.folder;
}

/** Thông báo cho một trạng thái; `announce` (mở lại trang sách): chỉ nhắc cái đã xong gần đây, không nhắc lần xuất từ lâu. */
export function jobView(job: ExportJob, chapters = 0, announce = false): JobView {
  if (job.state === "running") {
    const elapsed = job.elapsed ?? 0;
    return { kind: "loading", title: "Đang đóng gói sách…", description: chapters ? packingText(chapters, elapsed) : `đã ${formatClock(elapsed)}` };
  }
  if (announce && (job.finishedAgo ?? 0) > RECENT_SECONDS) return { kind: "none" };
  if (job.state === "done" && job.result) {
    const size = job.result.size ? ` · ${formatSize(job.result.size)}` : "";
    return { kind: "success", title: "Đã xuất file sách", description: `${exportedPlace(job.result)}${size}` };
  }
  if (job.state === "error") return { kind: "error", title: "Không xuất được file sách", description: job.error ?? "" };
  return { kind: "none" };
}

/** Dòng phụ trong menu: lần xuất gần nhất của cuốn này (nếu có), thay cho "Bạn chọn thư mục lưu ở bước kế". */
export function lastExportHint(job: ExportJob | undefined): string | null {
  if (job?.state === "running") return "Đang đóng gói - xem thông báo ở góc màn hình";
  if (job?.state === "done" && job.result) return `Lần xuất gần nhất: ${exportedPlace(job.result)}`;
  return null;
}
