import type { Bookmark, ListeningState } from "@/listen/model";
import type { NativeState, PeerLibrary, RemoteBook, ShareStatus } from "@/android/plugins";
import type { VieneuStatus } from "@/listen/vieneuModule";
import { emitNative, type NativeImpl } from "./capacitor";
import { respond } from "./desktopApi";
import { BOOKS, bookCast, chapterScript, chapterText, findBook, lastNight, localBook, type GalleryBook } from "./data";
import { NOW_SECONDS } from "./clock";
import { importPreview } from "./data";
import { galleryState, never } from "./state";

// Lõi native giả của app Android: sách trên máy, trình phát Media3, giọng đọc. Đọc / ghi vào thư viện giả trong bộ nhớ (mất khi tải lại trang).

const book = (id: unknown): GalleryBook => {
  const found = findBook(String(id));
  if (!found) throw new Error(`Không có sách ${String(id)}`);
  return found;
};

const onPhone = () => BOOKS.filter((item) => !item.streamed && !(item.producing && !item.chapters.some((chapter) => chapter.available)));

function touch(item: GalleryBook, change: (state: ListeningState) => ListeningState): ListeningState {
  item.state = { ...change(item.state), updatedAt: Math.floor(Date.now() / 1000) };
  return item.state;
}

// --- Trình phát ---------------------------------------------------------------------------------------------------------

const player: NativeState = {
  bookId: "",
  bookTitle: "",
  chapterId: null,
  chapterTitle: "",
  position: 0,
  duration: 0,
  playing: false,
  buffering: false,
  rate: 1,
  sleep: { mode: "off" },
};

function chapterOf(bookId: string, chapterId: number | null) {
  return findBook(bookId)?.chapters.find((chapter) => chapter.id === chapterId);
}

function changed(patch: Partial<NativeState>): NativeState {
  Object.assign(player, patch);
  const chapter = chapterOf(player.bookId, player.chapterId);
  if (chapter) {
    player.chapterTitle = chapter.subtitle ? `${chapter.title}: ${chapter.subtitle}` : chapter.title;
    player.duration = chapter.duration;
  }
  player.position = Math.max(0, Math.min(player.position, player.duration || player.position));
  const snapshot = { ...player, sleep: { ...player.sleep } };
  queueMicrotask(() => emitNative("EbookPlayer", "state", snapshot));
  return snapshot;
}

function step(delta: number): NativeState {
  const item = findBook(player.bookId);
  const index = item?.chapters.findIndex((chapter) => chapter.id === player.chapterId) ?? -1;
  const next = item?.chapters[index + delta];
  return next?.available ? changed({ chapterId: next.id, position: 0 }) : changed({});
}

export const ebookPlayer: NativeImpl = {
  getState: () => ({ ...player }),
  load: (options) =>
    changed({
      bookId: String(options.bookId),
      bookTitle: String(options.bookTitle),
      chapterId: Number(options.chapterId),
      position: Number(options.seconds) || 0,
      rate: Number(options.rate) || 1,
      playing: Boolean(options.autoplay) && galleryState.scenario.playing !== false,
    }),
  updateMetadata: (options) => changed({ bookTitle: String(options.title) }),
  play: () => changed({ playing: true }),
  pause: () => changed({ playing: false }),
  release: () => changed({ playing: false }),
  toggle: () => changed({ playing: !player.playing }),
  next: () => step(1),
  previous: () => step(-1),
  seekTo: (options) => changed({ position: Number(options.seconds) }),
  skip: (options) => changed({ position: player.position + Number(options.delta) }),
  jumpTo: (options) => changed({ chapterId: Number(options.chapterId), position: Number(options.seconds) || 0 }),
  setRate: (options) => changed({ rate: Number(options.rate) }),
  setSleep: (options) => {
    const mode = String(options.mode ?? "off") as NativeState["sleep"]["mode"];
    const minutes = Number(options.minutes) || 30;
    return changed({ sleep: mode === "off" ? { mode } : { mode, minutes, remaining: mode === "minutes" ? minutes * 60 : undefined, counting: player.playing } });
  },
  extendSleep: (options) =>
    changed({ sleep: { ...player.sleep, mode: "minutes", remaining: (player.sleep.remaining ?? 0) + (Number(options.minutes) || 10) * 60 } }),
  addBookmark: (options): Bookmark => {
    const item = book(player.bookId);
    const mark: Bookmark = { id: `bm${Date.now()}`, chapterId: player.chapterId ?? 1, seconds: player.position, note: String(options.note ?? ""), at: NOW_SECONDS, createdAt: NOW_SECONDS };
    touch(item, (state) => ({ ...state, bookmarks: [...state.bookmarks, mark] }));
    return mark;
  },
  lastNight: () => ({ session: galleryState.scenario.night ? lastNight() : null }),
  dismissLastNight: () => undefined,
  listenPrefs: () => ({}),
  configure: () => ({}),
  openNotificationSettings: () => undefined,
  notificationAccess: () => ({ state: "granted" }),
  requestNotificationAccess: () => ({ state: "granted" }),
};

