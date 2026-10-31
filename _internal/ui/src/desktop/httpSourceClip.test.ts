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

  it("bộ máy bỏ lượt xin (giọng trên máy, uxfix70): fetch nhận signal - huỷ là đóng kết nối, lỗi mang lý do cancelled (không thử lại)", async () => {
    let seen: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            seen = init?.signal ?? undefined;
            init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      ),
    );
    const controller = new AbortController();
    const pending = httpSource.readAloudClip!("supertonic:F1", "Đoạn bị bỏ.", { signal: controller.signal }).catch((e) => e);
    await Promise.resolve();
    controller.abort();
    const error = await pending;
    expect(seen?.aborted).toBe(true); // tín hiệu fetch nhận được đi theo signal của người gọi (watchedCall chuyển tiếp)
    expect(error).toBeInstanceOf(ReadAloudError);
    expect(error.reason).toBe("cancelled");
    expect(isTransientClipError(error)).toBe(false);
  });
});

/** Bản ghi như máy chủ gửi: 1 byte loại + 4 byte độ dài (big-endian) + nội dung. */
function record(kind: string, body: Uint8Array | object): Uint8Array {
  const bytes = body instanceof Uint8Array ? body : new TextEncoder().encode(JSON.stringify(body));
  const out = new Uint8Array(5 + bytes.length);
  out[0] = kind.charCodeAt(0);
  new DataView(out.buffer).setUint32(1, bytes.length, false);
  out.set(bytes, 5);
  return out;
}

const streamReply = (...records: Uint8Array[]) =>
  new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        records.forEach((item) => controller.enqueue(item));
        controller.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "application/vnd.abook.clipstream" } },
  );

describe("httpSource.readAloudClip phát luồng đoạn đang chờ (uxfix56)", () => {
  const bodies: Record<string, unknown>[] = [];
  const server = (reply: () => Response) => {
    bodies.length = 0;
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        bodies.push(JSON.parse(String(init.body)));
        return reply();
      }
      return new Response(new Blob(["mp3"]), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("MediaSource", { isTypeSupported: (type: string) => type === "audio/mpeg" });
    return fetchMock;
  };

  it("rank 0: xin phát luồng; clip về với byte đầu, kèm live, không tải file riêng; xong thì live.final có file", async () => {
    const fetchMock = server(() => streamReply(record("A", new Uint8Array([1, 2])), record("E", { url: "/media/readaloud/s.mp3", duration_ms: 900, words: [[0, 800]] })));
    const clip = await httpSource.readAloudClip!("edge:v", "Xin chào.", { rank: 0 });
    expect(bodies[0].stream).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1); // không GET file
    expect(clip.live).toBeDefined();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(clip.live!.state).toBe("done");
    expect(clip.live!.final!.url).toContain("/media/readaloud/s.mp3");
    expect(await clip.live!.final!.bytes!.text()).toBe("\u0001\u0002");
  });

  it("máy chủ có clip trong bộ đệm nên trả JSON như thường: vẫn tải file, không có live", async () => {
    server(() => json({ url: "/media/readaloud/c.mp3", duration_ms: 700, words: [] }));
    const clip = await httpSource.readAloudClip!("edge:v", "Xin chào.", { rank: 0 });
    expect(bodies[0].stream).toBe(true);
    expect(clip.live).toBeUndefined();
    expect(await clip.bytes!.text()).toBe("mp3");
  });

  it("lỗi trước byte đầu (X) hay lỗi HTTP: ném ReadAloudError đúng lý do", async () => {
    server(() => streamReply(record("X", { message: "Dịch vụ bận", reason: "timeout" })));
    await expect(httpSource.readAloudClip!("edge:v", "Xin chào.", { rank: 0 })).rejects.toMatchObject({ message: "Dịch vụ bận", reason: "timeout" });
    server(() => json({ error: "Giọng bị từ chối", reason: "rejected" }, 502));
    await expect(httpSource.readAloudClip!("edge:v", "Xin chào.", { rank: 0 })).rejects.toBeInstanceOf(ReadAloudError);
  });

  it("không phát luồng: đoạn đọc trước (rank khác 0), chỉ tra bộ đệm, chỗ chờ giữa đoạn (whole), trình duyệt không có MediaSource", async () => {
    server(() => json({ url: "/media/readaloud/c.mp3", duration_ms: 700, words: [] }));
    await httpSource.readAloudClip!("edge:v", "Một.", { rank: 1 });
    await httpSource.readAloudClip!("edge:v", "Hai.", {});
    await httpSource.readAloudClip!("edge:v", "Ba.", { rank: 0, whole: true });
    expect(bodies.map((body) => body.stream)).toEqual([undefined, undefined, undefined]);
    vi.stubGlobal("MediaSource", undefined);
    await httpSource.readAloudClip!("edge:v", "Bốn.", { rank: 0 });
    expect(bodies.at(-1)!.stream).toBeUndefined();
  });
});

