// Định dạng kiểu Việt: "1.234" cho số, "9 giờ 12 phút" cho thời lượng dài, "13:05" cho đồng hồ phát.

const numberFormat = new Intl.NumberFormat("vi-VN");

export function formatNumber(value: number): string {
  return numberFormat.format(Math.round(value));
}

/** Cỡ file: "850 MB", "3,2 GB" (một chữ số thập phân từ 1 GB trở lên). */
export function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(bytes / 1024 ** 3)} GB`;
  return `${formatNumber(bytes / 1024 ** 2)} MB`;
}

export function formatPercent(fraction: number): string {
  const value = Math.max(0, Math.min(1, fraction)) * 100;
  if (value > 0 && value < 1) return "<1%";
  if (value < 100 && value > 99) return "99%";
  return `${Math.floor(value)}%`;
}

/** Đồng hồ phát: 3:07, 13:05, 1:02:05 */
export function formatClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
  const whole = Math.floor(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  const mm = hours ? String(minutes).padStart(2, "0") : String(minutes);
  return `${hours ? `${hours}:` : ""}${mm}:${String(secs).padStart(2, "0")}`;
}

/** Đầu một câu để nhắc lại trong toast: bỏ ngoặc thoại hai đầu, cắt ở ranh giới từ - "Cậu ấy nói rằng hôm nay…". */
export function excerpt(text: string, max = 48): string {
  const clean = text.replace(/\s+/g, " ").trim().replace(/^["“”'‘’«»『』「」—–\-\s]+|["“”'‘’«»『』「」\s]+$/g, "");
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return `${(space > max / 2 ? cut.slice(0, space) : cut).replace(/[\s,.;:!?…—–-]+$/, "")}…`;
}

/** Cách đọc một tên để HIỆN: chữ đầu mỗi từ viết hoa - "rên-ta-rô" (phần tên máy tách từ "Nam rên-ta-rô") thành "Rên-ta-rô"
 *  (soát UX 29-09). Chỉ để hiện: ô sửa và dữ liệu giữ nguyên cách đọc đã lưu. */
export function shownReading(spoken: string): string {
  return spoken.replace(/(^|\s)(\p{Ll})/gu, (_match, gap: string, letter: string) => gap + letter.toUpperCase());
}

/** Thời lượng cho con người: "45 phút", "9 giờ 12 phút", "2 giờ". */
export function formatLength(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0 phút";
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return "dưới 1 phút";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${minutes} phút`;
  return rest ? `${hours} giờ ${rest} phút` : `${hours} giờ`;
}

/** Từ mức này của bước đang làm thì "còn dưới 2 phút" mới là "sắp xong" (soát UX a8: sách mới 21% mà đã ghi "sắp xong"). */
const NEAR_DONE = 0.85;

/** `fraction`: bước đang làm đã được bao nhiêu (0-1). Còn ít giây mà bước chưa tới mức gần xong thì chỉ nói còn dưới 2 phút -
 *  "sắp xong" là lời hứa về cái đích, không phải về con số giây. Không đưa `fraction` thì giữ nghĩa cũ. */
export function formatEta(seconds: number, fraction?: number): string {
  if (seconds < 90) return fraction === undefined || fraction >= NEAR_DONE ? "sắp xong" : "còn dưới 2 phút";
  return `còn khoảng ${formatLength(seconds)}`;
}

/** Thời gian còn lại của một cuốn đang chạy, theo bước máy đang ước (phân tích / thu âm), hoặc null khi chưa có tốc độ để ước. */
export function etaOf(book: {
  eta: { phase: string; seconds: number } | null;
  progress: { analysis: number; synthesis: number };
}): string | null {
  if (!book.eta) return null;
  return formatEta(book.eta.seconds, book.eta.phase === "synthesis" ? book.progress.synthesis : book.progress.analysis);
}

export function formatRelative(epochSeconds: number | null | undefined): string {
  if (!epochSeconds) return "";
  const delta = Date.now() / 1000 - epochSeconds;
  if (delta < 60) return "vừa xong";
  if (delta < 3600) return `${Math.floor(delta / 60)} phút trước`;
  if (delta < 86400) return `${Math.floor(delta / 3600)} giờ trước`;
  const days = Math.floor(delta / 86400);
  if (days === 1) return "hôm qua";
  if (days < 7) return `${days} ngày trước`;
  return formatDate(epochSeconds);
}

export function formatDate(epochSeconds: number): string {
  const date = new Date(epochSeconds * 1000);
  return date.toLocaleDateString("vi-VN", { day: "numeric", month: "numeric", year: "numeric" });
}

/** Đồng hồ đọc thành lời cho trình đọc màn hình: "5 phút 57 giây". */
export function spokenClock(seconds: number): string {
  const whole = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  const parts = [hours ? `${hours} giờ` : "", minutes ? `${minutes} phút` : "", `${secs} giây`].filter(Boolean);
  return parts.join(" ");
}

/** Mốc thời gian nói kiểu người: "hôm nay 14:02", "tối qua 23:41", "hôm qua 09:15", "3 ngày trước". */
export function formatWhen(epochSeconds: number | null | undefined): string {
  if (!epochSeconds) return "";
  const date = new Date(epochSeconds * 1000);
  const today = new Date();
  const days = Math.round(
    (new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() -
      new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) /
      86_400_000,
  );
  const time = date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  if (days <= 0) return Date.now() / 1000 - epochSeconds < 60 ? "vừa xong" : `hôm nay ${time}`;
  if (days === 1) return date.getHours() >= 18 ? `tối qua ${time}` : `hôm qua ${time}`;
  if (days < 7) return `${days} ngày trước`;
  return formatDate(epochSeconds);
}

export function formatTime(epochSeconds: number): string {
  const date = new Date(epochSeconds * 1000);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const time = date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  return sameDay ? time : `${time} · ${date.toLocaleDateString("vi-VN", { day: "numeric", month: "numeric" })}`;
}

/** Giấy phép nhạc đọc được: "CC BY 4.0", "CC BY-SA 4.0", "CC0 1.0". Danh mục chỉ giữ mã ("by", "cc0"); phiên bản lấy từ
 *  liên kết giấy phép nếu có (không đoán phiên bản khi không có), mã lạ thì giữ nguyên. */
export function licenseLabel(code?: string | null, url?: string | null): string {
  const match = url?.match(/creativecommons\.org\/(licenses|publicdomain)\/([a-z-]+)\/(\d+(?:\.\d+)?)/i);
  if (match) {
    const [, kind, slug, version] = match;
    if (kind.toLowerCase() === "licenses") return `CC ${slug.toUpperCase()} ${version}`;
    if (slug.toLowerCase() === "zero") return `CC0 ${version}`;
  }
  const raw = (code ?? "").trim();
  const lower = raw.toLowerCase();
  if (lower === "cc0") return "CC0";
  if (/^by(-(nc|nd|sa))*$/.test(lower)) return `CC ${lower.toUpperCase()}`;
  return raw;
}

/** Vân tay chứng chỉ để người dùng nhìn và đối chiếu: nhóm 4 ký tự, hoa - "AB12 CD34 ..." như `tls.display` / `Pin.display`.
 *  Nhận cả dạng hex lưu sẵn lẫn dạng đã nhóm (chạy lại không đổi); rỗng thì trả rỗng. */
export function formatFingerprint(value?: string | null): string {
  const hex = (value ?? "").replace(/\s+/g, "").toUpperCase();
  return hex.replace(/(.{4})(?=.)/g, "$1 ");
}
