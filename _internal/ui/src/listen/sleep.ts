import { S } from "../shared/strings.generated";
import { VALUE_SPECS, quantize, type ValueSpec } from "../shared/valuePickerLogic";
// Hẹn giờ ngủ - phần tính toán, chung cho máy tính và giao diện Android (lõi native tự đếm trên Android).
//
// Ba điều người nghe lúc buồn ngủ cần, rút ra từ đánh giá 26-09:
//  - thời gian chỉ trôi khi ĐANG PHÁT: tự tạm dừng rồi quay lại không bị tắt ngay lập tức, và con số trên nút
//    không bao giờ treo ở "1′" sau khi hết giờ;
//  - nhỏ dần theo thang dB (tai nghe âm lượng theo logarit): giảm đều theo biên độ thì mấy bậc cuối tụt như bị cắt;
//  - nghe thêm được bằng một thao tác (trên điện thoại là lắc máy; trên máy tính là chạm phím/chuột lúc đang nhỏ dần) và KHÔNG cộng dồn: đồng hồ chỉ về lại
//    số phút đã hẹn.

/** `chapters`: dừng khi hết chừng ấy chương (1 = "Hết chương này"), mặc định 1. */
export type SleepRequest = { kind: "off" } | { kind: "minutes"; minutes: number } | { kind: "chapter"; chapters?: number };

/** `leftMs` là thời gian còn lại tính tới mốc `since`; `since` = lúc bắt đầu đếm (đang phát), null khi đang dừng. */
export type SleepMode = (
  | { kind: "off" }
  | { kind: "minutes"; minutes: number; leftMs: number; since: number | null }
  | { kind: "chapter"; chapters: number }) & { stoppedAt?: number };

/** "Hết N chương": chọn N trong 1..10 (VALUE_SPECS.sleepChapters). */
export function chaptersOf(mode: SleepMode | SleepRequest): number {
  return mode.kind === "chapter" ? Math.max(1, Math.round(mode.chapters ?? 1)) : 0;
}
export const DEFAULT_FADE_SECONDS = 30;
export const DEFAULT_EXTEND_MINUTES = 10;
const FADE_FLOOR_DB = -40;

