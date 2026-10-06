import { registerPlugin, type PluginListenerHandle } from "@capacitor/core";
import type { Bookmark, BookPart, ListeningRecord, ListeningState, NightSession } from "@/listen/model";
import type { PreparePlan, PrepareStatus } from "@/listen/prepareAhead";
import type { MusicCredit } from "@/listen/musicBed";
import type { RemoteSleep, RemoteSleepCommand } from "@/listen/sleep";
import type { ReadAloudTimings, ReadAloudVoice } from "@/listen/readAloud";
import type { KeyCheck, OnlineProviderInfo } from "@/listen/VoiceSettings";
import type { Capabilities } from "@/shared/capabilities";
import type { EditsSyncState } from "@/shared/editsSync";
import type { AddedBook, ImportPreview } from "@/listen/textImport";
import type { ImportResult } from "@/studio/musicLocal";
import type { VieneuChoiceId, VieneuStatus } from "@/listen/vieneuModule";

// Hai plugin native của app Android (mobile/android/app/src/main/java/vn/abook/player):
//  EbookPlayer  - lõi phát Media3: hàng đợi chương, hẹn giờ ngủ, lắc để nghe thêm, nhật ký đêm.
//  EbookLibrary - sách đã tải + đồng bộ với máy tính qua Wi-Fi.

export interface NativeSleep {
  mode: "off" | "minutes" | "chapter";
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
  /** Ghi công bài nhạc nền đang kêu (MusicBed.credit); null khi im lặng. */
  musicCredit?: MusicCredit | null;
}

// Nhật ký đêm của lõi native - cùng hình dạng với listen/model.ts (NightSession).
export type BedtimeSession = NightSession;

export interface EbookPlayerPlugin {
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
  }): Promise<NativeState>;
  play(): Promise<NativeState>;
  pause(): Promise<NativeState>;
  toggle(): Promise<NativeState>;
  next(): Promise<NativeState>;
  previous(): Promise<NativeState>;
  seekTo(options: { seconds: number }): Promise<NativeState>;
  skip(options: { delta: number }): Promise<NativeState>;
  setRate(options: { rate: number }): Promise<NativeState>;
  /** `segment` + `word` (chương đọc to): native vào đúng mốc chữ ấy, kể cả đoạn chưa tạo tiếng - thắng `seconds`. */
  jumpTo(options: { chapterId: number; seconds: number; segment?: number; word?: number }): Promise<NativeState>;
  getState(): Promise<NativeState>;
  addBookmark(options: { note: string }): Promise<Bookmark>;
  setSleep(options: { mode: "off" | "minutes" | "chapter"; minutes?: number }): Promise<NativeState>;
  extendSleep(options: { minutes?: number }): Promise<NativeState>;
  configure(options: {
    sleepExtendMinutes?: number;
    sleepFadeSeconds?: number;
    shakeToExtend?: boolean;
    shakeAction?: "extend" | "reset";
    shakeSensitivity?: "gentle" | "normal" | "firm";
    flipToPause?: boolean;
    headsetSkips?: boolean;
    rewindAfterMinutes?: number;
    rewindSeconds?: number;
    safetyStopHours?: number;
    schedule?: { from: string; to: string; minutes: number } | null;
    /** Giọng đọc của "Nghe ngay" (mã giọng của ReadAloud.voices); "" = giọng mặc định của máy. */
    readAloudVoice?: string;
    /** Cuốn của `readAloudVoice`: lõi nhớ giọng ấy cho cuốn ấy (ReadAloud.chooseFor); không có thì cuốn đang nạp. */
    readAloudBook?: string;
    /** Nhà cung cấp giọng trực tuyến người nghe đã đồng ý gửi chữ tới (listen/onlineConsent.ts): lõi tự sang chương chữ chỉ với những giọng ấy. */
    readAloudOnlineOk?: string[];
  }): Promise<NativeState>;
  /** Quyền hiện thông báo (Android 13+): "off" = chưa cho, khay thông báo / màn khoá không có nút tạm dừng, tua. `load` KHÔNG chờ quyền này. */
  notificationAccess(): Promise<{ state: "granted" | "off" }>;
  /** Hiện hộp xin quyền của hệ thống (chỉ gọi sau khi đã nói vì sao - android/notifications.ts). */
  requestNotificationAccess(): Promise<{ state: "granted" | "off" }>;
  /** Mở trang thông báo của ABook trong Cài đặt Android. */
  openNotificationSettings(): Promise<void>;
  lastNight(): Promise<{ session: BedtimeSession | null }>;
  dismissLastNight(): Promise<void>;
  addListener(event: "state", handler: (state: NativeState) => void): Promise<PluginListenerHandle>;
}

