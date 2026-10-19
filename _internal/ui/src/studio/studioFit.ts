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
    const reason = "không có card đồ hoạ NVIDIA, hay driver NVIDIA chưa cài";
    return { level: "no", line: `Máy này ${reason}.`, reason };
  }
  if (!(gpu.memory > 0)) return { level: "maybe", line: `Card ${gpu.name}: chưa đọc được bộ nhớ của card, chưa biết có đủ không.` };
  const gb = cardGb(gpu.memory);
  const shown = `${gpu.name} (${Math.round(gb)} GB)`;
  if (gb >= STUDIO_TESTED_GB - 0.5) return { level: "ok", line: `Card ${shown}: đủ để làm sách nói (đã thử trên card ${STUDIO_TESTED_GB} GB).` };
  if (gb >= STUDIO_MIN_GB - 0.5) {
    return { level: "maybe", line: `Card ${shown}: có thể chạy được nhưng chưa thử trên card dưới ${STUDIO_TESTED_GB} GB, có thể chậm.` };
  }
  const reason = `card ${shown} ít bộ nhớ hơn mức tối thiểu ${STUDIO_MIN_GB} GB`;
  return { level: "no", line: `Card ${shown}: ít bộ nhớ hơn mức tối thiểu ${STUDIO_MIN_GB} GB.`, reason };
}

/** Câu nói thật khi máy không làm sách nói được - MỘT câu cho trình tạo sách, bước cuối và thẻ Cài Studio. */
export function noStudioLine(reason: string): string {
  return `Máy này không làm sách nói được (${reason}). Bạn vẫn nghe ngay mọi sách.`;
}
