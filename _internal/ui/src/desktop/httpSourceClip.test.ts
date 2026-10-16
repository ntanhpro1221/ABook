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
    expect(await clip.live!.final!.bytes.text()).toBe("\u0001\u0002");
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