describe("httpSource.readAloudClip: clip đuôi khi bấm giữa đoạn (uxfix56)", () => {
  const bodies: Record<string, unknown>[] = [];
  const server = (reply: (body: Record<string, unknown>) => Response) => {
    bodies.length = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        if (init?.method !== "POST") return new Response(new Blob(["mp3"]), { status: 200 });
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        return reply(body);
      }),
    );
    vi.stubGlobal("MediaSource", { isTypeSupported: () => true });
  };
  const full = "Ba bốn năm sáu.";
  const streamed = () => streamReply(record("A", new Uint8Array([1])), record("E", { url: "/media/readaloud/t.mp3", duration_ms: 900, words: [[0, 400], [400, 900]] }));

  it("chưa có cả đoạn trong bộ đệm: tra bộ đệm một lần rồi phát luồng phần đuôi, clip trả về có fromWord", async () => {
    server((body) => (body.cachedOnly ? json({ cached: false, reason: "uncached" }) : streamed()));
    const clip = await httpSource.readAloudClip!("edge:v", full, { rank: 0, tailFrom: 2 });
    expect(bodies.map((body) => [body.text, body.cachedOnly ?? false, body.stream ?? false])).toEqual([
      [full, true, false],
      ["năm sáu.", false, true],
    ]);
    expect(clip.fromWord).toBe(2);
    expect(clip.live).toBeDefined();
  });

  it("cả đoạn đã có trong bộ đệm: dùng luôn clip đủ cả đoạn (nghe ngay, mốc đủ), không fromWord", async () => {
    server(() => json({ url: "/media/readaloud/full.mp3", duration_ms: 2000, words: [[0, 400]] }));
    const clip = await httpSource.readAloudClip!("edge:v", full, { rank: 0, tailFrom: 2 });
    expect(bodies).toHaveLength(1);
    expect(bodies[0].cachedOnly).toBe(true);
    expect(clip.fromWord).toBeUndefined();
    expect(clip.durationMs).toBe(2000);
    expect(await clip.bytes!.text()).toBe("mp3");
  });

  it("phần đuôi đã có trong bộ đệm của máy chủ (JSON): clip có file và fromWord", async () => {
    server((body) => (body.cachedOnly ? json({ cached: false, reason: "uncached" }) : json({ url: "/media/readaloud/t.mp3", duration_ms: 900, words: [[0, 400], [400, 900]] })));
    const clip = await httpSource.readAloudClip!("edge:v", full, { rank: 0, tailFrom: 2 });
    expect(clip.fromWord).toBe(2);
    expect(clip.live).toBeUndefined();
    expect(await clip.bytes!.text()).toBe("mp3");
  });

  it("không phát luồng được (không MediaSource / chữ không có trong đoạn): xin cả đoạn như thường, không fromWord", async () => {
    server(() => json({ url: "/media/readaloud/full.mp3", duration_ms: 2000, words: [] }));
    vi.stubGlobal("MediaSource", undefined);
    let clip = await httpSource.readAloudClip!("edge:v", full, { rank: 0, tailFrom: 2 });
    expect(bodies.map((body) => [body.text, body.stream ?? false])).toEqual([[full, false]]);
    expect(clip.fromWord).toBeUndefined();
    vi.stubGlobal("MediaSource", { isTypeSupported: () => true });
    bodies.length = 0;
    clip = await httpSource.readAloudClip!("edge:v", full, { rank: 0, tailFrom: 9 });
    expect(bodies.map((body) => [body.text, body.stream ?? false])).toEqual([[full, false]]);
    expect(clip.fromWord).toBeUndefined();
  });

  it("lỗi thật của lượt tra bộ đệm (không phải 'chưa có') dừng luôn, không đi tiếp", async () => {
    server(() => json({ error: "hỏng", reason: "service" }, 500));
    await expect(httpSource.readAloudClip!("edge:v", full, { rank: 0, tailFrom: 2 })).rejects.toBeInstanceOf(ReadAloudError);
    expect(bodies).toHaveLength(1);
  });
});

