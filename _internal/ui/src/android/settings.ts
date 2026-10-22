import { DEFAULT_EXTEND_MINUTES, DEFAULT_FADE_SECONDS, EXTEND_CHOICES, FADE_CHOICES, SAFETY_STOP_CHOICES, choiceOr, cleanSleepSchedule } from "@/listen/sleep";
import { EbookLibrary, EbookPlayer } from "./plugins";

// Tuỳ chọn của trình phát trên điện thoại. Lưu trong WebView (localStorage) và đẩy phần native cần biết xuống
// lõi phát mỗi lần mở app và mỗi lần đổi.

export interface PlayerSettings {
  theme: "system" | "light" | "dark";
  sleepExtendMinutes: number;
  sleepFadeSeconds: number;
  shakeToExtend: boolean;
  /** Lắc = cộng thêm "Mỗi lần thêm" hay đặt lại từ đầu khoảng đã hẹn (Smart AudioBook Player). */
  shakeAction: "extend" | "reset";
  /** Nhẹ tay cũng tính (gentle) … phải lắc mạnh (firm): tránh lắc nhầm khi trở mình. */
  shakeSensitivity: "gentle" | "normal" | "firm";
  /** Úp màn hình xuống để tạm dừng, lật lên trong 10 phút để nghe tiếp. */
  flipToPause: boolean;
  /** Nút Trước/Sau trên tai nghe, đồng hồ, xe hơi = lùi/tới 15 giây (mặc định, quy ước app sách nói); tắt thì nhảy chương. */
  headsetSkips: boolean;
  /** Tạm dừng rồi nghe tiếp thì lùi lại một chút (luật chung hai nền: listen/sleep.ts `rewindAfter`). */
  autoRewind: boolean;
  /** Phát liên tục chừng này giờ không ai chạm máy thì tự nhỏ dần rồi dừng (0 = tắt). */
  safetyStopHours: number;
  /** Lịch đêm tự hẹn giờ. */
  sleepSchedule: { from: string; to: string; minutes: number } | null;
  /** Máy tự chọn nhạc nền cho sách chỉ có chữ chưa chọn nhạc (mặc định bật; Playlists.autoEnabled). */
  autoMusic: boolean;
  /** Lần đổi cuối trong Cài đặt (ms; 0 = chưa đổi lần nào): so với dấu native nhớ để biết bản nào mới hơn (`syncSettings`). */
  savedAt: number;
}

export const DEFAULT_SETTINGS: PlayerSettings = {
  theme: "system",
  sleepExtendMinutes: DEFAULT_EXTEND_MINUTES,
  sleepFadeSeconds: DEFAULT_FADE_SECONDS,
  shakeToExtend: true,
  shakeAction: "extend",
  shakeSensitivity: "normal",
  flipToPause: false,
  headsetSkips: true,
  autoRewind: true,
  safetyStopHours: 2,
  sleepSchedule: null,
  autoMusic: true,
  savedAt: 0,
};

const KEY = "abook-player-settings";

const flag = (value: unknown, fallback: boolean) => (typeof value === "boolean" ? value : fallback);
const oneOf = <T extends string>(value: unknown, choices: readonly T[], fallback: T): T => (choices.includes(value as T) ? (value as T) : fallback);

/** Tuỳ chọn đọc từ kho (localStorage, hay native) đưa về đúng kiểu và miền giá trị; trường sai về mặc định RIÊNG trường ấy (cùng hợp đồng với
 *  webui/library.py `Preferences`, soát a100 V2). Khoá lạ bỏ đi. */
export function normalizeSettings(raw: unknown): PlayerSettings {
  const given = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const stamp = given.savedAt;
  return {
    theme: oneOf(given.theme, ["system", "light", "dark"], DEFAULT_SETTINGS.theme),
    sleepExtendMinutes: choiceOr(given.sleepExtendMinutes, EXTEND_CHOICES, DEFAULT_SETTINGS.sleepExtendMinutes),
    sleepFadeSeconds: choiceOr(given.sleepFadeSeconds, FADE_CHOICES, DEFAULT_SETTINGS.sleepFadeSeconds),
    shakeToExtend: flag(given.shakeToExtend, DEFAULT_SETTINGS.shakeToExtend),
    shakeAction: oneOf(given.shakeAction, ["extend", "reset"], DEFAULT_SETTINGS.shakeAction),
    shakeSensitivity: oneOf(given.shakeSensitivity, ["gentle", "normal", "firm"], DEFAULT_SETTINGS.shakeSensitivity),
    flipToPause: flag(given.flipToPause, DEFAULT_SETTINGS.flipToPause),
    headsetSkips: flag(given.headsetSkips, DEFAULT_SETTINGS.headsetSkips),
    autoRewind: flag(given.autoRewind, DEFAULT_SETTINGS.autoRewind),
    safetyStopHours: choiceOr(given.safetyStopHours, SAFETY_STOP_CHOICES, DEFAULT_SETTINGS.safetyStopHours),
    sleepSchedule: cleanSleepSchedule(given.sleepSchedule),
    autoMusic: flag(given.autoMusic, DEFAULT_SETTINGS.autoMusic),
    savedAt: typeof stamp === "number" && Number.isFinite(stamp) && stamp > 0 ? stamp : 0,
  };
}

