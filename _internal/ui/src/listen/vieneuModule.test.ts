import { describe, expect, it } from "vitest";
import {
  benchmarkLabel,
  initialChoices,
  meteredNotice,
  selectionBytes,
  SUPERTONIC_COPY,
  suggestionText,
  tierVoicePrefix,
  vieneuLabel,
  type VieneuStatus,
} from "./vieneuModule";

const MB = 1024 * 1024;

function status(over: Partial<VieneuStatus> = {}): VieneuStatus {
  return {
    state: "missing",
    done: 0,
    total: 0,
    error: "",
    supported: true,
    reason: "",
    choices: [
      { id: "turbo", label: "Giọng VieNeu", detail: "", needs: ["libs", "g2p", "voices", "turbo"], bytes: 0, installed: false, recommended: true, default: true },
      { id: "nano", label: "Giọng VieNeu Nano", detail: "", needs: ["libs", "g2p", "voices", "nano"], bytes: 0, installed: false, recommended: false, default: false },
      { id: "aligner", label: "Tô đúng từng chữ đang đọc", detail: "", needs: ["libs", "aligner"], bytes: 0, installed: false, recommended: true, default: true },
    ],
    parts: [
      { id: "libs", label: "", bytes: 27 * MB, state: "missing" },
      { id: "g2p", label: "", bytes: 26 * MB, state: "missing" },
      { id: "voices", label: "", bytes: 3 * MB, state: "missing" },
      { id: "turbo", label: "", bytes: 200 * MB, state: "missing" },
      { id: "nano", label: "", bytes: 270 * MB, state: "missing" },
      { id: "aligner", label: "", bytes: 116 * MB, state: "current", external: true },
    ],
    outdatedParts: [],
    outdatedBytes: 0,
    benchmark: {},
    benchmarking: false,
    suggestion: null,
    device: { cores: 16, ramGb: 16, gpu: "", runs: "cpu" },
    recommended: "turbo",
    ...over,
  };
}

