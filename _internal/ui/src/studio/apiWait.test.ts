import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ReadAloudError } from "@/listen/readAloud";
import { httpSource } from "@/desktop/httpSource";
import { ApiError, api } from "./api";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
/** fetch của máy chủ im lặng: chỉ kết thúc khi bị huỷ. */
const hung = () =>
  vi.fn(
    (_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))),
  );

it("lời gọi thường: im 30 s thì gửi lại một lần, im nữa thì báo hết hạn như chính máy chủ (504, lý do timeout)", async () => {
  const fetchMock = hung();
  vi.stubGlobal("fetch", fetchMock);
  const result = api("/api/listen/library").catch((error) => error);
  await vi.advanceTimersByTimeAsync(29_999);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1);
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await vi.advanceTimersByTimeAsync(30_000);
  const error = await result;
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status: 504, detail: { reason: "timeout" } });
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("giọng đọc (clip, nghe thử): chờ 100 s mỗi lượt, gửi lại đúng lời gọi cũ", async () => {
  const fetchMock = hung();
  vi.stubGlobal("fetch", fetchMock);
  const clip = api("/api/readaloud/clip", { method: "POST", body: { voice: "v", text: "Xin chào." } }).catch((error) => error);
  const preview = api("/api/books/b1/voice/preview", { method: "POST", body: { voice: "v" } }).catch((error) => error);
  await vi.advanceTimersByTimeAsync(99_999);
  expect(fetchMock).toHaveBeenCalledTimes(2);
  await vi.advanceTimersByTimeAsync(1);
  expect(fetchMock).toHaveBeenCalledTimes(4);
  expect(fetchMock.mock.calls[2][1]?.body).toBe(fetchMock.mock.calls[0][1]?.body);
  expect(fetchMock.mock.calls[2][1]?.method).toBe("POST");
  await vi.advanceTimersByTimeAsync(100_000);
  expect(await clip).toMatchObject({ status: 504, detail: { reason: "timeout" } });
  expect(await preview).toMatchObject({ status: 504, detail: { reason: "timeout" } });
});

it("máy chủ tự báo lỗi kèm lý do (Edge hạn 91 s < 100 s): lý do của nó đi thẳng ra, không gửi lại", async () => {
  const fetchMock = vi.fn(
    (_url: string, init?: RequestInit) =>
      new Promise<Response>((resolve, reject) => {
        const timer = setTimeout(() => resolve(json({ error: "Microsoft trả lời quá chậm.", reason: "timeout" }, 504)), 91_000);
        init?.signal?.addEventListener("abort", () => {
          clearTimeout(timer);
          reject(new DOMException("aborted", "AbortError"));
        });
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  const result = api("/api/readaloud/clip", { method: "POST", body: {} }).catch((error) => error);
  await vi.advanceTimersByTimeAsync(91_000);
  const error = await result;
  expect(error).toMatchObject({ status: 504, message: "Microsoft trả lời quá chậm.", detail: { reason: "timeout" } });
  expect(fetchMock).toHaveBeenCalledTimes(1);
  // Lý do khác cũng nguyên vẹn.
  fetchMock.mockImplementationOnce(async () => json({ error: "Không có mạng.", reason: "offline" }, 503));
  await expect(api("/api/readaloud/clip", { method: "POST", body: {} })).rejects.toMatchObject({ status: 503, detail: { reason: "offline" } });
});

it("lời đáp dài về từng khúc đều đặn không bị cắt dù cả lượt vượt xa hạn 30 s", async () => {
  const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
    let n = 0;
    const text = JSON.stringify({ ok: true });
    const stream = new ReadableStream<Uint8Array>({
      pull: (controller) =>
        new Promise<void>((resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
          setTimeout(() => {
            if (n < text.length) controller.enqueue(new TextEncoder().encode(text[n++]));
            else controller.close();
            resolve();
          }, 20_000);
        }),
    });
    return Promise.resolve(new Response(stream, { status: 200 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  const result = api<{ ok: boolean }>("/api/listen/library");
  await vi.advanceTimersByTimeAsync(20_000 * 14);
  expect(await result).toEqual({ ok: true });
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("người gọi bỏ lượt (signal): vẫn là lỗi huỷ, không thành hết hạn và không gửi lại", async () => {
  const fetchMock = hung();
  vi.stubGlobal("fetch", fetchMock);
  const outer = new AbortController();
  const result = api("/api/readaloud/clip", { method: "POST", body: {}, signal: outer.signal }).catch((error) => error);
  await vi.advanceTimersByTimeAsync(10_000);
  outer.abort();
  expect(await result).toMatchObject({ name: "AbortError" });
  await vi.advanceTimersByTimeAsync(300_000);
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("httpSource.readAloudClip: máy chủ im lặng cả hai lượt = ReadAloudError lý do timeout (giọng đọc báo \"không dùng được\")", async () => {
  vi.stubGlobal("fetch", hung());
  const result = httpSource.readAloudClip!("edge:v", "Xin chào.", { rank: 1 }).catch((error) => error);
  await vi.advanceTimersByTimeAsync(200_000);
  const error = await result;
  expect(error).toBeInstanceOf(ReadAloudError);
  expect(error).toMatchObject({ reason: "timeout" });
});
