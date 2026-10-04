import type { Capabilities } from "@/shared/capabilities";
import type { CoverImage } from "@/shared/cover";
import type { VolumeProposal } from "@/studio/volumes";
import type { BookTemplate } from "@/studio/bookTemplates";
// Hợp đồng với server Python (abook/webui/server.py). Mọi chữ hiển thị đã được server dịch sẵn
// sang tiếng Việt (humanize.py); ở đây chỉ định kiểu và gọi.

export type Phase = "idle" | "analysis" | "casting" | "synthesis" | "done" | "stopped" | "error";

export interface Position {
  chapterId: number;
  seconds: number;
  duration: number;
  at: number;
}

export interface BookSummary {
  id: string;
  path: string;
  title: string;
  status: string;
  stage: string;
  phase: Phase;
  statusLabel: string;
  running: boolean;
  interrupted: boolean;
  starting: boolean;
  startError: string;
  createdAt: number | null;
  updatedAt: number | null;
  lastError: string;
  /** Sách đã xong: số yêu cầu sửa của người nghe ghi sau lần chạy cuối - chờ nút "Áp dụng" (store.pending_changes). */
  pendingChanges?: number;
  /** `analyzer`: model đã phân tích cuốn này (book_settings.json), "" ở sách không ghi. */
  settings: { profile: string; profileLabel: string; narrator: string; analyzer?: string };
  chapters: { total: number; completed: number; missingAudio?: number; failed: number; working: number };
  segments: { total: number; analyzed: number; recorded: number; finished: number; failed: number };
  progress: { overall: number; analysis: number; synthesis: number };
  audioSeconds: number;
  eta: { phase: Phase; seconds: number } | null;
  position: Position | null;
  /** Đang xếp hàng chờ cuốn khác chạy xong (thứ tự trong hàng), hoặc null. */
  queuePosition?: number | null;
  /** Đang tạm dừng mà tiến trình vẫn sống (power_source): máy tính đang chạy pin, hay người dùng bấm "Tạm dừng". */
  paused?: "battery" | "listener" | null;
  /** Lượt chạy này tạm dừng được: bắt đầu bằng bản app có tính năng ấy (lượt cũ chạy mã cũ tới hết). */
  canPause?: boolean;
  /** Phần nối tiếp của "Làm tiếp cuốn này" (continues.json): mã phần đầu + thứ tự phần; phần đầu và sách lẻ: null. */
  series?: { root: string; part: number } | null;
  /** Tập tạo cùng lúc với tập trước ("Tạo nhiều tập"): giọng và cách đọc tên gieo từ tập trước lúc tập này bắt đầu chạy. */
  seedPending?: boolean;
  broken?: string;
  /** Ảnh bìa thật (webui/covers.py), hoặc null khi dùng bìa vẽ từ tên. */
  cover?: CoverImage | null;
  /** Phân vai đã khoá: dàn nhân vật, giọng, cách đọc tên đã có để duyệt. */
  castLocked?: boolean;
  /** "Duyệt trước khi thu" (webui/precast.py). */
  precast?: PrecastFlags;
}

export interface PrecastFlags {
  /** Phân tích xong và phân vai đã khoá. */
  ready: boolean;
  /** "Chờ tôi duyệt trước khi thu" của cuốn này. */
  wait: boolean;
  /** Lúc Studio báo mốc phân tích xong (một lần mỗi cuốn), hoặc null. */
  announcedAt: number | null;
  /** Studio đang giữ cuốn này lại chờ duyệt (tạm dừng, chờ nút "Thu âm"). */
  held: boolean;
}

export interface PrecastView extends PrecastFlags {
  chapters: number;
  recordedChapters: number;
  /** Chương xa nhất đã thu xong: sửa ở chương sau nó không phải thu lại. */
  recordedThrough: { id: number; title: string } | null;
  /** Vài chương sắp thu, theo thứ tự đọc. */
  upcoming: { id: number; title: string }[];
}

