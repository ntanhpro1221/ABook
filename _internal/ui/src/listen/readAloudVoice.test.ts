import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReadAloudError, type ReadAloudClip, type ReadAloudVoice } from "./readAloud";
import type { ListenSource } from "./source";

const VOICES: ReadAloudVoice[] = [
  { id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My", provider: "edge", online: true, default: true, gender: "female" },
  { id: "edge:vi-VN-NamMinhNeural", name: "Nam Minh", provider: "edge", online: true, gender: "male" },
  { id: "fpt:banmai", name: "Ban Mai - miền Bắc (FPT.AI)", provider: "fpt", online: true, gender: "female" },
  { id: "azure:vi-VN-HoaiMyNeural", name: "Hoài My (Azure Speech)", provider: "azure", online: true, gender: "female" },
  { id: "device:an", name: "An", provider: "device", online: false },
];

/** Mỗi bài một bản module mới: lời nhắn "một lần cho cả phiên" không rò sang bài khác. */
async function fresh() {
  vi.resetModules();
  const target = new EventTarget();
  (globalThis as unknown as { window: EventTarget }).window = target;
  const store = new Map<string, string>();
  (globalThis as unknown as { localStorage: Storage }).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  } as Storage;
  return { module: await import("./readAloudVoice"), target, store };
}

/** Nguồn giả: `fail[mã giọng]` = lý do lỗi của giọng ấy; ghi lại mọi lần gọi. */
function source(fail: Record<string, string> = {}, voices: ReadAloudVoice[] = VOICES) {
  const calls: string[] = [];
  const value: ListenSource = {
    readAloudVoices: async () => voices,
    readAloudClip: async (voice: string): Promise<ReadAloudClip> => {
      calls.push(voice);
      if (fail[voice]) throw new ReadAloudError(`hỏng ${voice}`, fail[voice]);
      return { url: `/clip/${voice}`, durationMs: 1000, words: [] };
    },
  } as unknown as ListenSource;
  return { value, calls };
}