export function sleepFrom(request: SleepRequest, playing: boolean, now: number): SleepMode {
  if (request.kind === "chapter") return { kind: "chapter", chapters: chaptersOf(request) };
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

/** Dòng dưới đồng hồ khi hẹn giờ đứng vì tạm dừng. Điện thoại: SleepText.pausedNote. */
export function sleepPausedNote(): string {
  return S.s_sleep_paused_keep;
}

export const RECENT_STOP_MS = 30 * 60_000;

/** Hẹn giờ tự tắt tiếng chưa quá nửa giờ: tấm Hẹn giờ nói lúc tắt tiếng - kể cả khi lựa chọn còn giữ sau lần tự dừng (soát 0.4.173 B8).
 *  Máy tính: Player::sleepStoppedText; điện thoại: SleepText.recentlyStopped. */
export function sleepStoppedRecently(stoppedAt: number | null, now: number): boolean {
  return stoppedAt !== null && now - stoppedAt >= 0 && now - stoppedAt < RECENT_STOP_MS;
}

/** Nút "Bật lại N phút": chỉ khi hẹn giờ đã tắt hẳn. Điện thoại: SleepText.restartOffered; máy tính: SleepPopover (sleepKind "off"). */
export function sleepRestartOffered(mode: SleepMode, stoppedAt: number | null, now: number): boolean {
  return mode.kind === "off" && sleepStoppedRecently(stoppedAt, now);
}

export function sleepResumed(mode: SleepMode, now: number): SleepMode {
  if (mode.kind !== "minutes" || mode.since !== null) return mode;
  return { ...mode, since: now };
}

/** Số phút "Hẹn lại": hẹn phút thì đúng số người nghe đã chọn, hết chương thì `fallback` ("Mỗi lần nghe thêm" của Cài đặt). MỘT hàm cho nhãn nút và
 *  [sleepExtended]. Điện thoại: SleepText.extendMinutes (Kotlin). */
export function sleepExtendMinutes(mode: SleepMode, fallback: number): number {
  return mode.kind === "minutes" && mode.minutes > 0 ? mode.minutes : fallback;
}

/** Nhãn nút nghe thêm: đồng hồ về lại N phút, không cộng thêm. Điện thoại: SleepText.extendLabel. */
export function sleepExtendLabel(minutes: number): string {
  return S.s_hen_lai_0_phut_d6009aba(minutes);
}

/** Nghe thêm = hẹn lại: đồng hồ về đúng [sleepExtendMinutes] phút, không bao giờ hơn (bấm nhiều lần không cộng dồn); còn lại đã nhiều hơn thì giữ nguyên.
 *  Đang "hết chương" thì chuyển thành đếm `fallback` phút kể từ bây giờ. */
export function sleepExtended(mode: SleepMode, fallback: number, playing: boolean, now: number): SleepMode {
  if (mode.kind === "off") return mode;
  if (mode.kind === "minutes") {
    const picked = sleepExtendMinutes(mode, fallback);
    const left = sleepLeftMs(mode, now) ?? 0;
    return { kind: "minutes", minutes: picked, leftMs: Math.max(left, picked * 60_000), since: playing ? now : null };
  }
  return sleepFrom({ kind: "minutes", minutes: fallback }, playing, now);
}

/** Hệ số âm lượng khi còn `leftMs` trong đoạn nhỏ dần dài `fadeMs`: tuyến tính theo dB từ 0 xuống -40 dB. */
export function fadeGain(leftMs: number, fadeMs: number): number {
  if (fadeMs <= 0 || leftMs >= fadeMs) return 1;
  const progress = 1 - Math.max(0, leftMs) / fadeMs;
  return 10 ** ((FADE_FLOOR_DB * progress) / 20);
}

/** Hẹn "hết chương" lúc một chương vừa hết: còn chương nữa thì đếm tiếp (N-1), không thì null = dừng ở đây. */
export function sleepAfterChapter(mode: SleepMode): SleepMode | null {
  if (mode.kind !== "chapter") return mode;
  return mode.chapters > 1 ? { kind: "chapter", chapters: mode.chapters - 1 } : null;
}

function chapterLabel(mode: SleepMode & { kind: "chapter" }): string {
  return mode.chapters > 1 ? S.s_het_0_chuong_79433c77(mode.chapters) : S.s_het_chuong_f1d590bb;
}

/** Nhãn trên nút: "14:59", phút cuối vẫn đếm từng giây; "Hết chương", "Hết 3 chương". */
export function sleepLabel(mode: SleepMode, now: number): string {
  if (mode.kind === "chapter") return chapterLabel(mode);
  const left = sleepLeftMs(mode, now);
  if (left === null) return "";
  const seconds = Math.ceil(left / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Nhãn trên NÚT hẹn giờ: có đơn vị ("14 phút", "40 giây") - "14:51" ngay cạnh nút tốc độ và giọng đọc trông như giờ đồng hồ (soát UX a9). Bảng mở ra vẫn
 *  hiện đồng hồ đếm lùi đầy đủ ([sleepLabel]). */
export function sleepButtonLabel(mode: SleepMode, now: number): string {
  if (mode.kind === "chapter") return chapterLabel(mode);
  const left = sleepLeftMs(mode, now);
  if (left === null) return "";
  // Theo số giây làm tròn lên (như đồng hồ trong bảng): còn 59,5 giây là "1 phút", không phải "60 giây".
  const seconds = Math.ceil(left / 1000);
  return seconds < 60 ? S.s_0_giay_daac30d3(Math.max(1, seconds)) : S.s_0_phut_2596d212(Math.ceil(left / 60_000));
}

export function sleepSpoken(mode: SleepMode, now: number): string {
  if (mode.kind === "chapter") return mode.chapters > 1 ? S.s_hen_gio_ngu_dung_khi_het_0_chuong_94192fb5(mode.chapters) : S.s_hen_gio_ngu_dung_khi_het_chuong_nay_38902b7c;
  const left = sleepLeftMs(mode, now);
  if (left === null) return S.s_hen_gio_ngu_21073488;
  const seconds = Math.ceil(left / 1000);
  return seconds < 60 ? S.s_hen_gio_ngu_con_0_giay_b3403ad5(seconds) : S.s_hen_gio_ngu_con_0_phut_52a86bfa(Math.ceil(left / 60_000));
}

/**
 * Hẹn giờ ngủ của loa / TV: máy giữ phiên phát đếm (webui/cast.py, DlnaPlayers.kt - chỉ nó biết thiết bị đang phát hay
 * dừng), cùng luật với hẹn giờ ở đây: chỉ trôi khi đang phát. `left`: giây còn lại lúc máy ấy trả lời.
 */
export type RemoteSleep = { kind: "minutes"; minutes: number; left: number; counting: boolean } | { kind: "chapter" };

/** Lệnh hẹn giờ gửi loa / TV qua đường điều khiển từ xa (`/api/remote`, RemotePlayers): không phút nào = tắt hẹn giờ. */
export type RemoteSleepCommand = { action: "sleep"; minutes?: number; endOfChapter?: boolean };

/** Hẹn giờ của loa / TV theo cách nút hẹn giờ ở đây đọc; `receivedAt`: lúc nhận câu trả lời ấy. */
export function remoteSleepMode(sleep: RemoteSleep | null | undefined, receivedAt: number): SleepMode {
  if (!sleep) return { kind: "off" };
  if (sleep.kind === "chapter") return { kind: "chapter", chapters: 1 };
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

/** Lịch đêm: bấm nghe trong khung giờ này thì tự hẹn giờ ngủ (giờ dạng "22:00", khung có thể qua nửa đêm). */
export interface SleepSchedule {
  from: string;
  to: string;
  minutes: number;
}

/** Lần hẹn giờ cuối người nghe tự đặt (tuỳ chọn `lastSleep`, chủ sách 17-11): `kind` là loại của lần cuối, `minutes` / `chapters` là số gần nhất của
 *  từng loại. Hộp hẹn giờ mở sẵn ở mốc này, nút "Bật lại" đặt lại đúng nó. Cùng hợp đồng với webui/library.py (clean_last_sleep), Qt (playerlogic.h)
 *  và Android (LastSleep.kt) - tests/fixtures/settings/ranges.json `lastSleep`. */
export interface LastSleep {
  kind: "minutes" | "chapter";
  minutes: number;
  chapters: number;
}

/** Chưa từng đặt hẹn giờ: 30 phút. */
export const LAST_SLEEP_DEFAULT: LastSleep = { kind: "minutes", minutes: 30, chapters: 1 };

/** Lần hẹn cuối đã làm sạch (khoá thừa bỏ đi), hay null: thiếu khoá, sai kiểu, ngoài miền ở bất kỳ khoá nào - coi như chưa từng đặt. */
export function cleanLastSleep(value: unknown): LastSleep | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const { kind, minutes, chapters } = value as Record<string, unknown>;
  if (kind !== "minutes" && kind !== "chapter") return null;
  if (rangeOr(minutes, VALUE_SPECS.sleepMinutes, -1) !== minutes || rangeOr(chapters, VALUE_SPECS.sleepChapters, -1) !== chapters) return null;
  return { kind, minutes: minutes as number, chapters: chapters as number };
}

/** Lần hẹn cuối sau khi người nghe tự đặt `request`; tắt hẹn giờ thì giữ nguyên. */
export function lastSleepAfter(last: LastSleep, request: SleepRequest): LastSleep {
  if (request.kind === "minutes") return { ...last, kind: "minutes", minutes: request.minutes };
  if (request.kind === "chapter") return { ...last, kind: "chapter", chapters: chaptersOf(request) };
  return last;
}

/** Đặt lại đúng lần hẹn cuối (nút "Bật lại"). */
export function lastSleepRequest(last: LastSleep): SleepRequest {
  return last.kind === "chapter" ? { kind: "chapter", chapters: last.chapters } : { kind: "minutes", minutes: last.minutes };
}

/** Nhãn nút "Bật lại" (tối đa 4 chữ, một khuôn cho hai loại): "Bật lại 45 phút", "Bật lại 1 chương", "Bật lại 2 chương".
 *  Điện thoại: SleepText.restart, Qt: SleepPopover.qml - cùng từng chữ. */
export function lastSleepRestartLabel(last: LastSleep): string {
  return S.s_bat_lai_0bad8bcf + (last.kind === "minutes" ? S.s_0_phut_2596d212(last.minutes) : S.s_0_chuong_04093412(last.chapters));
}

// Hợp đồng của các tuỳ chọn hẹn giờ ngủ: miền tự do của bộ chọn giá trị (VALUE_SPECS), cùng bảng với webui/library.py (SLEEP_RANGES,
// SCHEDULE_MINUTES, clean_sleep_schedule) - file tuỳ chọn sửa tay / bản app khác ghi không được lọt vào trình phát (soát a100 V2).
export const FADE_RANGE = VALUE_SPECS.sleepFadeSeconds;
export const EXTEND_RANGE = VALUE_SPECS.sleepExtendMinutes;
export const SCHEDULE_MINUTES = VALUE_SPECS.scheduleMinutes;
const CLOCK = /^([01]\d|2[0-3]):[0-5]\d$/;

/** `value` nếu là số trong miền, đúng lưới bước của `spec`; không thì `fallback` - trường sai về mặc định RIÊNG trường ấy. */
export function rangeOr(value: unknown, spec: ValueSpec, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && quantize(spec, value) === value ? value : fallback;
}

/** Lịch đêm đúng cấu trúc ("HH:mm" 00:00-23:59 hai đầu, số phút trong miền), hay null: sai kiểu, thiếu trường, giờ lạ, số phút lạ. */
export function cleanSleepSchedule(value: unknown): SleepSchedule | null {
  if (!value || typeof value !== "object") return null;
  const { from, to, minutes } = value as Record<string, unknown>;
  if (typeof from !== "string" || !CLOCK.test(from) || typeof to !== "string" || !CLOCK.test(to)) return null;
  if (rangeOr(minutes, SCHEDULE_MINUTES, -1) !== minutes) return null;
  return { from, to, minutes };
}
