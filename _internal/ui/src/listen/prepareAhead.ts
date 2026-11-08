import { S } from "../shared/strings.generated";
// "Làm trước" (abook/readaloud/prepare.py, docs/LISTEN_ANYTHING.md mục 3): máy đọc sẵn các chương sắp nghe vào bộ đệm ở nền, để giọng đọc chậm
// hơn tốc độ nghe (giọng VieNeu trên máy yếu) vẫn nghe liền mạch, và trên điện thoại để nghe được khi không có mạng (lõi native: PrepareAhead.kt -
// việc nền chỉ chạy khi đang sạc, Wi-Fi). Phần thuần để thử riêng; nút ở VoiceMenu (PlayerViews.tsx).

import type { ListenChapter } from "./model";
import { onlineDestination } from "./onlineConsent";
import type { ReadAloudVoice } from "./readAloud";
import { formatSize } from "@/shared/format";
import { splitParagraphs, withoutLines } from "./textScript";

/** Khoá react-query của trạng thái làm trước (một việc một lúc cho cả máy): menu Giọng đọc và dấu "Đã làm sẵn" ở danh sách chương dùng chung. */
export const PREPARE_STATUS_KEY = ["readaloud", "prepare"] as const;

/** Một chương của việc làm trước (điện thoại): `ready` khi mọi đoạn đã nằm trong bộ đệm. */
export interface PreparedChapter {
  id: number;
  title: string;
  total: number;
  done: number;
  ready: boolean;
}

export interface PrepareStatus {
  state: "idle" | "running" | "done" | "cancelled" | "error";
  voice?: string;
  label?: string;
  /** Số đoạn nhận làm / đã gửi (máy chỉ nhận chừng vừa bộ đệm). */
  total?: number;
  offered?: number;
  done?: number;
  /** Thời lượng nghe ước của phần nhận làm (giây). */
  audioSeconds?: number;
  /** Ước thời gian còn lại (giây); null khi chưa biết tốc độ. */
  secondsLeft?: number | null;
  error?: string;
  /** Điện thoại: cuốn của việc, giọng có cần mạng, từng chương, số chương đã đưa. */
  bookId?: string;
  online?: boolean;
  chapters?: PreparedChapter[];
  chaptersOffered?: number;
  /** Điện thoại: "Chỉ khi đang sạc" (mặc định bật). */
  chargingOnly?: boolean;
  /** Điện thoại: vì sao việc chưa chạy lúc này. */
  waitingFor?: "charging" | "wifi" | "battery" | "listening" | null;
}

/** Việc làm trước giao diện gửi: nguồn tự lấy chữ (máy tính: chia đoạn ở đây rồi gửi; điện thoại: lõi native tự đọc chữ của chương). */
export interface PrepareRequest {
  voice: string;
  bookId: string;
  /** `skip`: dòng người nghe đã bỏ khỏi phần đọc - đoạn làm trước phải chia đúng như lúc nghe (cùng khoá bộ đệm). */
  chapters: Pick<ListenChapter, "id" | "title" | "skip">[];
  label: string;
  chargingOnly?: boolean;
}

/** Ước trước khi bấm (điện thoại): số chương nhận (vừa phần bộ đệm dành cho làm trước), giờ nghe, máy cần bao lâu (null: chưa đo tốc độ giọng này). */
export interface PreparePlan {
  chapters: number;
  offered: number;
  audioSeconds: number;
  secondsEstimate: number | null;
}

/** Bản đọc đã làm (clip trong bộ đệm của máy) chiếm bao nhiêu, tính bằng byte: của cuốn đang nghe và của cả máy (máy tính: webui `/api/readaloud/cache`). */
export interface ReadAloudCacheUsage {
  book: number;
  total: number;
}

/** Dòng nói bản đọc đã làm nặng bao nhiêu: "Cuốn này 12 MB · cả máy 148 MB". Ngắn một dòng, số và đơn vị dính liền (NBSP) - không rớt "141 MB)." xuống dòng riêng. */
export function cacheLabel(usage: ReadAloudCacheUsage): string {
  if (usage.book <= 0 && usage.total <= 0) return S.s_chua_luu_ban_doc_nao_7e94282d;
  const size = (bytes: number) => formatSize(bytes).replace(" ", " ");
  return S.s_0_ca_may_1_c42dbd32(usage.book > 0 ? S.s_cuon_nay_0_e00451d9(size(usage.book)) : S.s_cuon_nay_chua_co_93121203, usage.total > 0 ? size(usage.total) : S.s_chua_co_e995e679);
}