describe("giọng dự phòng của Nghe ngay", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("thứ tự đỡ: giọng dùng khóa -> Edge mặc định -> giọng của máy; Edge -> giọng của máy; giọng của máy thì không ai đỡ", async () => {
    const { module } = await fresh();
    expect(module.fallbackChain(VOICES, VOICES[2]).map((v) => v.id)).toEqual(["edge:vi-VN-HoaiMyNeural", "device:an"]);
    expect(module.fallbackChain(VOICES, VOICES[1]).map((v) => v.id)).toEqual(["device:an"]);
    expect(module.fallbackChain(VOICES, VOICES[4])).toEqual([]);
  });

  it("khóa hết hạn mức: đoạn ấy đọc bằng Edge, nói một lần, các đoạn sau đi thẳng sang Edge", async () => {
    const { module } = await fresh();
    const { value, calls } = source({ "fpt:banmai": "quota" });
    const notify = vi.fn();
    const fetch = module.speechFetcher(value, "b1", notify);
    expect((await fetch("fpt:banmai", "Một.")).url).toBe("/clip/edge:vi-VN-HoaiMyNeural");
    expect((await fetch("fpt:banmai", "Hai.")).url).toBe("/clip/edge:vi-VN-HoaiMyNeural");
    expect(calls).toEqual(["fpt:banmai", "edge:vi-VN-HoaiMyNeural", "edge:vi-VN-HoaiMyNeural"]);
    const messages = notify.mock.calls.map((call) => call[0]);
    // Chữ đi đâu đã được hỏi TRƯỚC lần đọc đầu (onlineConsent.ts) - ở đây chỉ còn lời báo rơi giọng, mỗi chuyện một lần.
    expect(messages).toEqual(["Khóa FPT.AI đã hết hạn mức - tạm đọc bằng giọng Hoài My."]);
  });

  it("khóa bị từ chối và Edge mất mạng: rơi tiếp xuống giọng của máy, mỗi chuyện một câu", async () => {
    const { module } = await fresh();
    const { value, calls } = source({ "azure:vi-VN-HoaiMyNeural": "auth", "edge:vi-VN-HoaiMyNeural": "offline" });
    const notify = vi.fn();
    const clip = await module.speechFetcher(value, "b1", notify)("azure:vi-VN-HoaiMyNeural", "Một.");
    expect(clip.url).toBe("/clip/device:an");
    expect(calls).toEqual(["azure:vi-VN-HoaiMyNeural", "edge:vi-VN-HoaiMyNeural", "device:an"]);
    expect(notify.mock.calls.map((call) => call[0])).toEqual([
      "Khóa Azure Speech không dùng được - tạm đọc bằng giọng Hoài My. Kiểm tra lại khóa trong Cài đặt.",
      module.FALLBACK_NOTICE,
    ]);
  });

  it("mất mạng mà máy không có giọng tiếng Việt: nói thật và chỉ cách, không hứa giọng của máy", async () => {
    const { module } = await fresh();
    const online = VOICES.filter((voice) => voice.online);
    const { value } = source({ "edge:vi-VN-HoaiMyNeural": "offline" }, online);
    const error = await module.speechFetcher(value, "b1", vi.fn())("edge:vi-VN-HoaiMyNeural", "Một.").catch((caught: unknown) => caught);
    expect((error as Error).message).toBe("Không có mạng - giọng Hoài My cần mạng."); // ngắn, nói tên giọng đang chọn
    expect(module.noOfflineMessage("Ban Mai")).toBe("Không có mạng - giọng Ban Mai cần mạng.");
    expect(module.isNoOfflineVoice((error as Error).message)).toBe(true); // giao diện nhận ra nó để đưa nút "Đọc bằng …" / "Tải giọng VieNeu"
    expect(module.isNoOfflineVoice(module.NO_OFFLINE_VOICE)).toBe(true); // bản của lõi điện thoại (ClipReader.NO_OFFLINE_VOICE), chưa kèm tên giọng
    expect(module.isNoOfflineVoice(module.FALLBACK_NOTICE)).toBe(false);
    expect((error as { reason?: string }).reason).toBe("offline"); // bộ đọc to không thử lại vô ích khi mất mạng
    // Lỗi dịch vụ (có mạng): cùng đường ra như mất mạng, bằng câu nói thẳng giọng nào không dùng được.
    const busy = source({ "edge:vi-VN-HoaiMyNeural": "service" }, online);
    const other = await module.speechFetcher(busy.value, "b1", vi.fn())("edge:vi-VN-HoaiMyNeural", "Hai.").catch((caught: unknown) => caught);
    expect((other as Error).message).toBe("Giọng Hoài My đang không dùng được.");
    expect((other as { reason?: string }).reason).toBe("service");
    expect(module.isVoiceStuck((other as Error).message)).toBe(true);
    expect(module.isVoiceStuck(module.NO_USABLE_VOICE)).toBe(true); // bản của lõi điện thoại (ClipReader.NO_USABLE_VOICE)
    expect(module.isVoiceStuck(module.FALLBACK_NOTICE)).toBe(false);
  });

  it("Edge bị từ chối (HTTP 403): nói giọng không dùng được, nhớ cả phiên - đoạn sau không gọi lại - và 'Thử lại' xoá trí nhớ ấy", async () => {
    const { module } = await fresh();
    const online = VOICES.filter((voice) => voice.online);
    const fail: Record<string, string> = { "edge:vi-VN-HoaiMyNeural": "rejected" };
    const { value, calls } = source(fail, online);
    const fetch = module.speechFetcher(value, "b1", vi.fn());
    const first = await fetch("edge:vi-VN-HoaiMyNeural", "Một.").catch((caught: unknown) => caught);
    expect((first as Error).message).toBe("Giọng Hoài My đang không dùng được.");
    const second = await fetch("edge:vi-VN-HoaiMyNeural", "Hai.").catch((caught: unknown) => caught);
    expect((second as Error).message).toBe("Giọng Hoài My đang không dùng được.");
    expect(calls).toEqual(["edge:vi-VN-HoaiMyNeural"]); // lần hai không đập thêm một kết nối
    // chỉ tra bộ đệm thì vẫn tra, không bị chặn
    await expect(fetch("edge:vi-VN-HoaiMyNeural", "Hai.", { cachedOnly: true })).rejects.toMatchObject({ reason: "rejected" });
    delete fail["edge:vi-VN-HoaiMyNeural"];
    module.forgetVoiceTrouble(); // người nghe bấm Thử lại
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Ba.")).url).toBe("/clip/edge:vi-VN-HoaiMyNeural");
  });

  it("bộ máy sẽ tự thử lại (willRetry): lỗi thoáng qua của Edge ném nguyên lên, không cho giọng nghỉ 5 phút, không rơi sang giọng của máy; lần thử cuối mới xử lý", async () => {
    const { module } = await fresh();
    const fail: Record<string, string> = { "edge:vi-VN-HoaiMyNeural": "service" };
    const { value, calls } = source(fail);
    const notify = vi.fn();
    const fetch = module.speechFetcher(value, "b1", notify);
    const first = await fetch("edge:vi-VN-HoaiMyNeural", "Một.", { willRetry: true }).catch((caught: unknown) => caught);
    expect(first).toMatchObject({ reason: "service" });
    expect((first as { final?: boolean }).final).toBeUndefined(); // lỗi gốc: bộ máy còn thử lại được
    expect(notify).not.toHaveBeenCalled();
    delete fail["edge:vi-VN-HoaiMyNeural"]; // Edge sống lại ở lần thử kế: không bị nghỉ oan
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Một.", { willRetry: true })).url).toBe("/clip/edge:vi-VN-HoaiMyNeural");
    expect(calls).toEqual(["edge:vi-VN-HoaiMyNeural", "edge:vi-VN-HoaiMyNeural"]);
    // Hết lần thử (willRetry tắt): xử lý như trước - rơi sang giọng của máy.
    fail["edge:vi-VN-HoaiMyNeural"] = "service";
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Hai.")).url).toBe("/clip/device:an");
    expect(notify).toHaveBeenCalledTimes(1);
  });

  it("quỹ thời gian thử lại (retryBefore): quá mốc ấy thì willRetry coi như tắt - rơi sang giọng của máy ngay trong lần hỏng này", async () => {
    const { module } = await fresh();
    const fail: Record<string, string> = { "edge:vi-VN-HoaiMyNeural": "timeout" };
    const { value } = source(fail);
    const fetch = module.speechFetcher(value, "b1", vi.fn());
    // còn quỹ: ném lỗi gốc lên cho bộ máy thử lại
    const open = await fetch("edge:vi-VN-HoaiMyNeural", "Một.", { willRetry: true, retryBefore: Date.now() + 60_000 }).catch((caught: unknown) => caught);
    expect(open).toMatchObject({ reason: "timeout" });
    // hết quỹ (mốc đã qua): không còn lần thử nào nữa nên đọc tạm bằng giọng của máy, không bắt người nghe chờ thêm
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Hai.", { willRetry: true, retryBefore: Date.now() - 1 })).url).toBe("/clip/device:an");
  });

  it("willRetry chỉ áp cho lỗi thoáng qua: bị từ chối / mất mạng vẫn xử lý ngay; không có giọng của máy thì lời cuối đánh dấu final (bộ máy không thử lại nữa)", async () => {
    const { module } = await fresh();
    const online = VOICES.filter((voice) => voice.online);
    const { value } = source({ "edge:vi-VN-HoaiMyNeural": "rejected" }, online);
    const fetch = module.speechFetcher(value, "b1", vi.fn());
    const rejected = await fetch("edge:vi-VN-HoaiMyNeural", "Một.", { willRetry: true }).catch((caught: unknown) => caught);
    expect(rejected).toMatchObject({ message: "Giọng Hoài My đang không dùng được.", final: true });
    const { module: other } = await fresh();
    const down = source({ "edge:vi-VN-HoaiMyNeural": "service" }, online);
    const last = await other.speechFetcher(down.value, "b1", vi.fn())("edge:vi-VN-HoaiMyNeural", "Một.").catch((caught: unknown) => caught);
    expect(last).toMatchObject({ message: "Giọng Hoài My đang không dùng được.", reason: "service", final: true });
  });

  it("lần hỏi mới (fresh): quên lệnh nghỉ 5 phút của giọng, gọi dịch vụ thật - đoạn người nghe vừa tới không bị chặn oan khi Edge đã khoẻ lại (a46)", async () => {
    const { module } = await fresh();
    const online = VOICES.filter((voice) => voice.online);
    const fail: Record<string, string> = { "edge:vi-VN-HoaiMyNeural": "service" };
    const { value, calls } = source(fail, online);
    const fetch = module.speechFetcher(value, "b1", vi.fn());
    // hết lần thử ở một đoạn xa: giọng bị cho nghỉ
    await fetch("edge:vi-VN-HoaiMyNeural", "Một.").catch(() => undefined);
    delete fail["edge:vi-VN-HoaiMyNeural"]; // Edge khoẻ lại
    const blocked = await fetch("edge:vi-VN-HoaiMyNeural", "Hai.").catch((caught: unknown) => caught);
    expect(blocked).toMatchObject({ message: "Giọng Hoài My đang không dùng được.", final: true });
    expect(calls).toHaveLength(1); // đoạn thường bị chặn ngay, không một lượt gọi nào đi ra
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Hai.", { fresh: true })).url).toBe("/clip/edge:vi-VN-HoaiMyNeural");
    expect(calls).toHaveLength(2);
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Ba.")).url).toBe("/clip/edge:vi-VN-HoaiMyNeural"); // hết nghỉ luôn
    // hỏi mới mà dịch vụ vẫn chết: nghỉ lại như cũ
    fail["edge:vi-VN-HoaiMyNeural"] = "service";
    await expect(fetch("edge:vi-VN-HoaiMyNeural", "Bốn.", { fresh: true })).rejects.toMatchObject({ final: true });
    await expect(fetch("edge:vi-VN-HoaiMyNeural", "Năm.")).rejects.toMatchObject({ final: true });
    expect(calls).toHaveLength(4);
  });

  it("Edge bị từ chối mà máy có giọng của máy: các đoạn sau đi thẳng sang giọng của máy, không gọi lại Edge", async () => {
    const { module } = await fresh();
    const { value, calls } = source({ "edge:vi-VN-HoaiMyNeural": "rejected" });
    const notify = vi.fn();
    const fetch = module.speechFetcher(value, "b1", notify);
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Một.")).url).toBe("/clip/device:an");
    expect((await fetch("edge:vi-VN-HoaiMyNeural", "Hai.")).url).toBe("/clip/device:an");
    expect(calls).toEqual(["edge:vi-VN-HoaiMyNeural", "device:an", "device:an"]);
    expect(notify).toHaveBeenCalledTimes(1);
  });

  it("đổi khóa trong Cài đặt: giọng dùng khóa được thử lại", async () => {
    const { module, target } = await fresh();
    const fail: Record<string, string> = { "fpt:banmai": "quota" };
    const { value, calls } = source(fail);
    const fetch = module.speechFetcher(value, "b1", vi.fn());
    await fetch("fpt:banmai", "Một.");
    delete fail["fpt:banmai"];
    target.dispatchEvent(new CustomEvent(module.ONLINE_KEYS_CHANGED_EVENT));
    expect((await fetch("fpt:banmai", "Hai.")).url).toBe("/clip/fpt:banmai");
    expect(calls.filter((voice) => voice === "fpt:banmai")).toHaveLength(2);
  });

  it("chữ không đọc được thì không đổi giọng; chỉ tra bộ đệm thì không rơi", async () => {
    const { module } = await fresh();
    const { value } = source({ "fpt:banmai": "empty", "edge:vi-VN-NamMinhNeural": "uncached" });
    const fetch = module.speechFetcher(value, "b1", vi.fn());
    await expect(fetch("fpt:banmai", "—")).rejects.toMatchObject({ reason: "empty" });
    await expect(fetch("edge:vi-VN-NamMinhNeural", "Một.", { cachedOnly: true })).rejects.toMatchObject({ reason: "uncached" });
  });

  it("giọng mặc định trong Cài đặt là giọng chung, cuốn đã chọn giọng riêng giữ nguyên", async () => {
    const { module } = await fresh();
    module.chooseVoice("b1", "edge:vi-VN-NamMinhNeural");
    module.chooseDefaultVoice("fpt:banmai");
    expect(module.defaultVoice()).toBe("fpt:banmai");
    expect(module.chosenVoice("b1")).toBe("edge:vi-VN-NamMinhNeural");
    expect(module.chosenVoice("b2")).toBe("fpt:banmai");
    expect(module.onlineNotice(VOICES[0])).toBe(module.ONLINE_NOTICE);
    expect(module.onlineNotice(VOICES[4])).toBe("");
  });

  it("lần chọn giọng đầu tiên (chưa có giọng mặc định) cũng làm giọng mặc định cho cuốn sau", async () => {
    const { module, target } = await fresh();
    const changed: string[] = [];
    target.addEventListener(module.DEFAULT_VOICE_EVENT, () => changed.push(module.defaultVoice()));
    module.chooseVoice("b1", "fpt:banmai");
    module.chooseVoice("b2", "edge:vi-VN-NamMinhNeural");
    expect(module.defaultVoice()).toBe("fpt:banmai");
    expect(module.chosenVoice("b3")).toBe("fpt:banmai");
    expect(changed).toEqual(["fpt:banmai"]);
  });

  it("đổi giọng ở trình phát chỉ cho cuốn ấy: giọng mặc định và cuốn khác giữ nguyên (soát a67)", async () => {
    const { module, target } = await fresh();
    const changed: string[] = [];
    target.addEventListener(module.DEFAULT_VOICE_EVENT, () => changed.push(module.defaultVoice()));
    module.chooseDefaultVoice("edge:vi-VN-HoaiMyNeural");
    module.chooseVoice("b1", "fpt:banmai");
    expect(module.chosenVoice("b1")).toBe("fpt:banmai");
    expect(module.defaultVoice()).toBe("edge:vi-VN-HoaiMyNeural");
    expect(module.chosenVoice("b2")).toBe("edge:vi-VN-HoaiMyNeural");
    // Chỉ Cài đặt đổi giọng mặc định - và báo lõi điện thoại (android/readAloud.ts) đúng một lần mỗi lần đặt.
    expect(changed).toEqual(["edge:vi-VN-HoaiMyNeural"]);
  });
});

