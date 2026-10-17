import { describe, expect, it } from "vitest";
import { ReadAloudError } from "./readAloud";
import { LiveClip, RecordReader, UNHEARD_MS, clipFromStream } from "./liveClip";
import { LiveFeed } from "./liveFeed";
import { FakeSource } from "./liveTestKit";

const encoder = new TextEncoder();

/** Bản ghi như máy chủ gửi (abook/webui/server.py ClipStream): 1 byte loại + 4 byte độ dài (big-endian) + nội dung. */
function record(kind: string, body: Uint8Array | object): Uint8Array {
  const bytes = body instanceof Uint8Array ? body : encoder.encode(JSON.stringify(body));
  const out = new Uint8Array(5 + bytes.length);
  out[0] = kind.charCodeAt(0);
  new DataView(out.buffer).setUint32(1, bytes.length, false);
  out.set(bytes, 5);
  return out;
}

const concat = (...parts: Uint8Array[]): Uint8Array => {
  const out = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));
  let at = 0;
  for (const part of parts) {
    out.set(part, at);
    at += part.length;
  }
  return out;
};

const bytes = (...values: number[]) => new Uint8Array(values);
const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe("RecordReader: tách bản ghi từ các khúc mạng", () => {
  it("bản ghi bị cắt ở chỗ nào giữa hai khúc mạng cũng ra đủ, đúng thứ tự", () => {
    const wire = concat(record("A", bytes(1, 2, 3)), record("W", { words: [[0, 5]], duration_ms: 5 }), record("A", bytes(9)), record("E", { url: "/m/x.mp3", duration_ms: 7, words: [[0, 7]] }));
    for (let cut = 0; cut <= wire.length; cut += 1) {
      const reader = new RecordReader();
      const found = [...reader.push(wire.slice(0, cut)), ...reader.push(wire.slice(cut))];
      expect(found.map((item) => item.kind)).toEqual(["A", "W", "A", "E"]);
      expect([...found[0].body]).toEqual([1, 2, 3]);
      expect([...found[2].body]).toEqual([9]);
      expect(reader.dangling).toBe(false);
    }
  });

  it("từng byte một vẫn tách được; bản ghi rỗng; còn dở thì báo dangling", () => {
    const wire = concat(record("A", bytes()), record("A", bytes(4, 5)));
    const reader = new RecordReader();
    const found = [...wire].flatMap((byte) => reader.push(bytes(byte)));
    expect(found.map((item) => [item.kind, [...item.body]])).toEqual([["A", []], ["A", [4, 5]]]);
    reader.push(record("A", bytes(1, 2, 3)).slice(0, 7));
    expect(reader.dangling).toBe(true);
  });
});

/** Luồng thân lời đáp điều khiển được: `send` đẩy một khúc mạng, `end` đóng, `crash` làm đứt. */
function wire() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  return { body, send: (chunk: Uint8Array) => controller.enqueue(chunk), end: () => controller.close(), crash: () => controller.error(new TypeError("network error")) };
}

const toUrl = (path: string) => `${path}?t=k`;

