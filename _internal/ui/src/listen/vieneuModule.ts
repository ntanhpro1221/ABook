// Mô-đun "Giọng VieNeu" của máy tính (abook/webui/vieneu_module.py, docs/LISTEN_ANYTHING.md mục 3): giọng đọc ngay trên máy cho "Nghe ngay",
// tải khi người dùng bấm. Phần thuần (không React) để thử riêng; thẻ ở VieneuModuleCard.tsx.

import { formatSize } from "@/studio/musicLocal";

export type VieneuChoiceId = "turbo" | "nano" | "aligner";

export interface VieneuChoice {
  id: VieneuChoiceId;
  label: string;
  detail: string;
  /** Các phần lựa chọn này cần (phần dùng chung như thư viện chạy model chỉ tính một lần). */
  needs: string[];
  /** Byte máy này còn thiếu cho riêng lựa chọn này. */
  bytes: number;
  installed: boolean;
  /** "Khuyên dùng" cho máy này (theo số lõi, RAM). */
  recommended: boolean;
  /** Đánh dấu sẵn lần đầu. */
  default: boolean;
}

export interface VieneuPart {
  id: string;
  label: string;
  bytes: number;
  state: "current" | "outdated" | "missing";
  external?: boolean;
}

export interface VieneuBenchmark {
  /** Giây máy làm cho mỗi giây nghe được (dưới 1 là kịp). */
  rtf: number;
  firstAudioMs: number;
}

export interface VieneuSuggestion {
  tier: "turbo" | "nano";
  rtf: number;
  /** Đổi sang Nano, hay sang giọng trực tuyến khi Nano cũng chậm. */
  switchTo: "nano" | "online";
  /** Giọng đề nghị đã có trên máy (không thì phải tải). */
  installed: boolean;
}

export interface VieneuStatus {
  state: "missing" | "downloading" | "ready" | "outdated" | "error" | "unsupported";
  done: number;
  total: number;
  error: string;
  supported: boolean;
  reason: string;
  choices: VieneuChoice[];
  parts: VieneuPart[];
  outdatedParts: string[];
  outdatedBytes: number;
  benchmark: Partial<Record<"turbo" | "nano", VieneuBenchmark>>;
  benchmarking: boolean;
  suggestion: VieneuSuggestion | null;
  device: { cores: number; ramGb: number; gpu: string; runs: string };
  recommended: "turbo" | "nano";
  /** Mức RTF từ đó trở lên giọng không đọc trực tiếp kịp (vieneu_module.SLOW_RTF). */
  slowRtf?: number;
  /** Bản mới chỉ dùng được sau khi mở lại app. */
  restart?: boolean;
}

/** Byte phải tải cho các lựa chọn đang đánh dấu: hợp các phần còn thiếu, phần dùng chung tính một lần. */
export function selectionBytes(status: Pick<VieneuStatus, "choices" | "parts">, chosen: readonly VieneuChoiceId[]): number {
  const parts = new Map(status.parts.map((part) => [part.id, part]));
  const wanted = new Set(status.choices.filter((choice) => chosen.includes(choice.id)).flatMap((choice) => choice.needs));
  let total = 0;
  for (const id of wanted) {
    const part = parts.get(id);
    if (part && part.state !== "current") total += part.bytes;
  }
  return total;
}

/** Lựa chọn đánh dấu sẵn: cái đã tải + cái mô-đun đánh dấu sẵn cho máy này. */
export function initialChoices(status: Pick<VieneuStatus, "choices">): VieneuChoiceId[] {
  return status.choices.filter((choice) => choice.installed || choice.default).map((choice) => choice.id);
}

export function vieneuPercent(status: Pick<VieneuStatus, "done" | "total">): number {
  return status.total > 0 ? Math.min(100, Math.floor((status.done / status.total) * 100)) : 0;
}

function seconds(value: number): string {
  return value.toFixed(1).replace(".", ",");
}

/** Dưới mức này giọng đọc trực tiếp được (còn chỗ cho đọc trước, nghe nhanh); trên thì nên "Làm trước" (vieneu_module.SLOW_RTF). */
export const LIVE_RTF = 0.8;

/** Câu nói kết quả tự đo, theo điều người nghe cần biết: đọc trực tiếp kịp không, không kịp thì "Làm trước" mất bao lâu. */
export function benchmarkLabel(tier: "turbo" | "nano", result: VieneuBenchmark, live = LIVE_RTF): string {
  const name = tier === "turbo" ? "Giọng VieNeu" : "Giọng VieNeu Nano";
  if (result.rtf >= live) {
    const hour = Math.max(1, Math.round(result.rtf * 60));
    return `${name}: máy này không kịp đọc trực tiếp (${seconds(result.rtf)} giây cho mỗi giây nghe). Vẫn nghe được bằng “Làm trước” trong nút Giọng đọc: mỗi giờ nghe máy cần làm trước khoảng ${hour} phút.`;
  }
  const speed = result.rtf > 0 ? 1 / result.rtf : 0;
  return `${name}: đọc trực tiếp được - máy này đọc nhanh gấp ${seconds(speed)} lần tốc độ nghe; đoạn đầu chương có tiếng sau khoảng ${seconds(result.firstAudioMs / 1000)} giây.`;
}

/** Lời đề nghị đổi giọng (không bao giờ tự đổi) và chữ trên nút. */
export function suggestionText(suggestion: VieneuSuggestion): { message: string; action: string } {
  const slow = suggestion.tier === "turbo" ? "Giọng VieNeu" : "Giọng VieNeu Nano";
  const lead = `${slow} không theo kịp người nghe trên máy này (${seconds(suggestion.rtf)} giây cho mỗi giây nghe) - nghe trực tiếp có thể phải chờ giữa các đoạn. Giữ giọng này thì dùng “Làm trước”.`;
  if (suggestion.switchTo === "nano") {
    return suggestion.installed
      ? { message: `${lead} Giọng VieNeu Nano nhẹ hơn và đã có trên máy.`, action: "Dùng giọng VieNeu Nano" }
      : { message: `${lead} Giọng VieNeu Nano nhẹ hơn, hợp với máy này hơn.`, action: "Tải giọng VieNeu Nano" };
  }
  return { message: `${lead} Giọng trực tuyến không bắt máy làm việc này (cần mạng).`, action: "Dùng giọng trực tuyến" };
}

/** Câu chính của thẻ theo trạng thái. */
export function vieneuLabel(status: VieneuStatus): string {
  if (status.state === "error") return status.error;
  if (status.state === "downloading") return `Đang tải giọng VieNeu (${formatSize(status.total)}) ${vieneuPercent(status)}%`;
  if (status.benchmarking) return "Đang thử giọng vừa tải trên máy này (vài giây)…";
  if (status.state === "unsupported") return status.reason ? `Máy này chưa dùng được giọng VieNeu: ${status.reason}.` : "Máy này chưa dùng được giọng VieNeu.";
  if (status.restart) return "Giọng VieNeu đã cập nhật - mở lại ABook để dùng bản mới.";
  if (status.state === "outdated") return `Giọng VieNeu có bản mới - ${formatSize(status.outdatedBytes)}. Bản đang dùng vẫn đọc bình thường.`;
  if (status.state === "ready") return "Giọng VieNeu đã có trên máy: chọn trong nút Giọng đọc khi nghe sách chỉ có chữ.";
  return "Đọc sách chỉ có chữ bằng giọng hay, ngay trên máy này - không cần mạng, chữ của sách không rời khỏi máy. Tải một lần; tải xong máy tự thử vài giây xem có kịp đọc trực tiếp không.";
}
