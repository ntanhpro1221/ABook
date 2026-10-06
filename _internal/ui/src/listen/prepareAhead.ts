// "Làm trước" (abook/readaloud/prepare.py, docs/LISTEN_ANYTHING.md mục 3): máy đọc sẵn các chương sắp nghe vào bộ đệm ở nền, để giọng đọc chậm
// hơn tốc độ nghe (giọng VieNeu trên máy yếu) vẫn nghe liền mạch, và trên điện thoại để nghe được khi không có mạng (lõi native: PrepareAhead.kt -
// việc nền chỉ chạy khi đang sạc, Wi-Fi). Phần thuần để thử riêng; nút ở VoiceMenu (PlayerViews.tsx).

import type { ListenChapter } from "./model";
import type { ReadAloudVoice } from "./readAloud";
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
  chapters: Pick<ListenChapter, "id" | "title">[];
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

/** Giọng nào có "Làm trước": VieNeu (chậm hơn tốc độ nghe trên máy yếu) ở mọi nơi; giọng trực tuyến khi nguồn làm trước được để nghe không cần
 *  mạng (điện thoại). Giọng của máy đã đọc nhanh, không cần mạng - không có. */
export function canPrepare(voice: Pick<ReadAloudVoice, "provider" | "online">, onlineToo: boolean): boolean {
  return voice.provider === "vieneu" || (onlineToo && voice.online);
}

/** Câu mời khi chưa có việc: nói đúng cái lợi người nghe nhận được với giọng này. */
export function prepareIntro(voice: Pick<ReadAloudVoice, "online">): string {
  return voice.online
    ? "Sắp không có mạng (tàu điện, máy bay)? Làm trước các chương tới để nghe được cả khi không có mạng."
    : "Máy đọc chậm? Làm trước các chương tới ở nền để nghe liền mạch, không phải chờ giữa các đoạn.";
}

/** "khoảng 1 giờ 20 phút", "khoảng 12 phút", "dưới 1 phút". */
export function spokenDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return "dưới 1 phút";
  if (minutes < 60) return `khoảng ${minutes} phút`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `khoảng ${hours} giờ${rest ? ` ${rest} phút` : ""}`;
}

/** Ước thời gian máy cần để làm trước `chars` ký tự với tốc độ `rtf` (giây máy làm cho mỗi giây nghe; trình phát ước ~14 ký tự mỗi giây nghe). */
export function prepareSeconds(chars: number, rtf: number): number {
  return (chars / 14) * rtf;
}

/** Câu ước trước khi bấm: "Khoảng 2 giờ nghe · máy cần khoảng 1 giờ 50 phút." */
export function planLabel(plan: PreparePlan): string {
  if (!plan.chapters) return "";
  const listen = `${spokenDuration(plan.audioSeconds).replace(/^khoảng /, "")} nghe`;
  const machine = plan.secondsEstimate != null ? ` · máy cần ${spokenDuration(plan.secondsEstimate)}` : "";
  const fits = plan.chapters < plan.offered ? `Vừa chỗ trống cho ${plan.chapters} chương: ` : "";
  const text = `${fits}${listen}${machine}.`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const WAITING: Record<NonNullable<PrepareStatus["waitingFor"]>, string> = {
  charging: "chờ cắm sạc",
  wifi: "chờ Wi-Fi",
  battery: "chờ pin đầy hơn",
  listening: "nhường cho chương đang nghe",
};

/** Câu nói tiến độ làm trước, theo điều người nghe cần biết. */
export function prepareLabel(status: PrepareStatus): string {
  const what = status.label || "các chương tới";
  const listen = status.audioSeconds ? ` (${spokenDuration(status.audioSeconds).replace("khoảng ", "")} nghe)` : "";
  const chapters = status.chapters;
  const ready = chapters ? `Đã sẵn sàng ${chapters.filter((chapter) => chapter.ready).length}/${chapters.length} chương` : "";
  if (status.state === "running") {
    if (chapters) {
      const how = status.waitingFor ? ` · ${WAITING[status.waitingFor]}` : status.secondsLeft != null ? ` · còn ${spokenDuration(status.secondsLeft)}` : "";
      return `${ready}${how}`;
    }
    const left = status.secondsLeft != null ? `, còn ${spokenDuration(status.secondsLeft)}` : "";
    return `Đang làm trước ${what}${listen}: ${status.done ?? 0}/${status.total ?? 0} đoạn${left}.`;
  }
  if (status.state === "done") {
    const partial = (status.offered ?? 0) > (status.total ?? 0) ? " - phần còn lại làm tiếp khi bạn nghe tới" : "";
    const gain = status.online ? "nghe được cả khi không có mạng" : "nghe liền mạch, không cần chờ";
    if (chapters && chapters.some((chapter) => !chapter.ready)) return `${ready} - phần còn lại làm tiếp khi bạn nghe tới.`;
    return `Đã làm trước ${what}${listen}: ${gain}${partial}.`;
  }
  if (status.state === "error") return status.error || "Làm trước bị dừng.";
  if (status.state === "cancelled") return chapters ? `Đã dừng làm trước (${ready.charAt(0).toLowerCase()}${ready.slice(1)}).` : "Đã dừng làm trước.";
  return "";
}

/** Các chương của cuốn `bookId` đã làm sẵn bằng giọng `voice` (dấu ở danh sách chương); `voice` "" = giọng mặc định, việc nào của cuốn cũng tính. */
export function readyChapterIds(status: PrepareStatus | undefined, bookId: string, voice: string): Set<number> {
  if (!status?.chapters || status.bookId !== bookId || (voice && status.voice !== voice)) return new Set();
  return new Set(status.chapters.filter((chapter) => chapter.ready).map((chapter) => chapter.id));
}
