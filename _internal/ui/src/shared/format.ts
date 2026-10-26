// Định dạng kiểu Việt: "1.234" cho số, "9 giờ 12 phút" cho thời lượng dài, "13:05" cho đồng hồ phát.

const numberFormat = new Intl.NumberFormat("vi-VN");

export function formatNumber(value: number): string {
  return numberFormat.format(Math.round(value));
}

/** Cỡ file: "850 MB", "3,2 GB" (một chữ số thập phân từ 1 GB trở lên). Dưới 10 MB cũng một chữ số thập phân ("0,5 MB", không làm tròn thành "0 MB" hay "1 MB");
 *  dưới 0,1 MB thì ghi KB. */
export function formatSize(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(bytes / 1024 ** 3)} GB`;
  const megabytes = bytes / 1024 ** 2;
  if (megabytes < 0.1) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (megabytes < 10) return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(megabytes)} MB`;
  return `${formatNumber(megabytes)} MB`;
}

/** Tên file trong một đường dẫn (dấu ngăn \ hay /): thông báo chỉ nói tên, đường đầy đủ để ở gợi ý khi rê chuột. */
export function fileName(path: string): string {
  return path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path;
}

/** Câu báo kết thúc bằng dấu chấm: lời lỗi của máy chủ khi thì có chấm, khi thì không (và có khi kết thúc bằng dấu nháy) - nối thêm câu sau cho đúng. */
export function endSentence(text: string): string {
  const clean = text.trim();
  return clean && !/[.!?…]$/.test(clean) ? `${clean}.` : clean;
}

/** Phân số 0..1 (NaN - tổng 0, chưa biết - là 0). */
export function clampFraction(fraction: number): number {
  return Number.isFinite(fraction) ? Math.max(0, Math.min(1, fraction)) : fraction === Infinity ? 1 : 0;
}

/** Số phần trăm nguyên của thanh tiến độ (aria-valuenow): làm tròn XUỐNG như chữ `formatPercent` - chưa xong thì không bao giờ 100. */
export function percentOf(fraction: number): number {
  return Math.floor(clampFraction(fraction) * 100);
}

