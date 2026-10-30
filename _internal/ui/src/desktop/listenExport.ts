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
  failed: "Chưa xuất được sách nói",
  stopped: "Đã dừng xuất",
  stoppedNote: "Phần đã làm được giữ - xuất lại để làm tiếp từ đó.",
};

export const FORMAT_CHOICES: { id: AudiobookFormat; label: string; hint: string }[] = [
  { id: "mp3", label: "MP3 theo chương", hint: "Một thư mục, mỗi chương một MP3 kèm danh sách phát. Trình phát nào cũng mở được." },
  { id: "m4b", label: "M4B cả cuốn", hint: "Một file có mục lục chương, nhớ chỗ nghe dở. Hợp Apple Books, BookPlayer, Smart AudioBook Player." },
];

/** Phần trả lời của GET /api/listen/books/<mã>/audiobook/plan. */
export interface AudiobookPlan {
  chapters: number;
  chars: number;
  /** Thời gian nghe (giây): độ dài thật của phần đã có (clip trong bộ đệm Nghe ngay, chương đã ghép) + phần chưa có ước theo tốc độ đo trên chính các clip ấy. */
  audioSeconds: number;
  /** Tốc độ đo của giọng (giây máy làm cho mỗi giây nghe); null khi chưa đo. */
  rtf: number | null;
  /** Máy đọc phần chưa có mất chừng này giây (chỉ khi đã đo tốc độ giọng); null: không ước. */
  secondsEstimate: number | null;
  /** Chương có đủ (đã ghép từ lần xuất trước, hay mọi đoạn đã có trong bộ đệm Nghe ngay): xuất ngay, không đọc lại. */
  readyChapters: number;
  /** Giây nghe đã có sẵn (clip trong bộ đệm + chương đã ghép); thiếu ở máy cũ. */
  readySeconds?: number;
  ffmpeg: FfmpegStatus;
  /** Ô "Kèm nhạc nền" (webui/music_export.py `packaged_state`): cuốn có nhạc gắn sẵn theo chương không, công tắc Nhạc nền của cuốn đang bật không. */
  music?: MusicExportState;
}

/** Ô "Kèm nhạc nền" của hộp xuất sách nói: `available` - cuốn có kế hoạch nhạc (không thì không hiện ô), `enabled` - mặc định của ô. */
export interface MusicExportState {
  available: boolean;
  enabled: boolean;
}

/** Lời ngắn dưới ô "Kèm nhạc nền". */
export const MUSIC_MIX_HINT = "Nhạc được trộn thẳng vào file, không tắt riêng được khi nghe.";

/** Công cụ ghép âm thanh (ffmpeg): tải riêng khi máy chưa có (GET/POST /api/ffmpeg). */
export interface FfmpegStatus {
  ready: boolean;
  outdated?: boolean;
  downloading: boolean;
  done: number;
  total: number;
  error: string;
  bytes: number;
  /** Lý do không tải được trên máy này (rỗng nếu tải được). */
  blocked: string;
  /** Nguyên văn lỗi của lần tải hỏng, thu trong "Chi tiết". */
  errorDetail?: string;
  /** Đang tải mà mạng vừa hỏng, đang chờ thử lại (RETRYING_NOTE). */
  retrying?: boolean;
}

export const fetchPlan = (bookId: string, voice: string) =>
  api<AudiobookPlan>(`/api/listen/books/${bookId}/audiobook/plan?voice=${encodeURIComponent(voice)}`);

export const ffmpegStatus = () => api<FfmpegStatus>("/api/ffmpeg");
export const ffmpegStart = () => api<FfmpegStatus>("/api/ffmpeg", { method: "POST", body: {} });
export const ffmpegCancel = () => api<FfmpegStatus>("/api/ffmpeg/cancel", { method: "POST", body: {} });
export const audiobookCancel = (bookId: string) => api<ExportJob>(`/api/listen/books/${bookId}/audiobook/cancel`, { method: "POST", body: {} });

/** Thân yêu cầu bắt đầu xuất (ngoài `target` / `cover` do host thêm). */
export const audiobookBody = (format: AudiobookFormat, voice: string, music = false) => ({ format, voice, ...(music ? { music: true } : {}) });

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

/** Nói phần nào đã có sẵn (đã nghe, đã Làm trước, lần xuất trước): "Đã đọc sẵn khoảng 52% - phần này xuất ngay, không đọc lại." Tính theo phần nghe
 *  đã có trên cả cuốn, không đếm chương đủ: soát a63 huỷ khi chương 2/3 đã đọc 57% mà hộp báo "1/3 chương". */
export function resumeText(plan: Pick<AudiobookPlan, "chapters" | "readyChapters" | "readySeconds" | "audioSeconds">): string {
  // readyChapters chỉ còn để biết đủ cả cuốn.
  if (plan.chapters && plan.readyChapters >= plan.chapters) return "Đã đọc sẵn cả cuốn - chỉ còn ghép thành file, không đọc lại.";
  const ready = plan.readySeconds ?? 0;
  if (ready >= 60 && plan.audioSeconds > 0) {
    // Chưa đủ cả cuốn thì không nói 100% (quãng lặng giữa đoạn, làm tròn).
    const percent = Math.min(99, Math.max(1, Math.round((ready / plan.audioSeconds) * 100)));
    return `Đã đọc sẵn khoảng ${percent}% - phần này xuất ngay, không đọc lại.`;
  }
  return "";
}

/** Phần trăm tải ffmpeg (0-100). */
export function ffmpegPercent(status: Pick<FfmpegStatus, "done" | "total">): number {
  return status.total > 0 ? Math.min(100, Math.round((100 * status.done) / status.total)) : 0;
}
