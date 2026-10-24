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
    download: "đang tải", downloading: "đang tải", fetch: "đang tải", voice: "đang tạo giọng đọc",
    encode: "đang ghép âm thanh", music: "đang trộn nhạc", "music-fetch": "đang tải nhạc nền",
    peaks: "đang kiểm đỉnh âm", reencode: "đang mã hoá lại", verify: "đang kiểm tra", done: "đã xong",
    prepare: "đang chuẩn bị", package: "đang đóng gói", export: "đang xuất",
  };
  const states: Record<string, string> = { RUNNING: "đang chạy", ENQUEUED: "đang chờ", FAILED: "hỏng", CANCELLED: "đã dừng", SUCCEEDED: "đã xong", BLOCKED: "đang chờ điều kiện" };
  const kinds: Record<string, string> = { BookDownloadWorker: "Tải sách", Mp3ExportWorker: "Xuất MP3", M4bExportWorker: "Xuất M4B", ListenExportWorker: "Xuất sách nói" };
  const count = (value: string | undefined) => value !== undefined && value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0 ? value : undefined;
  return report.work.flatMap((job, index) => {
    const progress = job.progress ?? {};
    const done = count(progress.done);
    const total = count(progress.total);
    const phase = progress.phase?.trim();
    if (done === undefined && total === undefined && !phase) return [];
    const title = job.tags.map((tag) => kinds[tag]).find(Boolean) ?? "Việc nền";
    return [{ label: `Việc ${index + 1}`, value: [title, states[job.state] ?? "chưa rõ trạng thái",
      done !== undefined && total !== undefined ? `${done}/${total}` : done !== undefined ? `đã làm ${done}` : total !== undefined ? `tổng ${total}` : "",
      phase ? `Pha: ${phases[phase] ?? phase}` : ""].filter(Boolean).join(" · ") }];
  });
}

function failed(part: unknown): string | null {
  if (!part || typeof part !== "object" || Array.isArray(part)) return null;
  const { error, collectionFailed } = part as Partial<DiagnosticsFailure>;
  if (typeof error !== "string" || !error.trim()) return null;
  // Playback.state luôn có error: lỗi phát vẫn là trạng thái đã thu được, không phải lỗi thu thập.
  if (!collectionFailed && ["bookId", "bookTitle", "playing", "position"].some(key => key in part)) return null;
  return "không đọc được";
}

/** Nguyên văn kỹ thuật chỉ để trong phần mở rộng; không đưa vào các dòng tóm tắt. */
export function failureDetails(report: DiagnosticsReport): DiagnosticsRow[] {
  return Object.entries(report).flatMap(([label, part]) => {
    const error = part && typeof part === "object" && !Array.isArray(part) ? (part as Partial<DiagnosticsFailure>).error : undefined;
    return typeof error === "string" && error.trim() ? [{ label, value: error.trim() }] : [];
  });
}