export interface Chapter {
  id: number;
  index: number;
  title: string;
  displayTitle: string;
  subtitle: string;
  fullTitle: string;
  status: string;
  statusLabel: string;
  segments: {
    total: number;
    analyzed: number;
    recorded: number;
    finished: number;
    failed: number;
    warnings: number;
  };
  seconds: number;
  playable: boolean;
  startedAt: number | null;
  completedAt: number | null;
  lastError: string;
}

export interface VoiceProfile {
  key: string;
  preset: string;
  tone: string;
}

export interface CastMember {
  name: string;
  displayName: string;
  gender: string;
  age: string;
  lines: number;
  seconds: number;
  voice: VoiceProfile | null;
  sampleId: number | null;
  firstChapter: string;
}

export interface Cast {
  narrator: { voice: string; lines: number; seconds: number; profile: VoiceProfile | null };
  characters: CastMember[];
  extras: CastMember[];
}

export interface ActivityItem {
  id: string;
  at: number;
  level: "info" | "success" | "warning" | "error";
  kind?: string;
  code?: string;
  text: string;
}

export interface ScriptSegment {
  id: number;
  paragraph: number;
  text: string;
  kind: "narration" | "dialogue" | "thought" | string;
  speaker: string;
  start: number | null;
  end: number | null;
  status: string;
}

export interface Script {
  chapterId: number;
  title: string;
  timed: boolean;
  duration: number;
  segments: ScriptSegment[];
}

export interface Voice {
  name: string;
  gender: string;
  region: string;
  style: string;
  recommended: boolean;
  preview: boolean;
}

export interface ScannedFile {
  path: string;
  name: string;
  title: string;
  firstLine: string;
  words: number;
  /** Số ký tự có chữ (không tính khoảng trắng) - hiện cạnh số chữ trong danh sách chương. */
  chars: number;
  bytes: number;
  /** Dòng ghi công người dịch ở đầu chương - trình tạo sách ĐỀ XUẤT bỏ chúng khỏi phần đọc, không bao giờ tự bỏ. */
  credits?: string[];
  /** Một file chứa nhiều tiêu đề "Chương N" (cả truyện trong một file): trình tạo sách ĐỀ XUẤT tách, không tự tách. */
  split?: { chapters: number; titles: string[]; preamble: boolean } | null;
}

/** Truyện kể ngôi thứ nhất? (abook/first_person.py) - cho câu hỏi "'Tôi' là ai?" ở bước chọn giọng. */
export interface FirstPersonHint {
  /** Tỉ lệ đoạn lời kể có "tôi/tớ/mình" trong ~20 chương đầu. */
  rate: number;
  firstPerson: boolean;
  /** Số chương (trong ~20 chương đầu, đủ dài) có >= 20% lời kể xưng "tôi" / số chương được đếm - cách máy quyết định
   *  từ 29-09: truyện chen chương ngoại truyện ngôi ba vẫn được nhận ra. Thiếu ở máy chủ cũ. */
  chaptersWithI?: number;
  chaptersSampled?: number;
  /** Tên viết hoa hay gặp nhất - gợi ý để chọn, không phải đáp án. */
  suggestions: string[];
  /** Chương đổi góc kể: tiêu đề là tên một nhân vật và chương kể bằng "tôi" (số chương theo thứ tự trong sách, từ 1). */
  chapters?: { chapter: number; title: string; name: string }[];
}

export interface ScanResult {
  files: ScannedFile[];
  skipped: string[];
  /** Đường dẫn không tồn tại. */
  missing: string[];
  /** Thư mục đã chọn không có TXT ngay bên trong - đây là các thư mục con có. */
  subfolders: string[];
  /** File EPUB / DOCX / PDF không tách được thành chương, kèm lý do (abook/importers.py). */
  errors?: string[];
  /** Không phải lỗi nhưng nên biết (thư mục có cả TXT lẫn EPUB: chỉ lấy TXT). */
  notes?: string[];
  /** Nhiều tập trong một nguồn (webui/volumes.py): máy ĐỀ XUẤT chia, null khi chỉ một tập. */
  volumes?: VolumeProposal | null;
  suggestedTitle: string;
  totals: { chapters: number; words: number; audioSeconds: number };
  /** Dự án đã làm từ chính những file này (so nội dung): `shared` file trùng, dự án ấy có `chapters` chương. */
  existing?: { id: string; title: string; statusLabel: string; shared: number; chapters: number }[];
}

