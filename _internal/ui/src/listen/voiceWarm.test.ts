import { afterEach, describe, expect, it } from "vitest";
import { setApiTransport, type ApiInit } from "@/studio/api";
import { hasLocalEngine } from "./source";

// Nạp sẵn model giọng trên máy lúc mở trang sách (livejoin3): chỉ giọng có engine (VieNeu, Supertonic) mới xin nạp; máy tính gọi POST /api/readaloud/warm.

afterEach(() => setApiTransport(null));

describe("nạp sẵn model giọng", () => {
  it("chỉ giọng trên máy có engine mới xin nạp", () => {
    expect(hasLocalEngine({ online: false, provider: "supertonic" })).toBe(true);
    expect(hasLocalEngine({ online: false, provider: "vieneu" })).toBe(true);
    expect(hasLocalEngine({ online: false, provider: "device" })).toBe(false);
    expect(hasLocalEngine({ online: true, provider: "edge" })).toBe(false);
    expect(hasLocalEngine(undefined)).toBe(false);
  });

  it("máy tính gửi đúng lệnh, lỗi thì im lặng", async () => {
    const calls: [string, ApiInit | undefined][] = [];
    setApiTransport(async (path, init) => {
      calls.push([path, init]);
      return { started: true };
    });
    const { httpSource } = await import("@/desktop/httpSource");
    httpSource.voiceWarm!("vieneu:nano/Đức Trí");
    await Promise.resolve();
    expect(calls).toEqual([["/api/readaloud/warm?voice=vieneu%3Anano%2F%C4%90%E1%BB%A9c%20Tr%C3%AD", { method: "POST" }]]);
    setApiTransport(async () => {
      throw new Error("mất kết nối");
    });
    expect(() => httpSource.voiceWarm!("supertonic:F1")).not.toThrow();
  });
});
