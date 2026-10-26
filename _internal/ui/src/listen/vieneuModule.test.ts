import { describe, expect, it } from "vitest";
import {
  acceleratedNote,
  benchmarkLabel,
  fastUnsupportedNote,
  initialChoices,
  offlineChoices,
  meteredNotice,
  moduleAdvice,
  refreshModuleSizes,
  removeAsk,
  selectionBytes,
  SUPERTONIC_COPY,
  suggestionText,
  toggleChoice,
  tierVoicePrefix,
  vieneuLabel,
  vieneuSpoken,
  type VieneuStatus,
} from "./vieneuModule";

const MB = 1_000_000;

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
  it("đo lại thì không nói là giọng vừa tải; máy không chạy được bản tăng tốc thì nói thẳng", () => {
    expect(vieneuLabel(status({ state: "ready", benchmarking: true }))).toContain("vừa tải");
    const measured = status({ state: "ready", benchmarking: true, benchmark: { turbo: { rtf: 0.2, firstAudioMs: 900 } } });
    expect(vieneuLabel(measured)).toBe("Đang đo lại tốc độ trên máy này (vài giây)");
    expect(fastUnsupportedNote(status())).toBeNull();
    expect(fastUnsupportedNote(status({ fastUnsupported: "CPU của máy này không có lệnh AVX2" }))).toBe("Bản tăng tốc: máy này không chạy được (CPU của máy này không có lệnh AVX2).");
  });

  it("tính phần dùng chung một lần và bỏ phần máy đã có", () => {
    expect(selectionBytes(status(), ["turbo"])).toBe(256 * MB);
    expect(selectionBytes(status(), ["turbo", "nano"])).toBe(526 * MB);
    expect(selectionBytes(status(), ["aligner"])).toBe(27 * MB);
    expect(selectionBytes(status(), [])).toBe(0);
  });

  it("khối mất mạng mời một giọng nhẹ nhất đủ đọc - giọng máy này được khuyên; gói đánh dấu sẵn là lựa chọn phụ (soát a64)", () => {
    expect(offlineChoices(status())).toEqual({ light: ["turbo"], full: ["turbo", "aligner"] });
    expect(offlineChoices(status({ recommended: "nano" })).light).toEqual(["nano"]);
    const had = status({ choices: status().choices.map((choice) => (choice.id === "turbo" ? { ...choice, installed: true } : choice)) });
    expect(offlineChoices(had)).toEqual({ light: [], full: ["aligner"] });
  });

  it("đánh dấu sẵn cái khuyên dùng và cái đã tải", () => {
    expect(initialChoices(status())).toEqual(["turbo", "aligner"]);
    const installed = status({ choices: status().choices.map((choice) => (choice.id === "nano" ? { ...choice, installed: true } : choice)) });
    expect(initialChoices(installed)).toEqual(["turbo", "nano", "aligner"]);
  });

  it("nói kết quả tự đo bằng tốc độ nghe", () => {
    expect(benchmarkLabel("turbo", { rtf: 0.25, firstAudioMs: 1500 })).toContain("nhanh gấp 4,0 lần");
    expect(benchmarkLabel("nano", { rtf: 1.25, firstAudioMs: 5000 })).toContain("không kịp đọc trực tiếp (1,3 giây");
    expect(benchmarkLabel("turbo", { rtf: 0.85, firstAudioMs: 5000 })).toContain("~51 phút");
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

  it("giọng Supertonic: cùng khung, lời riêng; máy chậm thì cũng chỉ sang “Làm trước” như VieNeu", () => {
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
    // Mạng hỏng giữa chừng, máy đang chờ thử lại: nói ra, không đứng ở "Đang tải x%" (soát a64).
    expect(vieneuLabel({ ...one, state: "downloading", done: 62, total: 100, retrying: true }, SUPERTONIC_COPY)).toBe("Mạng chập chờn - đang thử lại… (giọng Supertonic, 62%)");
    expect(benchmarkLabel("supertonic", { rtf: 0.2, firstAudioMs: 1400 })).toContain("nhanh gấp 5,0 lần");
    expect(benchmarkLabel("supertonic", { rtf: 1.9, firstAudioMs: 9000 })).toBe(
      "Giọng Supertonic: máy này không kịp đọc trực tiếp (1,9 giây cho mỗi giây nghe). Dùng “Làm trước”: mỗi giờ nghe cần ~114 phút.",
    );
    const slow = suggestionText({ tier: "supertonic", rtf: 1.1, switchTo: "online", installed: true });
    expect(slow.message).toContain("Giọng Supertonic đọc chậm");
    expect(slow.message).toContain("Giữ giọng này thì dùng “Làm trước”.");
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

describe("bản tăng tốc", () => {
  const fast = status({
    choices: [
      ...status().choices,
      { id: "fast", label: "Bản tăng tốc", detail: "", needs: ["libs", "g2p", "voices", "turbo", "gguf"], bytes: 199 * MB, installed: false, recommended: true, default: true, requires: ["turbo"] },
    ],
    parts: [...status().parts, { id: "gguf", label: "", bytes: 199 * MB, state: "missing" }],
  });

  it("đánh dấu bản tăng tốc thì đánh dấu luôn Giọng VieNeu, bỏ Giọng VieNeu thì bỏ luôn bản tăng tốc", () => {
    expect(toggleChoice(fast, [], "fast", true).sort()).toEqual(["fast", "turbo"]);
    expect(toggleChoice(fast, ["turbo", "fast", "aligner"], "turbo", false)).toEqual(["aligner"]);
    expect(toggleChoice(fast, ["turbo", "fast"], "fast", false)).toEqual(["turbo"]);
    expect(toggleChoice(fast, ["turbo"], "nano", true)).toEqual(["turbo", "nano"]);
  });

  it("tổng cần tải tính cả Giọng VieNeu mà bản tăng tốc cần, một lần", () => {
    expect(selectionBytes(fast, ["turbo", "fast"])).toBe((27 + 26 + 3 + 200 + 199) * MB);
    expect(selectionBytes(fast, ["fast"])).toBe((27 + 26 + 3 + 200 + 199) * MB);
  });

  it("câu dưới công tắc nói điều người nghe thấy", () => {
    expect(acceleratedNote({ on: false, active: false, problem: "" })).toBe("Đang đọc bằng bản thường.");
    expect(acceleratedNote({ on: true, active: true, problem: "" })).toBe("Đang đọc bằng bản tăng tốc.");
    expect(acceleratedNote({ on: true, active: false, problem: "server thoát" })).toContain("chưa chạy được");
  });
});

describe("cỡ các thẻ giọng sau khi một mô-đun cài / gỡ xong", () => {
  it("hỏi lại thẻ VieNeu, thẻ Supertonic và dòng Tốc độ giọng (soát a65: thẻ VieNeu còn 271 MB sau khi Supertonic cài phần chung)", () => {
    const asked: unknown[] = [];
    refreshModuleSizes({ invalidateQueries: ({ queryKey }) => asked.push(queryKey) });
    expect(asked).toEqual([
      ["readaloud", "vieneu"],
      ["readaloud", "supertonic"],
      ["readaloud", "voice-speed"],
    ]);
  });
});

describe("Cài đặt: hai mô-đun giọng trên máy, khuyên tải một (soát a66)", () => {
  const supertonic = status({
    choices: [{ id: "supertonic", label: "Giọng Supertonic", detail: "", needs: ["libs", "g2p", "supertonic"], bytes: 0, installed: false, recommended: false, default: true, removable: true }],
    recommended: "supertonic",
  });

  it("máy chưa có giọng nào: khuyên bản VieNeu của máy, Supertonic không đánh dấu sẵn", () => {
    const advice = moduleAdvice(status({ recommended: "nano" }), supertonic);
    expect(advice.advice).toContain("Nên dùng giọng VieNeu Nano");
    expect(advice.preselectSupertonic).toBe(false);
    expect(initialChoices(supertonic, advice.preselectSupertonic)).toEqual([]);
    expect(moduleAdvice(status({ recommended: "turbo" }), supertonic).advice).toContain("Nên dùng giọng VieNeu");
  });

  it("đã có một bộ giọng thì thôi khuyên; máy không chạy được VieNeu thì Supertonic đánh dấu sẵn như cũ", () => {
    const installed = status({ choices: status().choices.map((choice) => ({ ...choice, installed: true })) });
    expect(moduleAdvice(installed, supertonic)).toEqual({ advice: "", preselectSupertonic: false });
    expect(moduleAdvice(status(), { ...supertonic, choices: supertonic.choices.map((choice) => ({ ...choice, installed: true })) }).advice).toBe("");
    expect(moduleAdvice(status({ state: "unsupported" }), supertonic)).toEqual({ advice: "", preselectSupertonic: true });
    // Trạng thái VieNeu chưa về: chưa đánh dấu Supertonic (tránh tích sẵn rồi bỏ tích trước mắt người dùng).
    expect(moduleAdvice(undefined, supertonic).preselectSupertonic).toBe(false);
  });
});

describe("câu trình đọc màn hình nghe ở thẻ mô-đun (soát a67)", () => {
  it("đang thử lại nói đúng là đang thử lại, kèm mốc 25 %; vừa huỷ thì chỉ nói đã huỷ", () => {
    const retrying = vieneuSpoken(status({ state: "downloading", done: 62, total: 100, retrying: true }));
    expect(retrying.live).toContain("đang thử lại");
    expect(retrying.live).toContain("50%");
    expect(vieneuSpoken(status({ state: "downloading", done: 62, total: 100 })).live).toMatch(/^Đang tải .* · 50%$/);
    const cancelled = vieneuSpoken(status({ cancelled: true }));
    const label = vieneuLabel(status({ cancelled: true }));
    expect(`${cancelled.live} ${cancelled.rest}`).toBe(label);
    expect(cancelled.live.length).toBeLessThan(label.length);
    expect(vieneuSpoken(status({ state: "error", error: "Không tải được." }))).toEqual({ live: "Không tải được.", rest: "" });
  });
});

describe("removeAsk", () => {
  const book = (title: string, left: number) => ({ title, people: ["Noah"], left });
  it("nói số cuốn, vài tên cuốn và câu nào sẽ không đọc được", () => {
    const text = removeAsk({ bookCount: 4, peopleCount: 6, left: 120, books: [book("A", 100), book("B", 20), book("C", 0), book("D", 0)] });
    expect(text).toContain("4 cuốn đang dùng giọng này (“A”, “B”, “C” và 1 cuốn khác), 6 nhân vật.");
    expect(text).toContain("120 câu chưa thu");
    expect(text).toContain("tải lại giọng hay đổi giọng khác");
    expect(text).toContain("câu đã thu vẫn nghe được");
  });
  it("cuốn đã thu xong thì chỉ báo khi cần thu lại", () => {
    const text = removeAsk({ bookCount: 1, peopleCount: 2, left: 0, books: [book("A", 0)] });
    expect(text).toContain("1 cuốn đang dùng giọng này (“A”)");
    expect(text).not.toContain("chưa thu");
  });
  it("không cuốn nào dùng, hay không biết, vẫn có một câu hỏi ngắn", () => {
    expect(removeAsk({ bookCount: 0, peopleCount: 0, left: 0, books: [] })).toContain("Chưa cuốn nào");
    expect(removeAsk(null)).toContain("tải lại");
  });
});
