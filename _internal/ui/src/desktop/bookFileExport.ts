import { formatClock, formatSize } from "@/shared/format";

// "Xuất file sách" và "Xuất M4B" (menu "…" của trang sách): nói trước file sẽ nằm đâu, và trong lúc làm nói điều đổi theo thời gian.
// Máy chủ không báo "chương n/N" khi làm - chỉ có thời gian trôi qua là thứ thật để nói.

/** Chữ riêng của từng kiểu xuất chạy nền; phần còn lại (hỏi trạng thái, thông báo, nhắc lại khi mở trang) dùng chung. */
export interface ExportCopy {
  busy: string;
  done: string;
  failed: string;
}

export const BOOK_FILE_COPY: ExportCopy = { busy: "Đang đóng gói sách…", done: "Đã xuất file sách", failed: "Không xuất được file sách" };
export const M4B_COPY: ExportCopy = { busy: "Đang làm file M4B…", done: "Đã xuất M4B", failed: "Không xuất được M4B" };

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

/** Kết quả của một lượt xuất: một file (`file`), hay cả bộ mỗi phần một file (chỉ có `folder` + `parts`). M4B kể thêm số chương
 *  có trong file / của cả cuốn - chương chưa làm xong không vào file. */
export interface ExportResult {
  folder: string;
  file?: string;
  size?: number;
  parts?: unknown[];
  chapters?: number;
  chaptersTotal?: number;
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

/** "4/6 chương - chương chưa xong không có trong file" khi bản xuất thiếu chương; rỗng khi đủ hay không biết. */
export function missingChaptersNote(result: ExportResult): string {
  const { chapters, chaptersTotal } = result;
  if (chapters === undefined || chaptersTotal === undefined || chapters >= chaptersTotal) return "";
  return `${chapters}/${chaptersTotal} chương - chương chưa xong không có trong file`;
}

/** Thông báo cho một trạng thái; `announce` (mở lại trang sách): chỉ nhắc cái đã xong gần đây, không nhắc lần xuất từ lâu. */
export function jobView(job: ExportJob, chapters = 0, announce = false, copy: ExportCopy = BOOK_FILE_COPY): JobView {
  if (job.state === "running") {
    const elapsed = job.elapsed ?? 0;
    return { kind: "loading", title: copy.busy, description: chapters ? packingText(chapters, elapsed) : `đã ${formatClock(elapsed)}` };
  }
  if (announce && (job.finishedAgo ?? 0) > RECENT_SECONDS) return { kind: "none" };
  if (job.state === "done" && job.result) {
    const details = [job.result.size ? formatSize(job.result.size) : "", missingChaptersNote(job.result)].filter(Boolean);
    return { kind: "success", title: copy.done, description: [exportedPlace(job.result), ...details].join(" · ") };
  }
  if (job.state === "error") return { kind: "error", title: copy.failed, description: job.error ?? "" };
  return { kind: "none" };
}

/** Dòng phụ trong menu: lần xuất gần nhất của cuốn này (nếu có), thay cho "Bạn chọn thư mục lưu ở bước kế". */
export function lastExportHint(job: ExportJob | undefined, copy: ExportCopy = BOOK_FILE_COPY): string | null {
  if (job?.state === "running") return `${copy.busy.replace(/…$/, "")} - xem thông báo ở góc màn hình`;
  if (job?.state === "done" && job.result) return `Lần xuất gần nhất: ${exportedPlace(job.result)}`;
  return null;
}