export function loadSettings(): PlayerSettings {
  try {
    return normalizeSettings(JSON.parse(localStorage.getItem(KEY) ?? "{}"));
  } catch {
    return DEFAULT_SETTINGS;
  }
}

/** Lưu vào localStorage của WebView rồi đẩy xuống native. Trả `false` khi WebView không ghi được (hết hạn mức, bị chặn): thay đổi vẫn áp cho
 *  phiên này và native vẫn nhớ, nhưng người gọi nên báo (soát a100 T3). Dấu giờ mới đi cùng để lúc mở app biết bản nào mới hơn. */
export function saveSettings(settings: PlayerSettings): boolean {
  const stamped = { ...settings, savedAt: Math.max(Date.now(), settings.savedAt + 1) };
  let stored = true;
  try {
    localStorage.setItem(KEY, JSON.stringify(stamped));
  } catch {
    stored = false;
  }
  void pushSettings(stamped);
  return stored;
}

/** Lúc mở app: tuỳ chọn native đã nhớ (có dấu giờ MỚI HƠN bản WebView) thắng, vì localStorage của WebView có thể đã mất / không ghi được ở lần đổi
 *  gần nhất; ngược lại bản WebView được đẩy xuống như trước. Trả bản đang dùng. Native không trả lời được thì giữ bản WebView. */
export async function syncSettings(): Promise<PlayerSettings> {
  const local = loadSettings();
  const native = await EbookPlayer.listenPrefs().then((reply) => reply.prefs, () => null);
  const stamp = native?.settingsStamp;
  if (native && typeof stamp === "number" && stamp > local.savedAt) {
    const { schedule, settingsStamp: _stamp, ...rest } = native;
    const merged = normalizeSettings({ ...local, ...rest, sleepSchedule: schedule, savedAt: stamp });
    try {
      localStorage.setItem(KEY, JSON.stringify(merged));
    } catch {
      /* vẫn không ghi được: native giữ chuẩn */
    }
    return merged;
  }
  await pushSettings(local);
  return local;
}

export async function pushSettings(settings: PlayerSettings): Promise<void> {
  await EbookPlayer.configure({
    theme: settings.theme,
    sleepExtendMinutes: settings.sleepExtendMinutes,
    sleepFadeSeconds: settings.sleepFadeSeconds,
    shakeToExtend: settings.shakeToExtend,
    shakeAction: settings.shakeAction ?? "extend",
    shakeSensitivity: settings.shakeSensitivity ?? "normal",
    flipToPause: settings.flipToPause ?? false,
    headsetSkips: settings.headsetSkips !== false,
    autoRewind: settings.autoRewind !== false,
    safetyStopHours: settings.safetyStopHours,
    schedule: settings.sleepSchedule,
    settingsStamp: settings.savedAt,
    autoMusic: settings.autoMusic !== false,
  }).catch(() => undefined);
}

export function applyTheme(theme: PlayerSettings["theme"]): void {
  const dark = theme === "dark" || (theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  // Thanh trạng thái theo giao diện vừa đặt (soát a66: đổi sang tối khi app đang mở, biểu tượng vẫn màu tối, dải trên cùng #303030 lệch thân app).
  void EbookLibrary.systemBars({ dark, color: hexColor(getComputedStyle(document.body).backgroundColor) }).catch(() => undefined);
}

/** "rgb(14, 17, 21)" -> "#0e1115" (Android chỉ đọc dạng #rrggbb). */
export function hexColor(css: string): string {
  const [r = 0, g = 0, b = 0] = css.match(/\d+(\.\d+)?/g)?.map(Number) ?? [];
  return `#${[r, g, b].map((value) => Math.round(value).toString(16).padStart(2, "0")).join("")}`;
}
