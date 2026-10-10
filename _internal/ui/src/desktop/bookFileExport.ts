import { spokenDuration } from "@/listen/prepareAhead";
import { fileName, formatClock, formatSize } from "@/shared/format";
import { api } from "@/studio/api";

// "Xuất file sách" và "Xuất M4B" (menu "…" của trang sách): nói trước file sẽ nằm đâu, và trong lúc làm nói điều đổi theo thời gian.
// Máy chủ không báo "chương n/N" khi làm - chỉ có thời gian trôi qua là thứ thật để nói.

/** Chữ riêng của từng kiểu xuất chạy nền; phần còn lại (hỏi trạng thái, thông báo, nhắc lại khi mở trang) dùng chung. */
export interface ExportCopy {
  busy: string;
  done: string;
  failed: string;
  /** Việc có nút Huỷ: lời khi người dùng đã dừng nó ("Đã dừng xuất…") và điều còn lại ("Phần đã làm được giữ…"). */
  stopped?: string;
  stoppedNote?: string;
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
  /** Số file trong thư mục kết quả (xuất sách nói MP3: mỗi chương một file). */
  files?: number;
  chapters?: number;
  chaptersTotal?: number;
}

export interface ExportJob {
  state: "idle" | "running" | "done" | "error" | "cancelled";
  id?: string;
  /** Xuất sách nói (listen_export.py) báo tiến độ: pha ("voice" đọc / "encode" ghép file), chương i/N, % theo số chữ, ước còn lại (giây), đang nhường người nghe. */
  phase?: "voice" | "encode";
  chapter?: number;
  chapters?: number;
  percent?: number;
  secondsLeft?: number | null;
  waiting?: "listening" | null;
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
  | {
      kind: "loading" | "success" | "error" | "info";
      title: string;
      description: string;
      /** Đường đầy đủ của file vừa xuất: để ở gợi ý khi rê chuột, thông báo chỉ nói tên file. */
      place?: string;
      /** Việc báo được tiến độ: thanh phần trăm (0-1) dưới dòng mô tả. */
      progress?: number;
    };

/** Việc tự báo tiến độ (xuất sách nói): chữ + phần trăm 0-1; không báo thì null. */
function reportedProgress(job: ExportJob): { fraction: number; text: string } | null {
  if (job.chapter === undefined || !job.chapters) return null;
  const where = `Chương ${job.chapter}/${job.chapters}`;
  if (job.phase === "encode") return { fraction: 1, text: `Đang ghép file âm thanh · ${where}` };
  const parts = [where, `${job.percent ?? 0}%`];
  if (job.waiting === "listening") parts.push("nhường cho chương đang nghe");
  else if (job.secondsLeft != null) parts.push(`còn ${spokenDuration(job.secondsLeft)}`);
  return { fraction: (job.percent ?? 0) / 100, text: parts.join(" · ") };
}

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
    const reported = reportedProgress(job);
    if (reported) return { kind: "loading", title: copy.busy, description: reported.text, progress: reported.fraction };
    return { kind: "loading", title: copy.busy, description: chapters ? packingText(chapters, elapsed) : `đã ${formatClock(elapsed)}` };
  }
  if (announce && (job.finishedAgo ?? 0) > RECENT_SECONDS) return { kind: "none" };
  if (job.state === "cancelled") return copy.stopped ? { kind: "info", title: copy.stopped, description: copy.stoppedNote ?? "" } : { kind: "none" };
  if (job.state === "done" && job.result) {
    // Thông báo chỉ nói TÊN (file, hay thư mục khi mỗi phần một file + số file); đường đầy đủ ở gợi ý khi rê chuột và nút "Mở thư mục".
    const { file, folder } = job.result;
    const count = job.result.files ?? job.result.parts?.length;
    const details = [!file && count ? `${count} file` : "", job.result.size ? formatSize(job.result.size) : "", missingChaptersNote(job.result)].filter(Boolean);
    const place = file ?? folder;
    return { kind: "success", title: copy.done, description: [fileName(place), ...details].join(" · "), ...(fileName(place) !== place ? { place } : {}) };
  }
  if (job.state === "error") return { kind: "error", title: copy.failed, description: job.error ?? "" };
  return { kind: "none" };
}

/** Chữ dài quá `max` ký tự thì cắt Ở ĐẦU (giữ phần đuôi: đuôi file và số tập là chỗ phân biệt các lần xuất), thêm "…". */
export function clipStart(text: string, max: number): string {
  return text.length > max ? `…${text.slice(text.length - (max - 1))}` : text;
}

/** Số ký tự tối đa của tên file / thư mục trong dòng phụ của menu (dòng phụ cắt ở cuối khi quá rộng - tên không được nằm ở chỗ bị cắt). */
const HINT_NAME_MAX = 34;

/** Dòng phụ trong menu: lần xuất gần nhất của cuốn này (nếu có), thay cho "Bạn chọn thư mục lưu ở bước kế". Nói TÊN file / thư mục
 *  (đường đầy đủ ở `lastExportPlace`, hiện khi rê chuột): đường dài bị cắt ngay đầu thì chỉ còn thấy ổ đĩa và thư mục cha. */
export function lastExportHint(job: ExportJob | undefined, copy: ExportCopy = BOOK_FILE_COPY): string | null {
  if (job?.state === "running") return `${copy.busy.replace(/…$/, "")} - xem thông báo ở góc màn hình`;
  if (job?.state === "done" && job.result) return `Lần xuất gần nhất: ${clipStart(fileName(exportedPlace(job.result)), HINT_NAME_MAX)}`;
  return null;
}

/** Đường đầy đủ của lần xuất gần nhất (cho gợi ý khi rê chuột trên dòng phụ); chưa có thì undefined. */
export function lastExportPlace(job: ExportJob | undefined): string | undefined {
  return job?.state === "done" && job.result ? exportedPlace(job.result) : undefined;
}

/** Mã các cuốn đang có lượt xuất `kind` chạy ở máy chủ (GET /api/export-jobs). Mở (hay tải lại) app ở trang khác trang sách: đây là cách duy nhất
 *  biết có việc để hiện lại tiến độ. Hỏi hụt thì coi như không có (nhịp sau, hay trang sách, sẽ hỏi lại). */
export async function runningExports(kind: "bookfile" | "m4b" | "audiobook"): Promise<string[]> {
  try {
    const all = await api<Partial<Record<string, (ExportJob & { bookId: string })[]>>>("/api/export-jobs");
    return (all[kind] ?? []).filter((job) => job.state === "running").map((job) => job.bookId);
  } catch {
    return [];
  }
}
