import { registerPlugin, type PluginListenerHandle } from "@capacitor/core";
import type { Bookmark, BookPart, ListeningRecord, ListeningState, NightSession, SeriesLink } from "@/listen/model";
import type { PreparePlan, PrepareStatus } from "@/listen/prepareAhead";
import type { MusicCredit } from "@/listen/musicBed";
import type { RemoteSleep, RemoteSleepCommand } from "@/listen/sleep";
import type { ReadAloudTimings, ReadAloudVoice } from "@/listen/readAloud";
import type { KeyCheck, OnlineProviderInfo } from "@/listen/VoiceSettings";
import type { Capabilities } from "@/shared/capabilities";
import type { EditsSyncState } from "@/shared/editsSync";
import type { AddedBook, ImportPreview } from "@/listen/textImport";
import type { BluetoothPermission } from "./bluetoothPermission";
import type { MusicExportState } from "@/desktop/listenExport";
import type { ImportResult } from "@/studio/musicLocal";
import type { VieneuChoiceId, VieneuStatus } from "@/listen/vieneuModule";
import type { VoiceSpeedChoice, VoiceSpeedStatus } from "@/listen/voiceSpeed";
import type { DiagnosticsReport } from "@/shared/diagnostics";

// Hai plugin native của app Android (mobile/android/app/src/main/java/vn/abook/player):
//  EbookPlayer  - lõi phát Media3: hàng đợi chương, hẹn giờ ngủ, lắc để nghe thêm, nhật ký đêm.
//  EbookLibrary - sách đã tải + đồng bộ với máy tính qua Wi-Fi.

export interface NativeSleep {
  mode: "off" | "minutes" | "chapter";
  counting?: boolean;
  remaining?: number;
  minutes?: number;
  stoppedAt?: number;
}

export interface NativeState {
  kind?: string;
  bookId: string;
  bookTitle: string;
  chapterId: number | null;
  chapterTitle: string;
  position: number;
  duration: number;
  playing: boolean;
  buffering: boolean;
  rate: number;
  sleep: NativeSleep;
  /** Lỗi phát gần nhất (Playback.onError): mất kết nối khi nghe thẳng, hay file hỏng. Rỗng khi ổn. */
  error?: string;
  /** Lõi chưa lưu được chỗ đang nghe (bộ nhớ đầy...): lời báo cho người nghe (Playback.saveNow); rỗng khi ổn. Sự kiện `kind: "saveFailed"` mang nó MỘT lần. */
  saveError?: string;
  /** Ghi công bài nhạc nền đang kêu (MusicBed.credit); null khi im lặng. */
  musicCredit?: MusicCredit | null;
  /** Bài nhạc nền của chương đang nghe không phát được (MusicBed.brokenHere): đoạn ấy im lặng. */
  musicBroken?: boolean;
  /** Lời báo "mất mạng" khi nhạc nền đang bị giữ lại vì mạng (MusicBed.offlineNotice); rỗng khi ổn. */
  musicOffline?: string;
  /** Nhạc nền đang đổi theo cảnh (MusicBed.sceneActive). */
  musicScene?: boolean;
}

// Nhật ký đêm của lõi native - cùng hình dạng với listen/model.ts (NightSession).
export type BedtimeSession = NightSession;

export interface EbookPlayerPlugin {
  updateMetadata(options: { bookId: string; title: string; narrator: string; chapters: { id: number; title: string }[];
    queue?: { id: number; title: string; file: string; duration: number; text?: string }[] }): Promise<NativeState>;
  load(options: {
    bookId: string;
    bookTitle: string;
    narrator: string;
    /** Chương chỉ-có-chữ: `file` rỗng, `text` là tên mục chữ (`texts/<mã>.txt`) - lõi tự đọc chương ấy bằng `readAloudVoice`. */
    chapters: { id: number; title: string; file: string; duration: number; text?: string }[];
    chapterId: number;
    seconds: number;
    rate: number;
    autoplay?: boolean;
    readAloudVoice?: string;
    readAloudRecord?: string;
  }): Promise<NativeState>;
  play(): Promise<NativeState>;
  pause(): Promise<NativeState>;
  /** Đóng sách: tạm dừng giọng và nhả bộ phát nhạc nền (MusicBed.release). */
  release(): Promise<NativeState>;
  toggle(): Promise<NativeState>;
  next(): Promise<NativeState>;
  previous(): Promise<NativeState>;
  seekTo(options: { seconds: number }): Promise<NativeState>;
  skip(options: { delta: number }): Promise<NativeState>;
  setRate(options: { rate: number }): Promise<NativeState>;
  /** `segment` + `word` (chương đọc to): native vào đúng mốc chữ ấy, kể cả đoạn chưa tạo tiếng - thắng `seconds`. */
  jumpTo(options: { chapterId: number; seconds: number; segment?: number; word?: number }): Promise<NativeState>;
  getState(): Promise<NativeState>;
  addBookmark(options: { note: string; index?: number; quote?: string; anchor?: import("@/listen/readingAnchor").ReadingAnchor }): Promise<Bookmark>;
  setSleep(options: { mode: "off" | "minutes" | "chapter"; minutes?: number }): Promise<NativeState>;
  extendSleep(options: { minutes?: number }): Promise<NativeState>;
  configure(options: {
    /** Giao diện sáng/tối/theo máy: native chỉ NHỚ (ListenPrefs) để giao diện lấy lại khi localStorage của WebView mất (settings.ts `syncSettings`). */
    theme?: "system" | "light" | "dark";
    sleepExtendMinutes?: number;
    sleepFadeSeconds?: number;
    shakeToExtend?: boolean;
    shakeAction?: "extend" | "reset";
    shakeSensitivity?: "gentle" | "normal" | "firm";
    flipToPause?: boolean;
    headsetSkips?: boolean;
    /** Tự lùi khi nghe lại (AutoRewind.kt, cùng luật với máy tính). */
    autoRewind?: boolean;
    safetyStopHours?: number;
    schedule?: { from: string; to: string; minutes: number } | null;
    /** Dấu giờ (ms) lần đổi cuối trong Cài đặt; native nhớ cùng các tuỳ chọn trên (settings.ts `syncSettings`). */
    settingsStamp?: number;
    /** Máy tự chọn nhạc nền cho sách chỉ có chữ chưa chọn nhạc (Cài đặt > Nhạc nền). */
    autoMusic?: boolean;
    /** Giọng đọc của "Nghe ngay" (mã giọng của ReadAloud.voices); "" = giọng mặc định của máy. */
    readAloudVoice?: string;
    /** Cuốn của `readAloudVoice`: lõi nhớ giọng ấy cho cuốn ấy (ReadAloud.chooseFor); không có thì cuốn đang nạp. */
    readAloudBook?: string;
    /** Hồ sơ nghe của `readAloudVoice`: giọng riêng nhớ theo (cuốn, hồ sơ), hồ sơ khác của cùng cuốn không kế thừa. */
    readAloudRecord?: string;
    /** Giọng mặc định (Cài đặt) cho cuốn chưa chọn giọng riêng; "" = chưa đặt. Không đổi giọng của chương đang đọc. */
    readAloudDefault?: string;
    /** Nhà cung cấp giọng trực tuyến người nghe đã đồng ý gửi chữ tới (listen/onlineConsent.ts): lõi tự sang chương chữ chỉ với những giọng ấy. */
    readAloudOnlineOk?: string[];
  }): Promise<NativeState>;
  /** Quyền hiện thông báo (Android 13+): "off" = chưa cho, khay thông báo / màn khoá không có nút tạm dừng, tua. `load` KHÔNG chờ quyền này. */
  notificationAccess(): Promise<{ state: "granted" | "off" }>;
  /** Hiện hộp xin quyền của hệ thống (chỉ gọi sau khi đã nói vì sao - android/notifications.ts). */
  requestNotificationAccess(): Promise<{ state: "granted" | "off" }>;
  /** Mở trang thông báo của ABook trong Cài đặt Android. */
  openNotificationSettings(): Promise<void>;
  /** Tuỳ chọn nghe native đã nhớ (ListenPrefs.stored; kèm `settingsStamp`): lúc mở app giao diện lấy làm chuẩn khi bản localStorage cũ hơn. */
  listenPrefs(): Promise<{ prefs: Record<string, unknown> }>;
  lastNight(): Promise<{ session: BedtimeSession | null }>;
  dismissLastNight(): Promise<void>;
  addListener(event: "state", handler: (state: NativeState) => void): Promise<PluginListenerHandle>;
}

