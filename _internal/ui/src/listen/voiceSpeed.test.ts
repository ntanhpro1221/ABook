import { describe, expect, it } from "vitest";
import { needsFastDownload, VOICE_SPEED_OPTIONS, voiceSpeedDescription, voiceSpeedLine, type VoiceSpeedVoice } from "./voiceSpeed";

const voice = (over: Partial<VoiceSpeedVoice> = {}): VoiceSpeedVoice => ({
  id: "supertonic",
  name: "Giọng Supertonic",
  module: "supertonic",
  fastChoice: "supertonic_fast",
  rtf: 0.5,
  tier: "quality",
  using: "quality",
  fastBytes: 81_526_521,
  ...over,
});

describe("tốc độ giọng trên máy", () => {
  it("ba lựa chọn, Tự động đứng đầu", () => {
    expect(VOICE_SPEED_OPTIONS.map((option) => option.label)).toEqual(["Tự động", "Chất lượng cao nhất", "Nhanh hơn"]);
  });

  it("Tự động nói máy tự chọn thế nào, và sách xuất ra luôn dùng chất lượng cao nhất", () => {
    const text = voiceSpeedDescription("auto");
    expect(text).toContain("Máy kịp thì đọc bản hay nhất.");
    expect(text).toContain("sách xuất ra luôn dùng bản hay nhất");
    for (const choice of ["auto", "quality", "fast"] as const) {
      expect(voiceSpeedDescription(choice)).toContain("Chỉ áp cho giọng Supertonic");
    }
  });

  it("nói đang dùng bậc nào và vì sao", () => {
    expect(voiceSpeedLine(voice({ rtf: 1.2, tier: "fast", using: "fast", fastBytes: 0 }), "auto")).toBe(
      "Giọng Supertonic - Đang dùng: Nhanh hơn (máy này đọc chậm hơn tốc độ nghe).",
    );
    expect(voiceSpeedLine(voice(), "auto")).toBe("Giọng Supertonic - Đang dùng: Chất lượng cao nhất (máy này đọc kịp tốc độ nghe).");
    expect(voiceSpeedLine(voice({ rtf: null }), "auto")).toBe("Giọng Supertonic - Đang dùng: Chất lượng cao nhất (chưa đo được tốc độ máy này).");
    expect(voiceSpeedLine(voice({ rtf: 2, tier: "quality" }), "quality")).toBe("Giọng Supertonic - Đang dùng: Chất lượng cao nhất (bạn đã chọn).");
  });

  it("muốn bản nhanh hơn mà chưa tải: nói cỡ và mời tải; đã có thì thôi", () => {
    const lacking = voice({ tier: "fast", fastBytes: 81_526_521 });
    expect(voiceSpeedLine(lacking, "fast")).toBe("Giọng Supertonic - Đang dùng: Chất lượng cao nhất. Bản nhanh hơn cần tải thêm 78 MB.");
    expect(needsFastDownload(lacking)).toBe(true);
    expect(needsFastDownload({ ...lacking, using: "fast", fastBytes: 0 })).toBe(false);
    expect(needsFastDownload(voice())).toBe(false);
  });
});