/** Câu hỏi lại trước khi xoá bản đọc của cuốn: nói điều người nghe sẽ thấy sau đó. */
export function clearCacheQuestion(usage: ReadAloudCacheUsage): string {
  return S.s_xoa_0_ban_doc_cua_cuon_nay_nghe_toi_dau_ma_c87be917(formatSize(usage.book));
}

/** Cài đặt > Giọng đọc: bản đọc đã làm của cả máy nặng bao nhiêu ("Bản đọc đã làm chiếm 148 MB trên máy này."). */
export function storageLabel(usage: Pick<ReadAloudCacheUsage, "total">): string {
  return usage.total > 0 ? S.s_ban_doc_da_lam_chiem_0_tren_may_nay_903201f2(formatSize(usage.total)) : S.s_chua_co_ban_doc_da_luu_18fe660f;
}

/** Câu hỏi lại trước khi dọn bản đọc của cả máy. */
export function clearStorageQuestion(usage: Pick<ReadAloudCacheUsage, "total">): string {
  return S.s_don_0_ban_doc_da_lam_cua_moi_cuon_may_se_d_224ee5c4(formatSize(usage.total));
}

/** Các chương chỉ-có-chữ ngay sau chương đang nghe (tối đa `limit`). */
export function upcomingTextChapters(queue: ListenChapter[], currentId: number, limit = 5): ListenChapter[] {
  const index = queue.findIndex((chapter) => chapter.id === currentId);
  return queue.slice(index + 1).filter((chapter) => chapter.state === "text").slice(0, limit);
}

/** Chữ các đoạn đúng như trình phát chia (cùng khoá bộ đệm với lúc nghe) - kể cả bỏ các dòng người nghe đã bỏ khỏi phần đọc. Dòng ngăn cảnh ("***")
 *  trình phát chỉ lặng, không đọc: không làm trước. */
export async function paragraphsFor(chapters: Pick<ListenChapter, "id" | "skip">[], text: (chapterId: number) => Promise<string>): Promise<string[]> {
  const out: string[] = [];
  for (const chapter of chapters) {
    for (const paragraph of splitParagraphs(withoutLines(await text(chapter.id), chapter.skip))) {
      if (!paragraph.sceneBreak) out.push(paragraph.text);
    }
  }
  return out;
}

/** Giọng nào có "Làm trước": giọng tải về đọc trên máy (VieNeu, Supertonic - chậm hơn tốc độ nghe trên máy yếu) ở mọi nơi; giọng trực tuyến khi
 *  nguồn làm trước được để nghe không cần mạng (điện thoại). Giọng của máy đã đọc nhanh, không cần mạng - không có. */
export function canPrepare(voice: Pick<ReadAloudVoice, "provider" | "online">, onlineToo: boolean): boolean {
  return voice.provider === "vieneu" || voice.provider === "supertonic" || (onlineToo && voice.online);
}

/** Câu mời khi chưa có việc: nói đúng cái lợi người nghe nhận được với giọng này. */
export function prepareIntro(voice: Pick<ReadAloudVoice, "online"> & Partial<Pick<ReadAloudVoice, "provider">>): string {
  // Giọng trực tuyến: làm trước là gửi chữ các chương ấy đi - nói thẳng chữ đi đâu (soát a79 lỗi 6), không chỉ nói cái lợi.
  return voice.online
    ? S.s_lam_truoc_de_nghe_khi_khong_co_mang_0_3cd15943(voice.provider ? S.s_chu_se_duoc_gui_toi_0_362780c4(onlineDestination(voice.provider)) : "")
    : S.s_may_doc_cham_lam_truoc_de_nghe_lien_mach_42dca0d0;
}

/** "khoảng 1 giờ 20 phút", "khoảng 12 phút", "dưới 1 phút". */
export function spokenDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return S.s_duoi_1_phut_a1dd4f60;
  if (minutes < 60) return S.s_khoang_0_phut_db610fec(minutes);
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return S.s_khoang_0_gio_1_7ba17859(hours, rest ? S.s_0_phut_1bea6774(rest) : "");
}