export interface RemoteBook {
  audioVersion?: string;
  localAudioVersion?: string;
  /** Dấu phần mô tả (tên, tác giả, người đọc, liên kết bộ, tên chương - sync.manifest `metaVersion`) trên máy tính và trong bản đã tải. */
  metaVersion?: string;
  localMetaVersion?: string;
  id: string;
  title: string;
  narrator: string;
  duration: number;
  chaptersTotal: number;
  chaptersAvailable: number;
  complete: boolean;
  /** Máy kia đang làm cuốn này thật (Studio đang chạy) - "· đang làm" chỉ cho những cuốn này (soát a68 lỗi 13). */
  producing?: boolean;
  /** Cỡ audio khi tải về (byte) - hiện trước khi bấm Tải (soát a68 lỗi 7). */
  bytes?: number;
  updatedAt: number | null;
  downloaded: boolean;
  localChapters: number;
  /** Bìa trên máy tính (phiên bản) và bìa đã tải: khác nhau là có ảnh bìa mới để tải. */
  cover?: { color: string; version: number } | null;
  localCoverVersion: number;
  /** Dấu mốc chữ (sync.manifest `wordsVersion`) trên máy tính và trên máy này: khác nhau là có chữ sáng theo giọng đọc mới để tải. */
  wordsVersion?: string;
  localWordsVersion?: string;
  /** Sách của thiết bị ghép (Peers.kt): mã thiết bị ở đây và mã sách bên ấy - `id` là mã cục bộ. */
  source?: string;
  remoteId?: string;
}

/** Một thiết bị đã ghép ngoài máy tính chính (điện thoại khác, máy tính khác) và thư viện của nó. */
/** Trình phát trên máy khác (mạng trạm bước 4, RemotePlayers.kt): máy tính chính (`device` "main") hay thiết bị ghép. */
export interface RemotePlayer {
  device: string;
  name: string;
  /** Máy gì - chỉ để chọn biểu tượng. */
  kind: "computer" | "phone" | "speaker" | "tv" | "media";
  /** "cast": loa / TV trong mạng nhà - máy tính chính thấy (mã "cast:…", máy tính phục vụ audio) hay điện thoại tự thấy
   *  (mã "dlna:…", điện thoại phục vụ sách đã có trên nó); một thiết bị chỉ một mục (RemotePlayers.kt). */
  via?: "cast";
  /** Loa / TV `via` cast: "gcast" là Google Cast (Chromecast, Google TV, loa Nest) - máy tính chính hay điện thoại tự tìm thấy. */
  protocol?: "dlna" | "gcast";
  state: {
    bookId?: string;
    bookTitle?: string;
    chapterId?: number | null;
    chapterTitle?: string;
    position?: number;
    duration?: number;
    playing?: boolean;
    buffering?: boolean;
    rate?: number;
  } | null;
  /** Giây kể từ lần máy kia cập nhật trạng thái (máy tính báo lên host của nó; điện thoại đọc thẳng = 0). */
  age: number;
  acks: { id: string; ok: boolean; message: string }[];
  /** Cuốn ấy ở điện thoại này: mã máy tính chính (nghe thẳng/đã tải) hoặc `p<key>_<mã>` của thiết bị ghép. */
  localBookId: string;
  known: boolean;
  /** Hẹn giờ tắt của loa / TV (`via` cast): máy giữ phiên phát đếm - máy tính chính hay chính điện thoại (DlnaPlayers.kt). */
  sleep?: RemoteSleep | null;
}

export type RemotePlayerCommand =
  | { action: "play" | "pause" | "toggle" | "next" | "previous" | "stop" }
  | { action: "skip" | "seek"; seconds: number }
  | { action: "load"; bookId: string; chapterId: number; seconds: number }
  | RemoteSleepCommand;

export interface PeerLibrary {
  connectedVia?: string;
  key: string;
  name: string;
  host: string;
  /** Vân tay chứng chỉ TLS thiết bị đã ghi lúc ghép (hex), "" nếu chưa có. */
  fingerprint?: string;
  books: RemoteBook[];
  /** Thiết bị không trả lời (tắt, khác mạng, chưa bật "Cho máy khác nghe"). */
  error?: string;
  /** Chứng chỉ của thiết bị đã khác lúc ghép: `error` là câu bảo ghép lại, đọc thẳng được. */
  pinChanged?: boolean;
  /** Thiết bị trả 401: nó đã thôi ghép điện thoại này. */
  unpaired?: boolean;
  /** Chữ gốc của lỗi mạng cho mục "Chi tiết". */
  technical?: string;
}

