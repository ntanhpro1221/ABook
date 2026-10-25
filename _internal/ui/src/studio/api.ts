import type { Capabilities } from "@/shared/capabilities";
import type { CoverImage } from "@/shared/cover";
import type { VolumeProposal } from "@/studio/volumes";
import type { BookTemplate } from "@/studio/bookTemplates";
import { LISTEN_ONLY_EVENT, PEER_SILENT_EVENT, peerOf, throughPeer } from "@/shared/peerStudio";
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
  /** Phân tích bị ngắt giữa chừng (còn câu chờ, không tiến trình nào đang làm): chạy tiếp ra MỘT CUỐN KHÁC, lối sạch là
   *  "Làm lại phân tích từ đầu" (store.analysis_unfinished). */
  analysisInterrupted?: boolean;
  starting: boolean;
  startError: string;
  createdAt: number | null;
  updatedAt: number | null;
  lastError: string;
  /** Sách đã xong: số yêu cầu sửa của người nghe ghi sau lần chạy cuối - chờ nút "Áp dụng" (store.pending_changes). */
  pendingChanges?: number;
  /** `analyzer`: model đã phân tích cuốn này (book_settings.json), "" ở sách không ghi. */
  settings: { profile: string; profileLabel: string; narrator: string; analyzer?: string; /** Giọng kể đã chọn, chưa vào sách. */ narratorPending?: string };
  /** `completed`: chương nghe được, kể cả `redo` - chương chờ thu lại theo sửa của người nghe (bản cũ còn nghe được). */
  chapters: { total: number; completed: number; redo?: number; missingAudio?: number; failed: number; working: number };
  segments: { total: number; analyzed: number; pending?: number; recorded: number; finished: number; failed: number };
  progress: { overall: number; analysis: number; synthesis: number };
  audioSeconds: number;
  /** `phase` "speaker": lượt "Xác định người nói từng câu" sau khi phân tích xong cả truyện (speaker_pass.py). */
  eta: { phase: Phase | "speaker"; seconds: number } | null;
  /** Lượt "Xác định người nói từng câu" (chương xong / tổng, đang chạy lượt này không); null ở sách không có lượt ấy. */
  speakerPass?: { done: number; total: number; active: boolean } | null;
  position: Position | null;
  /** Đang xếp hàng chờ cuốn khác chạy xong (thứ tự trong hàng), hoặc null. */
  queuePosition?: number | null;
  /** Đang tạm dừng mà tiến trình vẫn sống (power_source): máy tính đang chạy pin, hay người dùng bấm "Tạm dừng". */
  paused?: "battery" | "listener" | null;
  /** Lượt chạy này tạm dừng được: bắt đầu bằng bản app có tính năng ấy (lượt cũ chạy mã cũ tới hết). */
  canPause?: boolean;
  /** Nhật ký phụ của lượt chạy không ghi được (antivirus giữ file, đĩa đầy) và đã bỏ `lines` dòng: sách vẫn chạy bình thường. */
  logLost?: { lines: number; lastError: string } | null;
  /** Đã bấm "Dừng": sách còn chạy tới chỗ dừng sạch kế (30 giây tới vài phút), chưa dừng hẳn - lúc ấy không tạm dừng hay làm tiếp được. */
  stopping?: boolean;
  /** Lượt chạy gần nhất chết vì sự cố (không phải bạn bấm Dừng): nguyên nhân do supervisor ghi, null khi không có. */
  runEnd?: { state: "failed" | "lost"; detail: string; exitCode: number | null } | null;
  /** Cuốn xếp hàng mà cuốn đang giữ máy lại đang tạm dừng: hàng đứng yên cho tới khi người dùng làm tiếp hay dừng cuốn ấy. */
  queueWaitsOn?: { id: string; title: string; paused: "battery" | "listener" } | null;
  /** Phần nối tiếp của "Làm tiếp cuốn này" (continues.json): mã phần đầu + thứ tự phần; phần đầu và sách lẻ: null. */
  series?: { root: string; part: number } | null;
  /** Tập tạo cùng lúc với tập trước ("Tạo nhiều tập"): giọng và cách đọc tên gieo từ tập trước lúc tập này bắt đầu chạy. */
  seedPending?: boolean;
  broken?: string;
  /** Vì sao không mở được (server.project_problem): "busy" = chương trình khác đang giữ sổ làm việc (tự hết - Thử lại), "damaged" = hỏng thật,
   *  "unfinished" = tạo dở, "other". */
  brokenKind?: "busy" | "damaged" | "unfinished" | "other";
  /** Hỏng thật mà có bản sao cũ cạnh sổ làm việc: khôi phục được. */
  backup?: boolean;
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
  /** Chương đã xong mà người nghe vừa sửa: chờ thu lại những câu ấy - không phải lỗi, bản cũ vẫn nghe được (`playable`). */
  redo?: boolean;
  startedAt: number | null;
  completedAt: number | null;
  lastError: string;
}