describe("clipFromStream: lời đáp phát luồng của máy chủ", () => {
  it("trả clip ngay khi byte tiếng đầu về; mốc tạm, khúc tiếp và kết quả cuối cập nhật clip.live", async () => {
    const stream = wire();
    const pending = clipFromStream(stream.body, toUrl);
    let settled = false;
    void pending.then(() => (settled = true));
    await flush();
    expect(settled).toBe(false);
    stream.send(record("A", bytes(1, 2)));
    const clip = await pending;
    expect(clip.url).toBe("");
    expect(clip.durationMs).toBe(0);
    expect(clip.words).toEqual([]);
    const live = clip.live!;
    expect(live.state).toBe("open");
    expect(live.chunks.map((chunk) => [...chunk])).toEqual([[1, 2]]);
    const seen: string[] = [];
    live.on((event) => seen.push(event));
    stream.send(concat(record("W", { words: [[0, 300], [300, 300]], duration_ms: 300 }), record("A", bytes(3))));
    await flush();
    expect(live.words).toEqual([[0, 300], [300, 300]]);
    expect(live.chunks).toHaveLength(2);
    stream.send(record("E", { url: "/media/readaloud/x.mp3", duration_ms: 1500, words: [[0, 700], [700, 1500]] }));
    stream.end();
    await flush();
    expect(live.state).toBe("done");
    expect(seen).toEqual(["words", "audio", "done"]);
    expect(live.final).toMatchObject({ url: "/media/readaloud/x.mp3?t=k", durationMs: 1500, words: [[0, 700], [700, 1500]] });
    expect([...new Uint8Array(await live.final!.bytes.arrayBuffer())]).toEqual([1, 2, 3]);
    expect(live.words).toEqual([[0, 700], [700, 1500]]);
  });

  it("bản ghi bị cắt giữa hai khúc mạng vẫn nối đúng", async () => {
    const stream = wire();
    const pending = clipFromStream(stream.body, toUrl);
    const all = concat(record("A", bytes(1, 2, 3, 4)), record("E", { url: "/m/y.mp3", duration_ms: 9, words: [] }));
    stream.send(all.slice(0, 3));
    stream.send(all.slice(3, 11));
    stream.send(all.slice(11));
    stream.end();
    const live = (await pending).live!;
    await flush();
    expect(live.state).toBe("done");
    expect(live.chunks.map((chunk) => [...chunk])).toEqual([[1, 2, 3, 4]]);
  });

  it("A và E cùng một khúc mạng: clip về với live đã xong", async () => {
    const stream = wire();
    stream.send(concat(record("A", bytes(7)), record("E", { url: "/m/z.mp3", duration_ms: 20, words: [[0, 20]] })));
    stream.end();
    const live = (await clipFromStream(stream.body, toUrl)).live!;
    expect(live.state).toBe("done");
    expect(live.final?.durationMs).toBe(20);
  });

  it("lỗi (X) trước byte đầu: ném ReadAloudError với đúng lý do", async () => {
    const stream = wire();
    const pending = clipFromStream(stream.body, toUrl);
    stream.send(record("X", { message: "Dịch vụ bận", reason: "timeout" }));
    stream.end();
    const error = await pending.catch((caught) => caught);
    expect(error).toBeInstanceOf(ReadAloudError);
    expect([error.message, error.reason]).toEqual(["Dịch vụ bận", "timeout"]);
  });

  it("đứt kết nối trước byte đầu: lỗi thoáng qua 'service'", async () => {
    const stream = wire();
    const pending = clipFromStream(stream.body, toUrl);
    stream.crash();
    const error = await pending.catch((caught) => caught);
    expect(error).toBeInstanceOf(ReadAloudError);
    expect(error.reason).toBe("service");
    await expect(clipFromStream(null, toUrl)).rejects.toBeInstanceOf(ReadAloudError);
  });

  it("lỗi (X) hay đứt kết nối sau khi đã phát: clip.live hỏng, kèm lý do", async () => {
    for (const how of ["x", "crash", "end"] as const) {
      const stream = wire();
      const pending = clipFromStream(stream.body, toUrl);
      stream.send(record("A", bytes(1)));
      const live = (await pending).live!;
      const seen: string[] = [];
      live.on((event) => seen.push(event));
      if (how === "x") stream.send(record("X", { message: "hết giờ", reason: "timeout" }));
      else if (how === "crash") stream.crash();
      if (how === "end") stream.end();
      await flush();
      expect(live.state).toBe("failed");
      expect(seen).toEqual(["failed"]);
      expect(live.error).toBeInstanceOf(ReadAloudError);
      expect(live.error!.reason).toBe(how === "x" ? "timeout" : "service");
    }
  });
});

const final = { url: "/m/a.mp3", durationMs: 100, words: [] as [number, number][], bytes: new Blob(["x"]) };

