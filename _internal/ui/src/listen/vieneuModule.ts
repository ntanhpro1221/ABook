import { S } from "../shared/strings.generated";
// Mô-đun "Giọng VieNeu" (docs/LISTEN_ANYTHING.md mục 3): giọng đọc ngay trên máy cho "Nghe ngay", tải khi người dùng bấm - máy tính
// (abook/webui/vieneu_module.py) và điện thoại (mobile/android/.../vieneu/VieneuModule.kt) cùng một hình trạng thái. Mô-đun "Giọng Supertonic" của
// máy tính (abook/webui/supertonic_module.py) dùng cùng khung và cùng hình trạng thái, chỉ khác lời (`ModuleCopy`). Phần thuần (không React) để
// thử riêng; thẻ ở VieneuModuleCard.tsx.

import { spokenProgress } from "@/shared/progressSpeech";
import { formatSize } from "@/shared/format";
import { CANCELLED_NOTE, RETRYING_NOTE } from "@/studio/musicLocal";

export type VieneuChoiceId = "turbo" | "nano" | "aligner" | "supertonic" | "fast" | "supertonic_fast";
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
  /** Nguyên văn lỗi của lần tải hỏng (`error`), thu trong "Chi tiết" (studio_setup.download_failure / PinnedFiles.failure). */
  errorDetail?: string;
  /** Lần tải vừa rồi bị người dùng huỷ: phần đã tải giữ, lần sau làm tiếp. */
  cancelled?: boolean;
  /** Đang tải mà mạng vừa hỏng, đang chờ thử lại (RETRYING_NOTE). */
  retrying?: boolean;
  /** Có khi bản tăng tốc đã tải (máy tính). */
  accelerated?: VieneuAccelerated | null;
  /** Lý do máy này không chạy được bản tăng tốc (lựa chọn ấy ẩn đi nhưng thẻ vẫn nói); rỗng/thiếu = chạy được. */
  fastUnsupported?: string;
}