export interface VoiceProfile {
  key: string;
  preset: string;
  /** Tên giọng để hiện (khoá `preset` gửi lại máy chủ). */
  label?: string;
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
  narrator: { voice: string; lines: number; seconds: number; profile: VoiceProfile | null; pendingVoice?: { preset: string; label?: string; gender: string } | null };
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
  /** Giây nghe ước của chương - cùng cách hộp Xuất sách nói ước (readaloud/prepare.listening_seconds). */
  audioSeconds: number;
  /** Số ký tự có chữ (không tính khoảng trắng) - hiện cạnh số chữ trong danh sách chương. */
  chars: number;
  bytes: number;
  /** Dòng ghi công người dịch ở đầu chương - trình tạo sách ĐỀ XUẤT bỏ chúng khỏi phần đọc, không bao giờ tự bỏ. */
  credits?: string[];
  /** Dòng xin ủng hộ / quảng cáo / nguồn ở cuối chương - đề xuất bỏ như `credits`, đồng ý một lần cho cả hai. */
  tailCredits?: string[];
  /** Một file chứa nhiều tiêu đề "Chương N" (cả truyện trong một file): trình tạo sách ĐỀ XUẤT tách, không tự tách. */
  split?: { chapters: number; titles: string[]; preamble: boolean; titleLine?: string } | null;
  /** Trang phụ của file sách (bìa, bản quyền, mục lục, mục rất ngắn - cùng luật với Nghe ngay): lý do. Chưa tích sẵn; người dùng tích lại được. */
  matter?: string;
  /** File dài hơn phần máy đọc để đếm: chữ, ký tự, thời lượng là ước tính (hiện "~"). */
  estimated?: boolean;
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
  totals: { chapters: number; words: number; audioSeconds: number; estimated?: boolean };
  /** Dự án đã làm từ chính những file này (so nội dung): `shared` file trùng, dự án ấy có `chapters` chương. */
  existing?: { id: string; title: string; statusLabel: string; shared: number; chapters: number }[];
}

/** "Làm tiếp cuốn này" (abook/continuation.py): trình tạo sách điền sẵn phần kế tiếp của một truyện dài, gieo từ
 * phần trước để nhân vật giữ giọng và tên giữ cách đọc. */
/** "Sửa thiết lập" của sách chưa bắt đầu (GET /api/books/<id>/redo - store.redo_plan): lựa chọn lúc tạo, điền lại vào trình
 *  tạo sách; tạo xong thì cuốn cũ vào Thùng rác. */
export interface RedoPlan {
  started: boolean;
  /** Phân tích dở dang: "làm lại" = phân tích lại từ đầu, bản dở vào Thùng rác. */
  analysisInterrupted?: boolean;
  paths: string[];
  title: string;
  profile: string;
  narrator: string;
  firstPerson: string;
  firstPersonChapters: Record<string, string>;
  /** Giới của “tôi” bạn đã nói lúc tạo ("" = chưa rõ), công tắc “người kể tự kể chuyện”, và giọng kể do máy chọn (không phải bạn bấm). */
  firstPersonGender?: "male" | "female" | "";
  tellerMode?: boolean;
  narratorAuto?: boolean;
  analysisModel: string;
  analysisModelMissing?: string;
  dropCreditLines: boolean;
  dropTailCreditLines?: boolean;
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
  /** Ở xa: tên máy tính phục vụ trang (remote_studio.forward) - trang chỉ nghe nói bật quyền sửa ở máy nào. */
  machine?: string;
  /** Đang mở Studio của máy tính đã ghép ngay trong app máy này (webui/peer_studio.py, `?peer=`): máy ấy là máy nào. */
  peer?: { id: string; name: string };
  /** App Windows đóng gói (webui/host.py): bản mới vỏ Tauri tìm thấy trên GitHub Releases, chờ người dùng bấm cài. */
  update?: { version: string; notes: string } | null;
  /** App đóng gói có vỏ Tauri: Cài đặt có nút "Kiểm tra bản mới" (lần tự kiểm lúc mở app im lặng khi mất mạng). */
  canCheckUpdate?: boolean;
  /** App Windows đóng gói: Studio (thư viện + model làm sách) tải thêm đã cài chưa. null: bản dev (runtime cạnh mã). */
  studio?: { installed: boolean; outdated?: boolean; damaged?: boolean; damagedSteps?: string[] } | null;
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
  /** File trạng thái hỏng đã được giữ lại lúc mở app (webui/notices.py): mỗi dòng báo một lần. */
  notices?: { id: string; text: string }[];
  libraryMoveRecovery?: import("@/desktop/LibraryMoveRecovery").LibraryMoveRecoveryState | null;
}

