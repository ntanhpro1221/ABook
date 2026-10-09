// Mô-đun "Giọng VieNeu" (docs/LISTEN_ANYTHING.md mục 3): giọng đọc ngay trên máy cho "Nghe ngay", tải khi người dùng bấm - máy tính
// (abook/webui/vieneu_module.py) và điện thoại (mobile/android/.../vieneu/VieneuModule.kt) cùng một hình trạng thái. Mô-đun "Giọng Supertonic" của
// máy tính (abook/webui/supertonic_module.py) dùng cùng khung và cùng hình trạng thái, chỉ khác lời (`ModuleCopy`). Phần thuần (không React) để
// thử riêng; thẻ ở VieneuModuleCard.tsx.

import { CANCELLED_NOTE, formatSize } from "@/studio/musicLocal";

export type VieneuChoiceId = "turbo" | "nano" | "aligner" | "supertonic" | "fast";
/** Giọng có kết quả tự đo riêng (mỗi tầng một lần đo). */
export type ModuleTier = "turbo" | "nano" | "supertonic";

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
  /** Gỡ được khỏi máy này (điện thoại, giọng Supertonic). */
  removable?: boolean;
  /** Lựa chọn khác phải có cùng (bản tăng tốc cần Giọng VieNeu): đánh dấu cái này thì đánh dấu luôn cái kia. */
  requires?: VieneuChoiceId[];
}

/** Bản tăng tốc của giọng VieNeu (máy tính, Windows có AVX2): công tắc của người dùng, đang chạy thật không, và lý do khi nó không chạy được. */
export interface VieneuAccelerated {
  on: boolean;
  active: boolean;
  problem: string;
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
  tier: ModuleTier;
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
  benchmark: Partial<Record<ModuleTier, VieneuBenchmark>>;
  benchmarking: boolean;
  suggestion: VieneuSuggestion | null;
  device: { cores: number; ramGb: number; gpu: string; runs: string };
  recommended: "turbo" | "nano" | "supertonic";
  /** Mức RTF từ đó trở lên giọng không đọc trực tiếp kịp (vieneu_module.SLOW_RTF). */
  slowRtf?: number;
  /** Bản mới chỉ dùng được sau khi mở lại app. */
  restart?: boolean;
  /** Đang dùng mạng tính phí (dữ liệu di động của điện thoại): chỉ để nhắc, không chặn. */
  metered?: boolean;
  /** Lần tải vừa rồi bị người dùng huỷ: phần đã tải giữ, lần sau làm tiếp. */
  cancelled?: boolean;
  /** Có khi bản tăng tốc đã tải (máy tính). */
  accelerated?: VieneuAccelerated | null;
}

