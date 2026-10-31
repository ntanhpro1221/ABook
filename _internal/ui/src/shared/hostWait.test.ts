import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ATTEMPTS, HostTimeout, IDLE_MS, SPEECH_IDLE_MS, STALL_MS, fetchWatched, idleMs, isSpeech, readText, watchedCall } from "./hostWait";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

/** Lời gọi mà máy chủ im lặng: chỉ kết thúc khi bị huỷ. */
const silent = vi.fn((signal: AbortSignal) => new Promise<Response>((_resolve, reject) => signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))));
afterEach(() => silent.mockClear());

/** Thân lời đáp nhả từng khúc, cách nhau `gap` ms (đồng hồ giả). */
function trickle(chunks: string[], gap: number, signal: AbortSignal): Response {
  let sent = 0;
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    pull: (controller) =>
      new Promise<void>((resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
        setTimeout(() => {
          if (sent < chunks.length) controller.enqueue(encoder.encode(chunks[sent++]));
          else controller.close();
          resolve();
        }, gap);
      }),
  });
  return new Response(stream, { status: 200 });
}

describe("chính sách chờ chung", () => {
  it("giọng đọc 100 s, mọi thứ khác 30 s; hạn chót của trình phát lớn hơn mọi hạn bên dưới", () => {
    expect([IDLE_MS, SPEECH_IDLE_MS, ATTEMPTS, STALL_MS]).toEqual([30_000, 100_000, 2, 215_000]);
    expect(idleMs("/api/readaloud/clip")).toBe(100_000);
    expect(idleMs("/api/readaloud/clip?x=1")).toBe(100_000);
    expect(idleMs("/api/books/abc/voice/preview")).toBe(100_000);
    for (const other of ["/api/readaloud/voices", "/api/readaloud/prepare", "/api/books/abc/voice", "/api/books/abc/script", "/api/listen/library"]) {
      expect(isSpeech(other), other).toBe(false);
      expect(idleMs(other)).toBe(30_000);
    }
  });
});

describe("watchedCall: hỏng khi KHÔNG CÓ BYTE NÀO về", () => {
  it("máy chủ im lặng: huỷ, gửi lại đúng một lần, rồi báo hết hạn", async () => {
    const result = watchedCall((signal) => silent(signal), 30_000, readText).catch((error) => error);
    await vi.advanceTimersByTimeAsync(29_999);
    expect(silent).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(silent).toHaveBeenCalledTimes(2);
    expect(silent.mock.calls[0][0].aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(await result).toBeInstanceOf(HostTimeout);
    expect(silent).toHaveBeenCalledTimes(2);
  });

  it("lượt gửi lại được trả lời thì không có lỗi nào", async () => {
    let tries = 0;
    const result = watchedCall(
      (signal) => (++tries === 1 ? silent(signal) : Promise.resolve(new Response("xong"))),
      30_000,
      readText,
    );
    await vi.advanceTimersByTimeAsync(30_000);
    expect(await result).toBe("xong");
    expect(tries).toBe(2);
  });

  it("máy chủ trả lời sát hạn (99 s với giọng đọc) thì không bị cắt", async () => {
    const result = watchedCall(() => new Promise<Response>((resolve) => setTimeout(() => resolve(new Response("clip")), 99_000)), SPEECH_IDLE_MS, readText);
    await vi.advanceTimersByTimeAsync(99_000);
    expect(await result).toBe("clip");
  });

  it("thân lời đáp về chậm nhưng từng khúc đều đặn thì không bao giờ hết hạn, dù cả lượt dài gấp nhiều lần hạn", async () => {
    const result = watchedCall((signal) => Promise.resolve(trickle(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"], 25_000, signal)), 30_000, readText);
    await vi.advanceTimersByTimeAsync(25_000 * 11);
    expect(await result).toBe("abcdefghij");
  });

  it("thân đang về rồi đứng im quá hạn: huỷ và gửi lại một lần", async () => {
    let tries = 0;
    const result = watchedCall(
      (signal) => {
        if (++tries > 1) return Promise.resolve(new Response("đủ"));
        const body = new ReadableStream<Uint8Array>({
          start: (controller) => controller.enqueue(new TextEncoder().encode("nửa")),
          pull: () => new Promise<void>((_resolve, reject) => signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))),
        });
        return Promise.resolve(new Response(body));
      },
      30_000,
      readText,
    );
    await vi.advanceTimersByTimeAsync(30_001);
    expect(await result).toBe("đủ");
    expect(tries).toBe(2);
  });

  it("người gọi bỏ lời gọi: lỗi huỷ như cũ, không gửi lại", async () => {
    const outer = new AbortController();
    const result = watchedCall((signal) => silent(signal), 30_000, readText, outer.signal).catch((error) => error);
    await vi.advanceTimersByTimeAsync(5_000);
    outer.abort();
    const error = await result;
    expect(error).toBeInstanceOf(DOMException);
    expect((error as DOMException).name).toBe("AbortError");
    await vi.advanceTimersByTimeAsync(120_000);
    expect(silent).toHaveBeenCalledTimes(1);
  });

  it("lỗi không phải im lặng (mất kết nối, máy chủ báo lỗi) đi thẳng ra, không gửi lại", async () => {
    const down = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(watchedCall(down, 30_000, readText)).rejects.toBeInstanceOf(TypeError);
    expect(down).toHaveBeenCalledTimes(1);
  });

  it("read trả về sớm (giao thân cho nơi đọc dần) thì hết canh, nhưng tín hiệu của người gọi vẫn huỷ được thân", async () => {
    const outer = new AbortController();
    let seen: AbortSignal | undefined;
    const handed = await watchedCall(
      (signal) => {
        seen = signal;
        return Promise.resolve(new Response("luồng"));
      },
      30_000,
      async (response) => response,
      outer.signal,
    );
    expect(handed).toBeInstanceOf(Response);
    await vi.advanceTimersByTimeAsync(600_000);
    expect(seen?.aborted).toBe(false);
    outer.abort();
    expect(seen?.aborted).toBe(true);
  });
});

describe("fetchWatched: file clip đã xong", () => {
  it("trả về Response đã đọc đủ, giữ nguyên trạng thái", async () => {
    const response = await fetchWatched("/media/readaloud/a.mp3", vi.fn(async () => new Response("mp3", { status: 200 })) as unknown as typeof fetch);
    expect(response.status).toBe(200);
    expect(await response.text()).toBe("mp3");
    const missing = await fetchWatched("/media/x", vi.fn(async () => new Response("", { status: 404 })) as unknown as typeof fetch);
    expect(missing.ok).toBe(false);
  });

  it("máy chủ im lặng 30 s hai lần: ném hết hạn (fetchClipBytes biến thành clip hỏng)", async () => {
    const hung = vi.fn((_url: string, init?: RequestInit) => silent(init!.signal!)) as unknown as typeof fetch;
    const result = fetchWatched("/media/x", hung).catch((error) => error);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(await result).toBeInstanceOf(HostTimeout);
  });
});
