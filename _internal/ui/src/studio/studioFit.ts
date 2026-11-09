import { S } from "../shared/strings.generated";
// Máy này có đủ để làm sách nói không - nói TRƯỚC khi bấm Cài Studio (soát a64): máy chủ dò card NVIDIA ngay khi màn Studio hỏi
// (webui/studio_setup.py `detected_gpu`), ở đây chỉ đổi số ra lời. Ngưỡng do Lead chốt: từ 8 GB đủ (dây chuyền đã chạy trên card 8 GB),
// 6-8 GB có thể chạy nhưng chưa thử, dưới 6 GB hay không có NVIDIA là không đủ.

export interface StudioGpu {
  name: string;
  /** Bộ nhớ của card (byte, NVML). */
  memory: number;
}

export type StudioFitLevel = "ok" | "maybe" | "no";

export interface StudioFit {
  level: StudioFitLevel;
  /** Câu về card này cho người dùng (một câu, có dấu chấm). */
  line: string;
  /** Máy không đủ: vì sao, viết để đặt trong ngoặc của `noStudioLine`. */
  reason?: string;
}

/** Bộ nhớ card đã thử thật (GB). */
export const STUDIO_TESTED_GB = 8;
/** Dưới mức này máy không làm sách nói được. */
export const STUDIO_MIN_GB = 6;

/** NVML báo cỡ thật của card, hơi dưới số in trên hộp (card "8 GB" báo ~7,99 GiB): so với ngưỡng trừ đi nửa GB. */
function cardGb(memory: number): number {
  return memory / 2 ** 30;
}

export function studioFit(gpu: StudioGpu | null): StudioFit {
  if (!gpu) {
    const reason = S.s_khong_co_card_do_hoa_nvidia_hay_driver_nvi_a6c48055;
    return { level: "no", line: S.s_may_nay_0_5e3f5d8a(reason), reason };
  }
  if (!(gpu.memory > 0)) return { level: "maybe", line: S.s_card_0_chua_doc_duoc_bo_nho_cua_card_chua_4cd85240(gpu.name) };
  const gb = cardGb(gpu.memory);
  const shown = `${gpu.name} (${Math.round(gb)} GB)`;
  if (gb >= STUDIO_TESTED_GB - 0.5) return { level: "ok", line: S.s_card_0_du_de_lam_sach_noi_da_thu_tren_card_b5a4639b(shown, STUDIO_TESTED_GB) };
  if (gb >= STUDIO_MIN_GB - 0.5) {
    return { level: "maybe", line: S.s_card_0_co_the_chay_duoc_nhung_chua_thu_tre_de6af127(shown, STUDIO_TESTED_GB) };
  }
  const reason = S.s_card_0_it_bo_nho_hon_muc_toi_thieu_1_gb_ecc94a35(shown, STUDIO_MIN_GB);
  return { level: "no", line: S.s_card_0_it_bo_nho_hon_muc_toi_thieu_1_gb_0f9b6322(shown, STUDIO_MIN_GB), reason };
}

/** Câu nói thật khi máy không làm sách nói được - MỘT câu cho trình tạo sách, bước cuối và thẻ Cài Studio. */
export function noStudioLine(reason: string): string {
  return S.s_may_nay_khong_lam_sach_noi_duoc_0_ban_van_cd426a59(reason);
}
