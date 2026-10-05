import { describe, expect, it } from "vitest";
import { groupByEngine, moduleNote, plainGroupLabels, sharedText, type EngineModuleStatus, type EngineVoice } from "./voiceEngines";

const voice = (over: Partial<EngineVoice> = {}): EngineVoice => ({
  name: "Ngọc Linh", engine: "vieneu", engineLabel: "VieNeu", installed: true, oneStep: false, sharedWith: [], otherUsers: 0, ...over,
});
const status = (over: Partial<EngineModuleStatus> = {}): EngineModuleStatus => ({
  state: "missing", done: 0, total: 0, bytes: 903_000_000, error: "", ...over,
});

describe("voices grouped by the machine that reads them", () => {
  it("keeps the server's order: VieNeu first, then the other machine, voices in order", () => {
    const groups = groupByEngine([
      voice({ name: "Ngọc Linh" }),
      voice({ name: "Bảo Trang", engine: "zerotts", engineLabel: "ZeroTTS", installed: false, oneStep: true }),
      voice({ name: "Trúc Ly" }),
      voice({ name: "Kim Oanh", engine: "zerotts", engineLabel: "ZeroTTS", installed: false, oneStep: true }),
    ]);
    expect(groups.map((group) => [group.label, group.installed, group.voices.map((item) => item.name)])).toEqual([
      ["VieNeu", true, ["Ngọc Linh", "Trúc Ly"]],
      ["ZeroTTS", false, ["Bảo Trang", "Kim Oanh"]],
    ]);
  });

  it("says plainly that two people sharing a one-tone voice will sound the same", () => {
    const shared = { sharedWith: [{ label: "Lucien", chapters: 3 }] };
    expect(sharedText(voice(shared))).toContain("máy lấy bậc âm sắc khác");
    expect(sharedText(voice({ ...shared, oneStep: true }))).toContain("nghe giống hệt nhau");
    expect(sharedText(voice())).toBe("Chưa ai dùng");
  });

  it("never calls the voice in use unused, and names groups plainly instead of by machine", () => {
    expect(sharedText(voice(), true)).toBe("Giọng đang đọc cho người này");
    expect(plainGroupLabels([{ engine: "vieneu" }, { engine: "zerotts" }])).toEqual(["Giọng chính", "Giọng thêm"]);
    expect(plainGroupLabels([{ engine: "zerotts" }, { engine: "vieneu" }, { engine: "supertonic" }])).toEqual(["Giọng thêm 1", "Giọng chính", "Giọng thêm 2"]);
  });
});

describe("the note under a machine that is not on this computer yet", () => {
  it("asks for a one-time download with its size, then shows progress, and disappears when ready", () => {
    expect(moduleNote(status())).toBe("Máy đọc khác: cần tải thêm 861 MB, một lần.");
    expect(moduleNote(status({ state: "downloading", done: 451_500_000, total: 903_000_000 }))).toBe("Đang tải giọng (861 MB) 50%");
    expect(moduleNote(status({ state: "error", error: "Không tải được giọng ZeroTTS: mất mạng." }))).toContain("mất mạng");
    expect(moduleNote(status({ state: "ready" }))).toBeNull();
    expect(moduleNote(undefined)).toBeNull();
  });
});
