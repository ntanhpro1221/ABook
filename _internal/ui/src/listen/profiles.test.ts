import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { httpSource } from "@/desktop/httpSource";
import { moveBookStorage } from "@/shared/bookStorage";
import { setApiTransport } from "@/studio/api";
import { NightRecorder } from "./night";

// Hồ sơ người nghe (soát a105): giọng riêng, nhật ký đêm, tốc độ đều đi theo MÃ HỒ SƠ của phiên phát, không theo "hồ sơ đang chọn" lúc ghi.

const at = (chapterId: number, seconds: number) => ({ chapterId, seconds, chapterTitle: `Chương ${chapterId}` });
const voices = [{ id: "device:a" }, { id: "device:b" }, { id: "device:default" }];

async function fresh() {
  vi.resetModules();
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => void values.set(key, value),
    removeItem: (key: string) => void values.delete(key),
    key: (index: number) => [...values.keys()][index] ?? null,
    get length() { return values.size; },
  });
  return { voice: await import("./readAloudVoice"), values };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("window", Object.assign(new EventTarget(), { setTimeout, clearTimeout }));
});
afterEach(() => {
  setApiTransport(null);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("quay lại hồ sơ A sau khi B chọn giọng khác: A vẫn đọc bằng giọng của A", async () => {
  const { voice } = await fresh();
  voice.chooseDefaultVoice("device:default");
  expect(voice.adoptSyncedVoice("book", { voice: "device:a", voiceAt: 100 }, voices, "r-a")).toBe(true);
  expect(voice.adoptSyncedVoice("book", { voice: "device:b", voiceAt: 200 }, voices, "r-b")).toBe(true);
  expect(voice.chosenVoice("book", "r-a")).toBe("device:a");
  expect(voice.chosenVoice("book", "r-b")).toBe("device:b");
  // máy kia gửi lại state cũ của A: không đè giọng A đã có, cũng không đè B
  expect(voice.adoptSyncedVoice("book", { voice: "device:a", voiceAt: 100 }, voices, "r-a")).toBe(false);
  expect(voice.chosenVoice("book", "r-a")).toBe("device:a");
  expect(voice.chosenVoice("book", "r-b")).toBe("device:b");
});

it("hồ sơ mới chưa chọn giọng riêng theo giọng mặc định, không kế thừa giọng của hồ sơ trước", async () => {
  const { voice } = await fresh();
  voice.chooseDefaultVoice("device:default");
  voice.chooseVoice("book", "device:a", "r-a");
  expect(voice.adoptSyncedVoice("book", {}, voices, "r-new")).toBe(false);
  expect(voice.chosenVoice("book", "r-new")).toBe("device:default");
  expect(voice.chosenVoice("book", "r-a")).toBe("device:a");
  expect(voice.chosenVoice("another-book")).toBe("device:default");
});

it("nơi không biết hồ sơ (vẽ tên giọng, xuất file) hỏi giọng của hồ sơ đang nghe cuốn ấy", async () => {
  const { voice } = await fresh();
  voice.chooseDefaultVoice("device:default");
  voice.chooseVoice("book", "device:a", "r-a");
  voice.chooseVoice("book", "device:b", "r-b");
  voice.rememberRecordOf("book", "r-a");
  expect(voice.chosenVoice("book")).toBe("device:a");
  voice.rememberRecordOf("book", "r-b");
  expect(voice.chosenVoice("book")).toBe("device:b");
  voice.rememberRecordOf("book", "r-new");
  expect(voice.chosenVoice("book")).toBe("device:default");
});

it("chọn giọng gửi kèm mã hồ sơ cho nơi ghi vào hồ sơ", async () => {
  const { voice } = await fresh();
  const sent: unknown[][] = [];
  voice.onVoiceChosen((...args) => sent.push(args));
  voice.chooseVoice("book", "device:a", "r-a");
  voice.rememberRecordOf("book", "r-b");
  voice.chooseVoice("book", "device:b");
  expect(sent).toEqual([["book", "device:a", "r-a"], ["book", "device:b", "r-b"]]);
});

it("đổi mã sách thì lựa chọn giọng theo hồ sơ đi theo", async () => {
  const { voice, values } = await fresh();
  voice.chooseVoice("old", "device:a", "r-a");
  moveBookStorage("old", "new");
  expect(voice.chosenVoice("new", "r-a")).toBe("device:a");
  expect([...values.keys()].some((key) => key.includes("old"))).toBe(false);
});

it("yêu cầu lưu đêm, đổi tốc độ, đổi giọng mang mã hồ sơ của phiên", async () => {
  const calls: { path: string; body: Record<string, unknown> }[] = [];
  setApiTransport(async (path, init) => {
    calls.push({ path, body: init?.body as Record<string, unknown> });
    return {};
  });
  const recorder = new NightRecorder((id, session, record) => httpSource.saveNight!(id, session, record));
  recorder.start({ id: "book", title: "Sách", record: "r-a" }, 15, at(1, 30));
  recorder.cancel(at(1, 50));
  await httpSource.setRate("book", 1.75, "r-a");
  await httpSource.setVoice!("book", "device:a", "r-a");
  expect(calls[0].path).toBe("/api/listen/books/book/night");
  expect(calls[0].body.record).toBe("r-a");
  expect((calls[0].body.events as { action?: string }[]).at(-1)?.action).toBe("timer-off");
  expect(calls[1]).toEqual({ path: "/api/listen/books/book/rate", body: { rate: 1.75, record: "r-a" } });
  expect(calls[2]).toEqual({ path: "/api/listen/books/book/voice", body: { voice: "device:a", record: "r-a" } });
});

it("hẹn giờ của người khác trong cùng cuốn là một đêm mới; cùng người trong 45 phút vẫn nối đêm cũ", () => {
  type Saved = { id: string; events: { type: string; position?: { chapterId: number } }[]; record?: string };
  const saved: Saved[] = [];
  const recorder = new NightRecorder(async (_id, session, record) => void saved.push({ ...session, record } as Saved));
  recorder.start({ id: "book", title: "Sách", record: "r-a" }, 15, at(1, 30));
  recorder.cancel(at(1, 50));
  const first = saved[0].id;
  vi.advanceTimersByTime(10_000);
  recorder.start({ id: "book", title: "Sách", record: "r-b" }, 20, at(5, 300));
  recorder.flush();
  const other = saved.at(-1)!;
  expect(other.id).not.toBe(first);
  expect(other.record).toBe("r-b");
  expect(other.events.filter((event) => event.type === "timer")).toHaveLength(1);
  expect(other.events[0].position?.chapterId).toBe(5);
  // lượt lưu muộn của A vẫn mang mã A
  expect(saved[0].record).toBe("r-a");
  // cùng người A hẹn lại trong 45 phút: nối đêm cũ
  const again = new NightRecorder(async (_id, session, record) => void saved.push({ ...session, record } as Saved));
  again.start({ id: "book", title: "Sách", record: "r-a" }, 15, at(1, 30));
  again.cancel(at(1, 50));
  const joined = saved.at(-1)!.id;
  vi.advanceTimersByTime(10_000);
  again.start({ id: "book", title: "Sách", record: "r-a" }, 20, at(2, 60));
  again.flush();
  expect(saved.at(-1)!.id).toBe(joined);
  expect(saved.at(-1)!.events.filter((event) => event.type === "timer")).toHaveLength(2);
});