export interface ManifestChapter {
  sha256?: string;
  id: number;
  index: number;
  title: string;
  subtitle: string;
  fullTitle: string;
  duration: number;
  available: boolean;
  file: string | null;
  size: number;
  script: string | null;
  /** File cả bộ (.abook phiên bản 3): số phần chứa chương. */
  part?: number;
  /** Chương chỉ có chữ (.abook phiên bản 5): `state` "text" và tên mục chữ `texts/<mã>.txt` (không `file`, không `script`). */
  state?: "text" | null;
  text?: string;
  /** Dòng người nghe bỏ khỏi phần đọc (lớp sửa `skip`, đã áp vào book.json - BookEdits.applyManifest). */
  skip?: string[];
  wordsVersion?: string;
}

/** Máy tính đã ghép có Studio: `key` "" là máy tính chính, còn lại là mã máy ghép thêm (Peers.kt). */
export interface StudioComputer {
  key: string;
  name: string;
  /** Máy tính chỉ cho điện thoại này nghe (`/api/app` của nó: công tắc "Điều khiển từ xa" hay quyền riêng của điện thoại tắt): Studio của máy ấy
   *  chỉ hiện trang "Chỉ nghe". Không hỏi được thì không có cờ (nút vẫn mở). */
  listenOnly?: boolean;
  /** Máy tính này GIỮ cuốn đã hỏi (`studioComputers({ book })`): "Mở Studio" ở trang sách đi thẳng tới máy ấy. */
  holdsBook?: boolean;
}

export interface LocalBook {
  wordsVersion?: string;
  format: string;
  id: string;
  title: string;
  /** Tác giả ghi trong file sách (book.json của sách chỉ-chữ). */
  author?: string;
  narrator: string;
  duration: number;
  chaptersTotal: number;
  chaptersAvailable: number;
  complete: boolean;
  version: string;
  chapters: ManifestChapter[];
  /** File cả bộ (.abook phiên bản 3): các phần theo thứ tự. */
  parts?: BookPart[];
  /** Phần nối tiếp của "Làm tiếp cuốn này": mã phần đầu + thứ tự phần (sync.manifest `series`); phần đầu và sách lẻ: null. */
  series?: SeriesLink | null;
  samples: string[];
  /** Ảnh bìa thật tải về cùng gói (webui/covers.py), hoặc null. */
  cover?: { file: string; version: number; color: string; width: number; height: number } | null;
  /** Giây Unix lúc sách về điện thoại (book.json ghi lần đầu). */
  addedAt?: number;
  state: ListeningState;
  bytes?: number;
  /** Chưa tải: nghe thẳng từ máy tính (Streaming.kt) - gói sách đã cất ở stream.json. */
  streamed?: boolean;
  /** Nghe thẳng từ thiết bị ghép (Peers.kt): tên thiết bị ấy. */
  sourceName?: string;
  /** Cuốn đang nghe thẳng mà máy giữ nó không trả lời (tắt, mất mạng): vẫn ở Thư viện để trình phát không đóng (soát a68 lỗi 3). */
  offline?: boolean;
  /** Cuốn là dự án Studio ở máy tính giữ nó (sync.py book_manifest) - trang sách có "Mở Studio". */
  studio?: boolean;
  /** Hồ sơ nghe gắn với cuốn (Store.records) - chỉ có khi mở một cuốn. */
  records?: ListeningRecord[];
  /** Máy này làm được gì với cuốn (shared/capabilities.ts): điện thoại không có xưởng, không có Studio; `link` = cuốn của máy tính. */
  capabilities?: Capabilities;
  /** Số thay đổi người nghe đã làm trên cuốn nhập từ file (lớp sửa, BookEdits.kt). */
  edits?: number;
  /** Trong số `edits`: ý muốn chờ Studio (BookWishes.kt) - chưa áp vào audio. */
  wishes?: number;
  /** Cuốn tải từ máy tính: phần sửa chưa gửi về máy tính + kết quả lần gửi gần nhất (EditsSync.kt). */
  editsSync?: EditsSyncState;
}

export interface DownloadEvent {
  bookId: string;
  done?: number;
  total?: number;
  files?: number;
  filesTotal?: number;
  finished?: boolean;
  error?: string;
  /** Chữ gốc của lỗi cho mục "Chi tiết". */
  technical?: string;
  /** Người nghe bấm Huỷ: dừng, phần đã về giữ lại để lần Tải sau tải tiếp. */
  cancelled?: boolean;
}

/** Tin của một lượt "Xuất MP3" (Mp3ExportWorker.kt): tiến độ (`done`/`total`), xong (`finished`), dừng (`stopped`) hay lỗi (`error`). */
export interface Mp3ExportEvent {
  selection?: boolean;
  bookId: string;
  run: string;
  done?: number;
  total?: number;
  finished?: boolean;
  files?: number;
  chaptersTotal?: number;
  folder?: string;
  /** Địa chỉ thư mục bản xuất để mở bằng app Tệp (`openFolder`); không có thì không có nút mở. */
  uri?: string;
  stopped?: boolean;
  error?: string;
  /** Chỉ trong `exportJobs` (ghi lúc việc bắt đầu): ô "Kèm nhạc nền" của lượt. */
  music?: boolean;
  /** "Kèm nhạc nền" (soát a99 V3): pha như `M4bExportEvent` (tải bài / trộn / kiểm đỉnh / mã hoá lại); `mixed`: chương ra file .m4a đã trộn nhạc; `musicMissing`: đoạn thiếu nhạc. */
  phase?: "music-fetch" | "music" | "peaks" | "reencode";
  chapter?: number;
  chapters?: number;
  peakRound?: number;
  peakOver?: number;
  percent?: number;
  mixed?: boolean;
  musicMissing?: number;
}

/** Tin của một lượt "Xuất M4B" (M4bExportWorker.kt): tiến độ (`done`/`total` chương, `percent` cả cuốn), xong (`finished`), dừng (`stopped`) hay lỗi. */
export interface M4bExportEvent {
  bookId: string;
  run: string;
  done?: number;
  total?: number;
  percent?: number;
  /** "Kèm nhạc nền": pha như máy tính (desktop/bookFileExport.ts ExportJob) - "music-fetch" tải bài thiếu (`done`/`total` bài), "music" trộn chương
   *  `chapter`/`chapters`, "peaks" kiểm đỉnh âm, "reencode" mã hoá lại lượt `peakRound` vì `peakOver` chương vượt đỉnh; không có = mã hoá thường. */
  phase?: "music-fetch" | "music" | "peaks" | "reencode";
  chapter?: number;
  chapters?: number;
  peakRound?: number;
  peakOver?: number;
  finished?: boolean;
  /** Tên file đã ghi, cỡ (byte), số chương có trong file / của cả cuốn (chương chưa làm xong không vào file). */
  name?: string;
  size?: number;
  chaptersTotal?: number;
  /** Số đoạn không có nhạc vì bài chưa tải được. */
  musicMissing?: number;
  /** Chương còn vượt đỉnh sau mọi lượt hạ (vẫn xong, chỉ ghi số). */
  overCeiling?: { chapter: number; dbtp: number }[];
  stopped?: boolean;
  error?: string;
}

