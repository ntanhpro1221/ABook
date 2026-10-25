import { describe, expect, it, vi } from "vitest";

vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: null, close: () => undefined }) }));

describe("hộp Gộp nhân vật (soát UX a23)", () => {
  it("nói giọng sẽ dùng - giọng vừa chọn mà chưa áp (B4)", async () => {
    const { voiceToUse } = await import("./MergePeople");
    const voice = { key: "vieneu:pham-tuyen", preset: "Phạm Tuyên", tone: "" };
    expect(voiceToUse({ voice, pendingVoice: { preset: "Hải Đăng", gender: "" } })).toBe("Hải Đăng");
    expect(voiceToUse({ voice, pendingVoice: { preset: "", gender: "Nữ" } })).toBe("Phạm Tuyên");
    expect(voiceToUse({ voice, pendingVoice: null })).toBe("Phạm Tuyên");
    // Giọng máy khác: khoá "baotrang", người nghe thấy nhãn.
    const engine = { key: "k", preset: "baotrang", label: "Bảo Trang", tone: "" };
    expect(voiceToUse({ voice: engine, pendingVoice: null })).toBe("Bảo Trang");
    expect(voiceToUse({ voice, pendingVoice: { preset: "F1", label: "Supertonic F1", gender: "" } })).toBe("Supertonic F1");
  });
});
