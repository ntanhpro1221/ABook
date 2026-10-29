// "Tốc độ giọng trên máy" (máy tính: abook/webui/voice_speed.py, điện thoại: readaloud/VoiceSpeed.kt - cùng hình trạng thái): giọng Supertonic
// có hai bậc khi nghe trực tiếp (giọng VieNeu chỉ có một). Một lựa chọn cho cả máy. Phần thuần (không React) để thử riêng; dòng cài đặt ở VoiceSpeedSetting.tsx.

import { formatSize } from "@/shared/format";
import type { VieneuChoiceId } from "./vieneuModule";

export type VoiceSpeedChoice = "auto" | "quality" | "fast";
export type VoiceSpeedTier = "quality" | "fast";

/** Một giọng có hai bậc đã tải trên máy. */
export interface VoiceSpeedVoice {
  id: "supertonic";
  /** "Giọng Supertonic". */
  name: string;
  /** Mô-đun chứa nó (để tải bản nhanh hơn). */
  module: "supertonic";
  /** Lựa chọn của thẻ mô-đun ứng với bản nhanh hơn. */
  fastChoice: VieneuChoiceId;
  /** Tốc độ tự đo của bậc chất lượng (giây máy làm cho mỗi giây nghe); null = chưa đo. */
  rtf: number | null;
  /** Bậc mà lựa chọn muốn. */
  tier: VoiceSpeedTier;
  /** Bậc Nghe ngay đang đọc (muốn nhanh mà chưa tải bản nhanh hơn thì vẫn là chất lượng). */
  using: VoiceSpeedTier;
  /** Byte bản nhanh hơn còn thiếu (0 = đã có). */
  fastBytes: number;
}

export interface VoiceSpeedStatus {
  choice: VoiceSpeedChoice;
  voices: VoiceSpeedVoice[];
}

export const VOICE_SPEED_TITLE = "Tốc độ đọc";

export const VOICE_SPEED_OPTIONS: { value: VoiceSpeedChoice; label: string }[] = [
  { value: "auto", label: "Tự động" },
  { value: "quality", label: "Chất lượng cao nhất" },
  { value: "fast", label: "Nhanh hơn" },
];

/** Tóm tắt Hiệu năng chỉ nhắc lựa chọn hiện tại; giải thích nằm trong thân gập. */
export function voiceSpeedLabel(choice: VoiceSpeedChoice): string {
  return VOICE_SPEED_OPTIONS.find(option => option.value === choice)!.label;
}

const DESCRIPTION: Record<VoiceSpeedChoice, string> = {
  auto: "Máy kịp thì đọc bản hay nhất.",
  quality: "Luôn đọc bản hay nhất; máy chậm có thể phải chờ.",
  fast: "Nhanh hơn, tiếng kém hơn chút - hợp máy yếu.",
};

/** Câu dưới các nút chọn: lựa chọn ấy làm gì, và rằng sách bạn xuất ra luôn dùng bản hay nhất. */
export function voiceSpeedDescription(choice: VoiceSpeedChoice): string {
  return `${DESCRIPTION[choice]} Chỉ áp cho giọng Supertonic; sách xuất ra luôn dùng bản hay nhất.`;
}

const TIER_LABEL: Record<VoiceSpeedTier, string> = { quality: "Chất lượng cao nhất", fast: "Nhanh hơn" };

function why(voice: VoiceSpeedVoice, choice: VoiceSpeedChoice): string {
  if (choice !== "auto") return "bạn đã chọn";
  if (voice.rtf === null) return "chưa đo được tốc độ máy này";
  return voice.tier === "fast" ? "máy này đọc chậm hơn tốc độ nghe" : "máy này đọc kịp tốc độ nghe";
}

/** Dòng của một giọng: đang dùng bậc nào và vì sao; muốn bản nhanh hơn mà chưa tải thì nói cỡ cần tải. */
export function voiceSpeedLine(voice: VoiceSpeedVoice, choice: VoiceSpeedChoice): string {
  const lead = `${voice.name} - Đang dùng: ${TIER_LABEL[voice.using]} (${why(voice, choice)})`;
  if (voice.tier === "fast" && voice.using !== "fast") {
    return `${voice.name} - Đang dùng: ${TIER_LABEL.quality}. Bản nhanh hơn cần tải thêm ${formatSize(voice.fastBytes)}.`;
  }
  return `${lead}.`;
}

/** Giọng cần tải bản nhanh hơn (lựa chọn muốn bậc nhanh mà file chưa có). */
export function needsFastDownload(voice: VoiceSpeedVoice): boolean {
  return voice.tier === "fast" && voice.using !== "fast" && voice.fastBytes > 0;
}