/** Một lượt xuất đang chạy (`exportJobs`): tin cuối của lượt kèm kiểu xuất. Chưa có tin nào thì chỉ có `kind`, `bookId`, `run`. */
export type RunningExport =
  | ({ kind: "mp3" } & Mp3ExportEvent)
  | ({ kind: "m4b" } & M4bExportEvent)
  | ({ kind: "audiobook" } & AudiobookExportEvent);

/** Phần trả lời của `audiobookPlan` ("Xuất sách nói", ListenExport.kt): cùng hình với máy tính (desktop/listenExport.ts AudiobookPlan, trừ ffmpeg - điện thoại tự mã hoá), thêm chỗ trống cần. */
export interface AudiobookPhonePlan {
  chapters: number;
  chars: number;
  audioSeconds: number;
  /** Máy làm phần còn lại mất chừng này giây (giọng đã đo tốc độ); null: chưa đo. */
  secondsEstimate: number | null;
  /** Chương có đủ (đã ghép từ lần xuất trước, hay mọi đoạn đã có trong bộ đệm Nghe ngay): xuất ngay, không đọc lại. */
  readyChapters: number;
  /** Giây nghe đã có sẵn (clip trong bộ đệm + chương đã ghép). */
  readySeconds?: number;
  /** Chỗ trống cần ở bộ nhớ máy trong lúc làm (byte); xoá khi xong. */
  bytes: number;
  /** Đoạn phải đọc lại: chương đã có giọng nhưng phải ghép lại vì đổi (bật / tắt) nhạc nền, mà clip đoạn ấy không còn trong bộ đệm. */
  rereads?: number;
  /** Ô "Kèm nhạc nền" (BookMusic.exportState): cuốn có kế hoạch nhạc không, mặc định của ô. */
  music?: MusicExportState;
}

/**
 * Tin của một lượt "Xuất sách nói" (ListenExportWorker.kt). Tiến độ mang các trường như việc xuất của máy tính (desktop/bookFileExport.ts ExportJob): pha ("voice" đọc / "encode"
 * ghép file), chương i/N, % theo số chữ, ước còn lại, đang nhường người nghe; xong (`finished`) kèm tên file, cỡ, số chương có trong file / của cả cuốn và địa chỉ để mở.
 */
export interface AudiobookExportEvent {
  bookId: string;
  run: string;
  phase?: "voice" | "music" | "music-fetch" | "peaks" | "reencode" | "encode";
  chapter?: number;
  chapters?: number;
  chapterTitle?: string;
  /** Pha "music-fetch": bài thứ `done` + 1 trong `total`. */
  done?: number;
  total?: number;
  peakRound?: number;
  peakOver?: number;
  musicMissing?: number;
  overCeiling?: { chapter: number; dbtp: number }[];
  percent?: number;
  secondsLeft?: number | null;
  waiting?: "listening" | "network" | null;
  finished?: boolean;
  name?: string;
  size?: number;
  chaptersTotal?: number;
  uri?: string;
  stopped?: boolean;
  error?: string;
}

/** "Cho máy khác nghe thư viện này" (LibraryServer.kt, mạng trạm bước 2): điện thoại phục vụ sách đã tải cho máy đã ghép. */
export interface ShareStatus {
  running: boolean;
  /** Tên máy khác thấy ("Samsung SM-A546E"). */
  name: string;
  port: number;
  /** Địa chỉ Wi-Fi của điện thoại - để gõ vào máy kia khi nó không tự tìm thấy. */
  addresses: string[];
  pairing: { code: string; expiresAt: number } | null;
  /** Nhập sai mã quá 5 lần: mã bị huỷ, phải tạo mã mới. */
  blocked: boolean;
  /** Vân tay SHA-256 chứng chỉ TLS của điện thoại (ShareTls.kt), nhóm 4 ký tự; "" khi chưa bật chia sẻ. */
  fingerprint?: string;
  devices: { id: string; name: string; pairedAt: number; lastSeen: number }[];
  error: string;
  /** Phục vụ cả qua Bluetooth (BluetoothShare.kt): "running", "" (chưa bật) hay lý do không bật được. */
  bluetooth?: { status: string; connections: number };
  /** Hãng máy (Build.MANUFACTURER) - chọn lời hướng dẫn cho ABook chạy nền (backgroundHelp.ts). */
  manufacturer?: string;
  /** ABook đã được miễn tối ưu pin (người dùng bật "Cho phép hoạt động dưới nền") - máy không đông ABook khi ở nền. */
  backgroundAllowed?: boolean;
}

