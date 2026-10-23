import { beforeEach, expect, it, vi } from "vitest";

// Hook chạy ngoài DOM: useRef / useState / useCallback giả tối thiểu, đủ để chạy useVoiceSample qua hai lần gọi chồng nhau.
const store = vi.hoisted(() => ({ refs: [] as { current: unknown }[], states: [] as unknown[], i: 0, j: 0 }));
vi.mock("react", async (original) => ({
  ...(await original<typeof import("react")>()),
  useRef: (value: unknown) => { const k = store.i++; return (store.refs[k] ??= { current: value }); },
  useState: (value: unknown) => {
    const k = store.j++;
    if (!(k in store.states)) store.states[k] = value;
    return [store.states[k], (next: unknown) => { store.states[k] = typeof next === "function" ? (next as (now: unknown) => unknown)(store.states[k]) : next; }];
  },
  useCallback: (callback: unknown) => callback,
  useEffect: () => undefined,
}));
vi.mock("@/shared/ui", () => ({ Button: () => null, StatusPill: () => null, radioGroupKeys: () => null, radioTabIndex: () => 0 }));
vi.mock("lucide-react", () => ({ Check: () => null, ChevronDown: () => null, KeyRound: () => null, Play: () => null, Square: () => null, Trash2: () => null }));
vi.mock("@/shared/SettingsNav", () => ({ MoreInfo: () => null }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({}), useQuery: () => ({}) }));
vi.mock("@/listen/ReadAloudStorage", () => ({ ReadAloudStorage: () => null }));

class FakeAudio {
  static all: FakeAudio[] = [];
  paused = false;
  muted = false;
  onended: (() => void) | null = null;
  constructor(public url: string) { FakeAudio.all.push(this); }
  pause() { this.paused = true; }
  async play() {}
}
(globalThis as unknown as { Audio: typeof FakeAudio }).Audio = FakeAudio;
(globalThis as unknown as { window: unknown }).window = Object.assign(new EventTarget(), { localStorage: { getItem: () => null }, location: { search: "?mute=1" } });
(globalThis as unknown as { localStorage: unknown }).localStorage = { getItem: () => null };

beforeEach(() => {
  FakeAudio.all = [];
  store.refs = [];
  store.states = [];
});

async function hook() {
  const { useVoiceSample } = await import("@/listen/VoiceSettings");
  const resolvers: Record<string, (url: string) => void> = {};
  const rejecters: Record<string, (error: Error) => void> = {};
  const render = () => {
    store.i = 0;
    store.j = 0;
    return useVoiceSample((voice) => new Promise<string>((resolve, reject) => { resolvers[voice] = resolve; rejecters[voice] = reject; }));
  };
  return { render, resolvers, rejecters };
}

it("hai lần Thử giọng chồng nhau: chỉ giọng bấm sau cùng được phát, giọng đầu về muộn bị bỏ (a106r)", async () => {
  const { render, resolvers } = await hook();
  const first = render().play("A");
  const second = render().play("B");
  resolvers.A("a.wav");
  await first;
  resolvers.B("b.wav");
  await second;
  expect(FakeAudio.all.map((audio) => audio.url)).toEqual(["b.wav"]); // giọng A về sau khi đã bấm B: không phát
  expect(FakeAudio.all.filter((audio) => !audio.paused).length).toBe(1);
  expect(render().playing).toBe("B");
  expect(render().loading).toBe("");
});

it("giọng sau về trước giọng đầu: giọng đầu về muộn không đè lên và không dừng giọng sau", async () => {
  const { render, resolvers } = await hook();
  const first = render().play("A");
  const second = render().play("B");
  resolvers.B("b.wav");
  await second;
  resolvers.A("a.wav");
  await first;
  expect(FakeAudio.all.map((audio) => [audio.url, audio.paused])).toEqual([["b.wav", false]]);
  expect(render().playing).toBe("B");
});

it("bấm dừng lúc còn đang lấy mẫu: mẫu về sau không tự phát; lỗi của lượt cũ không hiện", async () => {
  const { render, resolvers, rejecters } = await hook();
  const first = render().play("A");
  expect(render().loading).toBe("A");
  render().stop();
  expect(render().loading).toBe("");
  resolvers.A("a.wav");
  await first;
  expect(FakeAudio.all).toEqual([]);
  expect(render().playing).toBe("");
  const old = render().play("C");
  const next = render().play("D");
  rejecters.C(new Error("lỗi muộn của giọng cũ"));
  await old;
  expect(render().failed).toBeNull();
  resolvers.D("d.wav");
  await next;
  expect(FakeAudio.all.map((audio) => audio.url)).toEqual(["d.wav"]);
});