describe("httpSource.readAloudClip: giọng trên máy phát luồng (FLAC, local_stream)", () => {
  const bodies: Record<string, unknown>[] = [];
  const server = (types: string[], reply: () => Response) => {
    bodies.length = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        bodies.push(JSON.parse(String(init?.body)));
        return reply();
      }),
    );
    vi.stubGlobal("MediaSource", { isTypeSupported: (type: string) => types.includes(type) });
  };
  const FLAC = 'audio/mp4; codecs="flac"';

  it("trình duyệt nhận FLAC: xin cả luồng giọng trên máy, kèm tốc độ đang nghe; bản ghi M đặt kiểu tiếng, file cuối là WAV (không gom byte)", async () => {
    server(["audio/mpeg", FLAC], () =>
      streamReply(
        record("M", { mime: FLAC }),
        record("A", new Uint8Array([1, 2, 3])),
        record("W", { words: [[0, 400]], duration_ms: 800, heard_ms: 800 }),
        record("E", { url: "/media/readaloud/s.wav", duration_ms: 800, words: [[0, 400]], exact: false }),
      ),
    );
    const clip = await httpSource.readAloudClip!("supertonic:F1", "Xin chào.", { rank: 0, rate: 1.5 });
    expect(bodies[0]).toMatchObject({ stream: true, localStream: true, rate: 1.5 });
    await new Promise((resolve) => setTimeout(resolve, 0));
    const live = clip.live!;
    expect(live.mime).toBe(FLAC);
    expect(live.receivedMs).toBe(800);
    expect(live.final).toMatchObject({ durationMs: 800, exact: false });
    expect(live.final!.url).toContain("/media/readaloud/s.wav");
    expect(live.final!.bytes).toBeUndefined();
  });

  it("giọng trên máy (onDevice): đoạn đọc trước (rank > 0) cũng xin luồng khi trình duyệt nhận FLAC; trình duyệt chỉ nhận MP3 thì không (livejoin)", async () => {
    server(["audio/mpeg", FLAC], () => json({ url: "/media/readaloud/c.wav", duration_ms: 700, words: [] }));
    await httpSource.readAloudClip!("supertonic:F1", "Đoạn đọc trước.", { rank: 2, onDevice: true, soundLeft: 4.5 }).catch(() => undefined);
    expect(bodies[0]).toMatchObject({ stream: true, localStream: true, rank: 2, soundLeft: 4.5 });
    await httpSource.readAloudClip!("supertonic:F1", "Chỉ tra.", { rank: 2, onDevice: true, cachedOnly: true }).catch(() => undefined);
    await httpSource.readAloudClip!("supertonic:F1", "Chờ giữa đoạn.", { rank: 2, onDevice: true, whole: true }).catch(() => undefined);
    await httpSource.readAloudClip!("edge:v", "Edge đọc trước.", { rank: 2 }).catch(() => undefined);
    expect(bodies.slice(1).map((body) => body.stream)).toEqual([undefined, undefined, undefined]);
    server(["audio/mpeg"], () => json({ url: "/media/readaloud/c.wav", duration_ms: 700, words: [] }));
    await httpSource.readAloudClip!("supertonic:F1", "Không FLAC.", { rank: 2, onDevice: true }).catch(() => undefined);
    expect(bodies.at(-1)!.stream).toBeUndefined();
  });

  it("trình duyệt không nhận FLAC: không xin luồng giọng trên máy (máy chủ trả JSON như cũ); tốc độ thường thì không gửi rate", async () => {
    server(["audio/mpeg"], () => json({ url: "/media/readaloud/c.wav", duration_ms: 700, words: [] }));
    await httpSource.readAloudClip!("supertonic:F1", "Xin chào.", { rank: 0 }).catch(() => undefined);
    expect(bodies[0].stream).toBe(true);
    expect(bodies[0].localStream).toBeUndefined();
    expect(bodies[0].rate).toBeUndefined();
    expect(bodies[0].soundLeft).toBeUndefined();
  });

  it("bị bỏ giữa luồng (giọng trên máy): clip đang về hỏng với lý do cancelled, không phải mất kết nối", async () => {
    const controller = new AbortController();
    let stop!: ReadableStreamDefaultController<Uint8Array>;
    server(["audio/mpeg", FLAC], () =>
      new Response(
        new ReadableStream<Uint8Array>({
          start(c) {
            stop = c;
            c.enqueue(record("M", { mime: FLAC }));
            c.enqueue(record("A", new Uint8Array([1])));
          },
        }),
        { status: 200, headers: { "Content-Type": "application/vnd.abook.clipstream" } },
      ),
    );
    const clip = await httpSource.readAloudClip!("supertonic:F1", "Đoạn bị bỏ.", { rank: 0, signal: controller.signal });
    controller.abort();
    stop.error(new DOMException("aborted", "AbortError"));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(clip.live!.state).toBe("failed");
    expect(clip.live!.error!.reason).toBe("cancelled");
  });
});
