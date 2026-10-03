// "Làm trước" (abook/readaloud/prepare.py, docs/LISTEN_ANYTHING.md mục 3): máy đọc sẵn các chương sắp nghe vào bộ đệm ở nền, để giọng đọc chậm
// hơn tốc độ nghe (giọng VieNeu trên máy yếu) vẫn nghe liền mạch. Phần thuần để thử riêng; nút ở VoiceMenu (PlayerViews.tsx).

import type { ListenChapter } from "./model";
import { paragraphsOf, withoutLines } from "./textScript";

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
}

/** Các chương chỉ-có-chữ ngay sau chương đang nghe (tối đa `limit`). */
export function upcomingTextChapters(queue: ListenChapter[], currentId: number, limit = 5): ListenChapter[] {
  const index = queue.findIndex((chapter) => chapter.id === currentId);
  return queue.slice(index + 1).filter((chapter) => chapter.state === "text").slice(0, limit);
}

/** Chữ các đoạn đúng như trình phát chia (cùng khoá bộ đệm với lúc nghe) - kể cả bỏ các dòng người nghe đã bỏ khỏi phần đọc. */
export async function paragraphsFor(chapters: ListenChapter[], text: (chapterId: number) => Promise<string>): Promise<string[]> {
  const out: string[] = [];
  for (const chapter of chapters) out.push(...paragraphsOf(withoutLines(await text(chapter.id), chapter.skip)));
  return out;
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

/** Câu nói tiến độ làm trước, theo điều người nghe cần biết. */
export function prepareLabel(status: PrepareStatus): string {
  const what = status.label || "các chương tới";
  const listen = status.audioSeconds ? ` (${spokenDuration(status.audioSeconds).replace("khoảng ", "")} nghe)` : "";
  if (status.state === "running") {
    const left = status.secondsLeft != null ? `, còn ${spokenDuration(status.secondsLeft)}` : "";
    return `Đang làm trước ${what}${listen}: ${status.done ?? 0}/${status.total ?? 0} đoạn${left}.`;
  }
  if (status.state === "done") {
    const partial = (status.offered ?? 0) > (status.total ?? 0) ? " - phần còn lại làm tiếp khi bạn nghe tới" : "";
    return `Đã làm trước ${what}${listen}: nghe liền mạch, không cần chờ${partial}.`;
  }
  if (status.state === "error") return status.error || "Làm trước bị dừng.";
  if (status.state === "cancelled") return "Đã dừng làm trước.";
  return "";
}
