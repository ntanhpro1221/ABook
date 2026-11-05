import { describe, expect, it } from "vitest";
import { engineName, pickHeadline, pickMethod, rowBadge, rowNumbers, type VoicePickRow, type VoicePickStatus } from "./voicePick";

const row = (over: Partial<VoicePickRow> = {}): VoicePickRow => ({
  engine: "supertonic", voice: "supertonic:F1", measured: true, verdict: "", rtf: 0.25, ramMb: 530, loadMs: 900, cer: 0.03, natural: 3.25, error: "", ...over,
});
const status = (over: Partial<VoicePickStatus> = {}): VoicePickStatus => ({
  state: "ready", engines: [row(), row({ engine: "vieneu:nano", voice: "vieneu:nano/Adam", natural: 2.64 })], auto: "supertonic", override: "", chosen: "supertonic",
  asr: "whisper", natural: "utmosv2", ...over,
});

describe("Giọng theo máy", () => {
  it("names engines the way their download cards do", () => {
    expect(engineName("vieneu:turbo")).toBe("Giọng VieNeu");
    expect(engineName("vieneu:nano")).toBe("Giọng VieNeu Nano");
    expect(engineName("supertonic")).toBe("Giọng Supertonic");
    expect(engineName("moi:xyz")).toBe("moi:xyz");
  });

  it("says who chose the default in one or two words, and why another engine was left out", () => {
    expect(rowBadge(row(), status())).toBe("Máy chọn");
    expect(rowBadge(row(), status({ override: "vieneu:nano" }))).toBe("");
    expect(rowBadge(row({ engine: "vieneu:nano" }), status({ override: "vieneu:nano" }))).toBe("Bạn chọn");
    expect(rowBadge(row({ engine: "x", verdict: "slow" }), status())).toBe("Chậm");
    expect(rowBadge(row({ engine: "x", verdict: "unclear" }), status())).toBe("Chưa rõ");
    expect(rowBadge(row({ engine: "x", verdict: "error" }), status())).toBe("Lỗi");
    expect(rowBadge(row({ engine: "x", measured: false }), status())).toBe("Chưa thử");
  });

  it("writes the numbers as the listener reads them", () => {
    expect(rowNumbers(row())).toBe("Rõ 97% · Tự nhiên 3,3/5 · Nhanh gấp 4,0 lần · RAM +530 MB");
    expect(rowNumbers(row({ peakRamMb: 830 }))).toContain("RAM đỉnh 830 MB");
    expect(rowNumbers(row({ rtf: 1.2, cer: null, natural: null }))).toBe("Độ rõ: chưa đo · Tự nhiên: chưa đo · Chậm: 1,2 giây cho mỗi giây nghe · RAM +530 MB");
    expect(rowNumbers(row({ verdict: "error", error: "model hỏng" }))).toBe("Thử không được: model hỏng");
    expect(rowNumbers(row({ measured: false }))).toBe("Chưa thử trên máy này.");
  });

  it("headline names the default and who chose it", () => {
    expect(pickHeadline(status())).toBe("Sách chưa chọn giọng đọc bằng Giọng Supertonic (máy chọn theo số đo).");
    expect(pickHeadline(status({ override: "vieneu:nano", chosen: "vieneu:nano" }))).toBe("Sách chưa chọn giọng đọc bằng Giọng VieNeu Nano (bạn chọn).");
    expect(pickHeadline(status({ auto: null, chosen: "" }))).toContain("Chưa giọng nào trên máy vừa rõ vừa kịp đọc trực tiếp");
    expect(pickHeadline(status({ state: "measuring", measuring: "vieneu:nano", done: 1, total: 2 }))).toBe("Đang thử Giọng VieNeu Nano (2/2)");
    expect(pickHeadline(status({ state: "stale", engines: [row({ measured: false })], chosen: null, auto: null }))).toContain("bấm Thử");
    expect(pickHeadline(status({ state: "empty", engines: [] }))).toContain("Chưa có giọng nào trên máy");
    expect(pickMethod(status({ asr: "", natural: "" }))).toContain("chưa có bộ nghe lại");
  });
});