describe("LiveFeed: nối khúc vào MediaSource", () => {
  it("nối lần lượt từng khúc (chờ updateend), cả khúc về trước và sau sourceopen; xong thì endOfStream", () => {
    const live = new LiveClip();
    live.push(bytes(1));
    const source = new FakeSource();
    new LiveFeed(source, live, () => undefined);
    expect(source.buffer.appended).toEqual([]); // chưa sourceopen
    source.open();
    expect(source.types).toEqual(["audio/mpeg"]);
    expect(source.buffer.mode).toBe("sequence");
    expect(source.buffer.appended).toEqual([[1]]);
    live.push(bytes(2));
    live.push(bytes(3));
    expect(source.buffer.appended).toEqual([[1]]); // đang nối khúc 1: khúc sau chờ
    source.buffer.finish();
    expect(source.buffer.appended).toEqual([[1], [2]]);
    source.buffer.finish();
    source.buffer.finish();
    expect(source.buffer.appended).toEqual([[1], [2], [3]]);
    expect(source.ended).toBe(false); // clip chưa xong: phần tử audio tự dừng chờ
    live.finish(final);
    expect(source.ended).toBe(true);
  });

  it("clip xong mà còn khúc chưa nối: nối hết rồi mới endOfStream", () => {
    const live = new LiveClip();
    const source = new FakeSource();
    new LiveFeed(source, live, () => undefined);
    source.open();
    live.push(bytes(1));
    live.push(bytes(2));
    live.finish(final);
    expect(source.ended).toBe(false);
    source.buffer.finish();
    expect(source.ended).toBe(false);
    source.buffer.finish();
    expect(source.buffer.appended).toEqual([[1], [2]]);
    expect(source.ended).toBe(true);
  });

  it("nối lỗi: báo broken một lần và thôi", () => {
    const live = new LiveClip();
    const source = new FakeSource();
    let broken = 0;
    new LiveFeed(source, live, () => (broken += 1));
    source.buffer.fail = true;
    source.open();
    live.push(bytes(1));
    live.push(bytes(2));
    expect(broken).toBe(1);
  });

  it("close: không nối thêm", () => {
    const live = new LiveClip();
    const source = new FakeSource();
    const feed = new LiveFeed(source, live, () => undefined);
    source.open();
    feed.close();
    live.push(bytes(1));
    expect(source.buffer.appended).toEqual([]);
  });
});

describe("LiveClip: phần đã về (uxfix58)", () => {
  it("receivedMs: số byte đã về đổi ra ms theo 48 kbps CBR của Edge (6 byte mỗi ms); heardMs từ bản ghi W (chưa có W thì null)", async () => {
    const stream = wire();
    const pending = clipFromStream(stream.body, toUrl);
    stream.send(record("A", new Uint8Array(6000)));
    const live = (await pending).live!;
    expect(live.receivedMs).toBe(1000);
    expect(live.heardMs).toBeNull();
    stream.send(concat(record("A", new Uint8Array(3000)), record("W", { words: [[0, 800], [800, 1400]], duration_ms: 1400, heard_ms: 800 })));
    await flush();
    expect(live.receivedMs).toBe(1500);
    expect(live.heardMs).toBe(800);
    stream.send(record("W", { words: [[0, 800], [800, 1400]], duration_ms: 1400 })); // máy chủ cũ: không có heard_ms
    await flush();
    expect(live.heardMs).toBeNull();
  });

  it("bản ghi C (một mảnh giữa clip hỏng, uxfix63): cutAt = chữ tiếng sẽ dừng, báo 'cut' - clip vẫn đang về, khúc sau vẫn nhận", async () => {
    const stream = wire();
    const pending = clipFromStream(stream.body, toUrl);
    stream.send(record("A", new Uint8Array(600)));
    const live = (await pending).live!;
    const seen: string[] = [];
    live.on((event) => seen.push(event));
    expect(live.cutAt).toBeNull();
    stream.send(concat(record("C", { word: 7 }), record("A", new Uint8Array(600))));
    await flush();
    expect(live.cutAt).toBe(7);
    expect(seen).toEqual(["cut", "audio"]);
    expect(live.state).toBe("open");
    expect(live.receivedMs).toBe(200);
  });
});