/** "Làm tiếp cuốn này" (abook/continuation.py): trình tạo sách điền sẵn phần kế tiếp của một truyện dài, gieo từ
 * phần trước để nhân vật giữ giọng và tên giữ cách đọc. */
/** "Sửa thiết lập" của sách chưa bắt đầu (GET /api/books/<id>/redo - store.redo_plan): lựa chọn lúc tạo, điền lại vào trình
 *  tạo sách; tạo xong thì cuốn cũ vào Thùng rác. */
export interface RedoPlan {
  started: boolean;
  paths: string[];
  title: string;
  profile: string;
  narrator: string;
  firstPerson: string;
  firstPersonChapters: Record<string, string>;
  analysisModel: string;
  analysisModelMissing?: string;
  dropCreditLines: boolean;
  /** Cuốn này là phần nối tiếp: id phần trước, để cuốn làm lại vẫn mang dàn nhân vật từ đó. */
  seedFrom: string;
}

export interface ContinuationPlan {
  /** Phần mới nhất của cuốn - phần gieo từ (bấm ở phần cũ khi đã có phần sau thì là phần sau). */
  sourceId: string;
  sourceTitle: string;
  /** Bấm "Làm tiếp" ở một phần CŨ: tên phần ấy (phần mới vẫn nối sau phần mới nhất - `sourceTitle`). */
  clickedTitle?: string;
  latestTitle?: string;
  /** Model đọc hiểu của phần trước khi khác mặc định ("" = mặc định); model ấy không còn trong Ollama thì tên ở `analysisModelMissing`. */
  analysisModel?: string;
  analysisModelMissing?: string;
  /** Số của phần sắp tạo (phần trước + 1). */
  part: number;
  title: string;
  /** Các chương kế tiếp trong thư mục truyện, sau chương cuối đã làm - rỗng khi chưa có chương mới. */
  paths: string[];
  /** Thư mục truyện và file chương cuối đã làm (máy chủ cũ không có). */
  folder?: string;
  lastChapter?: string;
  profile: string;
  narrator: string;
  firstPerson: string;
  /** Phần trước đã phân tích xong; chưa thì sổ nhân vật mang theo chưa đủ. */
  analyzed: boolean;
  carries: {
    voices: number;
    pronunciations: number;
    listenerReadings: number;
    pins: number;
    aliases?: number;
    /** Tên hiển thị người nghe đã đặt cho nhân vật ("Đổi tên"). */
    names?: number;
    /** Quy ước 『』 của cuốn: người nói mọi câu 『』 ("NARRATOR" = người kể), rỗng khi chưa có. */
    bracket?: string;
  };
}

export interface AppInfo {
  version: string;
  readOnly: boolean;
  dialogs: boolean;
  /** Đang điều khiển ABook của máy khác qua Studio từ xa (webui/remote_studio.py): ẩn những gì chỉ có nghĩa trên chính
   * máy ấy - mở thư mục, đổi cài đặt của máy, ghép điện thoại, thanh điện thoại đang phát. */
  remote?: boolean;
  /** Ở xa và CHỈ được nghe (thiết bị đã ghép nhưng máy tính chưa cho điều khiển sản xuất): ẩn Studio. */
  listenOnly?: boolean;
  /** App Windows đóng gói (webui/host.py): bản mới vỏ Tauri tìm thấy trên GitHub Releases, chờ người dùng bấm cài. */
  update?: { version: string; notes: string } | null;
  /** App Windows đóng gói: Studio (thư viện + model làm sách) tải thêm đã cài chưa. null: bản dev (runtime cạnh mã). */
  studio?: { installed: boolean; outdated?: boolean } | null;
  /** Máy này làm được gì (shared/capabilities.ts): `/api/app?book=<mã>` điền thêm `workshop` / `link` của cuốn ấy. */
  capabilities?: Capabilities;
  libraryRoot: string;
  theme: "system" | "light" | "dark";
  playbackRate: number;
  volume: number;
  sleepFadeSeconds: number;
  sleepExtendMinutes: number;
  safetyStopHours: number;
  sleepSchedule: { from: string; to: string; minutes: number } | null;
}