export interface Preferences {
  readAloudVoice: string;
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
  /** Máy tự chọn nhạc nền cho sách chỉ có chữ chưa chọn nhạc (mặc định bật; listen/playlistBed.ts AUTO_MUSIC_LABEL). */
  autoMusic?: boolean;
  /** Mặc định của trình tạo sách cho sách mới ("" = giọng máy đề xuất). */
  newBookNarrator?: string;
  newBookProfile?: string;
  /** Mẫu thiết lập có tên cho sách mới (studio/bookTemplates.ts), tối đa 20. */
  bookTemplates?: BookTemplate[];
  /** Phím tắt một chữ cái (M, [ ], ?, J/K/1-9, O/R) - mặc định bật (shared/letterShortcuts.ts). */
  letterShortcuts?: boolean;
  /** Tạm dừng rồi nghe tiếp thì lùi vài giây - mặc định bật, theo máy này (listen/sleep.ts rewindAfter). */
  autoRewind?: boolean;
  /** Tiếng chạm của giao diện - mặc định bật, tự im khi sách đang phát (shared/feedback.ts). */
  touchSounds?: boolean;
  /** Nền vùng chữ đọc theo (shared/readingSurface.ts). */
  readingSurface?: import("@/shared/readingSurface").ReadingSurface;
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

// "Mở Studio" của máy tính đã ghép (shared/peerStudio.ts): trang mang `?peer=<mã máy>` thì mọi lời gọi đi qua cầu nối của máy này.
const peer: string = typeof window === "undefined" ? "" : peerOf(window.location.search);

/** Mã máy đang mở Studio (trang `?peer=`), "" khi là trang của chính máy này. */
export function currentPeer(): string {
  return peer;
}

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

/** Lỗi không ngờ của máy chủ (500 mang nguyên văn lỗi Python, vd "TypeError: …"): câu người dùng hiểu thay cho nguyên văn; nguyên văn giữ ở
 *  `technicalOf` để nơi hiện lỗi thu vào "Chi tiết" (soát a64: hộp Thêm sách hiện "TypeError: …" trần). Lỗi máy chủ đã viết bằng lời thì giữ nguyên. */
export const UNEXPECTED_ERROR = "Máy gặp lỗi không ngờ khi làm việc này. Thử lại; nếu vẫn lỗi, mở Chi tiết để gửi cho người hỗ trợ.";
const PYTHON_ERROR = /^[A-Z][A-Za-z]*(?:Error|Exception|Interrupt|Iteration|Exit)(?::|$)/;

/** Lời báo cho người dùng từ một lỗi của máy chủ: lỗi không ngờ thì câu chung, còn lại nguyên lời máy chủ. */
export function serverMessage(status: number, raw: string): { message: string; technical?: string } {
  return status >= 500 && PYTHON_ERROR.test(raw.trim()) ? { message: UNEXPECTED_ERROR, technical: raw.trim() } : { message: raw };
}

/** Nguyên văn kỹ thuật của một lỗi không ngờ (cho "Chi tiết"); "" với lỗi thường. */
export function technicalOf(error: unknown): string {
  return error instanceof ApiError && typeof error.detail.technical === "string" ? error.detail.technical : "";
}

/** Bản sửa máy chủ mời dùng khi từ chối một cách đọc ("Hên-kơ" -> "Hên-cơ"); "" khi không có. */
export function suggestionOf(error: unknown): string {
  const value = error instanceof ApiError ? error.detail.suggestion : undefined;
  return typeof value === "string" ? value : "";
}

/** `signal`: người gọi bỏ lượt này (fetch bị huỷ, kết nối đóng - máy chủ thấy và thôi làm, vd lượt đọc của giọng trên máy, uxfix70); đường truyền native bỏ qua. */
export type ApiInit = { method?: string; body?: unknown; signal?: AbortSignal; keepalive?: boolean };

/** Đường truyền thay cho `fetch` tới server cục bộ: điện thoại không có server, các lệnh sửa sách ("áp ngay") đi thẳng vào
 *  lõi native (android/localStudio.ts, EbookLibrary.studio) với cùng đường dẫn, cùng JSON như máy chủ máy tính. Máy tính không đặt. */
export type ApiTransport = (path: string, init?: ApiInit) => Promise<unknown>;
let transport: ApiTransport | null = null;

export function setApiTransport(next: ApiTransport | null): void {
  transport = next;
}

/** Đang chạy trong app điện thoại (có đường truyền vào lõi native, không có máy chủ): các đường chỉ máy chủ có (`/api/app`...) không có để hỏi. */
export function hasLocalTransport(): boolean {
  return transport !== null;
}

function send(path: string, init?: ApiInit): Promise<Response> {
  return fetch(throughPeer(path, peer), {
    method: init?.method ?? "GET",
    headers: {
      "X-Ebook-Token": token,
      ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    signal: init?.signal,
    keepalive: init?.keepalive,
  });
}

export async function api<T>(path: string, init?: ApiInit): Promise<T> {
  if (transport) return (await transport(path, init)) as T;
  return settle<T>(await send(path, init));
}

/** Trang này nhận được lời đáp phát luồng từ máy chủ cục bộ (clip đang đọc, listen/liveClip.ts)? Không khi có đường truyền native (điện thoại) hay đang mở Studio của máy khác (cầu nối gom cả lời đáp). */
export function canStream(): boolean {
  return transport === null && !peer;
}

/** Như [api], nhưng lời đáp có `Content-Type` bắt đầu bằng `streamType` thì giao cho `onStream` (đọc dần) thay vì đọc hết thành JSON; các lời đáp khác (JSON, lỗi) y như `api`. Chỉ gọi khi [canStream]. */
export async function apiOrStream<T, S>(path: string, init: ApiInit, streamType: string, onStream: (response: Response) => Promise<S>): Promise<T | S> {
  const response = await send(path, init);
  if (response.ok && (response.headers.get("Content-Type") ?? "").startsWith(streamType)) return onStream(response);
  return settle<T>(response);
}

async function settle<T>(response: Response): Promise<T> {
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    // Máy kia tắt / mất mạng giữa chừng: thanh "Studio của <máy>" báo và tự nối lại (desktop/PeerBar.tsx).
    if (peer && data?.unreachable) window.dispatchEvent(new CustomEvent(PEER_SILENT_EVENT, { detail: String(data.error ?? "") }));
    if (response.status === 403 && data?.listenOnly === true) window.dispatchEvent(new Event(LISTEN_ONLY_EVENT));
    const { message, technical } = serverMessage(response.status, String((data && data.error) || `Lỗi ${response.status}`));
    throw new ApiError(response.status, message, { ...(data && typeof data === "object" ? data : {}), ...(technical ? { technical } : {}) });
  }
  return data as T;
}

export function mediaUrl(path: string): string {
  const routed = throughPeer(path, peer);
  return token ? `${routed}${routed.includes("?") ? "&" : "?"}t=${encodeURIComponent(token)}` : routed;
}

export const urls = {
  chapterAudio: (bookId: string, chapterId: number) => mediaUrl(`/media/books/${bookId}/chapters/${chapterId}`),
  sample: (bookId: string, segmentId: number) => mediaUrl(`/media/books/${bookId}/samples/${segmentId}`),
  /** Bản "Nghe thử" một cách đọc tên: máy chủ trả sẵn đường dẫn (có mã bản nghe thử trong đó). */
  readingPreview: (path: string) => mediaUrl(path),
  voice: (name: string) => mediaUrl(`/media/voices/${encodeURIComponent(name)}`),
};