export function formatPercent(fraction: number): string {
  const value = clampFraction(fraction) * 100;
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

/** Rút một tên dài giữ CẢ đầu lẫn đuôi - "NGDtuanh-Lecoo" thành "NGDtu…Lecoo": tên máy thường chung đầu ("NGDtuanh-…") nên chỗ phân biệt máy nằm ở đuôi. */
export function middleEllipsis(text: string, max = 14): string {
  if (text.length <= max) return text;
  const tail = Math.floor((max - 1) / 2);
  const head = max - 1 - tail;
  return `${text.slice(0, head).trimEnd()}…${text.slice(text.length - tail).trimStart()}`;
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

/** Như `formatLength` nhưng làm tròn LÊN tới phút: thời gian còn lại nói cạnh đồng hồ đếm ngược của thanh phát ("-2:09" là "3 phút",
 *  không phải "2 phút" - soát a26 L10). */
export function formatLengthUp(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0 phút";
  return formatLength(Math.ceil(seconds / 60) * 60);
}

/** Từ mức này của bước đang làm thì "còn dưới 2 phút" mới là "sắp xong" (soát UX a8: sách mới 21% mà đã ghi "sắp xong"). */
const NEAR_DONE = 0.85;

/** `fraction`: bước đang làm đã được bao nhiêu (0-1). Còn ít giây mà bước chưa tới mức gần xong thì chỉ nói còn dưới 2 phút -
 *  "sắp xong" là lời hứa về cái đích, không phải về con số giây. Không đưa `fraction` thì giữ nghĩa cũ. */
export function formatEta(seconds: number, fraction?: number): string {
  if (seconds < 90) return fraction === undefined || fraction >= NEAR_DONE ? "sắp xong" : "còn dưới 2 phút";
  return `còn khoảng ${formatLength(seconds)}`;
}

/** Thời gian còn lại của một cuốn đang chạy, theo bước máy đang ước (phân tích / thu âm), hoặc null khi chưa có tốc độ để ước.
 *  Nói rõ là của bước nào: cạnh "N% tổng", "sắp xong" trần đọc thành cả cuốn sắp xong trong khi còn các bước sau (soát UX a18). */
export function etaOf(book: {
  eta: { phase: string; seconds: number } | null;
  progress: { analysis: number; synthesis: number };
  speakerPass?: { done: number; total: number } | null;
}, short = false): string | null {
  if (!book.eta) return null;
  // Gọn (cột hẹp của danh sách dự án, soát 24-10 - "pha thu âm còn khoảng 3 giờ 2…" bị cắt): bỏ "pha" và "khoảng", vẫn nói của bước nào.
  const say = (step: string, left: string) => (short ? `${step} ${left.replace(/^còn khoảng /, "còn ")}` : `pha ${step} ${left}`);
  if (book.eta.phase === "speaker") {
    const pass = book.speakerPass;
    return say(short ? "dò người nói" : "xác định người nói", formatEta(book.eta.seconds, pass && pass.total ? pass.done / pass.total : undefined));
  }
  const synthesis = book.eta.phase === "synthesis";
  const left = formatEta(book.eta.seconds, synthesis ? book.progress.synthesis : book.progress.analysis);
  return say(synthesis ? "thu âm" : "phân tích", left);
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

/** Dòng ghi công của một bài nhạc nền: chuỗi `attribution` của danh mục khi bài có tác giả; không có tác giả (bài cc0, nhạc người dùng nhập)
 *  thì chỉ tên bài - không bao giờ in "by" rỗng. Bản Python: `music_export.credit_line`. */
export function musicCreditText(track: { title?: string | null; creator?: string | null; attribution?: string | null }): string {
  const creator = (track.creator ?? "").trim();
  const attribution = (track.attribution ?? "").trim();
  if (attribution && creator) return attribution;
  return [(track.title ?? "").trim(), creator].filter(Boolean).join(" - ");
}

/** Nhạc nền này có giấy phép đòi ghi công (khác cc0; nhạc người dùng nhập không có giấy phép) - nhạc ấy trong sách đã được cắt vòng, trộn dưới giọng đọc
 *  và chỉnh âm lượng, nên phải kèm [MUSIC_MODIFIED_NOTE] (CC BY đòi nói rõ đã chỉnh sửa). */
export function musicNeedsModifiedNote(license?: string | null): boolean {
  const code = (license ?? "").trim().toLowerCase();
  return code !== "" && code !== "cc0";
}

/** Lời "đã chỉnh sửa" đi kèm ghi công nhạc CC BY; cùng câu với bản xuất MP3 / M4B (`music_export.MODIFIED_NOTE`). */
export const MUSIC_MODIFIED_NOTE = "Đã chỉnh sửa: các bài nhạc được cắt vòng, trộn nhỏ dưới giọng đọc và chỉnh âm lượng cho vừa sách.";

/** Vân tay chứng chỉ để người dùng nhìn và đối chiếu: nhóm 4 ký tự, hoa - "AB12 CD34 ..." như `tls.display` / `Pin.display`.
 *  Nhận cả dạng hex lưu sẵn lẫn dạng đã nhóm (chạy lại không đổi); rỗng thì trả rỗng. */
export function formatFingerprint(value?: string | null): string {
  const hex = (value ?? "").replace(/\s+/g, "").toUpperCase();
  return hex.replace(/(.{4})(?=.)/g, "$1 ");
}

/** Ghép các phần của một dòng phụ bằng " · " (bỏ phần rỗng): MỘT chỗ làm dấu chấm giữa - nhờ vậy khoảng trắng hai bên dấu luôn đều
 *  nhau, thay vì mỗi nơi tự gắn "· " vào đầu từng phần trong một hàng có `gap`. */
export function joinParts(parts: ReadonlyArray<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" · ");
}
