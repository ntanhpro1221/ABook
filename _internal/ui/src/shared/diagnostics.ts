import { S } from "./strings.generated";
import { formatSize } from "./format";

// Bản chẩn đoán của điện thoại (mobile/.../Diagnostics.kt) - máy tính đọc qua `GET /api/remote/<mã>/diagnostics`, điện thoại tự xem ở Cài đặt → Chẩn đoán.
// Mọi phần đều tuỳ chọn. Lỗi thu thập mới có collectionFailed; bản cũ chỉ có { error } vẫn đọc được.

export interface DiagnosticsFailure {
  error: string;
  collectionFailed?: boolean;
}
type Part<T> = (T & Partial<DiagnosticsFailure>) | DiagnosticsFailure;

export interface DiagnosticsReport {
  schema?: number;
  app?: Part<{ package?: string; versionName?: string; versionCode?: number; debug?: boolean; pid?: number }>;
  device?: Part<{ sdk?: number; release?: string; manufacturer?: string; model?: string }>;
  time?: Part<{ epochMillis?: number; iso?: string; timezone?: string }>;
  battery?: Part<{ percent?: number | null; charging?: boolean }>;
  network?: Part<{ connected?: boolean; wifi?: boolean; cellular?: boolean; vpn?: boolean; ethernet?: boolean; bluetooth?: boolean; validated?: boolean; metered?: boolean }>;
  storage?: Part<{ freeBytes?: number; totalBytes?: number }>;
  notifications?: Part<{ enabled?: boolean }>;
  power?: Part<{ ignoringBatteryOptimizations?: boolean; powerSave?: boolean; deviceIdle?: boolean; backgroundRestricted?: boolean }>;
  playback?: Part<{ bookId?: string; bookTitle?: string; chapterId?: number; chapterTitle?: string; position?: number; duration?: number; playing?: boolean; buffering?: boolean; error?: string }>;
  work?: DiagnosticsFailure | { id: string; state: string; tags: string[]; attempts: number; stopReason: number; progress: Record<string, string> }[];
  share?: Part<{ running?: boolean; pairedDevices?: number; lastError?: string }>;
  exitReasons?: DiagnosticsFailure | { reason: string; code: number; description: string; timestamp: number; importance: string; importanceCode?: number; pssKb: number; rssKb: number; trace?: string }[];
  crashes?: DiagnosticsFailure | { name: string; text: string }[];
  dataRecovery?: Part<{ savingBlocked?: boolean; notices?: { kind?: string; at?: number; preservedFile?: string; pending?: boolean }[] }>;
  log?: DiagnosticsFailure | string[];
  logcat?: DiagnosticsFailure | string[];
  truncated?: boolean;
  /** Giây (epoch) máy tính nhận bản này; điện thoại không điền. */
  fetchedAt?: number;
}

export interface DiagnosticsRow {
  label: string;
  value: string;
}

