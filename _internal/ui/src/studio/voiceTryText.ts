import { formatLength, formatNumber } from "@/shared/format";

// "Nghe thử bằng câu của sách" (webui/reading_preview.py `voice_preview`): máy đọc một câu của chính nhân vật bằng giọng đang
// cân nhắc, trước khi đổi giọng - hộp "Đổi giọng" và hộp "Áp dụng". Phần thuần ở đây để thử được không cần giao diện.

export type GenderFilter = "male" | "female" | "all";

/** Đủ để máy chủ dựng đúng giọng sẽ áp (cùng phép POST /voice): giọng đã chọn, hay giới, hay giọng cần tránh. */
export interface VoiceRequest {
  character: string;
  preset?: string;
  gender?: string;
  avoid?: string;
}

/** Đổi giọng là thu lại mọi câu đã thu của người ấy (voice_picker.py `rerecord`). */
export interface Rerecord {
  lines: number;
  seconds: number;
  /** False: cuốn chưa xong chương nào để đo - thời gian là số ước dư tay. */
  measured: boolean;
}

/** Danh sách dài (57 giọng): lọc Nam / Nữ / Tất cả, giữ thứ tự máy chủ gửi. */
export function byGender<V extends { gender: string }>(voices: readonly V[], filter: GenderFilter): V[] {
  return filter === "all" ? [...voices] : voices.filter((voice) => voice.gender === filter);
}

/** Thời gian thu lại: số đo của chính cuốn ("trên máy này"), hay số ước khi chưa đo được - nói rõ là ước. `measured`
 *  không có (máy chủ cũ) thì coi như số đo. */
export function estimateText(seconds: number, measured?: boolean): string {
  const length = seconds < 60 ? "chưa tới 1 phút" : `khoảng ${formatLength(seconds)}`;
  return measured === false ? `${length} - ước chừng, vì cuốn chưa xong chương nào để đo` : `${length} trên máy này`;
}

/** Một dòng trong hộp "Đổi giọng": đổi giọng tốn gì. */
export function rerecordText(name: string, cost: Rerecord): string {
  if (!cost.lines) return `Chưa câu nào của ${name} được thu - đổi giọng không phải thu lại gì.`;
  return `Đổi giọng là thu lại ${formatNumber(cost.lines)} câu đã thu của ${name}, ${estimateText(cost.seconds, cost.measured)}.`;
}

/** Khoá bản nghe thử trong phiên: cùng sách, cùng người, cùng giọng thì phát lại, không hỏi máy chủ. */
export function tryKey(bookId: string, request: VoiceRequest): string {
  return [bookId, request.character, request.preset ?? "", request.gender ?? "", request.avoid ?? ""].join("\u0000");
}