describe("giọng chạy trên máy để đỡ khi mất mạng", () => {
  const edge = { id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My", provider: "edge", online: true, gender: "female" } as ReadAloudVoice;
  const nano = [
    { id: "vieneu:nano/adam", name: "Adam (VieNeu Nano)", provider: "vieneu", online: false, gender: "male" },
    { id: "vieneu:nano/aihan", name: "Ái Hân (VieNeu Nano)", provider: "vieneu", online: false, gender: "female" },
  ] as ReadAloudVoice[];

  it("picks an installed on-device voice of the same gender, none when only online voices are there", async () => {
    const { module } = await fresh();
    expect(module.localVoiceFor([edge, ...nano], edge)?.id).toBe("vieneu:nano/aihan");
    expect(module.localVoiceFor([edge, ...nano], undefined)?.id).toBe("vieneu:nano/adam");
    expect(module.localVoiceFor([edge], edge)).toBeUndefined();
    expect(module.localVoiceFor([edge, { id: "device:an", name: "An", provider: "device", online: false }], edge)).toBeUndefined();
  });
});


describe("giọng mặc định khi chưa chọn", () => {
  const nano = [
    { id: "vieneu:nano/adam", name: "Adam (VieNeu Nano)", provider: "vieneu", online: false, gender: "male" },
    { id: "vieneu:nano/aihan", name: "Ái Hân (VieNeu Nano)", provider: "vieneu", online: false, gender: "female" },
  ] as ReadAloudVoice[];

  it("defaults to a VieNeu voice of the default voice's gender, never the first one (Adam), when no preferred voice is there", async () => {
    const { module } = await fresh();
    expect(VOICES.find((voice) => voice.default)?.gender).toBe("female");
    expect(module.resolveVoice([...VOICES, ...nano], "")?.id).toBe("vieneu:nano/aihan");
  });

  it("prefers a neutral storytelling voice over the first one in the list (Adam bựa)", async () => {
    const { module } = await fresh();
    const voices = [
      ...VOICES,
      { id: "vieneu:turbo/Adam bựa", name: "Adam bựa (VieNeu)", provider: "vieneu", online: false, gender: "male" },
      { id: "vieneu:turbo/Ngọc Linh", name: "Ngọc Linh (VieNeu)", provider: "vieneu", online: false, gender: "female" },
    ] as ReadAloudVoice[];
    expect(module.resolveVoice(voices, "")?.id).toBe("vieneu:turbo/Ngọc Linh");
    expect(module.resolveVoice(voices, "vieneu:turbo/Adam bựa")?.id).toBe("vieneu:turbo/Adam bựa"); // đã chọn thì giữ
  });

  it("follows the cases shared with the Android core (tests/fixtures/default_voice)", async () => {
    const { module } = await fresh();
    const shared = JSON.parse(readFileSync(new URL("../../../tests/fixtures/default_voice/cases.json", import.meta.url)).toString("utf8")) as {
      preferred: Record<string, string[]>;
      cases: { name: string; gender: string | null; voices: [string, string][]; expect: string | null }[];
    };
    expect(module.NARRATOR_VOICES).toEqual(shared.preferred);
    for (const item of shared.cases) {
      const voices = item.voices.map(([id, gender]) => ({ id, name: id, provider: "vieneu", online: false, gender })) as ReadAloudVoice[];
      expect(module.narratorVoice(voices, item.gender ?? undefined)?.id ?? null, item.name).toBe(item.expect);
    }
  });

  it("keeps a voice the listener chose, and falls back to the machine default when no VieNeu voice exists", async () => {
    const { module } = await fresh();
    expect(module.resolveVoice([...VOICES, ...nano], "edge:vi-VN-NamMinhNeural")?.id).toBe("edge:vi-VN-NamMinhNeural");
    expect(module.resolveVoice(VOICES, "")?.id).toBe("edge:vi-VN-HoaiMyNeural");
    expect(module.resolveVoice([...VOICES, ...nano], "vieneu:nano/gone")?.id).toBe("edge:vi-VN-HoaiMyNeural"); // đã chọn mà giọng không còn: như trước
  });
});

describe("tải xong giọng trên máy khi đã rời Cài đặt (soát a69)", () => {
  it("vòng hỏi sống cả phiên: tải xong thì danh sách giọng hỏi lại, không cần thẻ Cài đặt còn trên màn", async () => {
    vi.useFakeTimers();
    try {
      const { module } = await fresh();
      let installed = false;
      const asked: number[] = [];
      const value = {
        readAloudVoices: async () => {
          asked.push(1);
          return installed ? [...VOICES, { id: "supertonic:F1", name: "Supertonic F1", provider: "supertonic", online: false }] : VOICES;
        },
      } as unknown as ListenSource;
      expect((await module.voicesOf(value)).some((v) => v.id === "supertonic:F1")).toBe(false);
      // Thẻ bấm tải rồi người dùng rời Cài đặt: chỉ còn vòng hỏi; lần hỏi thứ ba thấy đã xong.
      let polls = 0;
      const done = vi.fn();
      const poll = async () => {
        polls += 1;
        if (polls < 3) return true;
        installed = true;
        return false;
      };
      module.watchVoiceModule("supertonic", poll, done);
      module.watchVoiceModule("supertonic", poll, done); // thẻ mở lại giữa chừng: không thêm vòng hỏi thứ hai
      expect((await module.voicesOf(value)).length).toBe(VOICES.length);
      await vi.advanceTimersByTimeAsync(3500);
      expect(polls).toBe(3);
      expect(done).toHaveBeenCalledTimes(1);
      expect((await module.voicesOf(value)).some((v) => v.id === "supertonic:F1")).toBe(true);
      expect(asked.length).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