/** Per-job details supplement the counts without exposing worker IDs. */
export function workProgressRows(report: DiagnosticsReport): DiagnosticsRow[] {
  if (!Array.isArray(report.work)) return [];
  const phases: Record<string, string> = {
    download: S.s_dang_tai_1fd8b1ef, downloading: S.s_dang_tai_1fd8b1ef, fetch: S.s_dang_tai_1fd8b1ef, voice: S.s_dang_tao_giong_doc_799156a0,
    encode: S.s_dang_ghep_am_thanh_9153c306, music: S.s_dang_tron_nhac_e4d467d5, "music-fetch": S.s_dang_tai_nhac_nen_98212286,
    peaks: S.s_dang_kiem_dinh_am_0858dcd2, reencode: S.s_dang_ma_hoa_lai_266e95f8, verify: S.s_dang_kiem_tra_3c8395d9, done: S.s_da_xong_fce9b751,
    prepare: S.s_dang_chuan_bi_d4a83411, package: S.s_dang_dong_goi_f7c98bff, export: S.s_dang_xuat_67231e8c,
  };
  const states: Record<string, string> = { RUNNING: S.s_dang_chay_01527862, ENQUEUED: S.s_dang_cho_ed662259, FAILED: S.s_hong_284f6108, CANCELLED: S.s_da_dung_caf33d01, SUCCEEDED: S.s_da_xong_fce9b751, BLOCKED: S.s_dang_cho_dieu_kien_a44f208b };
  const kinds: Record<string, string> = { BookDownloadWorker: S.s_tai_sach_3c83e586, Mp3ExportWorker: S.s_xuat_mp3_60946614, M4bExportWorker: S.s_xuat_m4b_4a708187, ListenExportWorker: S.s_xuat_sach_noi_219fb12a };
  const count = (value: string | undefined) => value !== undefined && value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0 ? value : undefined;
  return report.work.flatMap((job, index) => {
    const progress = job.progress ?? {};
    const done = count(progress.done);
    const total = count(progress.total);
    const phase = progress.phase?.trim();
    if (done === undefined && total === undefined && !phase) return [];
    const title = job.tags.map((tag) => kinds[tag]).find(Boolean) ?? S.s_viec_nen_364c2b5d;
    return [{ label: S.s_viec_0_ce676501(index + 1), value: [title, states[job.state] ?? S.s_chua_ro_trang_thai_8f3e99b0,
      done !== undefined && total !== undefined ? `${done}/${total}` : done !== undefined ? S.s_da_lam_0_1c2d81d0(done) : total !== undefined ? S.s_tong_0_ccc4947d(total) : "",
      phase ? `Pha: ${phases[phase] ?? phase}` : ""].filter(Boolean).join(" · ") }];
  });
}

function failed(part: unknown): string | null {
  if (!part || typeof part !== "object" || Array.isArray(part)) return null;
  const { error, collectionFailed } = part as Partial<DiagnosticsFailure>;
  if (typeof error !== "string" || !error.trim()) return null;
  // Playback.state luôn có error: lỗi phát vẫn là trạng thái đã thu được, không phải lỗi thu thập.
  if (!collectionFailed && ["bookId", "bookTitle", "playing", "position"].some(key => key in part)) return null;
  return S.s_khong_doc_duoc_20e38587;
}

/** Nguyên văn kỹ thuật chỉ để trong phần mở rộng; không đưa vào các dòng tóm tắt. */
export function failureDetails(report: DiagnosticsReport): DiagnosticsRow[] {
  return Object.entries(report).flatMap(([label, part]) => {
    const error = part && typeof part === "object" && !Array.isArray(part) ? (part as Partial<DiagnosticsFailure>).error : undefined;
    return typeof error === "string" && error.trim() ? [{ label, value: error.trim() }] : [];
  });
}

const yes = (value: boolean | undefined) => (value ? S.s_co_8e3aafe8 : S.s_khong_0ec84c3f);