describe("LiveClip.shownWords: mốc chữ để tô sáng (uxfix61)", () => {
  it("chữ chưa tới (bắt đầu từ heardMs trở đi) bị đẩy ra xa; chữ đã có tiếng và máy chủ cũ (không heardMs) giữ nguyên", () => {
    const live = new LiveClip();
    const stacked: [number, number][] = [[0, 250], [250, 500], [500, 500], [500, 500]];
    live.setWords(stacked);
    expect(live.shownWords).toEqual(stacked);
    live.setWords(stacked, 500);
    expect(live.shownWords).toEqual([[0, 250], [250, 500], [UNHEARD_MS, UNHEARD_MS], [UNHEARD_MS, UNHEARD_MS]]);
    expect(live.words).toEqual(stacked); // mốc gốc không đổi (xin tiếp clip đuôi dựa vào nó)
  });
});

describe("LiveFeed: nối phần tiếp sau một clip đứt giữa chừng (uxfix58)", () => {
  const broke = () => {
    const live = new LiveClip();
    const source = new FakeSource();
    let broken = 0;
    const feed = new LiveFeed(source, live, () => (broken += 1));
    source.open();
    live.push(bytes(1));
    source.buffer.finish();
    live.push(bytes(2));
    source.buffer.finish();
    live.fail(new ReadAloudError("đứt", "service"));
    return { live, source, feed, broken: () => broken };
  };

  it("clip hỏng: không endOfStream ngay - phần đã nối vẫn phát và phần tử audio chờ phần tiếp", () => {
    const { source } = broke();
    expect(source.buffer.appended).toEqual([[1], [2]]);
    expect(source.ended).toBe(false);
  });

  it("chain: khúc của phần tiếp nối thẳng sau khúc cuối của phần hỏng (cùng MediaSource), endOfStream khi phần tiếp xong", () => {
    const { source, feed } = broke();
    const next = new LiveClip();
    next.push(bytes(7));
    feed.chain(next);
    expect(source.buffer.appended).toEqual([[1], [2], [7]]);
    source.buffer.finish();
    next.push(bytes(8));
    source.buffer.finish();
    expect(source.buffer.appended).toEqual([[1], [2], [7], [8]]);
    expect(source.ended).toBe(false);
    next.finish(final);
    expect(source.ended).toBe(true);
  });

  it("phần tiếp cũng hỏng rồi finish(): nối nốt phần đã về của nó rồi endOfStream, không chờ nữa", () => {
    const { source, feed } = broke();
    const next = new LiveClip();
    next.push(bytes(7));
    feed.chain(next);
    source.buffer.finish();
    next.fail(new ReadAloudError("đứt nữa", "service"));
    expect(source.ended).toBe(false);
    feed.finish();
    expect(source.ended).toBe(true);
  });

  it("finish() khi không có phần tiếp: chờ nối hết khúc đã về rồi endOfStream", () => {
    const { source, feed } = broke();
    feed.finish();
    expect(source.ended).toBe(true);
    expect(source.buffer.appended).toEqual([[1], [2]]);
  });

  it("finish() lúc còn khúc chưa nối: nối hết đã", () => {
    const live = new LiveClip();
    const source = new FakeSource();
    const feed = new LiveFeed(source, live, () => undefined);
    source.open();
    live.push(bytes(1));
    live.push(bytes(2));
    live.fail(new ReadAloudError("đứt", "service"));
    feed.finish();
    expect(source.ended).toBe(false);
    source.buffer.finish();
    source.buffer.finish();
    expect(source.buffer.appended).toEqual([[1], [2]]);
    expect(source.ended).toBe(true);
  });
});
