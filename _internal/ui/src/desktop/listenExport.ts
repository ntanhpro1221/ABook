import type { ReadAloudVoice } from "@/listen/readAloud";
import { KEYED_PROVIDERS } from "@/listen/readAloudVoice";
import { spokenDuration } from "@/listen/prepareAhead";
import { api } from "@/studio/api";
import type { ExportCopy, ExportJob } from "./bookFileExport";

// "Xuất sách nói (MP3 / M4B)" của sách Nghe ngay (webui/listen_export.py): chữ trong hộp, ước thời gian, và các lệnh gọi máy chủ.
// Sách chỉ có chữ được đọc bằng giọng của máy rồi ghép thành file âm thanh để mang sang trình phát khác (điện thoại, xe hơi).

export type AudiobookFormat = "mp3" | "m4b";

export const AUDIOBOOK_COPY: ExportCopy = {
  busy: "Đang làm sách nói…",
  done: "Đã xuất sách nói",
  failed: "Không xuất được sách nói",
  stopped: "Đã dừng xuất sách nói",
  stoppedNote: "Phần đã làm được giữ - xuất lại để làm tiếp từ đó.",
};

export const FORMAT_CHOICES: { id: AudiobookFormat; label: string; hint: string }[] = [
  { id: "mp3", label: "MP3 - mỗi chương một file", hint: "Một thư mục, mỗi chương một MP3 kèm danh sách phát. Trình phát nào cũng mở được." },
  { id: "m4b", label: "M4B - cả cuốn một file", hint: "Một file có mục lục chương, nhớ chỗ nghe dở. Hợp Apple Books, BookPlayer, Smart AudioBook Player." },
];

/** Phần trả lời của GET /api/listen/books/<mã>/audiobook/plan. */
export interface AudiobookPlan {
  chapters: number;
  chars: number;
  /** Thời gian nghe ước (giây): số chữ / 14 chữ mỗi giây. */
  audioSeconds: number;
  /** Tốc độ đo của giọng (giây máy làm cho mỗi giây nghe); null khi chưa đo. */
  rtf: number | null;
  /** Máy làm cả cuốn mất chừng này giây (chỉ khi đã đo tốc độ giọng); null: không ước. */
  secondsEstimate: number | null;
  /** Chương đã ghép sẵn từ một lần xuất bị dừng (cùng giọng, cùng chữ): lần này làm tiếp. */
  readyChapters: number;
  ffmpeg: FfmpegStatus;
}

/** Công cụ ghép âm thanh (ffmpeg): tải riêng khi máy chưa có (GET/POST /api/ffmpeg). */
export interface FfmpegStatus {
  ready: boolean;
  downloading: boolean;
  done: number;
  total: number;
  error: string;
  bytes: number;
  /** Lý do không tải được trên máy này (rỗng nếu tải được). */
  blocked: string;
}

export const fetchPlan = (bookId: string, voice: string) =>
  api<AudiobookPlan>(`/api/listen/books/${bookId}/audiobook/plan?voice=${encodeURIComponent(voice)}`);

export const ffmpegStatus = () => api<FfmpegStatus>("/api/ffmpeg");
export const ffmpegStart = () => api<FfmpegStatus>("/api/ffmpeg", { method: "POST", body: {} });
export const ffmpegCancel = () => api<FfmpegStatus>("/api/ffmpeg/cancel", { method: "POST", body: {} });
export const audiobookCancel = (bookId: string) => api<ExportJob>(`/api/listen/books/${bookId}/audiobook/cancel`, { method: "POST", body: {} });

/** Thân yêu cầu bắt đầu xuất (ngoài `target` / `cover` do host thêm). */
export const audiobookBody = (format: AudiobookFormat, voice: string) => ({ format, voice });

/** Chữ của giọng trực tuyến gửi CẢ CUỐN ra ngoài máy; rỗng khi giọng chạy trên máy. */
export function wholeBookNotice(voice: Pick<ReadAloudVoice, "provider" | "online">): string {
  if (!voice.online) return "";
  const keyed = KEYED_PROVIDERS[voice.provider];
  if (keyed) return `Chữ của cả cuốn được gửi tới ${keyed} để đọc, bằng khóa của bạn - dịch vụ có thể tính tiền vào tài khoản của bạn.`;
  if (voice.provider === "edge") return "Chữ của cả cuốn được gửi tới máy chủ Microsoft để đọc.";
  return "Chữ của cả cuốn được gửi tới dịch vụ ngoài để đọc.";
}

/** Dòng nói sách dài bao nhiêu và máy cần bao lâu: "12 chương · khoảng 8 giờ nghe · máy cần khoảng 2 giờ 10 phút." */
export function planText(plan: Pick<AudiobookPlan, "chapters" | "audioSeconds" | "secondsEstimate">): string {
  const machine = plan.secondsEstimate != null ? ` · máy cần ${spokenDuration(plan.secondsEstimate)}` : "";
  return `${plan.chapters} chương · ${spokenDuration(plan.audioSeconds)} nghe${machine}.`;
}

/** Nói điều gì sẽ xảy ra với phần đã làm: "Đã có sẵn 3/12 chương từ lần trước - làm tiếp từ đó." */
export function resumeText(plan: Pick<AudiobookPlan, "chapters" | "readyChapters">): string {
  if (!plan.readyChapters) return "";
  if (plan.readyChapters >= plan.chapters) return "Mọi chương đã ghép sẵn từ lần trước - chỉ còn ghép thành file.";
  return `Đã có sẵn ${plan.readyChapters}/${plan.chapters} chương từ lần trước - làm tiếp từ đó.`;
}

/** Phần trăm tải ffmpeg (0-100). */
export function ffmpegPercent(status: Pick<FfmpegStatus, "done" | "total">): number {
  return status.total > 0 ? Math.min(100, Math.round((100 * status.done) / status.total)) : 0;
}
