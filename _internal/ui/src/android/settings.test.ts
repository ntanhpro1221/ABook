import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ configure: vi.fn(), listenPrefs: vi.fn(), store: new Map<string, string>(), failWrites: false }));
vi.mock("./plugins", () => ({ EbookPlayer: { configure: h.configure, listenPrefs: h.listenPrefs }, EbookLibrary: { systemBars: vi.fn() } }));
import { DEFAULT_SETTINGS, loadSettings, normalizeSettings, saveSettings, syncSettings } from "./settings";

// Tuỳ chọn trình phát của điện thoại (soát a100 V2, T3). Không có DOM trong vitest - localStorage giả có thể giả vờ đầy.
beforeEach(() => {
  h.store.clear();
  h.failWrites = false;
  h.configure.mockReset().mockResolvedValue({});
  h.listenPrefs.mockReset().mockResolvedValue({ prefs: {} });
  Object.assign(globalThis, {
    localStorage: {
      getItem: (key: string) => h.store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        if (h.failWrites) throw new Error("QuotaExceededError");
        h.store.set(key, value);
      },
    },
  });
});

const KEY = "abook-player-settings";
const pushed = () => h.configure.mock.calls.at(-1)![0];

describe("loadSettings", () => {
  it("thiếu hay hỏng cú pháp thì dùng mặc định", () => {
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
    h.store.set(KEY, "broken");
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("trường sai kiểu hay ngoài miền về mặc định riêng trường ấy, trường đúng giữ nguyên", () => {
    h.store.set(KEY, JSON.stringify({ shakeToExtend: "false", autoRewind: "false", sleepFadeSeconds: null, safetyStopHours: -2, sleepExtendMinutes: -10, theme: "dark", flipToPause: true, shakeAction: "reset" }));
    expect(loadSettings()).toEqual({ ...DEFAULT_SETTINGS, theme: "dark", flipToPause: true, shakeAction: "reset" });
  });

  it.each([
    {},
    { from: 12, to: "06:00", minutes: 30 },
    { from: { bad: 1 }, to: "06:00", minutes: 30 },
    { from: "22:00", to: "6:00", minutes: 30 },
    { from: "22:00", to: "06:00", minutes: -10 },
    { from: "22:00", to: "06:00", minutes: 20 },
    { from: "22:00", to: "06:00" },
    [],
    "22:00",
    5,
  ])("lịch đêm sai cấu trúc %j thành không có lịch, các trường khác giữ nguyên", (schedule) => {
    h.store.set(KEY, JSON.stringify({ sleepSchedule: schedule, sleepFadeSeconds: 60 }));
    expect(loadSettings()).toEqual({ ...DEFAULT_SETTINGS, sleepFadeSeconds: 60 });
  });

  it("lịch đêm đúng được giữ, khoá thừa bỏ đi", () => {
    h.store.set(KEY, JSON.stringify({ sleepSchedule: { from: "23:15", to: "05:45", minutes: 45, extra: 1 } }));
    expect(loadSettings().sleepSchedule).toEqual({ from: "23:15", to: "05:45", minutes: 45 });
  });

  it("mọi mức giao diện đưa ra đều được nhận", () => {
    const all = { sleepFadeSeconds: 10, sleepExtendMinutes: 15, safetyStopHours: 0, theme: "light", shakeSensitivity: "firm", headsetSkips: false };
    expect(normalizeSettings(all)).toEqual({ ...DEFAULT_SETTINGS, ...all });
  });
});

describe("saveSettings", () => {
  it("ghi được thì trả true, dấu giờ tăng và đi cùng bản đẩy xuống native", () => {
    expect(saveSettings({ ...DEFAULT_SETTINGS, autoRewind: false })).toBe(true);
    const stored = JSON.parse(h.store.get(KEY)!);
    expect(stored.autoRewind).toBe(false);
    expect(stored.savedAt).toBeGreaterThan(0);
    expect(pushed()).toMatchObject({ autoRewind: false, settingsStamp: stored.savedAt });
  });

  it("WebView không ghi được thì trả false (để màn hình báo) nhưng vẫn đẩy xuống native", () => {
    h.failWrites = true;
    expect(saveSettings({ ...DEFAULT_SETTINGS, autoRewind: false })).toBe(false);
    expect(pushed()).toMatchObject({ autoRewind: false });
  });
});

describe("syncSettings lúc mở app", () => {
  it("native nhớ bản MỚI hơn (WebView không ghi được lần đổi cuối) thì native thắng và được chép lại vào WebView", async () => {
    h.store.set(KEY, JSON.stringify({ autoRewind: true, theme: "dark", savedAt: 100 }));
    h.listenPrefs.mockResolvedValue({ prefs: { autoRewind: false, sleepFadeSeconds: 60, schedule: { from: "22:00", to: "06:00", minutes: 30 }, settingsStamp: 200 } });
    const settings = await syncSettings();
    expect(settings).toMatchObject({ autoRewind: false, sleepFadeSeconds: 60, theme: "dark", savedAt: 200, sleepSchedule: { from: "22:00", to: "06:00", minutes: 30 } });
    expect(JSON.parse(h.store.get(KEY)!)).toMatchObject({ autoRewind: false, savedAt: 200 });
    expect(h.configure).not.toHaveBeenCalled(); // native đã có đúng giá trị ấy
  });

  it("WebView mới hơn hay bằng thì WebView được đẩy xuống, native không đè ngược", async () => {
    h.store.set(KEY, JSON.stringify({ autoRewind: false, savedAt: 300 }));
    h.listenPrefs.mockResolvedValue({ prefs: { autoRewind: true, settingsStamp: 200 } });
    expect((await syncSettings()).autoRewind).toBe(false);
    expect(pushed()).toMatchObject({ autoRewind: false, settingsStamp: 300 });
  });

  it("native chưa có gì (cài mới) hay không trả lời được thì giữ bản WebView", async () => {
    h.store.set(KEY, JSON.stringify({ autoRewind: false }));
    expect((await syncSettings()).autoRewind).toBe(false);
    h.listenPrefs.mockRejectedValue(new Error("no plugin"));
    expect((await syncSettings()).autoRewind).toBe(false);
    expect(pushed()).toMatchObject({ autoRewind: false });
  });

  it("native trả giá trị hỏng thì trường ấy về mặc định, không làm hỏng cả bản", async () => {
    h.listenPrefs.mockResolvedValue({ prefs: { sleepFadeSeconds: -5, autoRewind: false, schedule: { from: 1 }, settingsStamp: 5 } });
    const settings = await syncSettings();
    expect(settings).toMatchObject({ sleepFadeSeconds: DEFAULT_SETTINGS.sleepFadeSeconds, autoRewind: false, sleepSchedule: null });
  });
});
