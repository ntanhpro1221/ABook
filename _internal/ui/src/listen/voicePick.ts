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
  if (engine === "zerotts") return "Giọng ZeroTTS";
  const tier = ENGINE_TIER[engine];
  return tier ? tierName(tier) : engine;
}

/** Nhãn ngắn cạnh tên bộ giọng (1-2 chữ): bộ đang làm mặc định, ai chọn; hay vì sao không được chọn. */
export function rowBadge(row: VoicePickRow, status: Pick<VoicePickStatus, "auto" | "override">): string {
  if (status.override === row.engine) return "Bạn chọn";
  if (!status.override && status.auto === row.engine) return "Máy chọn";
  if (!row.measured) return "Chưa thử";
  return { error: "Lỗi", unclear: "Chưa rõ", slow: "Chậm", "": "" }[row.verdict];
}

/** Dòng số đo của một bộ giọng, theo điều người nghe nhận ra: rõ bao nhiêu, tự nhiên bao nhiêu, kịp nghe không, tốn bao nhiêu RAM. */
export function rowNumbers(row: VoicePickRow, live = 0.8): string {
  if (!row.measured) return "Chưa thử trên máy này.";
  if (row.verdict === "error") return row.error ? `Thử không được: ${row.error}` : "Thử không được.";
  const parts = [
    row.cer === null ? "Độ rõ: chưa đo" : `Rõ ${Math.round((1 - row.cer) * 100)}%`,
    row.natural === null ? "Tự nhiên: chưa đo" : `Tự nhiên ${seconds(row.natural)}/5`,
    row.rtf === null ? "" : row.rtf >= live ? `Chậm: ${seconds(row.rtf)} giây cho mỗi giây nghe` : `Nhanh gấp ${seconds(1 / Math.max(row.rtf, 0.01))} lần`,
    row.peakRamMb == null ? (row.ramMb === null ? "" : `RAM +${row.ramMb} MB`) : `RAM đỉnh ${row.peakRamMb} MB`,
  ];
  return parts.filter(Boolean).join(" · ");
}

/** Câu đầu thẻ. */
export function pickHeadline(status: VoicePickStatus): string {
  if (status.state === "measuring") {
    const step = Math.min((status.done ?? 0) + 1, status.total ?? 1);
    return status.measuring ? `Đang thử ${engineName(status.measuring)} (${step}/${status.total ?? 1})` : "Đang nghe lại và chấm";
  }
  if (status.error) return status.error;
  if (status.state === "empty") return "Chưa có giọng nào trên máy - tải một bộ giọng ở trên rồi máy sẽ tự thử.";
  if (status.state === "stale" && !status.engines.some((row) => row.measured)) return "Máy chưa thử các giọng: bấm Thử để máy chọn giọng hợp nhất.";
  const chosen = status.chosen ? engineName(status.chosen) : "";
  const who = status.override ? "bạn chọn" : "máy chọn theo số đo";
  const lead = chosen
    ? `Sách chưa chọn giọng đọc bằng ${chosen} (${who}).`
    : "Chưa giọng nào trên máy vừa rõ vừa kịp đọc trực tiếp: sách chưa chọn giọng dùng giọng mặc định.";
  return status.state === "stale" ? `${lead} Có giọng mới tải chưa thử - bấm Thử lại.` : lead;
}

/** Ghi chú nhỏ: chấm bằng gì (một lượt luôn dùng cùng bộ nghe, cùng bộ chấm cho mọi giọng). */
export function pickMethod(status: Pick<VoicePickStatus, "asr" | "natural">): string {
  if (!status.asr && !status.natural) return "Cùng vài câu cho mọi giọng; chưa có bộ nghe lại trên máy này; chưa có bộ chấm tự nhiên. Chọn: kịp đọc trực tiếp, rồi nhanh nhất.";
  const asr = status.asr ? "nghe lại bằng bộ nghe của app" : "chưa có bộ nghe lại trên máy này";
  const natural = status.natural ? "chấm tự nhiên bằng UTMOS" : "chưa có bộ chấm tự nhiên";
  return `Cùng vài câu cho mọi giọng; ${asr}; ${natural}. Chọn: đọc rõ, kịp đọc trực tiếp, rồi tự nhiên nhất.`;
}
