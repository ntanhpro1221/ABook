import { formatSize } from "@/shared/format";

// Xuất `.abookproj` chạy nền ở máy chủ (webui/server.py `post_projectfile_job`, projectfile.pack): GET .../projectfile-job báo pha + đã/tổng.
// Hộp Xuất đổi nó thành một dòng cho người nghe và một thanh tiến độ.

export type PackPhase = "prepare" | "listen" | "views" | "hash" | "write";

export interface PackJob {
  state: "idle" | "running" | "done" | "error" | "cancelled";
  phase?: PackPhase;
  /** "listen": số chương đã gom; "hash" / "write": số byte đã băm / đã ghi. */
  done?: number;
  total?: number;
  elapsed?: number;
  error?: string;
  result?: { folder: string; file: string; size: number; missingSources?: string[] };
}

/** Phần của thanh tiến độ (0-1) mỗi pha chiếm - theo thời gian đo trên dự án 400 chương (gom chương, băm audio, ghi gói). Chỉ để thanh chạy đều. */
const SPAN: Record<PackPhase, [number, number]> = {
  prepare: [0, 0.02],
  listen: [0.02, 0.38],
  views: [0.38, 0.42],
  hash: [0.42, 0.72],
  write: [0.72, 1],
};

export interface PackView {
  /** "Đang đóng gói (12/400 chương)…" */
  title: string;
  /** 0-1; null: chưa có mẫu số (thanh chạy không biết trước). */
  fraction: number | null;
}

export function packView(job: PackJob | null | undefined): PackView {
  const base = "Đang đóng gói";
  if (!job || !job.phase || job.state !== "running") return { title: `${base}…`, fraction: null };
  const [from, to] = SPAN[job.phase];
  const total = job.total ?? 0;
  const done = Math.min(job.done ?? 0, total);
  const inner = total > 0 ? done / total : 0;
  const fraction = from + (to - from) * inner;
  if (job.phase === "listen" && total > 0) return { title: `${base} (${done}/${total} chương)…`, fraction };
  if ((job.phase === "hash" || job.phase === "write") && total > 0) return { title: `${base} (${formatSize(done)}/${formatSize(total)})…`, fraction };
  return { title: `${base}…`, fraction: job.phase === "prepare" ? null : from };
}

/** Người dùng bấm Huỷ khi đang gói dự án (máy chủ trả "cancelled"): cùng lời báo với lúc huỷ tải nhạc nền. */
export class PackCancelled extends Error {}

/** Màn hình gói bị gỡ (đóng trang, sang cuốn khác) giữa lúc máy chủ còn gói: KHÔNG phải huỷ - việc vẫn chạy, nên không được báo "Đã huỷ xuất"; ExportJobHost nhận theo dõi tiếp. */
export class PackDetached extends Error {}

/** Theo việc gói dự án tới khi xong (hỏi mỗi giây): trả kết quả, hay ném `PackCancelled` (người dùng huỷ) / `PackDetached` (`alive()` hết đúng) / lỗi của máy chủ.
 *  Hỏi hụt `maxMisses` lần liền mới coi là hỏng (mạng chớp không phải việc hỏng). */
export async function followPackJob({
  fetchJob,
  alive,
  onJob,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  maxMisses = 5,
}: {
  fetchJob: () => Promise<PackJob>;
  alive: () => boolean;
  onJob: (job: PackJob) => void;
  sleep?: (ms: number) => Promise<void>;
  maxMisses?: number;
}): Promise<NonNullable<PackJob["result"]>> {
  let misses = 0;
  while (alive()) {
    let job: PackJob;
    try {
      job = await fetchJob();
      misses = 0;
    } catch (error) {
      if (++misses >= maxMisses) throw error;
      await sleep(1000);
      continue;
    }
    if (job.state === "done" && job.result) return job.result;
    if (job.state === "cancelled") throw new PackCancelled();
    if (job.state !== "running") throw new Error(job.error ?? "Chưa gói được dự án.");
    onJob(job);
    await sleep(1000);
  }
  throw new PackDetached();
}

const KNOWN: { pattern: RegExp; summary: string }[] = [
  { pattern: /No space left|ENOSPC|disk full|WinError 112|not enough space|disk quota/i, summary: "Ổ đĩa hết chỗ trống. Giải phóng dung lượng hoặc chọn thư mục ở ổ khác rồi gói lại." },
  {
    pattern: /PermissionError|WinError 5\b|WinError 32|Access is denied|being used by another process|Errno 13/i,
    summary: "Không ghi được vào thư mục đã chọn (đang bị khoá hay không đủ quyền). Chọn thư mục khác rồi gói lại.",
  },
];

/** Lỗi thô của máy chủ -> câu cho người nghe + nguyên văn cho "Chi tiết". Lỗi máy chủ đã viết bằng tiếng Việt (vd. "Dự án đang chạy…") giữ nguyên, không có Chi tiết. */
export function packError(raw: string): { summary: string; detail: string } {
  const detail = raw.trim();
  const known = KNOWN.find((entry) => entry.pattern.test(detail));
  if (known) return { summary: known.summary, detail };
  if (/[ạảãàáâấầẩẫậắằẳẵặẹẻẽèéêếềểễệỉĩịọỏõòóôốồổỗộớờởỡợụủũùúưứừửữựỳỷỹýđ]/i.test(detail)) return { summary: detail, detail: "" };
  return { summary: "Chưa gói được dự án.", detail };
}