export interface EbookLibraryPlugin {
  info(): Promise<{ root: string }>;
  discover(options: { timeoutMs?: number }): Promise<{ computers: { host: string; port: number; name: string; kind?: string }[] }>;
  shareStatus(): Promise<ShareStatus>;
  setShare(options: { enabled: boolean }): Promise<ShareStatus>;
  sharePair(): Promise<ShareStatus>;
  shareCancelPairing(): Promise<ShareStatus>;
  shareRevoke(options: { id: string }): Promise<ShareStatus>;
  /** Trang thông tin ứng dụng của ABook trong Cài đặt Android (cho ABook chạy nền). */
  openAppSettings(): Promise<void>;
  /** Thanh trạng thái + thanh điều hướng theo giao diện của APP (settings.applyTheme), không theo sáng/tối của máy: chữ/biểu tượng sáng trên nền
   *  tối khi `dark`, dải sau thanh mang màu `color` (#rrggbb) của thân app. */
  systemBars(options: { dark: boolean; color: string }): Promise<void>;
  /** Hãng máy + ABook đã được chạy nền chưa (PowerManager.isIgnoringBatteryOptimizations) - màn xuất nhắc khi chưa (BackgroundNote.tsx). */
  backgroundStatus(): Promise<{ manufacturer: string; backgroundAllowed: boolean }>;
  pair(options: { host: string; port: number; code: string; device?: string }): Promise<{ name: string }>;
  /** Quyền "Thiết bị ở gần" (Bluetooth) lúc này, chưa xin gì: "denied" = đã từ chối hẳn, chỉ Cài đặt Android bật lại được (bluetoothPermission.ts). */
  bluetoothPermission(): Promise<{ state: BluetoothPermission }>;
  /** Máy đã ghép Bluetooth với điện thoại (BluetoothLink.kt); Android 12+ xin quyền "Thiết bị ở gần" lần đầu. */
  bluetoothDevices(): Promise<{ devices: { address: string; name: string; kind: "computer" | "phone"; abook: boolean }[] }>;
  /** Ghép máy tính chính qua Bluetooth - cùng mã 6 số, đi qua đường hầm; sau đó `connection().host` là "bt:<địa chỉ>". */
  pairBluetooth(options: { address: string; code: string; device?: string }): Promise<{ name: string }>;
  /** `fingerprint`: vân tay chứng chỉ TLS máy tính đã ghi lúc ghép (hex; Pin.kt) - để đối chiếu, "" nếu chưa có. */
  connection(): Promise<{ paired: boolean; host: string; port: number; name: string; fingerprint?: string; lastAddress?: string; deviceName?: string; connectedVia?: string }>;
  /** Tên điện thoại này máy khác thấy (DeviceName.kt) - báo luôn cho các máy đã ghép. */
  setDeviceName(options: { name: string }): Promise<{ name: string }>;
  unpair(): Promise<void>;
  /** Máy tính mở Studio được (StudioLink.kt): máy tính chính (`key` "") rồi các máy tính ghép thêm. */
  studioComputers(options?: { book?: string }): Promise<{ computers: StudioComputer[] }>;
  /** Studio từ xa: mở trang Studio của máy tính đã ghép (StudioActivity.kt, webui/remote_studio.py) - máy `computer` ("" = máy tính
   *  chính), hay thẳng cuốn `book` (mã trên điện thoại này) trong Studio của máy tính giữ nó. */
  openStudio(options?: { computer?: string; book?: string }): Promise<void>;
  /** Mở trang / file APK của bản phát hành mới bằng trình duyệt của máy (chỉ đường GitHub của ABook - updates.ts). */
  openRelease(options: { url: string }): Promise<void>;
  /** Thông báo Studio (StudioAlerts.kt): sách xong, dừng vì lỗi, có việc mới cần duyệt. `permitted`: Android cho đăng
   *  thông báo không (Android 13+ phải xin). */
  studioAlerts(): Promise<{ enabled: boolean; permitted: boolean }>;
  setStudioAlerts(options: { enabled: boolean }): Promise<{ enabled: boolean; permitted: boolean }>;
  remoteLibrary(): Promise<{ name: string; books: RemoteBook[] }>;
  download(options: { bookId: string; source?: string; remoteId?: string }): Promise<{ bookId: string }>;
  /** Huỷ lượt tải đang chạy (dừng ở khối kế, giữ phần đã về). */
  cancelDownload(options: { bookId: string }): Promise<void>;
  /** Thiết bị ghép ngoài máy tính chính (mạng trạm bước 2 - Peers.kt). */
  peers(): Promise<{ peers: { key: string; name: string; host: string; port: number }[] }>;
  peerPair(options: { host: string; port: number; code: string }): Promise<{ key: string; name: string }>;
  /** Ghép thiết bị đã ghép Bluetooth với điện thoại này - cùng mã 6 số, đi qua Bluetooth. */
  peerPairBluetooth(options: { address: string; code: string }): Promise<{ key: string; name: string }>;
  /** Sửa chưa gửi của các cuốn nghe thẳng của một thiết bị ghép - thứ thôi ghép sẽ xoá; `sendable`: thiết bị là máy tính (nhận được sửa). */
  peerUnsent(options: { key: string }): Promise<{ books: { id: string; title: string; changes: number }[]; changes: number; sendable: boolean; cache: { books: number; bytes: number; places: number } }>;
  /** Thôi ghép; còn sửa chưa gửi thì từ chối trừ khi `send` (gửi hết về máy ấy rồi mới gỡ) hay `discard` (bỏ phần sửa). */
  peerForget(options: { key: string; send?: boolean; discard?: boolean }): Promise<void>;
  peerLibraries(): Promise<{ peers: PeerLibrary[] }>;
  remotePlayers(): Promise<{ players: RemotePlayer[] }>;
  /** Tìm lại loa / TV ngay (điện thoại tự tìm - PhoneCast); danh sách mới hiện ở lần `remotePlayers` kế. */
  scanPlayers(): Promise<void>;
  /** "load" mang mã cuốn của điện thoại này - bên native đổi sang mã của máy kia (hoặc từ chối: máy kia không có). */
  remoteCommand(options: { device: string; command: RemotePlayerCommand }): Promise<{ id?: string; ok?: boolean; message?: string }>;
  localBooks(): Promise<{ books: LocalBook[]; notices?: string[] }>;
  /** Sách trên máy tính chưa tải mà nghe thẳng được; máy tính không trả lời thì rỗng. */
  streamableBooks(): Promise<{ books: LocalBook[] }>;
  book(options: { id: string }): Promise<LocalBook>;
  readText(options: { id: string; path: string }): Promise<{ text: string }>;
  /** Văn bản của nhiều file trong gói một lượt (ô "Tìm trong sách"): theo thứ tự `paths`, null cho file không có; chữ quá nhiều thì trả phần đầu
   *  (ít mục hơn `paths`) - hỏi lại phần còn lại. */
  readTexts(options: { id: string; paths: string[] }): Promise<{ texts: (string | null)[] }>;
  /** Sửa sách "áp ngay" trên điện thoại (LocalStudio.kt): cùng đường dẫn `/api/books/<mã>/...`, cùng JSON như máy chủ máy tính
   *  (docs/EDITING.md); `status` >= 400 là lỗi, `body.error` là câu cho người dùng (android/localStudio.ts đổi thành ApiError). */
  studio(options: { method: string; path: string; body?: unknown }): Promise<{ status: number; body: unknown }>;
  /** Điện thoại làm được gì (BookEdits.kt): luôn không có Studio, không có xưởng; `link` theo cuốn `id` (có là cuốn của máy tính). */
  capabilities(options: { id?: string }): Promise<Capabilities>;
  /** "Gửi về máy tính": gửi ngay phần sửa của cuốn tải từ máy tính (EditsSync.kt) qua đường TLS đã ghim. Trả trạng thái mới; không
   *  tới được máy tính hay máy tính không nhận thì từ chối với câu nói lý do - phần sửa vẫn nằm trên máy này. */
  sendEdits(options: { id: string }): Promise<EditsSyncState>;
  /** Gửi tự động xong (hay lỗi): trạng thái `editsSync` của cuốn đã đổi - giao diện làm mới. */
  addListener(event: "editsSync", handler: (event: { bookId: string }) => void): Promise<PluginListenerHandle>;
  /** Công tắc "Cho máy khác nghe thư viện này" đổi từ ngoài màn hình (nút "Tắt chia sẻ" trên thông báo): hỏi lại `shareStatus`. */
  addListener(event: "shareChanged", handler: () => void): Promise<PluginListenerHandle>;
  /** Lưu cuốn nhập từ file (kèm thay đổi của người nghe) thành file mới - hộp thoại "tạo file" của hệ thống hỏi chỗ lưu. `as` không nói:
   *  giữ loại file cuốn đã đến (`.abookproj` hay `.abook`). */
  /** `ask`: luôn hỏi chỗ lưu ("Lưu thành…"); không thì "Lưu" ghi thẳng vào chỗ đã lưu lần trước của cuốn này, chưa có mới hỏi. */
  saveBook(options: { id: string; as?: "abook" | "abookproj"; ask?: boolean }): Promise<{ saved: boolean; name?: string; size?: number; edits?: number }>;
  /** Bản lưu cũ app đang giữ hộ (lần lưu hỏng giữa chừng mà bản trước chưa trả lại được vào file - OldSaves.kt); `modified` tính bằng giây. */
  listOldSaves(): Promise<{ files: { name: string; size: number; modified: number }[] }>;
  /** "Lưu ra…": hộp chọn chỗ lưu của hệ thống rồi chép bản cũ `name` ra đó; `saved: false` khi người dùng bỏ qua hộp. */
  exportOldSave(options: { name: string }): Promise<{ saved: boolean }>;
  /** Xoá hẳn một bản lưu cũ (không lấy lại được; giao diện đã hỏi xác nhận). */
  deleteOldSave(options: { name: string }): Promise<{ deleted: boolean }>;
  /** "Chia sẻ…": đóng cuốn (kèm thay đổi của người nghe) thành file rồi mở bảng chia sẻ của hệ thống (Zalo, Drive, email…). `as` không nói:
   *  sách nghe `.abook`. `shared: true` khi bảng chia sẻ đã mở. */
  shareBook(options: { id: string; as?: "abook" | "abookproj" }): Promise<{ shared: boolean; name?: string }>;
  /** Cài đặt → Chẩn đoán (Diagnostics.kt, AppLog.kt): bản chẩn đoán của chính điện thoại với `lines` dòng nhật ký cuối (mặc định 500). */
  diagnostics(options?: { lines?: number }): Promise<DiagnosticsReport>;
  /** "Gửi nhật ký": ghi gói .zip (chẩn đoán + nhật ký chữ) rồi mở bảng chia sẻ của hệ thống - người dùng tự chọn gửi cho ai; app không gửi đi đâu. */
  shareDiagnostics(): Promise<{ shared: boolean; name?: string }>;
  /** "Xoá nhật ký": bỏ nhật ký của app và các file văng. */
  clearDiagnostics(): Promise<{ cleared: boolean }>;
  /** "Xuất MP3 để nghe ở app khác" (Mp3Export.kt): thư mục MP3 như máy tính, chạy nền. Lần đầu (hay `pick`) hỏi chỗ lưu bằng bộ
   *  chọn thư mục của hệ thống rồi nhớ lại. `cover`: bìa tự vẽ (data URL PNG) khi sách không có bìa. Tiến độ / kết quả: sự kiện
   *  "mp3Export" mang cùng `run`. `started: false` khi không chọn thư mục. */
  exportMp3(options: { bookId: string; cover?: string; pick?: boolean; chapterIds?: number[]; music?: boolean }): Promise<{ started: boolean; run?: string; folder?: string; chapters?: number }>;
  /** "Mở thư mục" ở thông báo xuất xong: mở thư mục bản xuất bằng app Tệp. `opened: false` khi máy không có app nào mở được. */
  openFolder(options: { uri: string }): Promise<{ opened: boolean }>;
  addListener(event: "mp3Export", handler: (event: Mp3ExportEvent) => void): Promise<PluginListenerHandle>;
  /** "Xuất M4B cho app sách nói" (M4bExport.kt): cả cuốn một file `.m4b` có mục lục chương, chạy nền. Hệ thống hỏi tên và chỗ lưu
   *  (mỗi lần). `cover`: bìa tự vẽ (data URL PNG) khi sách không có bìa. Tiến độ / kết quả: sự kiện "m4bExport" mang cùng `run`.
   *  `started: false` khi không chọn chỗ lưu; sách chưa có chương nghe được thì từ chối ngay. */
  exportM4b(options: { bookId: string; cover?: string; music?: boolean }): Promise<{ started: boolean; run?: string; name?: string; chapters?: number }>;
  /** Ô "Kèm nhạc nền" của "Xuất M4B": cuốn có kế hoạch nhạc không, mặc định theo công tắc Nhạc nền của cuốn. */
  m4bMusicState(options: { bookId: string }): Promise<MusicExportState>;
  /** Dừng lượt xuất M4B đang chạy của cuốn (file dở bị xoá). */
  cancelM4bExport(options: { bookId: string }): Promise<void>;
  addListener(event: "m4bExport", handler: (event: M4bExportEvent) => void): Promise<PluginListenerHandle>;
  /** "Xuất sách nói" của sách chỉ có chữ (ListenExport.kt): ước trước khi bấm - số chương, giờ nghe, máy cần bao lâu, chương đã làm sẵn từ lần trước. */
  audiobookPlan(options: { bookId: string; voice: string; music?: boolean }): Promise<AudiobookPhonePlan>;
  /** Đọc cả cuốn bằng giọng `voice` rồi ghép thành MỘT file `.m4b` có mục lục chương, chạy nền. Hệ thống hỏi tên và chỗ lưu (mỗi lần). `cover`: bìa tự vẽ (data URL PNG)
   *  khi sách không có bìa. Tiến độ / kết quả: sự kiện "audiobookExport" mang cùng `run`. `started: false` khi không chọn chỗ lưu; sách không có chữ để đọc thì từ chối ngay. */
  exportAudiobook(options: { bookId: string; voice: string; cover?: string; music?: boolean }): Promise<{ started: boolean; run?: string; name?: string }>;
  /** Dừng lượt xuất sách nói của cuốn (file dở bị xoá, phần đã đọc xong giữ để xuất lại làm tiếp). */
  cancelAudiobookExport(options: { bookId: string }): Promise<void>;
  /** Các lượt xuất (MP3, M4B, sách nói) đang chạy, tin cuối của từng lượt: mở lại (hay tải lại) giao diện giữa lúc việc nền chạy thì hiện lại tiến độ
   *  và nhận tiếp tin xong / lỗi. */
  exportJobs(): Promise<{ jobs: RunningExport[] }>;
  /** Mở file vừa xuất bằng app nghe sách nói của máy; `opened: false` khi không mở được. */
  openFile(options: { uri: string }): Promise<{ opened: boolean }>;
  addListener(event: "audiobookExport", handler: (event: AudiobookExportEvent) => void): Promise<PluginListenerHandle>;
  /** Xoá khỏi điện thoại có Hoàn tác (TrashPending.kt): cuốn nằm chờ 30 giây rồi xoá hẳn. `undo`: mã cho `undoDelete`; null khi xoá thẳng (không đổi tên được). */
  deleteBook(options: { id: string }): Promise<{ undo: string | null }>;
  /** Đưa cuốn vừa xoá về chỗ cũ; từ chối khi quá hạn (đã xoá hẳn) hay chỗ cũ đã có cuốn cùng mã. */
  undoDelete(options: { token: string }): Promise<void>;
  /** `bytes`: cả thư viện; `books`: cỡ từng cuốn trên máy (mã thư mục = mã cuốn). */
  storage(): Promise<{ bytes: number; free: number; books: { id: string; bytes: number; title?: string }[] }>;
  progress(options: { id: string; chapterId: number; seconds: number; duration: number; anchor?: import("@/listen/readingAnchor").ReadingAnchor }): Promise<ListeningState>;
  saveReading(options: { id: string; chapterId: number; index: number; at?: number; rev?: import("@/listen/readingPosition").ReadingPosition["rev"]; anchor?: import("@/listen/readingAnchor").ReadingAnchor; quote?: string; record?: string }): Promise<ListeningState>;
  setChapterDone(options: { id: string; chapterId: number; done: boolean; record?: string }): Promise<ListeningState>;
  setFinished(options: { id: string; finished: boolean; record?: string }): Promise<ListeningState>;
  setRate(options: { id: string; rate: number; record?: string }): Promise<void>;
  /** Giọng Nghe ngay riêng của cuốn ("" = giọng mặc định) - đi theo hồ sơ nghe sang máy kia (soát a68 lỗi 8). */
  setVoice(options: { id: string; voice: string; record?: string }): Promise<void>;
  addBookmark(options: { id: string; chapterId: number; seconds: number; note: string; index?: number; quote?: string; anchor?: import("@/listen/readingAnchor").ReadingAnchor; createdAt?: number; record?: string }): Promise<Bookmark>;
  restoreBookmark(options: { id: string; mark: Bookmark }): Promise<Bookmark>;
  updateBookmark(options: { id: string; markId: string; note: string; record?: string }): Promise<void>;
  deleteBookmark(options: { id: string; markId: string; record?: string }): Promise<void>;
  syncState(options: { id: string }): Promise<ListeningState>;
  createRecord(options: { id: string; name: string }): Promise<{ records: ListeningRecord[] }>;
  activateRecord(options: { id: string; record: string }): Promise<{ records: ListeningRecord[] }>;
  renameRecord(options: { id: string; record: string; name: string }): Promise<{ records: ListeningRecord[] }>;
  deleteRecord(options: { id: string; record: string }): Promise<{ records: ListeningRecord[] }>;
  moveRecord(options: { id: string; record: string; book: string }): Promise<{ records: ListeningRecord[] }>;
  addListener(event: "download", handler: (event: DownloadEvent) => void): Promise<PluginListenerHandle>;
  /** Bộ chọn file của hệ thống để mở một file sách .abook; kết quả về qua sự kiện "import". */
  pickBook(): Promise<{ picked: boolean }>;
  confirmOlderImport(options: { source: string }): Promise<void>;
  exportHistory(options: { bookId: string }): Promise<{ exports: { kind: string; target: string; changed: number[] }[] }>;
  addListener(event: "import", handler: (event: ImportEvent) => void): Promise<PluginListenerHandle>;
  /** App khác gửi tới một file EPUB / DOCX / PDF / TXT ("Mở bằng", chia sẻ): native đã chép nó như `pickSource` - giao diện mở bước
   *  xem trước của "Thêm sách từ file…". `error`: không chép được, câu cho người dùng. */
  addListener(event: "textPicked", handler: (event: { ref?: string; name?: string; pdf?: string; error?: string }) => void): Promise<PluginListenerHandle>;
  /** "Nhập nhạc của tôi…": hộp chọn file của hệ thống (nhiều bản một lúc), nhập từng bản vào kho nhạc của điện thoại (MusicStore.kt);
   *  trả khi nhập xong - cùng JSON như `/api/music/local/import` của máy tính - hay `{picked: false}` khi không chọn gì. */
  pickMusic(): Promise<{ picked: boolean } & Partial<ImportResult>>;
  addListener(event: "musicImport", handler: (event: { done: number; total: number }) => void): Promise<PluginListenerHandle>;
  /** "Thêm sách từ file…" (BookImport.kt + TextBook.kt): bộ chọn file / thư mục của hệ thống; chép thứ đã chọn vào thư mục tạm của app
   *  (`ref`). `book`: thứ chọn là file sách .abook / .abookproj - đã đi đường "Mở file sách" (sự kiện `import`), không có `ref`. `pdf`: đường dẫn bản sao PDF - WebView lấy chữ bằng pdf.js (shared/pdfPages.ts) rồi đưa sang `previewImport`. */
  pickSource(options: { kind: "file" | "folder"; multiple?: boolean }): Promise<{
    picked: boolean;
    ref?: string;
    name?: string;
    pdf?: string;
    book?: boolean;
    /** Chỉ khi `multiple`: mỗi file đã chọn một mục - đã chép (`ref`), file sách .abook đã mở (`book`), hay không chép được (`error`). */
    items?: { ref?: string; name?: string; pdf?: string; book?: boolean; error?: string }[];
  }>;
  /** Đọc thứ đã chọn bằng luật nhập sách của Kotlin; PDF thì kèm `pages` (các dòng từng trang) pdf.js đã lấy ra. Lỗi đọc được: từ chối
   *  với câu cho người dùng. */
  previewImport(options: {
    ref: string;
    pages?: string[][];
    title?: string;
    author?: string;
    splitChapters?: boolean;
    /** Đề xuất về chú thích đã tích (EPUB / DOCX): `hideMarks` + `notes` ""/"end"/"drop" - cùng luật với máy tính (importers.FootnoteChoice). */
    footnotes?: { hideMarks: boolean; notes: "" | "end" | "drop" };
  }): Promise<ImportPreview>;
  /** Nhập thành sách chỉ-chữ (TextBook.kt → BookFileImport): `title` rỗng thì giữ tên của file sách. `chapters`: các hàng của bước xem trước
   *  người dùng giữ lại + tên mới của chúng (chỉ đổi tên); không có thì các chương mặc định (mục rất ngắn chưa tích). */
  createImport(options: { ref: string; title: string; separate?: boolean; chapters?: { index: number; title?: string }[] }): Promise<AddedBook>;
  discardImport(options: { ref: string }): Promise<void>;
}