function when(millis: number): string {
  const date = new Date(millis);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Tóm tắt cho người đọc: mỗi mục có dữ liệu thì một dòng "nhãn: giá trị" (phần thiếu thì bỏ, phần lỗi thì nói không đọc được). */
export function summaryRows(report: DiagnosticsReport): DiagnosticsRow[] {
  const rows: DiagnosticsRow[] = [];
  const add = (label: string, part: unknown, value: () => string | null) => {
    if (part === undefined || part === null) return;
    const problem = failed(part);
    if (problem) {
      rows.push({ label, value: problem });
      return;
    }
    const text = value();
    if (text) rows.push({ label, value: text });
  };
  add(S.s_ban_abook_046fa27d, report.app, () => {
    const app = report.app as { versionName?: string; versionCode?: number; debug?: boolean };
    return [`${app.versionName ?? "?"}${app.versionCode !== undefined ? ` (${app.versionCode})` : ""}`, app.debug ? S.s_ban_thu_3095d3e2 : ""].filter(Boolean).join(" · ");
  });
  add(S.s_dien_thoai_8185f4c9, report.device, () => {
    const device = report.device as { sdk?: number; release?: string; manufacturer?: string; model?: string };
    return `${[device.manufacturer, device.model].filter(Boolean).join(" ")} · Android ${device.release ?? "?"}${device.sdk ? ` (API ${device.sdk})` : ""}`;
  });
  add(S.s_gio_tren_may_6a6cdf95, report.time, () => {
    const time = report.time as { epochMillis?: number; timezone?: string };
    return time.epochMillis ? `${when(time.epochMillis)}${time.timezone ? ` · ${time.timezone}` : ""}` : null;
  });
  add(S.s_copy_ff1cee744146, report.battery, () => {
    const battery = report.battery as { percent?: number | null; charging?: boolean };
    return `${typeof battery.percent === "number" ? `${battery.percent}%` : S.s_khong_ro_e5605c9b}${battery.charging ? S.s_dang_sac_d0d1332a : ""}`;
  });
  add(S.s_mang_4b4e6369, report.network, () => {
    const net = report.network as NonNullable<Extract<DiagnosticsReport["network"], { connected?: boolean }>>;
    if (!net.connected) return S.s_chua_co_mang_c903ca13;
    const ways = [net.wifi && S.s_wi_fi_337253f2, net.cellular && S.s_di_dong_541aae75, net.vpn && "VPN", net.ethernet && S.s_day_mang_56c3cabb, net.bluetooth && S.s_bluetooth_8bb29098].filter(Boolean);
    return [ways.join(" + ") || S.s_co_mang_23deb37d, net.validated ? "" : S.s_chua_ra_duoc_internet_43c4be0b, net.metered ? S.s_tinh_cuoc_707dc43c : ""].filter(Boolean).join(" · ");
  });
  add(S.s_cho_trong_a5fb7e34, report.storage, () => {
    const storage = report.storage as { freeBytes?: number; totalBytes?: number };
    return typeof storage.freeBytes === "number" ? `${formatSize(storage.freeBytes)}${storage.totalBytes ? ` / ${formatSize(storage.totalBytes)}` : ""}` : null;
  });
  add(S.s_thong_bao_a9b656f5, report.notifications, () => ((report.notifications as { enabled?: boolean }).enabled ? S.s_dang_bat_a2be6d6c : S.s_dang_tat_6d495acb));
  add(S.s_chay_nen_4553c5f8, report.power, () => {
    const power = report.power as { ignoringBatteryOptimizations?: boolean; powerSave?: boolean; backgroundRestricted?: boolean };
    return [S.s_mien_toi_uu_pin_0_032bafe2(yes(power.ignoringBatteryOptimizations)), power.backgroundRestricted ? S.s_bi_han_che_chay_nen_d4b2a7df : "", power.powerSave ? S.s_dang_tiet_kiem_pin_287c6ba6 : ""].filter(Boolean).join(" · ");
  });
  add(S.s_dang_nghe_9310d8cf, report.playback, () => {
    const playback = report.playback as { bookTitle?: string; chapterId?: number; position?: number; playing?: boolean; error?: string };
    if (!playback.bookTitle) return S.s_chua_mo_cuon_nao_1220ce65;
    const place = typeof playback.position === "number" ? S.s_0_phut_1_giay_c311e6ad(Math.floor(playback.position / 60), Math.floor(playback.position % 60)) : "";
    return `${playback.bookTitle}${playback.chapterId !== undefined ? S.s_chuong_0_89692e2f(playback.chapterId) : ""}${place} · ${playback.playing ? S.s_dang_phat_e3baf7da : S.s_tam_dung_eea0842f}${playback.error?.trim() ? S.s_co_loi_phat_7482c4cf : ""}`;
  });
  add(S.s_viec_nen_364c2b5d, report.work, () => {
    const work = Array.isArray(report.work) ? report.work : [];
    if (!work.length) return S.s_khong_co_viec_nao_2e68f374;
    const count = (state: string) => work.filter((job) => job.state === state).length;
    return [S.s_0_dang_chay_e713dc05(count("RUNNING")), S.s_0_dang_cho_5c390e4f(count("ENQUEUED")), count("FAILED") ? S.s_0_hong_3175a907(count("FAILED")) : "", count("CANCELLED") ? S.s_0_da_dung_f4fbf66d(count("CANCELLED")) : ""].filter(Boolean).join(" · ");
  });
  add(S.s_cho_may_khac_nghe_thu_vien_65b8bfae, report.share, () => {
    const share = report.share as { running?: boolean; pairedDevices?: number; lastError?: string };
    return share.running ? S.s_dang_bat_0_may_da_ghep_3e406d18(share.pairedDevices ?? 0) : S.s_dang_tat_0_f25d61a9(share.lastError ? ` (${share.lastError})` : "");
  });
  add(S.s_lan_tat_gan_nhat_3fae581d, report.exitReasons, () => {
    const last = Array.isArray(report.exitReasons) ? report.exitReasons[0] : undefined;
    return last ? `${last.reason}${last.timestamp ? ` · ${when(last.timestamp)}` : ""}` : null;
  });
  add(S.s_lan_vang_dee6eb16, report.crashes, () => (Array.isArray(report.crashes) && report.crashes.length ? S.s_0_lan_duoc_ghi_lai_d9ec830f(report.crashes.length) : null));
  add(S.s_phuc_hoi_du_lieu_7dde2059, report.dataRecovery, () => {
    const recovery = report.dataRecovery as { savingBlocked?: boolean; notices?: { kind?: string; at?: number; preservedFile?: string; pending?: boolean }[] };
    const kinds: Record<string, string> = { recovered: S.s_da_giu_ban_cu_698af56c, "saving-blocked": S.s_dang_chan_luu_e91d5596, "notice-read-error": S.s_chua_doc_duoc_canh_bao_ea2b6021, warning: S.s_canh_bao_9e63a91e };
    return [recovery.savingBlocked ? S.s_app_dang_chan_luu_de_giu_du_lieu_cua_ban_cd56418e : "", ...(recovery.notices ?? []).map((notice) =>
      [kinds[notice.kind ?? ""] ?? S.s_canh_bao_9e63a91e, notice.at ? when(notice.at) : "", notice.preservedFile, notice.pending ? S.s_chua_luu_canh_bao_bdc85d89 : ""].filter(Boolean).join(" · "))].filter(Boolean).join("; ") || S.s_chua_co_canh_bao_45795006;
  });
  return rows;
}

/** Các dòng của một mục nhật ký (`log` / `logcat`); phần lỗi hay thiếu thì mảng rỗng. */
export function logLines(report: DiagnosticsReport, key: "log" | "logcat" = "log"): string[] {
  const part = report[key];
  return Array.isArray(part) ? part : [];
}

/** Câu thay cho phần nhật ký khi không có dòng nào. */
export function emptyLogNote(report: DiagnosticsReport, key: "log" | "logcat" = "log"): string {
  const problem = failed(report[key]);
  return problem ?? S.s_chua_co_dong_nao_88732bb0;
}

/** Tên file lưu: `abook-nhat-ky-<tên máy>-<ngày-giờ>.json` (bỏ ký tự Windows không cho). */
export function reportFileName(deviceName: string, now: Date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const name = deviceName.replace(/[^\p{L}\p{N}._-]+/gu, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "dien-thoai";
  return `abook-nhat-ky-${name}-${stamp}.json`;
}

/** Trình duyệt thường (không có hộp chọn thư mục của app): tải file về qua thanh tải của trình duyệt. */
export function downloadText(name: string, text: string, type = "application/json"): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
