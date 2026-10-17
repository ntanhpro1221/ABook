import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ONLINE_RETRY_MS, retryWhenOnline } from "./onlineRetry";

describe("retryWhenOnline", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("mạng về thì tự Thử lại sau một nhịp, một lần cho nhiều sự kiện sát nhau", () => {
    const target = new EventTarget();
    const retry = vi.fn();
    retryWhenOnline(retry, target as unknown as Window);
    target.dispatchEvent(new Event("online"));
    target.dispatchEvent(new Event("online"));
    vi.advanceTimersByTime(ONLINE_RETRY_MS - 1);
    expect(retry).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("gỡ (lời báo đã tắt) trước khi tới giờ thì không thử, sự kiện sau cũng không", () => {
    const target = new EventTarget();
    const retry = vi.fn();
    const stop = retryWhenOnline(retry, target as unknown as Window);
    target.dispatchEvent(new Event("online"));
    stop();
    target.dispatchEvent(new Event("online"));
    vi.advanceTimersByTime(ONLINE_RETRY_MS * 2);
    expect(retry).not.toHaveBeenCalled();
  });
});
