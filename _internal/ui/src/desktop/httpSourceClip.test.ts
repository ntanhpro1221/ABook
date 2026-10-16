import { afterEach, describe, expect, it, vi } from "vitest";
import { isTransientClipError, ReadAloudError } from "@/listen/readAloud";
import { httpSource } from "./httpSource";

afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("httpSource.readAloudClip tải luôn file audio (uxfix53)", () => {
  it("xin clip bằng POST rồi lấy file audio bằng fetch; clip trả về kèm file", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${url.split("?")[0]}`);
        if (init?.method === "POST") return json({ url: "/media/readaloud/abc.mp3", duration_ms: 1500, words: [[0, 400]] });
        return new Response(new Blob(["mp3"], { type: "audio/mpeg" }), { status: 200 });
      }),
    );
    const clip = await httpSource.readAloudClip!("edge:v", "Xin chào.", { rank: 0 });
    expect(calls).toEqual(["POST /api/readaloud/clip", "GET /media/readaloud/abc.mp3"]);
    expect(clip.url).toContain("/media/readaloud/abc.mp3");
    expect(clip.durationMs).toBe(1500);
    expect(await clip.bytes!.text()).toBe("mp3");
  });

  it("không tải được file audio = clip hỏng (lỗi thoáng qua, bộ máy thử lại như lỗi máy chủ)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => (init?.method === "POST" ? json({ url: "/media/readaloud/abc.mp3", duration_ms: 1500, words: [] }) : new Response("", { status: 404 }))),
    );
    const error = await httpSource.readAloudClip!("edge:v", "Xin chào.").catch((e) => e);
    expect(error).toBeInstanceOf(ReadAloudError);
    expect(isTransientClipError(error)).toBe(true);
  });

  it("chỉ tra bộ đệm mà chưa có: không tải file nào; mẫu giọng (readAloudSample) chỉ lấy đường dẫn, không tải file", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === "POST" ? json(JSON.parse(String(init.body)).cachedOnly ? { cached: false, reason: "uncached" } : { url: "/media/readaloud/s.mp3", duration_ms: 900, words: [] }) : new Response("x"),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(httpSource.readAloudClip!("edge:v", "Chưa có.", { cachedOnly: true })).rejects.toMatchObject({ reason: "uncached" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const sample = await httpSource.readAloudSample!("edge:v", "Nghe thử.");
    expect(sample).toContain("/media/readaloud/s.mp3");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