/** Kết quả mở một file sách (.abook): mã sách vừa vào Thư viện, hay lý do không nhận. */
export interface ImportEvent {
  how?: string;
  source?: string;
  bookId?: string;
  title?: string;
  /** Cuốn đã có trên máy và đã có thay đổi của người nghe: số thay đổi được giữ nguyên (BookFileImport.Imported.keptEdits). */
  keptEdits?: number;
  /** Số bài nhạc nền hỏng trong file đã bị bỏ (BookFileImport.Imported.brokenMusic) - sách vẫn mở, đoạn ấy im lặng. */
  brokenMusic?: number;
  error?: string;
}

/** "Nghe ngay" trên điện thoại (docs/LISTEN_ANYTHING.md mục 3): giọng của máy (Android TextToSpeech) và mốc thời gian câu / chữ mà LÕI NATIVE đọc ra.
 *  Chương chỉ-có-chữ vào hàng đợi `EbookPlayer.load` như chương thường (kèm `readAloudVoice`); JS chỉ hỏi giọng và mốc, không tự đọc. */
export interface ReadAloudPlugin {
  voices(): Promise<{ voices: ReadAloudVoice[] }>;
  /** Mốc hiện có của chương (mọi câu theo thứ tự; câu chưa đọc có mốc ước, không có `words`). */
  script(options: { bookId: string; chapterId: number }): Promise<ReadAloudTimings>;
  /** Mở trang sách / trình phát với giọng trên máy: nạp sẵn model của giọng ấy (EnginePreload.kt). Trả ngay; `started` false = không có gì để nạp, đã nạp, hay máy không dư. */
  warmVoice(options: { voice: string }): Promise<{ started: boolean }>;
  /** Lõi đã có mốc mới cho chương (một câu vừa đọc xong, hay nạp chương): hỏi lại `script`. */
  addListener(event: "readAloudScript", handler: (event: { bookId: string; chapterId: number }) => void): Promise<PluginListenerHandle>;
  /** Một đoạn vừa được đọc tạm bằng giọng kế (khoá bị từ chối / hết hạn mức / mất mạng): câu nói một lần cho người nghe. */
  addListener(event: "readAloudNotice", handler: (event: { message: string }) => void): Promise<PluginListenerHandle>;
  /** "Thử giọng" (Cài đặt): đọc `text` bằng giọng này, trả đường dẫn file trên máy (phát qua `Capacitor.convertFileSrc`). */
  /** `bookId`: cách đọc riêng của cuốn ấy; `readings`: cách đọc đem nghe thử (chưa lưu - thắng của cuốn). */
  sample(options: { voice: string; text: string; bookId?: string; readings?: Record<string, string> }): Promise<{ path: string }>;
  /** Giọng dùng khoá của người dùng (OnlineVoices.kt): mô tả từng nhà cung cấp - khoá chỉ ở dạng che. */
  onlineProviders(): Promise<{ providers: OnlineProviderInfo[] }>;
  setOnlineKey(options: { provider: string; key: string; region: string }): Promise<OnlineProviderInfo>;
  removeOnlineKey(options: { provider: string }): Promise<OnlineProviderInfo>;
  checkOnlineKey(options: { provider: string }): Promise<KeyCheck>;
  /** Mô-đun "Giọng VieNeu" (vieneu/VieneuModule.kt): cùng hình trạng thái với máy tính. `vieneuStart` không kèm `choices` = cập nhật phần đã cũ. */
  vieneuStatus(): Promise<VieneuStatus>;
  vieneuStart(options: { choices?: VieneuChoiceId[] }): Promise<VieneuStatus>;
  vieneuMeasure(): Promise<VieneuStatus>;
  vieneuRemove(options: { choice: VieneuChoiceId }): Promise<VieneuStatus>;
  /** Huỷ lần tải đang chạy: dừng ở nhịp đọc kế, phần đã tải giữ để lần sau làm tiếp (trạng thái kèm `cancelled`). */
  vieneuCancel(): Promise<VieneuStatus>;
  /** Mô-đun "Giọng Supertonic" (readaloud/SupertonicModule.kt): cùng hình trạng thái, cùng lệnh. */
  supertonicStatus(): Promise<VieneuStatus>;
  supertonicStart(options: { choices?: VieneuChoiceId[] }): Promise<VieneuStatus>;
  supertonicMeasure(): Promise<VieneuStatus>;
  supertonicRemove(options: { choice: VieneuChoiceId }): Promise<VieneuStatus>;
  supertonicCancel(): Promise<VieneuStatus>;
  /** "Tốc độ giọng trên máy" (readaloud/VoiceSpeed.kt): cùng hình trạng thái với máy tính (/api/readaloud/voice-speed). */
  voiceSpeed(): Promise<VoiceSpeedStatus>;
  setVoiceSpeed(options: { choice: VoiceSpeedChoice }): Promise<VoiceSpeedStatus>;
  /** "Làm trước" (PrepareAhead.kt): việc nền của WorkManager đọc sẵn các chương này bằng đúng giọng ấy vào bộ đệm - chạy cả khi app đã đóng. */
  preparePlan(options: { bookId: string; voice: string; chapterIds: number[] }): Promise<PreparePlan>;
  prepareStart(options: { bookId: string; voice: string; chapterIds: number[]; label: string; chargingOnly?: boolean }): Promise<PrepareStatus>;
  prepareStatus(): Promise<PrepareStatus>;
  prepareCancel(): Promise<PrepareStatus>;
  prepareOptions(options: { chargingOnly: boolean }): Promise<PrepareStatus>;
  /** Bản đọc đã làm (bộ đệm clip, kể cả phần "Làm trước") chiếm bao nhiêu byte và dọn hết (Cài đặt > Giọng đọc); `book` luôn 0 - điện thoại chỉ báo cả máy. */
  cacheUsage(): Promise<{ book: number; total: number }>;
  cacheClear(): Promise<{ book: number; total: number }>;
  /** Tiến độ làm trước (sau mỗi đoạn, mỗi lần đổi). */
  addListener(event: "readAloudPrepare", handler: (status: PrepareStatus) => void): Promise<PluginListenerHandle>;
}

export const EbookPlayer = registerPlugin<EbookPlayerPlugin>("EbookPlayer");
export const ReadAloud = registerPlugin<ReadAloudPlugin>("ReadAloud");
export const EbookLibrary = registerPlugin<EbookLibraryPlugin>("EbookLibrary");