// --- Thư viện trên máy ---------------------------------------------------------------------------------------------------

function remoteBook(item: GalleryBook, downloaded: boolean): RemoteBook {
  const local = localBook(item);
  return {
    id: item.id,
    title: item.title,
    narrator: item.narrator,
    duration: local.duration,
    chaptersTotal: local.chaptersTotal,
    chaptersAvailable: local.chaptersAvailable,
    complete: local.complete,
    producing: item.producing,
    bytes: local.bytes,
    updatedAt: item.state.updatedAt ?? null,
    downloaded,
    localChapters: downloaded ? local.chaptersAvailable : 0,
    cover: item.cover ? { color: item.cover.color, version: 1 } : null,
    localCoverVersion: downloaded && item.cover ? 1 : 0,
  };
}

const share = (): ShareStatus => ({
  running: false,
  name: "Điện thoại của Hà",
  port: 47631,
  addresses: [],
  pairing: null,
  blocked: false,
  devices: [],
  error: "",
  manufacturer: "samsung",
  backgroundAllowed: true,
});

const computer = () => (galleryState.scenario.paired === false ? null : { name: "Máy tính phòng khách", host: "192.168.1.20", port: 47630 });

const vieneu = (): VieneuStatus =>
  ({
    state: "missing",
    done: 0,
    total: 0,
    error: "",
    supported: true,
    reason: "",
    choices: [],
    parts: [],
    outdatedParts: [],
    outdatedBytes: 0,
    benchmark: {},
    benchmarking: false,
    suggestion: null,
    device: { cores: 8, ramGb: 8, gpu: "Mali-G68", runs: "cpu" },
    recommended: "supertonic",
  }) as VieneuStatus;