export interface RemoteBook {
  id: string;
  title: string;
  narrator: string;
  duration: number;
  chaptersTotal: number;
  chaptersAvailable: number;
  complete: boolean;
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
}

export interface ManifestChapter {
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
}

export interface LocalBook {
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
  samples: string[];
  /** Ảnh bìa thật tải về cùng gói (webui/covers.py), hoặc null. */
  cover?: { file: string; version: number; color: string; width: number; height: number } | null;
  state: ListeningState;
  bytes?: number;
  /** Chưa tải: nghe thẳng từ máy tính (Streaming.kt) - gói sách đã cất ở stream.json. */
  streamed?: boolean;
  /** Nghe thẳng từ thiết bị ghép (Peers.kt): tên thiết bị ấy. */
  sourceName?: string;
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
}

/** Tin của một lượt "Xuất MP3" (Mp3ExportWorker.kt): tiến độ (`done`/`total`), xong (`finished`), dừng (`stopped`) hay lỗi (`error`). */
export interface Mp3ExportEvent {
  bookId: string;
  run: string;
  done?: number;
  total?: number;
  finished?: boolean;
  files?: number;
  chaptersTotal?: number;
  folder?: string;
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
}

export interface EbookLibraryPlugin {
  info(): Promise<{ root: string }>;
  discover(options: { timeoutMs?: number }): Promise<{ computers: { host: string; port: number; name: string; kind?: string }[] }>;
  shareStatus(): Promise<ShareStatus>;
  setShare(options: { enabled: boolean }): Promise<ShareStatus>;
  sharePair(): Promise<ShareStatus>;
  shareCancelPairing(): Promise<ShareStatus>;
  shareRevoke(options: { id: string }): Promise<ShareStatus>;
  pair(options: { host: string; port: number; code: string; device?: string }): Promise<{ name: string }>;
  /** Máy đã ghép Bluetooth với điện thoại (BluetoothLink.kt); Android 12+ xin quyền "Thiết bị ở gần" lần đầu. */
  bluetoothDevices(): Promise<{ devices: { address: string; name: string; kind: "computer" | "phone"; abook: boolean }[] }>;
  /** Ghép máy tính chính qua Bluetooth - cùng mã 6 số, đi qua đường hầm; sau đó `connection().host` là "bt:<địa chỉ>". */
  pairBluetooth(options: { address: string; code: string; device?: string }): Promise<{ name: string }>;
  /** `fingerprint`: vân tay chứng chỉ TLS máy tính đã ghi lúc ghép (hex; Pin.kt) - để đối chiếu, "" nếu chưa có. */
  connection(): Promise<{ paired: boolean; host: string; port: number; name: string; fingerprint?: string }>;
  unpair(): Promise<void>;
  /** Studio từ xa: mở trang Studio của máy tính đã ghép (StudioActivity.kt, webui/remote_studio.py). */
  openStudio(): Promise<void>;
  /** Mở trang / file APK của bản phát hành mới bằng trình duyệt của máy (chỉ đường GitHub của ABook - updates.ts). */
  openRelease(options: { url: string }): Promise<void>;
  /** Thông báo Studio (StudioAlerts.kt): sách xong, dừng vì lỗi, có việc mới cần duyệt. `permitted`: Android cho đăng
   *  thông báo không (Android 13+ phải xin). */
  studioAlerts(): Promise<{ enabled: boolean; permitted: boolean }>;
  setStudioAlerts(options: { enabled: boolean }): Promise<{ enabled: boolean; permitted: boolean }>;
  remoteLibrary(): Promise<{ name: string; books: RemoteBook[] }>;
  download(options: { bookId: string; source?: string; remoteId?: string }): Promise<{ bookId: string }>;
  /** Thiết bị ghép ngoài máy tính chính (mạng trạm bước 2 - Peers.kt). */
  peers(): Promise<{ peers: { key: string; name: string; host: string; port: number }[] }>;
  peerPair(options: { host: string; port: number; code: string }): Promise<{ key: string; name: string }>;
  /** Ghép thiết bị đã ghép Bluetooth với điện thoại này - cùng mã 6 số, đi qua Bluetooth. */
  peerPairBluetooth(options: { address: string; code: string }): Promise<{ key: string; name: string }>;
  peerForget(options: { key: string }): Promise<void>;
  peerLibraries(): Promise<{ peers: PeerLibrary[] }>;
  remotePlayers(): Promise<{ players: RemotePlayer[] }>;
  /** Tìm lại loa / TV ngay (điện thoại tự tìm - PhoneCast); danh sách mới hiện ở lần `remotePlayers` kế. */
  scanPlayers(): Promise<void>;
  /** "load" mang mã cuốn của điện thoại này - bên native đổi sang mã của máy kia (hoặc từ chối: máy kia không có). */
  remoteCommand(options: { device: string; command: RemotePlayerCommand }): Promise<{ id?: string; ok?: boolean; message?: string }>;
  localBooks(): Promise<{ books: LocalBook[] }>;
  /** Sách trên máy tính chưa tải mà nghe thẳng được; máy tính không trả lời thì rỗng. */
  streamableBooks(): Promise<{ books: LocalBook[] }>;
  book(options: { id: string }): Promise<LocalBook>;
  readText(options: { id: string; path: string }): Promise<{ text: string }>;
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
  /** Lưu cuốn nhập từ file (kèm thay đổi của người nghe) thành file mới - hộp thoại "tạo file" của hệ thống hỏi chỗ lưu. `as` không nói:
   *  giữ loại file cuốn đã đến (`.abookproj` hay `.abook`). */
  saveBook(options: { id: string; as?: "abook" | "abookproj" }): Promise<{ saved: boolean; name?: string; size?: number; edits?: number }>;
  /** "Chia sẻ…": đóng cuốn (kèm thay đổi của người nghe) thành file rồi mở bảng chia sẻ của hệ thống (Zalo, Drive, email…). `as` không nói:
   *  sách nghe `.abook`. `shared: true` khi bảng chia sẻ đã mở. */
  shareBook(options: { id: string; as?: "abook" | "abookproj" }): Promise<{ shared: boolean; name?: string }>;
  /** "Xuất MP3 để nghe ở app khác" (Mp3Export.kt): thư mục MP3 như máy tính, chạy nền. Lần đầu (hay `pick`) hỏi chỗ lưu bằng bộ
   *  chọn thư mục của hệ thống rồi nhớ lại. `cover`: bìa tự vẽ (data URL PNG) khi sách không có bìa. Tiến độ / kết quả: sự kiện
   *  "mp3Export" mang cùng `run`. `started: false` khi không chọn thư mục. */
  exportMp3(options: { bookId: string; cover?: string; pick?: boolean }): Promise<{ started: boolean; run?: string; folder?: string; chapters?: number }>;
  addListener(event: "mp3Export", handler: (event: Mp3ExportEvent) => void): Promise<PluginListenerHandle>;
  deleteBook(options: { id: string }): Promise<void>;
  storage(): Promise<{ bytes: number; free: number }>;
  progress(options: { id: string; chapterId: number; seconds: number; duration: number }): Promise<ListeningState>;
  setChapterDone(options: { id: string; chapterId: number; done: boolean }): Promise<ListeningState>;
  setFinished(options: { id: string; finished: boolean }): Promise<ListeningState>;
  setRate(options: { id: string; rate: number }): Promise<void>;
  addBookmark(options: { id: string; chapterId: number; seconds: number; note: string }): Promise<Bookmark>;
  updateBookmark(options: { id: string; markId: string; note: string }): Promise<void>;
  deleteBookmark(options: { id: string; markId: string }): Promise<void>;
  syncState(options: { id: string }): Promise<ListeningState>;
  createRecord(options: { id: string; name: string }): Promise<{ records: ListeningRecord[] }>;
  activateRecord(options: { id: string; record: string }): Promise<{ records: ListeningRecord[] }>;
  renameRecord(options: { id: string; record: string; name: string }): Promise<{ records: ListeningRecord[] }>;
  deleteRecord(options: { id: string; record: string }): Promise<{ records: ListeningRecord[] }>;
  moveRecord(options: { id: string; record: string; book: string }): Promise<{ records: ListeningRecord[] }>;
  addListener(event: "download", handler: (event: DownloadEvent) => void): Promise<PluginListenerHandle>;
  /** Bộ chọn file của hệ thống để mở một file sách .abook; kết quả về qua sự kiện "import". */
  pickBook(): Promise<{ picked: boolean }>;
  addListener(event: "import", handler: (event: ImportEvent) => void): Promise<PluginListenerHandle>;
  /** App khác gửi tới một file EPUB / DOCX / PDF / TXT ("Mở bằng", chia sẻ): native đã chép nó như `pickSource` - giao diện mở bước
   *  xem trước của "Thêm sách từ file…". `error`: không chép được, câu cho người dùng. */
  addListener(event: "textPicked", handler: (event: { ref?: string; name?: string; pdf?: string; error?: string }) => void): Promise<PluginListenerHandle>;
  /** "Nhập nhạc của tôi…": hộp chọn file của hệ thống (nhiều bản một lúc), nhập từng bản vào kho nhạc của điện thoại (MusicStore.kt);
   *  trả khi nhập xong - cùng JSON như `/api/music/local/import` của máy tính - hay `{picked: false}` khi không chọn gì. */
  pickMusic(): Promise<{ picked: boolean } & Partial<ImportResult>>;
  addListener(event: "musicImport", handler: (event: { done: number; total: number }) => void): Promise<PluginListenerHandle>;
  /** "Thêm sách từ file…" (BookImport.kt + TextBook.kt): bộ chọn file / thư mục của hệ thống; chép thứ đã chọn vào thư mục tạm của app
   *  (`ref`). `pdf`: đường dẫn bản sao PDF - WebView lấy chữ bằng pdf.js (shared/pdfPages.ts) rồi đưa sang `previewImport`. */
  pickSource(options: { kind: "file" | "folder" }): Promise<{ picked: boolean; ref?: string; name?: string; pdf?: string }>;
  /** Đọc thứ đã chọn bằng luật nhập sách của Kotlin; PDF thì kèm `pages` (các dòng từng trang) pdf.js đã lấy ra. Lỗi đọc được: từ chối
   *  với câu cho người dùng. */
  previewImport(options: { ref: string; pages?: string[][]; title?: string; author?: string; splitChapters?: boolean }): Promise<ImportPreview>;
  /** Nhập thành sách chỉ-chữ (TextBook.kt → BookFileImport): `title` rỗng thì giữ tên của file sách. `chapters`: các hàng của bước xem trước
   *  người dùng giữ lại + tên mới của chúng (chỉ đổi tên); không có thì các chương mặc định (mục rất ngắn chưa tích). */
  createImport(options: { ref: string; title: string; separate?: boolean; chapters?: { index: number; title?: string }[] }): Promise<AddedBook>;
  discardImport(options: { ref: string }): Promise<void>;
}