const yes = (value: boolean | undefined) => (value ? "có" : "không");

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
  add("Bản ABook", report.app, () => {
    const app = report.app as { versionName?: string; versionCode?: number; debug?: boolean };
    return [`${app.versionName ?? "?"}${app.versionCode !== undefined ? ` (${app.versionCode})` : ""}`, app.debug ? "bản thử" : ""].filter(Boolean).join(" · ");
  });
  add("Điện thoại", report.device, () => {
    const device = report.device as { sdk?: number; release?: string; manufacturer?: string; model?: string };
    return `${[device.manufacturer, device.model].filter(Boolean).join(" ")} · Android ${device.release ?? "?"}${device.sdk ? ` (API ${device.sdk})` : ""}`;
  });
  add("Giờ trên máy", report.time, () => {
    const time = report.time as { epochMillis?: number; timezone?: string };
    return time.epochMillis ? `${when(time.epochMillis)}${time.timezone ? ` · ${time.timezone}` : ""}` : null;
  });
  add("Pin", report.battery, () => {
    const battery = report.battery as { percent?: number | null; charging?: boolean };
    return `${typeof battery.percent === "number" ? `${battery.percent}%` : "không rõ"}${battery.charging ? " · đang sạc" : ""}`;
  });
  add("Mạng", report.network, () => {
    const net = report.network as NonNullable<Extract<DiagnosticsReport["network"], { connected?: boolean }>>;
    if (!net.connected) return "chưa có mạng";
    const ways = [net.wifi && "Wi-Fi", net.cellular && "di động", net.vpn && "VPN", net.ethernet && "dây mạng", net.bluetooth && "Bluetooth"].filter(Boolean);
    return [ways.join(" + ") || "có mạng", net.validated ? "" : "chưa ra được Internet", net.metered ? "tính cước" : ""].filter(Boolean).join(" · ");
  });
  add("Chỗ trống", report.storage, () => {
    const storage = report.storage as { freeBytes?: number; totalBytes?: number };
    return typeof storage.freeBytes === "number" ? `${formatSize(storage.freeBytes)}${storage.totalBytes ? ` / ${formatSize(storage.totalBytes)}` : ""}` : null;
  });
  add("Thông báo", report.notifications, () => ((report.notifications as { enabled?: boolean }).enabled ? "đang bật" : "đang tắt"));
  add("Chạy nền", report.power, () => {
    const power = report.power as { ignoringBatteryOptimizations?: boolean; powerSave?: boolean; backgroundRestricted?: boolean };
    return [`miễn tối ưu pin: ${yes(power.ignoringBatteryOptimizations)}`, power.backgroundRestricted ? "bị hạn chế chạy nền" : "", power.powerSave ? "đang tiết kiệm pin" : ""].filter(Boolean).join(" · ");
  });
  add("Đang nghe", report.playback, () => {
    const playback = report.playback as { bookTitle?: string; chapterId?: number; position?: number; playing?: boolean; error?: string };
    if (!playback.bookTitle) return "chưa mở cuốn nào";
    const place = typeof playback.position === "number" ? ` · ${Math.floor(playback.position / 60)} phút ${Math.floor(playback.position % 60)} giây` : "";
    return `${playback.bookTitle}${playback.chapterId !== undefined ? ` · chương ${playback.chapterId}` : ""}${place} · ${playback.playing ? "đang phát" : "tạm dừng"}${playback.error?.trim() ? " · có lỗi phát" : ""}`;
  });
  add("Việc nền", report.work, () => {
    const work = Array.isArray(report.work) ? report.work : [];
    if (!work.length) return "không có việc nào";
    const count = (state: string) => work.filter((job) => job.state === state).length;
    return [`${count("RUNNING")} đang chạy`, `${count("ENQUEUED")} đang chờ`, count("FAILED") ? `${count("FAILED")} hỏng` : "", count("CANCELLED") ? `${count("CANCELLED")} đã dừng` : ""].filter(Boolean).join(" · ");
  });
  add("Cho máy khác nghe thư viện", report.share, () => {
    const share = report.share as { running?: boolean; pairedDevices?: number; lastError?: string };
    return share.running ? `đang bật · ${share.pairedDevices ?? 0} máy đã ghép` : `đang tắt${share.lastError ? ` (${share.lastError})` : ""}`;
  });
  add("Lần tắt gần nhất", report.exitReasons, () => {
    const last = Array.isArray(report.exitReasons) ? report.exitReasons[0] : undefined;
    return last ? `${last.reason}${last.timestamp ? ` · ${when(last.timestamp)}` : ""}` : null;
  });
  add("Lần văng", report.crashes, () => (Array.isArray(report.crashes) && report.crashes.length ? `${report.crashes.length} lần được ghi lại` : null));
  add("Phục hồi dữ liệu", report.dataRecovery, () => {
    const recovery = report.dataRecovery as { savingBlocked?: boolean; notices?: { kind?: string; at?: number; preservedFile?: string; pending?: boolean }[] };
    const kinds: Record<string, string> = { recovered: "đã giữ bản cũ", "saving-blocked": "đang chặn lưu", "notice-read-error": "chưa đọc được cảnh báo", warning: "cảnh báo" };
    return [recovery.savingBlocked ? "App đang chặn lưu để giữ dữ liệu của bạn" : "", ...(recovery.notices ?? []).map((notice) =>
      [kinds[notice.kind ?? ""] ?? "cảnh báo", notice.at ? when(notice.at) : "", notice.preservedFile, notice.pending ? "chưa lưu cảnh báo" : ""].filter(Boolean).join(" · "))].filter(Boolean).join("; ") || "chưa có cảnh báo";
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
  return problem ?? "Chưa có dòng nào.";
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