export const ebookLibrary: NativeImpl = {
  info: () => ({ root: "/data/user/0/vn.abook.player/files" }),
  localBooks: () => (galleryState.scenario.library === "loading" ? never() : galleryState.scenario.library === "error" ? Promise.reject(new Error("Không đọc được thư mục sách (bộ nhớ đầy)")) : {
    books: galleryState.scenario.library === "empty" ? [] : onPhone().map(localBook),
    notices: [],
  }),
  streamableBooks: () => ({
    books: galleryState.scenario.library === "full" && computer() ? BOOKS.filter((item) => item.streamed).map(localBook) : [],
  }),
  book: (options) => localBook(book(options.id)),
  readText: (options) => {
    const item = book(options.id);
    const path = String(options.path);
    const script = path.match(/^scripts\/(\d+)\.json$/);
    if (script) return { text: JSON.stringify(chapterScript(item, Number(script[1]))) };
    const text = path.match(/^texts\/(\d+)\.txt$/);
    if (text) return { text: chapterText(item, Number(text[1])) };
    if (path === "cast.json") return { text: item.imported ? "" : JSON.stringify(bookCast(item)) };
    return { text: "" };
  },
  readTexts: (options) => ({
    texts: (options.paths as string[]).map((path) => (ebookLibrary.readText({ id: options.id, path }) as { text: string }).text),
  }),
  capabilities: () => ({ toolchain: false, workshop: false, link: true, sync: true, local: true }),
  progress: (options) =>
    touch(book(options.id), (state) => ({ ...state, last: { chapterId: Number(options.chapterId), seconds: Number(options.seconds), at: NOW_SECONDS } })),
  saveReading: (options) => touch(book(options.id), (state) => state),
  setChapterDone: (options) => touch(book(options.id), (state) => state),
  setFinished: (options) => touch(book(options.id), (state) => ({ ...state, finished: Boolean(options.finished) })),
  setRate: (options) => void touch(book(options.id), (state) => ({ ...state, rate: Number(options.rate) })),
  setVoice: () => undefined,
  syncState: (options) => book(options.id).state,
  addBookmark: (options): Bookmark => {
    const mark: Bookmark = { id: `bm${Date.now()}`, chapterId: Number(options.chapterId), seconds: Number(options.seconds), note: String(options.note ?? ""), at: NOW_SECONDS };
    touch(book(options.id), (state) => ({ ...state, bookmarks: [...state.bookmarks, mark] }));
    return mark;
  },
  updateBookmark: () => undefined,
  deleteBookmark: (options) => void touch(book(options.id), (state) => ({ ...state, bookmarks: state.bookmarks.filter((mark) => mark.id !== options.markId) })),
  restoreBookmark: (options) => options.mark,
  storage: () => ({
    bytes: onPhone().reduce((sum, item) => sum + (localBook(item).bytes ?? 0), 0),
    free: 21_400_000_000,
    books: onPhone().map((item) => ({ id: item.id, title: item.title, bytes: localBook(item).bytes ?? 0 })),
  }),
  connection: () => {
    const paired = computer();
    return paired ? { paired: true, ...paired, deviceName: "Điện thoại của Hà", lastAddress: paired.host } : { paired: false, host: "", port: 0, name: "" };
  },
  remoteLibrary: () => ({ name: "Máy tính phòng khách", books: BOOKS.filter((item) => !item.imported).map((item) => remoteBook(item, !item.streamed)) }),
  peers: () => ({ peers: [] }),
  peerLibraries: (): { peers: PeerLibrary[] } => ({ peers: [] }),
  discover: () => ({ computers: computer() ? [] : [{ host: "192.168.1.20", port: 47630, name: "Máy tính phòng khách", kind: "computer" }] }),
  shareStatus: share,
  setShare: share,
  backgroundStatus: () => ({ manufacturer: "samsung", backgroundAllowed: true }),
  bluetoothPermission: () => ({ state: "granted" }),
  bluetoothDevices: () => ({ devices: [] }),
  studioComputers: () => ({ computers: computer() ? [{ key: "", name: "Máy tính phòng khách", holdsBook: true }] : [] }),
  studioAlerts: () => ({ enabled: true, permitted: true }),
  remotePlayers: () => ({ players: [] }),
  scanPlayers: () => undefined,
  exportJobs: () => ({ jobs: [] }),
  exportHistory: () => ({ exports: [] }),
  listOldSaves: () => ({ files: [] }),
  systemBars: () => undefined,
  sendEdits: () => ({ pending: 0, last: null }),
  m4bMusicState: () => ({ music: false, tracks: 0, missing: 0 }),
  deleteBook: () => ({ undo: "undo-1" }),
  undoDelete: () => undefined,
  download: (options) => ({ bookId: options.bookId }),
  diagnostics: () => ({ lines: [], files: [], bytes: 0 }),
  // Lệnh sửa sách "áp ngay" của điện thoại (android/localStudio.ts): cùng đường + JSON như máy chủ máy tính - đi vào máy chủ giả.
  studio: async (options) => {
    const reply = await respond(String(options.path), String(options.method ?? "GET"), (options.body ?? {}) as Record<string, unknown>);
    return { status: reply.status, body: reply.body };
  },
  // "Thêm sách từ file…": hộp chọn file của hệ thống trả một file EPUB tự đặt; xem trước đọc nó thành mục lục.
  pickSource: (options) => {
    const file = { ref: "content://gallery/tiem-sach-tren-gac-xep.epub", name: "Tiệm sách trên gác xép.epub" };
    return options.multiple ? { picked: true, items: [file] } : { picked: true, ...file };
  },
  previewImport: () => importPreview(),
  createImport: () => ({ id: "gac-xep", how: "new", chapters: 7 }),
  discardImport: () => undefined,
};

export const readAloud: NativeImpl = {
  voices: () => ({
    voices: [
      { id: "device:vi-vn-x-gft-local", name: "Tiếng Việt (giọng nữ)", provider: "device", online: false, default: true, gender: "female" },
      { id: "device:vi-vn-x-vic-local", name: "Tiếng Việt (giọng nam)", provider: "device", online: false, gender: "male" },
      { id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My", provider: "edge", online: true, gender: "female" },
    ],
  }),
  script: () => ({ segments: [] }),
  warmVoice: () => ({ started: false }),
  sample: () => ({ path: "" }),
  onlineProviders: () => ({ providers: [] }),
  vieneuStatus: vieneu,
  supertonicStatus: vieneu,
  voiceSpeed: () => ({ choice: "auto", voices: [] }),
  prepareStatus: () => ({ state: "idle", done: 0, total: 0, label: "", error: "" }),
  cacheUsage: () => ({ book: 0, total: 0 }),
};

export const capacitorApp: NativeImpl = {
  getInfo: () => ({ name: "ABook", id: "vn.abook.player", build: "138", version: "0.4.138" }),
  getState: () => ({ isActive: true }),
  getLaunchUrl: () => ({}),
  minimizeApp: () => undefined,
  exitApp: () => undefined,
  toggleBackButtonHandler: () => undefined,
};
