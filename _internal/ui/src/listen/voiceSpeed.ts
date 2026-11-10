import { S } from "../shared/strings.generated";
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

export const VOICE_SPEED_TITLE = S.s_chat_luong_giong_5d1c8e07;

export const VOICE_SPEED_OPTIONS: { value: VoiceSpeedChoice; label: string }[] = [
  { value: "auto", label: S.s_tu_dong_a25c8028 },
  { value: "quality", label: S.s_chat_luong_cao_nhat_74af310a },
  { value: "fast", label: S.s_nhanh_hon_ecd73c9a },
];

/** Tóm tắt Hiệu năng chỉ nhắc lựa chọn hiện tại; giải thích nằm trong thân gập. */
export function voiceSpeedLabel(choice: VoiceSpeedChoice): string {
  return VOICE_SPEED_OPTIONS.find(option => option.value === choice)!.label;
}

const DESCRIPTION: Record<VoiceSpeedChoice, string> = {
  auto: S.s_may_kip_thi_doc_ban_hay_nhat_afe3d688,
  quality: S.s_luon_doc_ban_hay_nhat_may_cham_co_the_phai_2de7d693,
  fast: S.s_nhanh_hon_tieng_kem_hon_chut_hop_may_yeu_d7e135a1,
};

/** Câu dưới các nút chọn: lựa chọn ấy làm gì, và rằng sách bạn xuất ra luôn dùng bản hay nhất. */
export function voiceSpeedDescription(choice: VoiceSpeedChoice): string {
  return S.s_0_chi_ap_cho_giong_supertonic_sach_xuat_ra_ebca17bb(DESCRIPTION[choice]);
}

const TIER_LABEL: Record<VoiceSpeedTier, string> = { quality: S.s_chat_luong_cao_nhat_74af310a, fast: S.s_nhanh_hon_ecd73c9a };

function why(voice: VoiceSpeedVoice, choice: VoiceSpeedChoice): string {
  if (choice !== "auto") return S.s_ban_da_chon_f4117fe4;
  if (voice.rtf === null) return S.s_chua_do_duoc_toc_do_may_nay_6a6f6928;
  return voice.tier === "fast" ? S.s_may_nay_doc_cham_hon_toc_do_nghe_1766f852 : S.s_may_nay_doc_kip_toc_do_nghe_aa82c4ab;
}

/** Dòng của một giọng: đang dùng bậc nào và vì sao; muốn bản nhanh hơn mà chưa tải thì nói cỡ cần tải. */
export function voiceSpeedLine(voice: VoiceSpeedVoice, choice: VoiceSpeedChoice): string {
  const lead = S.s_0_dang_dung_1_2_44e852fc(voice.name, TIER_LABEL[voice.using], why(voice, choice));
  if (voice.tier === "fast" && voice.using !== "fast") {
    return S.s_0_dang_dung_1_ban_nhanh_hon_can_tai_them_2_59000948(voice.name, TIER_LABEL.quality, formatSize(voice.fastBytes));
  }
  return `${lead}.`;
}

/** Giọng cần tải bản nhanh hơn (lựa chọn muốn bậc nhanh mà file chưa có). */
export function needsFastDownload(voice: VoiceSpeedVoice): boolean {
  return voice.tier === "fast" && voice.using !== "fast" && voice.fastBytes > 0;
}
