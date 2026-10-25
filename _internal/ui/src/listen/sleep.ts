// Hẹn giờ ngủ - phần tính toán, chung cho máy tính và giao diện Android (lõi native tự đếm trên Android).
//
// Ba điều người nghe lúc buồn ngủ cần, rút ra từ đánh giá 26-09:
//  - thời gian chỉ trôi khi ĐANG PHÁT: tự tạm dừng rồi quay lại không bị tắt ngay lập tức, và con số trên nút
//    không bao giờ treo ở "1′" sau khi hết giờ;
//  - nhỏ dần theo thang dB (tai nghe âm lượng theo logarit): giảm đều theo biên độ thì mấy bậc cuối tụt như bị cắt;
//  - nghe thêm được bằng một thao tác (trên điện thoại là lắc máy; trên máy tính là chạm phím/chuột lúc đang nhỏ dần).

export type SleepRequest = { kind: "off" } | { kind: "minutes"; minutes: number } | { kind: "chapter" };

/** `leftMs` là thời gian còn lại tính tới mốc `since`; `since` = lúc bắt đầu đếm (đang phát), null khi đang dừng. */
export type SleepMode =
  | { kind: "off" }
  | { kind: "minutes"; minutes: number; leftMs: number; since: number | null }
  | { kind: "chapter" };

export const SLEEP_CHOICES = [5, 10, 15, 30, 45, 60];
export const DEFAULT_FADE_SECONDS = 30;
export const DEFAULT_EXTEND_MINUTES = 10;
const FADE_FLOOR_DB = -40;

export function sleepFrom(request: SleepRequest, playing: boolean, now: number): SleepMode {
  if (request.kind !== "minutes") return request;
  return { kind: "minutes", minutes: request.minutes, leftMs: request.minutes * 60_000, since: playing ? now : null };
}

export function sleepLeftMs(mode: SleepMode, now: number): number | null {
  if (mode.kind !== "minutes") return null;
  return Math.max(0, mode.since === null ? mode.leftMs : mode.leftMs - Math.max(0, now - mode.since));
}

/** Đồng hồ ngừng khi tạm dừng, chạy tiếp khi phát. */
export function sleepPaused(mode: SleepMode, now: number): SleepMode {
  if (mode.kind !== "minutes" || mode.since === null) return mode;
  return { ...mode, leftMs: sleepLeftMs(mode, now) ?? 0, since: null };
}

export function sleepResumed(mode: SleepMode, now: number): SleepMode {
  if (mode.kind !== "minutes" || mode.since !== null) return mode;
  return { ...mode, since: now };
}

/** Nghe thêm: cộng vào thời gian còn lại. Đang "hết chương" thì chuyển thành đếm phút kể từ bây giờ. */
export function sleepExtended(mode: SleepMode, minutes: number, playing: boolean, now: number): SleepMode {
  if (mode.kind === "minutes") {
    const left = sleepLeftMs(mode, now) ?? 0;
    return { kind: "minutes", minutes: mode.minutes, leftMs: left + minutes * 60_000, since: playing ? now : null };
  }
  return sleepFrom({ kind: "minutes", minutes }, playing, now);
}

/** Hệ số âm lượng khi còn `leftMs` trong đoạn nhỏ dần dài `fadeMs`: tuyến tính theo dB từ 0 xuống -40 dB. */
export function fadeGain(leftMs: number, fadeMs: number): number {
  if (fadeMs <= 0 || leftMs >= fadeMs) return 1;
  const progress = 1 - Math.max(0, leftMs) / fadeMs;
  return 10 ** ((FADE_FLOOR_DB * progress) / 20);
}

