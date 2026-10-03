import { describe, expect, it, vi } from "vitest";
import type { Script } from "@/listen/model";
import { VOICE_CHANGED_EVENT, mergeTimings, type ReadAloudTimings } from "@/listen/readAloud";
import { chooseVoice } from "@/listen/readAloudVoice";
import { ONLINE_CONSENT_EVENT, giveOnlineConsent } from "@/listen/onlineConsent";
import { textScript } from "@/listen/textScript";
import type { ReadAloudPlugin } from "./plugins";
import { PREPARE_STATUS_KEY, type PrepareStatus } from "@/listen/prepareAhead";
import { phonePrepare, refreshScript, textScriptKey, watchReadAloud } from "./readAloud";

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
    const handlers = new Map<string, (event: never) => void>();
    const remove = vi.fn();
    const api = {
      script: vi.fn(async () => TIMINGS),
      addListener: vi.fn(async (event: string, handler: (event: never) => void) => {
        handlers.set(event, handler);
        return { remove };
      }),
    } as unknown as Pick<ReadAloudPlugin, "script" | "addListener">;
    const configure = vi.fn();
    const notify = vi.fn();
    const stop = watchReadAloud(client, api, configure, notify);
    // Mở app: lõi biết ngay người nghe đã đồng ý gửi chữ cho nhà cung cấp nào (chưa ai) - nó chỉ tự sang chương chữ với những giọng ấy.
    expect(configure).toHaveBeenCalledWith({ readAloudOnlineOk: [] });
    (handlers.get("readAloudScript") as (event: { bookId: string; chapterId: number }) => void)({ bookId: BOOK, chapterId: 1 });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect((client.getQueryData(textScriptKey(BOOK, 1)) as Script | undefined)?.timed).toBe(true);
    // Lõi đọc tạm một đoạn bằng giọng kế: câu của lõi hiện lên cho người nghe.
    (handlers.get("readAloudNotice") as (event: { message: string }) => void)({ message: "Khóa FPT.AI đã hết hạn mức - tạm đọc bằng giọng Hoài My (Edge)." });
    expect(notify).toHaveBeenCalledWith("Khóa FPT.AI đã hết hạn mức - tạm đọc bằng giọng Hoài My (Edge).");
    // Tiến độ "Làm trước" do việc nền đẩy lên: vào đúng khoá menu Giọng đọc và danh sách chương đọc.
    const status: PrepareStatus = { state: "running", bookId: BOOK, voice: "edge:a", chapters: [] };
    (handlers.get("readAloudPrepare") as (event: PrepareStatus) => void)(status);
    expect(client.getQueryData(PREPARE_STATUS_KEY)).toEqual(status);

    chooseVoice(BOOK, "device:vi-vn-an");
    expect(configure).toHaveBeenCalledWith({ readAloudVoice: "device:vi-vn-an", readAloudBook: BOOK });
    giveOnlineConsent("edge");
    expect(configure).toHaveBeenCalledWith({ readAloudOnlineOk: ["edge"] });
    stop();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(remove).toHaveBeenCalledTimes(3);
    target.dispatchEvent(new CustomEvent(VOICE_CHANGED_EVENT, { detail: BOOK }));
    target.dispatchEvent(new CustomEvent(ONLINE_CONSENT_EVENT));
    expect(configure).toHaveBeenCalledTimes(3);
  });
});

describe("phonePrepare", () => {
  it("gửi mã chương cho lõi native, không gửi chữ; mọi lệnh đi đúng phương thức của plugin", async () => {
    const status: PrepareStatus = { state: "running", chargingOnly: true };
    const api = {
      preparePlan: vi.fn(async () => ({ chapters: 2, offered: 2, audioSeconds: 600, secondsEstimate: null })),
      prepareStart: vi.fn(async () => status),
      prepareStatus: vi.fn(async () => status),
      prepareCancel: vi.fn(async () => ({ state: "cancelled" as const })),
      prepareOptions: vi.fn(async () => ({ ...status, chargingOnly: false })),
    };
    const prepare = phonePrepare(api);
    expect(prepare.readAloudPrepareOnline).toBe(true);
    const request = { voice: "edge:a", bookId: BOOK, chapters: [{ id: 3, title: "Chương 3" }, { id: 4, title: "Chương 4" }], label: "2 chương tới" };
    expect((await prepare.readAloudPreparePlan(request)).chapters).toBe(2);
    expect(api.preparePlan).toHaveBeenCalledWith({ bookId: BOOK, voice: "edge:a", chapterIds: [3, 4] });
    await prepare.readAloudPrepare({ ...request, chargingOnly: false });
    expect(api.prepareStart).toHaveBeenCalledWith({ bookId: BOOK, voice: "edge:a", chapterIds: [3, 4], label: "2 chương tới", chargingOnly: false });
    expect(await prepare.readAloudPrepareStatus()).toBe(status);
    expect((await prepare.readAloudPrepareCancel()).state).toBe("cancelled");
    expect((await prepare.readAloudPrepareOptions({ chargingOnly: false })).chargingOnly).toBe(false);
    expect(api.prepareOptions).toHaveBeenCalledWith({ chargingOnly: false });
  });
});