/** Câu nhắc trước khi tải bằng dữ liệu di động (null khi không cần nhắc). */
export function meteredNotice(status: Pick<VieneuStatus, "metered">, bytes: number): string | null {
  if (!status.metered || bytes <= 0) return null;
  return `Điện thoại đang dùng dữ liệu di động - tải ${formatSize(bytes)} có thể tốn tiền mạng. Nên chờ có Wi-Fi.`;
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

/** Đánh dấu / bỏ đánh dấu một lựa chọn: đánh dấu cái cần cái khác (bản tăng tốc cần Giọng VieNeu) thì đánh dấu cả hai; bỏ cái được cần thì bỏ luôn cái cần nó. */
export function toggleChoice(status: Pick<VieneuStatus, "choices">, picked: readonly VieneuChoiceId[], id: VieneuChoiceId, on: boolean): VieneuChoiceId[] {
  if (on) {
    const needed = status.choices.find((choice) => choice.id === id)?.requires ?? [];
    return [...new Set([...picked, id, ...needed])];
  }
  const dependants = status.choices.filter((choice) => choice.requires?.includes(id)).map((choice) => choice.id);
  return picked.filter((item) => item !== id && !dependants.includes(item));
}

/** Câu dưới công tắc bản tăng tốc: nói điều người nghe thấy (đọc nhanh hơn hay đang đọc bằng bản thường), không nói cách làm. */
export function acceleratedNote(state: VieneuAccelerated): string {
  if (!state.on) return "Đang đọc bằng bản thường.";
  if (state.problem) return "Máy này chưa chạy được bản tăng tốc nên đang đọc bằng bản thường. Bấm “Thử lại tốc độ” để thử lại.";
  return state.active ? "Đang đọc bằng bản tăng tốc." : "Bản tăng tốc sẽ dùng từ lần đọc kế.";
}

/** Lời của một mô-đun trong thẻ (giọng VieNeu hay giọng Supertonic): tên, tiêu đề, câu mời tải, các tầng đo, nơi lưu truy vấn. */
export interface ModuleCopy {
  key: string;
  /** Tên mô-đun, viết hoa đầu ("Giọng VieNeu"); giữa câu thì hạ chữ đầu. */
  name: string;
  title: string;
  invite: string;
  tiers: readonly ModuleTier[];
}

export const VIENEU_COPY: ModuleCopy = {
  key: "vieneu",
  name: "Giọng VieNeu",
  title: "Giọng VieNeu · tải thêm, đọc ngay trên máy",
  invite: "Đọc sách chỉ có chữ bằng giọng hay, ngay trên máy này - không cần mạng, chữ của sách không rời khỏi máy (app chỉ hỏi mạng lấy cấu hình và danh mục nhạc, không gửi chữ của sách). Tải một lần; tải xong máy tự thử vài giây xem có kịp đọc trực tiếp không.",
  tiers: ["turbo", "nano"],
};

export const SUPERTONIC_COPY: ModuleCopy = {
  key: "supertonic",
  name: "Giọng Supertonic",
  title: "Giọng Supertonic · tải thêm, đọc ngay trên máy",
  invite: "Mười giọng nam nữ đọc sách chỉ có chữ ngay trên máy này - nhẹ máy, không cần mạng, chữ của sách không rời khỏi máy (app chỉ hỏi mạng lấy cấu hình và danh mục nhạc, không gửi chữ của sách). Tải một lần; tải xong máy tự thử vài giây xem có kịp đọc trực tiếp không.",
  tiers: ["supertonic"],
};

const TIER_NAME: Record<ModuleTier, string> = { turbo: "Giọng VieNeu", nano: "Giọng VieNeu Nano", supertonic: "Giọng Supertonic" };

export function tierName(tier: ModuleTier): string {
  return TIER_NAME[tier];
}

/** Đầu mã giọng của một tầng ("vieneu:nano/", "supertonic:") - để đổi mọi cuốn đang dùng tầng ấy sang giọng khác. */
export function tierVoicePrefix(tier: ModuleTier): string {
  return tier === "supertonic" ? "supertonic:" : `vieneu:${tier}/`;
}

export function lowerFirst(text: string): string {
  return text.charAt(0).toLowerCase() + text.slice(1);
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
export function benchmarkLabel(tier: ModuleTier, result: VieneuBenchmark, live = LIVE_RTF): string {
  const name = tierName(tier);
  if (result.rtf >= live) {
    const hour = Math.max(1, Math.round(result.rtf * 60));
    return `${name}: máy này không kịp đọc trực tiếp (${seconds(result.rtf)} giây cho mỗi giây nghe). Vẫn nghe được bằng “Làm trước” trong nút Giọng đọc: mỗi giờ nghe máy cần làm trước khoảng ${hour} phút.`;
  }
  const speed = result.rtf > 0 ? 1 / result.rtf : 0;
  return `${name}: đọc trực tiếp được - máy này đọc nhanh gấp ${seconds(speed)} lần tốc độ nghe; đoạn đầu chương có tiếng sau khoảng ${seconds(result.firstAudioMs / 1000)} giây.`;
}

/** Lời đề nghị đổi giọng (không bao giờ tự đổi) và chữ trên nút. */
export function suggestionText(suggestion: VieneuSuggestion): { message: string; action: string } {
  const slow = tierName(suggestion.tier);
  const lead = `${slow} không theo kịp người nghe trên máy này (${seconds(suggestion.rtf)} giây cho mỗi giây nghe) - nghe trực tiếp có thể phải chờ giữa các đoạn. Giữ giọng này thì dùng “Làm trước”.`;
  if (suggestion.switchTo === "nano") {
    return suggestion.installed
      ? { message: `${lead} Giọng VieNeu Nano đọc nhẹ máy hơn và đã có trên máy.`, action: "Dùng giọng VieNeu Nano" }
      : { message: `${lead} Giọng VieNeu Nano đọc nhẹ máy hơn, hợp với máy này hơn.`, action: "Tải giọng VieNeu Nano" };
  }
  return { message: `${lead} Giọng trực tuyến không bắt máy làm việc này (cần mạng).`, action: "Dùng giọng trực tuyến" };
}

/** Câu chính của thẻ theo trạng thái. */
export function vieneuLabel(status: VieneuStatus, copy: ModuleCopy = VIENEU_COPY): string {
  const mid = lowerFirst(copy.name);
  if (status.state === "error") return status.error;
  if (status.state === "downloading") return `Đang tải ${mid} (${formatSize(status.total)}) ${vieneuPercent(status)}%`;
  if (status.benchmarking) return "Đang thử giọng vừa tải trên máy này (vài giây)…";
  if (status.state === "unsupported") return status.reason ? `Máy này chưa dùng được ${mid}: ${status.reason}.` : `Máy này chưa dùng được ${mid}.`;
  if (status.restart) return `${copy.name} đã cập nhật - mở lại ABook để dùng bản mới.`;
  const cancelled = status.cancelled ? `${CANCELLED_NOTE} ` : "";
  if (status.state === "outdated") return `${cancelled}${copy.name} có bản mới - ${formatSize(status.outdatedBytes)}. Bản đang dùng vẫn đọc bình thường.`;
  if (status.state === "ready") return `${copy.name} đã có trên máy: chọn trong nút Giọng đọc khi nghe sách chỉ có chữ.`;
  return `${cancelled}${copy.invite}`;
}
