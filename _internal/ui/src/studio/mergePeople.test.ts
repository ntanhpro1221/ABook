import { describe, expect, it, vi } from "vitest";
import { SENTENCE } from "./decisions";

vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: null, close: () => undefined }) }));

describe("hộp Gộp nhân vật (soát UX a23)", () => {
  it("lời báo theo trạng thái sách, không mời bấm nút không có (B5)", async () => {
    const { mergedDescription } = await import("./MergePeople");
    const waitingReview = mergedDescription(SENTENCE.cast, 0);
    expect(waitingReview).not.toMatch(/Áp dụng thay đổi/);
    expect(waitingReview).not.toMatch(/thu lại/);
    expect(mergedDescription(SENTENCE.done, 7)).toMatch(/thu lại/);
    expect(mergedDescription(SENTENCE.done, 7)).toMatch(/Áp dụng thay đổi/);
  });

  it("nói giọng sẽ dùng - giọng vừa chọn mà chưa áp (B4)", async () => {
    const { voiceToUse } = await import("./MergePeople");
    const voice = { key: "vieneu:pham-tuyen", preset: "Phạm Tuyên", tone: "" };
    expect(voiceToUse({ voice, pendingVoice: { preset: "Hải Đăng", gender: "" } })).toBe("Hải Đăng");
    expect(voiceToUse({ voice, pendingVoice: { preset: "", gender: "Nữ" } })).toBe("Phạm Tuyên");
    expect(voiceToUse({ voice, pendingVoice: null })).toBe("Phạm Tuyên");
  });
});