/** Nhãn trên nút: "14:59", phút cuối vẫn đếm từng giây; "Hết chương". */
export function sleepLabel(mode: SleepMode, now: number): string {
  if (mode.kind === "chapter") return "Hết chương";
  const left = sleepLeftMs(mode, now);
  if (left === null) return "";
  const seconds = Math.ceil(left / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Nhãn trên NÚT hẹn giờ: có đơn vị ("14 phút", "40 giây") - "14:51" ngay cạnh nút tốc độ và giọng đọc trông như giờ đồng hồ (soát UX a9). Bảng mở ra vẫn
 *  hiện đồng hồ đếm lùi đầy đủ ([sleepLabel]). */
export function sleepButtonLabel(mode: SleepMode, now: number): string {
  if (mode.kind === "chapter") return "Hết chương";
  const left = sleepLeftMs(mode, now);
  if (left === null) return "";
  return left < 60_000 ? `${Math.max(1, Math.ceil(left / 1000))} giây` : `${Math.ceil(left / 60_000)} phút`;
}

export function sleepSpoken(mode: SleepMode, now: number): string {
  if (mode.kind === "chapter") return "Hẹn giờ tắt: dừng khi hết chương này";
  const left = sleepLeftMs(mode, now);
  if (left === null) return "Hẹn giờ tắt";
  const minutes = Math.ceil(left / 60_000);
  return left < 60_000 ? `Hẹn giờ tắt: còn ${Math.ceil(left / 1000)} giây` : `Hẹn giờ tắt: còn ${minutes} phút`;
}

/**
 * Hẹn giờ tắt của loa / TV: máy giữ phiên phát đếm (webui/cast.py, DlnaPlayers.kt - chỉ nó biết thiết bị đang phát hay
 * dừng), cùng luật với hẹn giờ ở đây: chỉ trôi khi đang phát. `left`: giây còn lại lúc máy ấy trả lời.
 */
export type RemoteSleep = { kind: "minutes"; minutes: number; left: number; counting: boolean } | { kind: "chapter" };

/** Lệnh hẹn giờ gửi loa / TV qua đường điều khiển từ xa (`/api/remote`, RemotePlayers): không phút nào = tắt hẹn giờ. */
export type RemoteSleepCommand = { action: "sleep"; minutes?: number; endOfChapter?: boolean };

/** Hẹn giờ của loa / TV theo cách nút hẹn giờ ở đây đọc; `receivedAt`: lúc nhận câu trả lời ấy. */
export function remoteSleepMode(sleep: RemoteSleep | null | undefined, receivedAt: number): SleepMode {
  if (!sleep) return { kind: "off" };
  if (sleep.kind === "chapter") return { kind: "chapter" };
  return { kind: "minutes", minutes: sleep.minutes, leftMs: sleep.left * 1000, since: sleep.counting ? receivedAt : null };
}

export function remoteSleepCommand(request: SleepRequest): RemoteSleepCommand {
  if (request.kind === "chapter") return { action: "sleep", endOfChapter: true };
  return { action: "sleep", minutes: request.kind === "minutes" ? request.minutes : 0 };
}

/** Nút đổi ngay dưới tay người bấm, trước khi loa / TV trả lời. */
export function remoteSleepAfter(command: RemoteSleepCommand, playing: boolean): RemoteSleep | null {
  if (command.endOfChapter) return { kind: "chapter" };
  const minutes = command.minutes ?? 0;
  return minutes > 0 ? { kind: "minutes", minutes, left: minutes * 60, counting: playing } : null;
}

/** Tự lùi khi nghe lại (giây), theo độ dài lần dừng: dưới nửa phút thì thôi; tới 10 phút lùi 5 giây; lâu hơn lùi 10 giây. MỘT luật cho hai nền:
 *  điện thoại AutoRewind.kt cùng số, bộ ví dụ chung tests/fixtures/auto_rewind/cases.json. */
export const REWIND_SHORT_MS = 30_000;
export const REWIND_LONG_MS = 10 * 60_000;
export function rewindAfter(pausedMs: number): number {
  if (pausedMs < REWIND_SHORT_MS) return 0;
  if (pausedMs <= REWIND_LONG_MS) return 5;
  return 10;
}

/** Lịch đêm: bấm nghe trong khung giờ này thì tự hẹn giờ ngủ (giờ dạng "22:00", khung có thể qua nửa đêm). */
export interface SleepSchedule {
  from: string;
  to: string;
  minutes: number;
}

// Hợp đồng của các tuỳ chọn hẹn giờ ngủ: đúng các mức giao diện đưa ra, cùng bảng với webui/library.py (SLEEP_CHOICES, SCHEDULE_MINUTES,
// clean_sleep_schedule) - file tuỳ chọn sửa tay / bản app khác ghi không được lọt vào trình phát (soát a100 V2). Android dùng lại ở settings.ts.
export const FADE_CHOICES = [10, 30, 60];
export const EXTEND_CHOICES = [5, 10, 15];
export const SAFETY_STOP_CHOICES = [0, 1, 2, 3];
export const SCHEDULE_MINUTES = [15, 30, 45, 60];
const CLOCK = /^([01]\d|2[0-3]):[0-5]\d$/;

/** `value` nếu là một trong `choices` (đúng kiểu số), không thì `fallback` - trường sai về mặc định RIÊNG trường ấy. */
export function choiceOr(value: unknown, choices: readonly number[], fallback: number): number {
  return typeof value === "number" && choices.includes(value) ? value : fallback;
}

/** Lịch đêm đúng cấu trúc ("HH:mm" 00:00-23:59 hai đầu, số phút trong các mức), hay null: sai kiểu, thiếu trường, giờ lạ, số phút lạ. */
export function cleanSleepSchedule(value: unknown): SleepSchedule | null {
  if (!value || typeof value !== "object") return null;
  const { from, to, minutes } = value as Record<string, unknown>;
  if (typeof from !== "string" || !CLOCK.test(from) || typeof to !== "string" || !CLOCK.test(to)) return null;
  if (typeof minutes !== "number" || !SCHEDULE_MINUTES.includes(minutes)) return null;
  return { from, to, minutes };
}