/** Kết quả mở một file sách (.abook): mã sách vừa vào Thư viện, hay lý do không nhận. */
export interface ImportEvent {
  bookId?: string;
  title?: string;
  /** Cuốn đã có trên máy và đã có thay đổi của người nghe: số thay đổi được giữ nguyên (BookFileImport.Imported.keptEdits). */
  keptEdits?: number;
  error?: string;
}

/** "Nghe ngay" trên điện thoại (docs/LISTEN_ANYTHING.md mục 3): giọng của máy (Android TextToSpeech) và mốc thời gian câu / chữ mà LÕI NATIVE đọc ra.
 *  Chương chỉ-có-chữ vào hàng đợi `EbookPlayer.load` như chương thường (kèm `readAloudVoice`); JS chỉ hỏi giọng và mốc, không tự đọc. */
export interface ReadAloudPlugin {
  voices(): Promise<{ voices: ReadAloudVoice[] }>;
  /** Mốc hiện có của chương (mọi câu theo thứ tự; câu chưa đọc có mốc ước, không có `words`). */
  script(options: { bookId: string; chapterId: number }): Promise<ReadAloudTimings>;
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
  /** "Làm trước" (PrepareAhead.kt): việc nền của WorkManager đọc sẵn các chương này bằng đúng giọng ấy vào bộ đệm - chạy cả khi app đã đóng. */
  preparePlan(options: { bookId: string; voice: string; chapterIds: number[] }): Promise<PreparePlan>;
  prepareStart(options: { bookId: string; voice: string; chapterIds: number[]; label: string; chargingOnly?: boolean }): Promise<PrepareStatus>;
  prepareStatus(): Promise<PrepareStatus>;
  prepareCancel(): Promise<PrepareStatus>;
  prepareOptions(options: { chargingOnly: boolean }): Promise<PrepareStatus>;
  /** Tiến độ làm trước (sau mỗi đoạn, mỗi lần đổi). */
  addListener(event: "readAloudPrepare", handler: (status: PrepareStatus) => void): Promise<PluginListenerHandle>;
}

export const EbookPlayer = registerPlugin<EbookPlayerPlugin>("EbookPlayer");
export const ReadAloud = registerPlugin<ReadAloudPlugin>("ReadAloud");
export const EbookLibrary = registerPlugin<EbookLibraryPlugin>("EbookLibrary");