/** Câu nhắc trước khi tải bằng dữ liệu di động (null khi không cần nhắc). */
export function meteredNotice(status: Pick<VieneuStatus, "metered">, bytes: number): string | null {
  if (!status.metered || bytes <= 0) return null;
  return S.s_dien_thoai_dang_dung_du_lieu_di_dong_tai_0_8aee54f4(formatSize(bytes));
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

/** Dòng mờ khi máy không chạy được bản tăng tốc (không ẩn im lặng); null khi không có gì để nói. */
export function fastUnsupportedNote(status: Pick<VieneuStatus, "fastUnsupported">): string | null {
  return status.fastUnsupported ? S.s_ban_tang_toc_may_nay_khong_chay_duoc_0_2d47887c(status.fastUnsupported) : null;
}

/** Câu dưới công tắc bản tăng tốc: nói điều người nghe thấy (đọc nhanh hơn hay đang đọc bằng bản thường), không nói cách làm. */
export function acceleratedNote(state: VieneuAccelerated): string {
  if (!state.on) return S.s_dang_doc_bang_ban_thuong_1621d77e;
  if (state.problem) return S.s_may_nay_chua_chay_duoc_ban_tang_toc_dang_d_b34f3faf;
  return state.active ? S.s_dang_doc_bang_ban_tang_toc_c2dce725 : S.s_ban_tang_toc_se_dung_tu_lan_doc_ke_12b359e4;
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
  name: S.s_giong_vieneu_371ad9fb,
  title: S.s_giong_vieneu_371ad9fb,
  invite: S.s_giong_hay_doc_ngay_tren_may_khong_can_mang_69bed8de,
  tiers: ["turbo", "nano"],
};

export const SUPERTONIC_COPY: ModuleCopy = {
  key: "supertonic",
  name: S.s_giong_supertonic_9922ded4,
  title: S.s_giong_supertonic_9922ded4,
  invite: S.s_muoi_giong_nam_nu_nhe_may_khong_can_mang_c_4e018b39,
  tiers: ["supertonic"],
};

/** Khoá truy vấn của dòng "Tốc độ giọng trên máy" (VoiceSpeedSetting.tsx). */
export const VOICE_SPEED_KEY = ["readaloud", "voice-speed"] as const;

/** Mọi thứ trong Cài đặt có cỡ "còn phải tải" tính cả phần dùng chung giữa các giọng (thư viện chạy model, bộ đọc chữ): thẻ VieNeu, thẻ Supertonic, dòng
 *  "Tốc độ giọng trên máy". Một mô-đun cài / gỡ xong thì hỏi lại cả ba - trước đây thẻ VieNeu còn ghi 271 MB sau khi Supertonic đã cài phần chung (đúng là
 *  228 MB) tới khi ra vào lại Cài đặt (soát a65). */
export const MODULE_QUERY_KEYS: readonly (readonly string[])[] = [["readaloud", VIENEU_COPY.key], ["readaloud", SUPERTONIC_COPY.key], VOICE_SPEED_KEY];

export function refreshModuleSizes(client: { invalidateQueries(filters: { queryKey: readonly unknown[] }): unknown }): void {
  for (const queryKey of MODULE_QUERY_KEYS) void client.invalidateQueries({ queryKey });
}

const TIER_NAME: Record<ModuleTier, string> = { turbo: S.s_giong_vieneu_371ad9fb, nano: S.s_giong_vieneu_nano_dc5fdeb6, supertonic: S.s_giong_supertonic_9922ded4 };

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

/** Những cuốn trong thư viện máy này đang dùng giọng của một mô-đun (voice_picker.engine_use): hỏi trước khi gỡ. */
export interface VoiceUse {
  bookCount: number;
  peopleCount: number;
  /** Câu của những người đó chưa thu: gỡ mô-đun thì các câu ấy không đọc được tới khi tải lại hay đổi giọng. */
  left: number;
  books: { title: string; people: string[]; left: number }[];
}

/** Lời hỏi trước khi gỡ một giọng khỏi máy, nói từ phía người nghe: cuốn nào còn cần, câu nào sẽ không đọc được. `use` null: không biết
 *  (máy này không có sách dùng giọng ấy, hay chưa hỏi được) - vẫn hỏi một câu ngắn. */
export function removeAsk(use: VoiceUse | null): string {
  if (!use) return S.s_giong_se_khong_con_tren_may_nay_cho_toi_kh_cb683781;
  if (!use.bookCount) return S.s_chua_cuon_nao_dung_giong_nay_ban_tai_lai_d_7cef0995;
  const titles = use.books.slice(0, 3).map((book) => `“${book.title}”`).join(", ");
  const more = use.bookCount > 3 ? S.s_va_0_cuon_khac_718f50c0(use.bookCount - 3) : "";
  const who = S.s_0_cuon_dang_dung_giong_nay_1_2_3_nhan_vat_3f43fca5(use.bookCount, titles, more, use.peopleCount);
  const rest = use.left
    ? S.s_0_cau_chua_thu_se_im_toi_khi_ban_tai_lai_g_e35ca678(use.left)
    : S.s_cac_cau_da_thu_van_nghe_duoc_a3a367c7;
  return `${who} ${rest}`;
}

/** Lựa chọn đánh dấu sẵn: cái đã tải + cái mô-đun đánh dấu sẵn cho máy này (`preselect` = false: chỉ cái đã tải - mô-đun không phải cái
 *  được khuyên, moduleAdvice). */
export function initialChoices(status: Pick<VieneuStatus, "choices">, preselect = true): VieneuChoiceId[] {
  return status.choices.filter((choice) => choice.installed || (preselect && choice.default)).map((choice) => choice.id);
}

/** Cài đặt có hai mô-đun giọng trên máy (VieNeu, Supertonic) mà người mới chỉ cần một (soát a66: cả hai thẻ đánh dấu sẵn, ~500 MB, không lời
 *  khuyên). Khuyên theo cách app chọn giọng mặc định: giọng VieNeu (narratorVoice - readAloudVoice.ts) ở bản máy này được khuyên (Turbo / Nano);
 *  Supertonic chỉ đánh dấu sẵn khi máy không chạy được VieNeu. `advice`: một dòng đặt trên hai thẻ, rỗng khi máy đã có một trong hai. */
export function moduleAdvice(vieneu: Pick<VieneuStatus, "state" | "choices" | "recommended"> | undefined, supertonic: Pick<VieneuStatus, "choices"> | undefined): {
  advice: string;
  preselectSupertonic: boolean;
} {
  const has = (status: Pick<VieneuStatus, "choices"> | undefined) => Boolean(status?.choices.some((choice) => choice.installed));
  // Trạng thái VieNeu chưa về: chưa đánh dấu gì ở Supertonic (tích sẵn rồi bỏ tích ngay trước mắt người dùng thì rối).
  if (vieneu === undefined) return { advice: "", preselectSupertonic: false };
  if (vieneu.state === "unsupported") return { advice: "", preselectSupertonic: true };
  if (has(vieneu) || has(supertonic)) return { advice: "", preselectSupertonic: false };
  const name = lowerFirst(tierName(vieneu.recommended === "nano" ? "nano" : "turbo"));
  return {
    advice: S.s_nen_dung_0_chi_can_tai_mot_bo_giong_46fb0d74(name),
    preselectSupertonic: false,
  };
}

/** Khối "Không có mạng" của trình phát mời tải NHẸ NHẤT đủ đọc: đúng một giọng VieNeu máy này được khuyên (`recommended`: Turbo hay Nano, cùng cách
 *  thẻ trong Cài đặt đánh dấu), không kèm "Tô đúng từng chữ" hay "Bản tăng tốc" - gói đánh dấu sẵn của Cài đặt (`full`) là lựa chọn phụ (soát a64: khối
 *  ấy từng mời 535 MB). Chỉ phần còn thiếu. */
export function offlineChoices(status: Pick<VieneuStatus, "choices" | "recommended">): { light: VieneuChoiceId[]; full: VieneuChoiceId[] } {
  const missing = (ids: VieneuChoiceId[]) => ids.filter((id) => !status.choices.find((choice) => choice.id === id)?.installed);
  const tier: VieneuChoiceId = status.recommended === "nano" ? "nano" : "turbo";
  const light = status.choices.some((choice) => choice.id === tier) ? missing([tier]) : [];
  return { light, full: missing(initialChoices(status)) };
}

export function vieneuPercent(status: Pick<VieneuStatus, "done" | "total">): number {
  return status.total > 0 ? Math.min(100, Math.floor((status.done / status.total) * 100)) : 0;
}

export function seconds(value: number): string {
  return value.toFixed(1).replace(".", ",");
}

/** Dưới mức này giọng đọc trực tiếp được (còn chỗ cho đọc trước, nghe nhanh); trên thì nên "Làm trước" (vieneu_module.SLOW_RTF). */
export const LIVE_RTF = 0.8;

/** Câu nói kết quả tự đo, theo điều người nghe cần biết: đọc trực tiếp kịp không, không kịp thì "Làm trước" mất bao lâu. */
export function benchmarkLabel(tier: ModuleTier, result: VieneuBenchmark, live = LIVE_RTF): string {
  const name = tierName(tier);
  if (result.rtf >= live) {
    const hour = Math.max(1, Math.round(result.rtf * 60));
    return S.s_0_may_nay_khong_kip_doc_truc_tiep_1_giay_c_1d699e69(name, seconds(result.rtf), hour);
  }
  const speed = result.rtf > 0 ? 1 / result.rtf : 0;
  return S.s_0_doc_truc_tiep_duoc_may_nay_doc_nhanh_gap_b0ef506b(name, seconds(speed), seconds(result.firstAudioMs / 1000));
}

/** Lời đề nghị đổi giọng (không bao giờ tự đổi) và chữ trên nút. */
export function suggestionText(suggestion: VieneuSuggestion): { message: string; action: string } {
  const slow = tierName(suggestion.tier);
  const lead = S.s_0_doc_cham_tren_may_nay_1_giay_cho_moi_gia_10e817a5(slow, seconds(suggestion.rtf));
  if (suggestion.switchTo === "nano") {
    return suggestion.installed
      ? { message: S.s_0_giong_vieneu_nano_nhe_hon_da_co_san_fef4245f(lead), action: S.s_dung_giong_vieneu_nano_b84996dd }
      : { message: S.s_0_giong_vieneu_nano_nhe_hon_hop_may_nay_05bccaca(lead), action: S.s_tai_giong_vieneu_nano_e24acf37 };
  }
  return { message: S.s_0_giong_truc_tuyen_nhe_may_can_mang_be7ce311(lead), action: S.s_dung_giong_truc_tuyen_a5bae2dc };
}

/** Câu chính của thẻ theo trạng thái. */
export function vieneuLabel(status: VieneuStatus, copy: ModuleCopy = VIENEU_COPY): string {
  const mid = lowerFirst(copy.name);
  if (status.state === "error") return status.error;
  if (status.state === "downloading") return status.retrying ? `${RETRYING_NOTE} (${mid}, ${vieneuPercent(status)}%)` : S.s_dang_tai_0_1_0d39c288(formatSize(status.total), vieneuPercent(status));
  // Chưa có số đo nào = giọng vừa tải; đã có = bật / tắt bản tăng tốc hay “Thử lại tốc độ” (không tải gì cả).
  if (status.benchmarking) return Object.keys(status.benchmark).length === 0 ? S.s_dang_thu_giong_vua_tai_tren_may_nay_vai_gi_1b19cd1b : S.s_dang_do_lai_toc_do_tren_may_nay_vai_giay_c7a38eb7;
  if (status.state === "unsupported") return status.reason ? S.s_may_nay_chua_dung_duoc_0_aaad0a2a(status.reason) : S.s_may_nay_chua_dung_duoc_faf04aee;
  if (status.restart) return S.s_0_da_cap_nhat_mo_lai_abook_de_dung_ban_moi_442e5d5d(copy.name);
  const cancelled = status.cancelled ? `${CANCELLED_NOTE} ` : "";
  if (status.state === "outdated") return S.s_0_1_co_ban_moi_2_ban_dang_dung_van_doc_bin_49647651(cancelled, copy.name, formatSize(status.outdatedBytes));
  if (status.state === "ready") return S.s_0_da_co_tren_may_chon_trong_nut_giong_doc_fef93830(copy.name);
  return `${cancelled}${copy.invite}`;
}

/** Phần câu chính mà trình đọc màn hình đọc khi trạng thái đổi (vùng role=status của thẻ): đang tải thì pha thật (đang thử lại hay đang tải) + mốc
 *  25 %; vừa huỷ thì chỉ "Đã huỷ…" - đoạn giới thiệu dài phía sau vẫn đọc được khi duyệt trang, không bị đọc lại mỗi lần huỷ (soát a67). `rest`:
 *  phần còn lại của câu chính, nằm ngoài vùng ấy. */
export function vieneuSpoken(status: VieneuStatus, copy: ModuleCopy = VIENEU_COPY): { live: string; rest: string } {
  const mid = lowerFirst(copy.name);
  if (status.state === "downloading") {
    const phase = status.retrying ? `${RETRYING_NOTE.replace(/…$/, "")} (${mid})` : S.s_dang_tai_0_03db34d6(mid);
    return { live: spokenProgress(phase, vieneuPercent(status) / 100), rest: "" };
  }
  const label = vieneuLabel(status, copy);
  if (status.cancelled && label.startsWith(`${CANCELLED_NOTE} `)) return { live: CANCELLED_NOTE, rest: label.slice(CANCELLED_NOTE.length + 1) };
  return { live: label, rest: "" };
}