/** Ước thời gian máy cần để làm trước `chars` ký tự với tốc độ `rtf` (giây máy làm cho mỗi giây nghe; trình phát ước ~14 ký tự mỗi giây nghe). */
export function prepareSeconds(chars: number, rtf: number): number {
  return (chars / 14) * rtf;
}

/** Câu ước trước khi bấm: "Khoảng 2 giờ nghe · máy cần khoảng 1 giờ 50 phút." */
export function planLabel(plan: PreparePlan): string {
  if (!plan.chapters) return "";
  const listen = `${spokenDuration(plan.audioSeconds).replace(/^khoảng /, "")} nghe`;
  const machine = plan.secondsEstimate != null ? S.s_may_can_0_6e7b3653(spokenDuration(plan.secondsEstimate)) : "";
  const fits = plan.chapters < plan.offered ? S.s_vua_cho_trong_cho_0_chuong_6f9821bd(plan.chapters) : "";
  const text = `${fits}${listen}${machine}.`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const WAITING: Record<NonNullable<PrepareStatus["waitingFor"]>, string> = {
  charging: S.s_cho_cam_sac_2dc75384,
  wifi: S.s_cho_wi_fi_d0476dd8,
  battery: S.s_cho_pin_day_hon_d715a386,
  listening: S.s_nhuong_cho_chuong_dang_nghe_93babd54,
};

/** Câu nói tiến độ làm trước, theo điều người nghe cần biết. */
export function prepareLabel(status: PrepareStatus): string {
  const what = status.label || S.s_cac_chuong_toi_536a96b8;
  const listen = status.audioSeconds ? ` (${spokenDuration(status.audioSeconds).replace(S.s_khoang_934859d7, "")} nghe)` : "";
  const chapters = status.chapters;
  const ready = chapters ? S.s_da_san_sang_0_1_chuong_06edeb48(chapters.filter((chapter) => chapter.ready).length, chapters.length) : "";
  if (status.state === "running") {
    if (chapters) {
      const how = status.waitingFor ? ` · ${WAITING[status.waitingFor]}` : status.secondsLeft != null ? S.s_con_0_9531b6c6(spokenDuration(status.secondsLeft)) : "";
      return `${ready}${how}`;
    }
    const left = status.secondsLeft != null ? S.s_con_0_b23acf60(spokenDuration(status.secondsLeft)) : "";
    return S.s_dang_lam_truoc_0_1_2_3_doan_4_b696b41e(what, listen, status.done ?? 0, status.total ?? 0, left);
  }
  if (status.state === "done") {
    const partial = (status.offered ?? 0) > (status.total ?? 0) ? S.s_phan_con_lai_lam_tiep_khi_ban_nghe_toi_a3c9e257 : "";
    const gain = status.online ? S.s_nghe_duoc_ca_khi_khong_co_mang_9308f988 : S.s_nghe_lien_mach_khong_can_cho_35e14b83;
    if (chapters && chapters.some((chapter) => !chapter.ready)) return S.s_0_phan_con_lai_lam_tiep_khi_ban_nghe_toi_d5f3d6f8(ready);
    return S.s_da_lam_truoc_0_1_2_3_fc3aa7ee(what, listen, gain, partial);
  }
  if (status.state === "error") return status.error || S.s_lam_truoc_bi_dung_9e573747;
  if (status.state === "cancelled") return chapters ? S.s_da_dung_lam_truoc_0_1_786d6dfb(ready.charAt(0).toLowerCase(), ready.slice(1)) : S.s_da_dung_lam_truoc_3658da6b;
  return "";
}

/** Các chương của cuốn `bookId` đã làm sẵn bằng giọng `voice` (dấu ở danh sách chương); `voice` "" = giọng mặc định, việc nào của cuốn cũng tính. */
export function readyChapterIds(status: PrepareStatus | undefined, bookId: string, voice: string): Set<number> {
  if (!status?.chapters || status.bookId !== bookId || (voice && status.voice !== voice)) return new Set();
  return new Set(status.chapters.filter((chapter) => chapter.ready).map((chapter) => chapter.id));
}
