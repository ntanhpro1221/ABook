import { describe, expect, it, vi } from "vitest";
import type { Script } from "@/listen/model";
import { VOICE_CHANGED_EVENT, mergeTimings, type ReadAloudTimings } from "@/listen/readAloud";
import { chooseVoice } from "@/listen/readAloudVoice";
import { textScript } from "@/listen/textScript";
import { refreshScript, textScriptKey, watchReadAloud } from "./readAloud";

const BOOK = "b1";
const TEXT = "Chương 1\n\nXin chào các bạn.\n\nTạm biệt.";

/** Bộ nhớ react-query giả: chỉ hai hàm mà bộ theo dõi dùng. */
function memory(initial?: Script) {
  const data = new Map<string, unknown>();
  const key = (k: readonly unknown[]) => JSON.stringify(k);
  if (initial) data.set(key(textScriptKey(BOOK, 1)), initial);
  return {
    getQueryData: (k: readonly unknown[]) => data.get(key(k)),
    setQueryData: (k: readonly unknown[], value: Script) => {
      data.set(key(k), value);
      return value;
    },
    data,
    key,
  };
}

const TIMINGS: ReadAloudTimings = {
  segments: [
    { start: 0, end: 1.2 },
    { start: 1.2, end: 3.2, words: [[1200, 1800], [1800, 2300], [2300, 2700], [2700, 3200]] },
    { start: 3.2, end: 4.4 },
  ],
};

describe("mergeTimings", () => {
  it("gắn mốc câu và chữ của lõi native vào kịch bản chữ, giữ nguyên chữ", () => {
    const base = textScript(1, "Chương 1", TEXT);
    const merged = mergeTimings(base, TIMINGS);
    expect(merged.timed).toBe(true);
    expect(merged.duration).toBe(4.4);
    expect(merged.segments.map((segment) => [segment.text, segment.start, segment.end])).toEqual([
      ["Chương 1", 0, 1.2],
      ["Xin chào các bạn.", 1.2, 3.2],
      ["Tạm biệt.", 3.2, 4.4],
    ]);
    expect(merged.segments[1].words).toHaveLength(4);
    expect(merged.segments[0].words).toBeUndefined();
    expect(merged.segments[0].kind).toBe("heading");
    expect(base.timed).toBe(false); // không đổi bản gốc
  });

  it("thiếu mốc ở một câu thì câu ấy giữ nguyên; không mốc nào thì trả kịch bản cũ", () => {
    const base = textScript(1, "Chương 1", TEXT);
    expect(mergeTimings(base, { segments: [] })).toBe(base);
    const partial = mergeTimings(base, { segments: [{ start: 0, end: 2 }] });
    expect(partial.segments[1].start).toBeNull();
    expect(partial.segments[0].end).toBe(2);
  });
});

describe("refreshScript", () => {
  it("ghi mốc mới vào kịch bản chữ đang mở", async () => {
    const client = memory(textScript(1, "Chương 1", TEXT));
    const api = { script: vi.fn(async () => TIMINGS) };
    expect(await refreshScript(client, api, BOOK, 1)).toBe(true);
    expect(api.script).toHaveBeenCalledWith({ bookId: BOOK, chapterId: 1 });
    expect((client.getQueryData(textScriptKey(BOOK, 1)) as Script | undefined)?.timed).toBe(true);
  });

  it("chương chưa mở thì khỏi hỏi lõi; lõi lỗi thì giữ kịch bản cũ", async () => {
    const api = { script: vi.fn(async () => TIMINGS) };
    expect(await refreshScript(memory(), api, BOOK, 1)).toBe(false);
    expect(api.script).not.toHaveBeenCalled();
    const client = memory(textScript(1, "Chương 1", TEXT));
    const broken = { script: vi.fn(async () => Promise.reject(new Error("không có"))) };
    expect(await refreshScript(client, broken, BOOK, 1)).toBe(false);
    expect((client.getQueryData(textScriptKey(BOOK, 1)) as Script | undefined)?.timed).toBe(false);
  });
});

describe("watchReadAloud", () => {
  it("nghe sự kiện readAloudScript của lõi, báo lõi khi đổi giọng, và gỡ sạch", async () => {
    const target = new EventTarget();
    (globalThis as unknown as { window: EventTarget }).window = target;
    const store = new Map<string, string>();
    (globalThis as unknown as { localStorage: Storage }).localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    } as Storage;
    const client = memory(textScript(1, "Chương 1", TEXT));
    let fire: (event: { bookId: string; chapterId: number }) => void = () => undefined;
    const remove = vi.fn();
    const api = {
      script: vi.fn(async () => TIMINGS),
      addListener: vi.fn(async (_event: "readAloudScript", handler: typeof fire) => {
        fire = handler;
        return { remove };
      }),
    };
    const configure = vi.fn();
    const stop = watchReadAloud(client, api, configure);
    fire({ bookId: BOOK, chapterId: 1 });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect((client.getQueryData(textScriptKey(BOOK, 1)) as Script | undefined)?.timed).toBe(true);

    chooseVoice(BOOK, "device:vi-vn-an");
    expect(configure).toHaveBeenCalledWith({ readAloudVoice: "device:vi-vn-an" });
    stop();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(remove).toHaveBeenCalled();
    target.dispatchEvent(new CustomEvent(VOICE_CHANGED_EVENT, { detail: BOOK }));
    expect(configure).toHaveBeenCalledTimes(1);
  });
});