describe("mô-đun Giọng VieNeu", () => {
  it("tính phần dùng chung một lần và bỏ phần máy đã có", () => {
    expect(selectionBytes(status(), ["turbo"])).toBe(256 * MB);
    expect(selectionBytes(status(), ["turbo", "nano"])).toBe(526 * MB);
    expect(selectionBytes(status(), ["aligner"])).toBe(27 * MB);
    expect(selectionBytes(status(), [])).toBe(0);
  });

  it("đánh dấu sẵn cái khuyên dùng và cái đã tải", () => {
    expect(initialChoices(status())).toEqual(["turbo", "aligner"]);
    const installed = status({ choices: status().choices.map((choice) => (choice.id === "nano" ? { ...choice, installed: true } : choice)) });
    expect(initialChoices(installed)).toEqual(["turbo", "nano", "aligner"]);
  });

  it("nói kết quả tự đo bằng tốc độ nghe", () => {
    expect(benchmarkLabel("turbo", { rtf: 0.25, firstAudioMs: 1500 })).toContain("nhanh gấp 4,0 lần");
    expect(benchmarkLabel("nano", { rtf: 1.25, firstAudioMs: 5000 })).toContain("không kịp đọc trực tiếp (1,3 giây");
    expect(benchmarkLabel("turbo", { rtf: 0.85, firstAudioMs: 5000 })).toContain("khoảng 51 phút");
  });

  it("đề nghị đổi giọng, không tự đổi", () => {
    expect(suggestionText({ tier: "turbo", rtf: 0.9, switchTo: "nano", installed: false }).action).toBe("Tải giọng VieNeu Nano");
    expect(suggestionText({ tier: "turbo", rtf: 0.9, switchTo: "nano", installed: true }).action).toBe("Dùng giọng VieNeu Nano");
    expect(suggestionText({ tier: "nano", rtf: 1.4, switchTo: "online", installed: true }).message).toContain("cần mạng");
  });

  it("câu chính theo trạng thái", () => {
    expect(vieneuLabel(status({ state: "downloading", done: 50, total: 100 * MB }))).toContain("0%");
    expect(vieneuLabel(status({ state: "outdated", outdatedBytes: 3 * MB }))).toContain("3,0 MB");
    expect(vieneuLabel(status({ state: "error", error: "Không tải được." }))).toBe("Không tải được.");
    expect(vieneuLabel(status())).toContain("không cần mạng");
  });

  it("điện thoại: thư viện chạy model của Gói nhạc không tính lại, Nano khuyên dùng", () => {
    const phone = status({
      choices: [
        { id: "nano", label: "Giọng VieNeu Nano", detail: "", needs: ["ort", "g2p", "voices", "nano"], bytes: 0, installed: false, recommended: true, default: true },
        { id: "turbo", label: "Giọng VieNeu", detail: "", needs: ["ort", "g2p", "voices", "turbo"], bytes: 0, installed: false, recommended: false, default: false },
      ],
      parts: [
        { id: "ort", label: "", bytes: 12 * MB, state: "current", external: true },
        { id: "g2p", label: "", bytes: 28 * MB, state: "missing" },
        { id: "voices", label: "", bytes: 3 * MB, state: "missing" },
        { id: "turbo", label: "", bytes: 200 * MB, state: "missing" },
        { id: "nano", label: "", bytes: 270 * MB, state: "missing" },
      ],
      recommended: "nano",
    });
    expect(initialChoices(phone)).toEqual(["nano"]);
    expect(selectionBytes(phone, ["nano"])).toBe(301 * MB);
    expect(selectionBytes(phone, ["nano", "turbo"])).toBe(501 * MB);
  });

  it("giọng Supertonic: cùng khung, lời riêng, không nhắc “Làm trước” (giọng này đọc trực tiếp)", () => {
    const one = status({
      choices: [{ id: "supertonic", label: "Giọng Supertonic", detail: "", needs: ["libs", "g2p", "supertonic"], bytes: 0, installed: false, recommended: false, default: true, removable: true }],
      parts: [
        { id: "libs", label: "", bytes: 27 * MB, state: "current", external: true },
        { id: "g2p", label: "", bytes: 26 * MB, state: "missing" },
        { id: "supertonic", label: "", bytes: 380 * MB, state: "missing" },
      ],
      recommended: "supertonic",
    });
    expect(initialChoices(one)).toEqual(["supertonic"]);
    expect(selectionBytes(one, ["supertonic"])).toBe(406 * MB);
    expect(vieneuLabel(one, SUPERTONIC_COPY)).toContain("Mười giọng nam nữ");
    expect(vieneuLabel({ ...one, state: "ready" }, SUPERTONIC_COPY)).toBe("Giọng Supertonic đã có trên máy: chọn trong nút Giọng đọc khi nghe sách chỉ có chữ.");
    expect(vieneuLabel({ ...one, state: "downloading", done: 40, total: 100 * MB }, SUPERTONIC_COPY)).toContain("Đang tải giọng Supertonic");
    expect(benchmarkLabel("supertonic", { rtf: 0.2, firstAudioMs: 1400 })).toContain("nhanh gấp 5,0 lần");
    expect(benchmarkLabel("supertonic", { rtf: 1.1, firstAudioMs: 9000 })).not.toContain("Làm trước");
    const slow = suggestionText({ tier: "supertonic", rtf: 1.1, switchTo: "online", installed: true });
    expect(slow.message).toContain("Giọng Supertonic không theo kịp");
    expect(slow.message).not.toContain("Làm trước");
    expect(tierVoicePrefix("supertonic")).toBe("supertonic:");
    expect(tierVoicePrefix("nano")).toBe("vieneu:nano/");
  });

  it("nhắc tốn dữ liệu di động trước khi tải, không chặn", () => {
    expect(meteredNotice({ metered: true }, 301 * MB)).toContain("dữ liệu di động");
    expect(meteredNotice({ metered: false }, 301 * MB)).toBeNull();
    expect(meteredNotice({ metered: true }, 0)).toBeNull();
    expect(meteredNotice({}, 5 * MB)).toBeNull();
  });
});
