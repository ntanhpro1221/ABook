import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ONLINE_RETRY_MS, retryWhenOnline, whenBackOnline } from "./onlineRetry";

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

describe("mạng về: chỉ tự phát khi người nghe đã bấm phát (soát a66)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const online = (wantsPlay: boolean) => {
    const target = new EventTarget();
    const retry = vi.fn();
    const dismiss = vi.fn();
    retryWhenOnline(whenBackOnline(() => wantsPlay, retry, dismiss), target as unknown as Window);
    target.dispatchEvent(new Event("online"));
    vi.advanceTimersByTime(ONLINE_RETRY_MS);
    return { retry, dismiss };
  };

  it("đã bấm phát, lỗi lúc đang phát / chờ phát: tự Thử lại", () => {
    const { retry, dismiss } = online(true);
    expect(retry).toHaveBeenCalledTimes(1);
    expect(dismiss).not.toHaveBeenCalled();
  });

  it("lỗi sinh lúc mở app, chưa bấm phát: chỉ gỡ lời báo, không phát", () => {
    const { retry, dismiss } = online(false);
    expect(retry).not.toHaveBeenCalled();
    expect(dismiss).toHaveBeenCalledTimes(1);
  });
});
