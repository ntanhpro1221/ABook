import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { leftWithPeer, watchUntilBack } from "./peerBack";

// Soát a27 lỗi 3: máy kia tắt giữa chừng rồi bật lại - trình phát tự thử lại đúng một lần khi máy ấy trả lời.

describe("watchUntilBack", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("window", globalThis);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("tries once when the other computer answers again", async () => {
    const answers = [false, false, true, true];
    const onBack = vi.fn();
    watchUntilBack(async () => answers.shift() ?? true, onBack, { everyMs: 1000 });
    await vi.advanceTimersByTimeAsync(2500);
    expect(onBack).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1000);
    expect(onBack).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("a failed question counts as no answer, and stopping ends it", async () => {
    const onBack = vi.fn();
    const ask = vi.fn(async () => {
      throw new Error("mất mạng");
    });
    const stop = watchUntilBack(ask, onBack, { everyMs: 1000 });
    await vi.advanceTimersByTimeAsync(3500);
    expect(ask).toHaveBeenCalledTimes(3);
    stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(ask).toHaveBeenCalledTimes(3);
    expect(onBack).not.toHaveBeenCalled();
  });

  it("gives up after a while", async () => {
    const ask = vi.fn(async () => false);
    watchUntilBack(ask, vi.fn(), { everyMs: 1000, giveUpMs: 2500 });
    await vi.advanceTimersByTimeAsync(10_000);
    expect(ask).toHaveBeenCalledTimes(2);
  });
});

// Soát a27 lỗi 11: bỏ ghép khi đang nạp cuốn của máy kia - trình phát đóng thay vì giữ cuốn đã rời Thư viện.
describe("leftWithPeer", () => {
  it("closes only a book of another machine that is gone from the library", () => {
    const remote = { id: "r", remote: { computer: "Máy A" } };
    expect(leftWithPeer(remote, [{ id: "x" }])).toBe(true);
    expect(leftWithPeer(remote, [{ id: "r" }])).toBe(false);
    expect(leftWithPeer(remote, undefined)).toBe(false);
    expect(leftWithPeer({ id: "mine" }, [])).toBe(false);
    expect(leftWithPeer(null, [])).toBe(false);
  });
});
