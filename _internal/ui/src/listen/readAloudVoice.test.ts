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
    // Lỗi dịch vụ (có mạng): vẫn là lời của dịch vụ.
    const busy = source({ "edge:vi-VN-HoaiMyNeural": "service" }, online);
    const other = await module.speechFetcher(busy.value, "b1", vi.fn())("edge:vi-VN-HoaiMyNeural", "Hai.").catch((caught: unknown) => caught);
    expect((other as Error).message).toBe("hỏng edge:vi-VN-HoaiMyNeural");
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

  it("defaults to the first VieNeu voice when the listener has chosen nothing and VieNeu is installed", async () => {
    const { module } = await fresh();
    expect(module.resolveVoice([...VOICES, ...nano], "")?.id).toBe("vieneu:nano/adam");
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
      preferred: string[];
      cases: { name: string; ids: string[]; expect: string | null }[];
    };
    expect([...module.NARRATOR_VOICES]).toEqual(shared.preferred);
    for (const item of shared.cases) {
      const voices = item.ids.map((id) => ({ id, name: id, provider: "vieneu", online: false })) as ReadAloudVoice[];
      expect(module.narratorVoice(voices)?.id ?? null, item.name).toBe(item.expect);
    }
  });

  it("keeps a voice the listener chose, and falls back to the machine default when no VieNeu voice exists", async () => {
    const { module } = await fresh();
    expect(module.resolveVoice([...VOICES, ...nano], "edge:vi-VN-NamMinhNeural")?.id).toBe("edge:vi-VN-NamMinhNeural");
    expect(module.resolveVoice(VOICES, "")?.id).toBe("edge:vi-VN-HoaiMyNeural");
    expect(module.resolveVoice([...VOICES, ...nano], "vieneu:nano/gone")?.id).toBe("edge:vi-VN-HoaiMyNeural"); // đã chọn mà giọng không còn: như trước
  });
});
