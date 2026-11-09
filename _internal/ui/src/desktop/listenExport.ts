import { S } from "../shared/strings.generated";
import type { ReadAloudVoice } from "@/listen/readAloud";
import { KEYED_PROVIDERS } from "@/listen/readAloudVoice";
import { spokenDuration } from "@/listen/prepareAhead";
import { api } from "@/studio/api";
import type { ExportCopy, ExportJob } from "./bookFileExport";

// "Xuất sách nói (MP3 / M4B)" của sách Nghe ngay (webui/listen_export.py): chữ trong hộp, ước thời gian, và các lệnh gọi máy chủ.
// Sách chỉ có chữ được đọc bằng giọng của máy rồi ghép thành file âm thanh để mang sang trình phát khác (điện thoại, xe hơi).

export type AudiobookFormat = "mp3" | "m4b";

export const AUDIOBOOK_COPY: ExportCopy = {
  busy: S.s_dang_lam_sach_noi_6c41169d,
  done: S.s_da_xuat_sach_noi_82ff590c,
  failed: S.s_chua_xuat_duoc_sach_noi_5468423d,
  stopped: S.s_da_dung_xuat_ab8ac9d1,
  stoppedNote: S.s_phan_da_lam_duoc_giu_xuat_lai_de_lam_tiep_5da9523a,
};

export const FORMAT_CHOICES: { id: AudiobookFormat; label: string; hint: string }[] = [
  { id: "mp3", label: S.s_mp3_theo_chuong_a08d3a89, hint: S.s_mot_thu_muc_moi_chuong_mot_mp3_kem_danh_sa_d7562c0b },
  { id: "m4b", label: S.s_m4b_ca_cuon_2cba5ce9, hint: S.s_mot_file_co_muc_luc_chuong_nho_cho_nghe_do_903bace3 },
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
export const MUSIC_MIX_HINT = S.s_nhac_duoc_tron_thang_vao_file_khong_tat_ri_e1608133;

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
  if (keyed) return S.s_chu_cua_ca_cuon_duoc_gui_toi_0_de_doc_bang_388c1afd(keyed);
  if (voice.provider === "edge") return S.s_chu_cua_ca_cuon_duoc_gui_toi_may_chu_micro_301f6ec7;
  return S.s_chu_cua_ca_cuon_duoc_gui_toi_dich_vu_ngoai_a88c44d1;
}

/** Dòng nói sách dài bao nhiêu và máy cần bao lâu: "12 chương · khoảng 8 giờ nghe · máy cần khoảng 2 giờ 10 phút." */
export function planText(plan: Pick<AudiobookPlan, "chapters" | "audioSeconds" | "secondsEstimate">): string {
  const machine = plan.secondsEstimate != null ? S.s_may_can_0_6e7b3653(spokenDuration(plan.secondsEstimate)) : "";
  return S.s_0_chuong_1_nghe_2_7610a1f8(plan.chapters, spokenDuration(plan.audioSeconds), machine);
}

/** Nói phần nào đã có sẵn (đã nghe, đã Làm trước, lần xuất trước): "Đã đọc sẵn khoảng 52% - phần này xuất ngay, không đọc lại." Tính theo phần nghe
 *  đã có trên cả cuốn, không đếm chương đủ: soát a63 huỷ khi chương 2/3 đã đọc 57% mà hộp báo "1/3 chương". */
export function resumeText(plan: Pick<AudiobookPlan, "chapters" | "readyChapters" | "readySeconds" | "audioSeconds">): string {
  // readyChapters chỉ còn để biết đủ cả cuốn.
  if (plan.chapters && plan.readyChapters >= plan.chapters) return S.s_da_doc_san_ca_cuon_chi_con_ghep_thanh_file_d6e392df;
  const ready = plan.readySeconds ?? 0;
  if (ready >= 60 && plan.audioSeconds > 0) {
    // Chưa đủ cả cuốn thì không nói 100% (quãng lặng giữa đoạn, làm tròn).
    const percent = Math.min(99, Math.max(1, Math.round((ready / plan.audioSeconds) * 100)));
    return S.s_da_doc_san_khoang_0_phan_nay_xuat_ngay_kho_6b951d4f(percent);
  }
  return "";
}

/** Phần trăm tải ffmpeg (0-100). */
export function ffmpegPercent(status: Pick<FfmpegStatus, "done" | "total">): number {
  return status.total > 0 ? Math.min(100, Math.round((100 * status.done) / status.total)) : 0;
}