export interface Preferences {
  libraryRoot: string;
  theme: "system" | "light" | "dark";
  playbackRate: number;
  volume: number;
  sleepFadeSeconds: number;
  sleepExtendMinutes: number;
  safetyStopHours: number;
  sleepSchedule: { from: string; to: string; minutes: number } | null;
  /** Máy tính xách tay rút sạc: tạm dừng tạo sách (abook/power_source.py). */
  pauseOnBattery?: boolean;
  /** Mặc định của trình tạo sách cho sách mới ("" = giọng máy đề xuất). */
  newBookNarrator?: string;
  newBookProfile?: string;
  /** Mẫu thiết lập có tên cho sách mới (studio/bookTemplates.ts), tối đa 20. */
  bookTemplates?: BookTemplate[];
}

// Mã phiên do cửa sổ app gắn vào URL (?t=...). Giữ lại trong phiên để điều hướng nội bộ không làm mất nó.
const TOKEN_KEY = "abook-token";
const token: string = (() => {
  // Không có `window` khi chạy bài thử (vitest, môi trường node): không có mã phiên để đọc.
  const fromUrl = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("t");
  try {
    if (fromUrl) sessionStorage.setItem(TOKEN_KEY, fromUrl);
    return fromUrl ?? sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return fromUrl ?? "";
  }
})();

export class ApiError extends Error {
  status: number;
  /** Các trường máy chủ gửi kèm lời báo lỗi - `suggestion`: cách đọc bị từ chối, viết lại đúng chính tả. */
  detail: Record<string, unknown>;
  constructor(status: number, message: string, detail: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/** Bản sửa máy chủ mời dùng khi từ chối một cách đọc ("Hên-kơ" -> "Hên-cơ"); "" khi không có. */
export function suggestionOf(error: unknown): string {
  const value = error instanceof ApiError ? error.detail.suggestion : undefined;
  return typeof value === "string" ? value : "";
}

export type ApiInit = { method?: string; body?: unknown };

/** Đường truyền thay cho `fetch` tới server cục bộ: điện thoại không có server, các lệnh sửa sách ("áp ngay") đi thẳng vào
 *  lõi native (android/localStudio.ts, EbookLibrary.studio) với cùng đường dẫn, cùng JSON như máy chủ máy tính. Máy tính không đặt. */
export type ApiTransport = (path: string, init?: ApiInit) => Promise<unknown>;
let transport: ApiTransport | null = null;

export function setApiTransport(next: ApiTransport | null): void {
  transport = next;
}

export async function api<T>(path: string, init?: ApiInit): Promise<T> {
  if (transport) return (await transport(path, init)) as T;
  const response = await fetch(path, {
    method: init?.method ?? "GET",
    headers: {
      "X-Ebook-Token": token,
      ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new ApiError(response.status, (data && data.error) || `Lỗi ${response.status}`, data && typeof data === "object" ? data : {});
  }
  return data as T;
}

export function mediaUrl(path: string): string {
  return token ? `${path}${path.includes("?") ? "&" : "?"}t=${encodeURIComponent(token)}` : path;
}

export const urls = {
  chapterAudio: (bookId: string, chapterId: number) => mediaUrl(`/media/books/${bookId}/chapters/${chapterId}`),
  sample: (bookId: string, segmentId: number) => mediaUrl(`/media/books/${bookId}/samples/${segmentId}`),
  /** Bản "Nghe thử" một cách đọc tên: máy chủ trả sẵn đường dẫn (có mã bản nghe thử trong đó). */
  readingPreview: (path: string) => mediaUrl(path),
  voice: (name: string) => mediaUrl(`/media/voices/${encodeURIComponent(name)}`),
};
