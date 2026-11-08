import { S } from "../shared/strings.generated";
import { seconds, tierName, type ModuleTier } from "./vieneuModule";

/** Thẻ "Giọng theo máy" (máy tính, abook/webui/voice_pick.py): số đo từng bộ giọng trên máy + bộ làm mặc định (máy chọn theo số đo, hay người dùng chọn tay). */
export interface VoicePickRow {
  /** "vieneu:turbo", "vieneu:nano", "supertonic"... (abook/readaloud/engine_pick.engine_of) */
  engine: string;
  voice: string;
  measured: boolean;
  /** "" = đủ điều kiện làm mặc định; "error" đo hỏng, "unclear" nghe lại sai nhiều, "slow" không kịp đọc trực tiếp. */
  verdict: "" | "error" | "unclear" | "slow";
  rtf: number | null;
  ramMb: number | null;
  peakRamMb?: number | null;
  loadMs: number | null;
  cer: number | null;
  natural: number | null;
  error: string;
}

export interface VoicePickStatus {
  state: "unsupported" | "empty" | "stale" | "ready" | "measuring";
  engines: VoicePickRow[];
  /** Bộ máy chọn theo số đo (null: chưa đo / không bộ nào đạt). */
  auto: string | null;
  /** Bộ người dùng chọn tay ("" = theo số đo). */
  override: string;
  chosen: string | null;
  asr?: string;
  natural?: string;
  at?: string;
  done?: number;
  total?: number;
  measuring?: string;
  error?: string;
  liveRtf?: number;
  cerGate?: number;
}

const ENGINE_TIER: Record<string, ModuleTier> = { "vieneu:turbo": "turbo", "vieneu:nano": "nano", supertonic: "supertonic" };

/** Tên bộ giọng như thẻ tải của nó gọi ("Giọng VieNeu", "Giọng Supertonic"); bộ cắm thêm chưa có tên thì mã của nó. */
export function engineName(engine: string): string {
  if (engine === "zerotts") return S.s_giong_zerotts_2fdf72ba;
  const tier = ENGINE_TIER[engine];
  return tier ? tierName(tier) : engine;
}

/** Nhãn ngắn cạnh tên bộ giọng (1-2 chữ): bộ đang làm mặc định, ai chọn; hay vì sao không được chọn. */
export function rowBadge(row: VoicePickRow, status: Pick<VoicePickStatus, "auto" | "override">): string {
  if (status.override === row.engine) return S.s_ban_chon_1c143e0b;
  if (!status.override && status.auto === row.engine) return S.s_may_chon_4329a3f3;
  if (!row.measured) return S.s_chua_thu_d168d4a9;
  return { error: S.s_loi_e68991b7, unclear: S.s_chua_ro_be464a5a, slow: S.s_cham_6ddeaddc, "": "" }[row.verdict];
}

/** Dòng số đo của một bộ giọng, theo điều người nghe nhận ra: rõ bao nhiêu, tự nhiên bao nhiêu, kịp nghe không, tốn bao nhiêu RAM. */
export function rowNumbers(row: VoicePickRow, live = 0.8): string {
  if (!row.measured) return S.s_chua_thu_tren_may_nay_db7eeae5;
  if (row.verdict === "error") return row.error ? S.s_thu_khong_duoc_0_bf5f8af8(row.error) : S.s_thu_khong_duoc_07616f5a;
  const parts = [
    row.cer === null ? S.s_do_ro_chua_do_0986efe7 : S.s_ro_0_68776af2(Math.round((1 - row.cer) * 100)),
    row.natural === null ? S.s_tu_nhien_chua_do_3eaed012 : S.s_tu_nhien_0_5_876223ac(seconds(row.natural)),
    row.rtf === null ? "" : row.rtf >= live ? S.s_cham_0_giay_cho_moi_giay_nghe_3439900c(seconds(row.rtf)) : S.s_nhanh_gap_0_lan_fd951c7d(seconds(1 / Math.max(row.rtf, 0.01))),
    row.peakRamMb == null ? (row.ramMb === null ? "" : `RAM +${row.ramMb} MB`) : S.s_ram_dinh_0_mb_077d5736(row.peakRamMb),
  ];
  return parts.filter(Boolean).join(" · ");
}

/** Câu đầu thẻ. */
export function pickHeadline(status: VoicePickStatus): string {
  if (status.state === "measuring") {
    const step = Math.min((status.done ?? 0) + 1, status.total ?? 1);
    return status.measuring ? S.s_dang_thu_0_1_2_2e3a7ef6(engineName(status.measuring), step, status.total ?? 1) : S.s_dang_nghe_lai_va_cham_37b438f4;
  }
  if (status.error) return status.error;
  if (status.state === "empty") return S.s_chua_co_giong_nao_tren_may_tai_mot_bo_gion_7bdc8937;
  if (status.state === "stale" && !status.engines.some((row) => row.measured)) return S.s_may_chua_thu_cac_giong_bam_thu_de_may_chon_f3ae77fe;
  const chosen = status.chosen ? engineName(status.chosen) : "";
  const who = status.override ? S.s_ban_chon_bfffd506 : S.s_may_chon_theo_so_do_f4a15e17;
  const lead = chosen
    ? S.s_sach_chua_chon_giong_doc_bang_0_1_e09ed89f(chosen, who)
    : S.s_chua_giong_nao_tren_may_vua_ro_vua_kip_doc_0bb2767a;
  return status.state === "stale" ? S.s_0_co_giong_moi_tai_chua_thu_bam_thu_lai_88ad6e44(lead) : lead;
}

/** Ghi chú nhỏ: chấm bằng gì (một lượt luôn dùng cùng bộ nghe, cùng bộ chấm cho mọi giọng). */
export function pickMethod(status: Pick<VoicePickStatus, "asr" | "natural">): string {
  if (!status.asr && !status.natural) return S.s_cung_vai_cau_cho_moi_giong_chua_co_bo_nghe_e6bb15d4;
  const asr = status.asr ? S.s_nghe_lai_bang_bo_nghe_cua_app_7dd45ea2 : S.s_chua_co_bo_nghe_lai_tren_may_nay_faf4f956;
  const natural = status.natural ? S.s_cham_tu_nhien_bang_utmos_b3d7574f : S.s_chua_co_bo_cham_tu_nhien_fa118b8d;
  return S.s_cung_vai_cau_cho_moi_giong_0_1_chon_doc_ro_1c89fd7d(asr, natural);
}
