import type { MusicCues } from "./musicBed";
import type { PlaylistQueue } from "./playlistBed";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";
import type { Bookmark, BookmarkSentence, Cast, ListenBook, ListenChapter, ListeningRecord, ListeningSession, ListeningState, NightSession, Script } from "./model";
import type { EditsSyncState } from "@/shared/editsSync";
import type { TextImport } from "./textImport";
import { textScript } from "./textScript";
import type { ChapterText } from "./bookSearch";
import { timedTextScript, VOICE_CHANGED_EVENT, type ClipOptions, type ReadAloudClip, type ReadAloudTimings, type ReadAloudVoice } from "./readAloud";
import { bookVoiceCaption, chosenVoice, resolveVoice, runsOnThisMachine, voicesOf } from "./readAloudVoice";
import { retryChapterText } from "./labels";
import type { VieneuBackend } from "./VieneuModuleCard";
import type { PreparePlan, PrepareRequest, PrepareStatus, ReadAloudCacheUsage } from "./prepareAhead";

// Nguồn dữ liệu của phía Nghe. Giao diện chỉ nói chuyện với giao diện này:
// máy tính cài bằng HTTP tới server cục bộ, Android cài bằng file gói sách trên máy.

export interface SavedBook {
  saved: boolean;
  /** Tên file (điện thoại) hay đường dẫn đầy đủ (máy tính). */
  file?: string;
  /** Máy tính: thư mục chứa file - để mở bằng "Mở thư mục". */
  folder?: string;
  size?: number;
  /** Số thay đổi của người nghe nằm trong file. */
  edits?: number;
}

export interface ListenSource {
  kind: "desktop" | "android";
  library(): Promise<ListenBook[]>;
  book(id: string): Promise<ListenBook>;
  script(bookId: string, chapterId: number): Promise<Script>;
  /** Chữ của chương chỉ-có-chữ (`ListenChapter.state` "text"): màn đọc dựng các đoạn từ đây (textScript.ts). */
  chapterText(bookId: string, chapterId: number): Promise<string>;
  /** "Tìm trong sách" (bookSearch.ts): chữ của nhiều chương trong MỘT lần hỏi - sách hàng nghìn chương không phải hỏi từng chương. Dùng qua
   *  `chapterTexts`. Nguồn nào không có (điện thoại đọc file ngay trên máy) thì tìm từng chương như màn đọc. */
  searchTexts?(bookId: string, chapters: { id: number; text: boolean }[]): Promise<SearchText[]>;
  /** "Thêm sách từ file…" (textImport.ts); nguồn nào chưa có thì giao diện ẩn nút. */
  textImport?: TextImport;
  /** "Nghe ngay" (readAloud.ts): các giọng đọc có trên máy này và việc đọc một đoạn chữ thành clip (audio + mốc từng chữ). Nguồn nào chưa có
   *  thì chương chỉ-có-chữ chỉ đọc được bằng mắt. Android: lõi native tự đọc (plugin ReadAloud, android/readAloud.ts) nên không có `readAloudClip`. */
  readAloudVoices?(): Promise<ReadAloudVoice[]>;
  /** Mô-đun giọng VieNeu của nền tảng (tải / trạng thái) khi nguồn không phải máy chủ cục bộ: khối lỗi của trình phát tải giọng ngay tại chỗ qua đây. Máy tính dùng `desktopVieneu`. */
  vieneu?: VieneuBackend;
  readAloudClip?(voice: string, text: string, options?: ClipOptions): Promise<ReadAloudClip>;
  /** Nghe thử một giọng (Cài đặt › Giọng đọc, menu giọng của trình phát) hay một cách đọc ("Đọc từ này là…" - `options.readings`, cách đọc
   *  của cuốn `options.bookId`): đọc `text` bằng giọng ấy, trả địa chỉ phát được. */
  readAloudSample?(voice: string, text: string, options?: Pick<ClipOptions, "bookId" | "readings">): Promise<string>;
  /** "Làm trước" (prepareAhead.ts): đọc sẵn các chương này vào bộ đệm ở nền; nguồn nào chưa có thì giao diện ẩn nút. */
  readAloudPrepare?(request: PrepareRequest): Promise<PrepareStatus>;
  readAloudPrepareStatus?(): Promise<PrepareStatus>;
  readAloudPrepareCancel?(): Promise<PrepareStatus>;
  /** Điện thoại: ước trước khi bấm, "Chỉ khi đang sạc", dấu "Đã làm sẵn" từng chương. */
  readAloudPreparePlan?(request: PrepareRequest): Promise<PreparePlan>;
  readAloudPrepareOptions?(options: { chargingOnly: boolean }): Promise<PrepareStatus>;
  /** Máy tính: bản đọc đã làm (bộ đệm clip) của cuốn và của cả máy, và xoá phần của cuốn ("Xoá bản đọc đã làm" ở menu Giọng đọc). */
  readAloudCache?(bookId: string): Promise<ReadAloudCacheUsage>;
  readAloudCacheClear?(bookId: string): Promise<ReadAloudCacheUsage>;
  /** Cài đặt > Giọng đọc: bản đọc đã làm của cả máy (`book` luôn 0) và dọn hết. */
  readAloudCacheTotal?(): Promise<ReadAloudCacheUsage>;
  readAloudCacheClearAll?(): Promise<ReadAloudCacheUsage>;
  /** Làm trước được cả giọng trực tuyến - để nghe khi không có mạng (điện thoại, và máy tính xách tay lúc đi tàu / máy bay). */
  readAloudPrepareOnline?: boolean;
  /** Nơi tự đọc chương (lõi native Android) cho biết mốc thời gian câu / chữ đã có của một chương chỉ-có-chữ; chưa có gì thì null. */
  readAloudTimings?(bookId: string, chapterId: number): Promise<ReadAloudTimings | null>;
  cast(bookId: string): Promise<Cast>;
  /** Nhạc nền của một chương (rãnh nhạc của cuốn - webui/music_plan.py): mốc thời gian + đường lấy file. Nguồn nào
   *  chưa có thì trình phát không chơi nhạc nền. */
  musicCues?(bookId: string, chapterId: number): Promise<MusicCues>;
  /** Xin máy chủ tải sẵn bài nhạc `link` (bài của mốc kế, bài đầu chương kế - POST /api/music/warm): trả ngay, tải ở nền; hỏng thì im lặng
   *  (mốc ấy tới thì tự tải như cũ). Nguồn nào không có thì bài chỉ tải khi mốc của nó tới. */
  musicWarm?(link: string): void;
  /** Mở trang sách / trình phát của cuốn có giọng trên máy (VieNeu, Supertonic): xin nạp sẵn model của giọng ấy - trả ngay, nạp ở nền, hỏng hay máy không dư (pin yếu, thiếu RAM) thì im lặng
   *  (bấm phát nạp như cũ). Máy tính: POST /api/readaloud/warm; điện thoại: ReadAloud.warmVoice. */
  voiceWarm?(voice: string): void;
  /** Danh sách phát người nghe đã chọn cho cả cuốn (sách chỉ có chữ - playlistBed.ts): hàng bài theo thứ tự phát; không bài nào
   *  thì trình phát dùng mốc nhạc của chương như thường. Android: lõi native tự phát (MusicBed.kt). */
  musicPlaylist?(bookId: string): Promise<PlaylistQueue>;
  audioUrl(bookId: string, chapterId: number): string;
  sampleUrl(bookId: string, sampleId: number): string;
  voiceUrl(name: string): string;
  /** `record`: hồ sơ nghe mà trình phát đang phát - ghi vào đúng hồ sơ ấy dù máy khác vừa đổi hồ sơ đang dùng. */
  beginProgress?(bookId: string, sessionId: string, record?: string): Promise<unknown>;
  saveProgress(bookId: string, chapterId: number, seconds: number, duration: number, record?: string, anchor?: import("./readingAnchor").ReadingAnchor,
    delivery?: { sessionId?: string; revision?: number; keepalive?: boolean }): Promise<ListeningState | void>;
  setChapterDone(bookId: string, chapterId: number, done: boolean): Promise<ListeningState>;
  setFinished(bookId: string, finished: boolean): Promise<ListeningState>;
  setRate(bookId: string, rate: number): Promise<void>;
  /** Giọng Nghe ngay riêng của cuốn vào hồ sơ nghe - đi sang máy kia như tốc độ (soát a68 lỗi 8). */
  setVoice?(bookId: string, voice: string): Promise<void>;
  addBookmark(bookId: string, chapterId: number, seconds: number, note: string, record?: string, sentence?: BookmarkSentence): Promise<Bookmark>;
  /** Hỏi thiết bị kia bản mới nhất của hồ sơ nghe đang dùng (điện thoại hỏi máy tính đã ghép); máy tính là nơi giữ. */
  refreshListening?(bookId: string): Promise<void>;
  updateBookmark(bookId: string, id: string, note: string): Promise<void>;
  deleteBookmark(bookId: string, id: string): Promise<void>;
  /** Hoàn tác xoá dấu trang. */
  restoreBookmark(bookId: string, mark: Bookmark): Promise<void>;
  /** Đêm gần nhất có hẹn giờ ngủ (cho thẻ "Tối qua"). */
  lastNight(): Promise<{ bookId: string; night: NightSession } | null>;
  dismissNight(bookId: string, nightId: string | undefined): Promise<void>;
  /** Chỉ bộ máy phát web cần: lõi native tự ghi nhật ký đêm. */
  saveNight?(bookId: string, night: NightSession): Promise<void>;
  /** Lịch sử phiên nghe (nguồn nào chưa có thì tab Lịch sử ẩn đi). */
  sessions?(bookId: string): Promise<ListeningSession[]>;
  addSession?(bookId: string, session: ListeningSession, record?: string): Promise<void>;
  /** Gửi được cả lúc trang đang đóng (fetch keepalive). */
  addSessionOnExit?(bookId: string, session: ListeningSession, record?: string): void;
  /** Chỗ đọc dở ở chế độ đọc (nguồn nào không có thì giao diện tự nhớ trong máy). */
  saveReading?(bookId: string, chapterId: number, index: number, position?: import("./readingPosition").ReadingPosition, record?: string): Promise<void>;
  /** Lưu cuốn nhập từ file (kèm thay đổi của người nghe) thành file `.abook` mới: máy tính ghi vào thư mục xuất (hay
   *  `folder`), điện thoại hỏi chỗ lưu bằng hộp thoại của hệ thống lần đầu rồi nhớ (`ask` hỏi lại). `saved: false` khi người dùng bỏ qua. */
  saveBook?(bookId: string, options?: { folder?: string; as?: "abook" | "abookproj"; ask?: boolean }): Promise<SavedBook>;
  /** Điện thoại: gửi file sách `.abook` của cuốn (kèm thay đổi của người nghe) qua bảng chia sẻ của hệ thống. */
  shareBook?(bookId: string): Promise<void>;
  /** Điện thoại: gửi ngay phần sửa của cuốn tải từ máy tính về máy tính (EditsSync.kt); trả trạng thái mới, lỗi thì nói lý do. */
  sendEdits?(bookId: string): Promise<EditsSyncState>;
  /** Hồ sơ nghe (nguồn nào chưa có thì giao diện ẩn đi); mỗi lệnh trả danh sách hồ sơ mới của cuốn. */
  records?: {
    create(bookId: string, name: string): Promise<ListeningRecord[]>;
    activate(bookId: string, recordId: string): Promise<ListeningRecord[]>;
    rename(bookId: string, recordId: string, name: string): Promise<ListeningRecord[]>;
    remove(bookId: string, recordId: string): Promise<ListeningRecord[]>;
    /** Gắn hồ sơ sang cuốn `toBook` (bản làm lại của cùng truyện…), thành hồ sơ đang dùng ở đó; trả hồ sơ còn lại của cuốn này. */
    move(bookId: string, recordId: string, toBook: string): Promise<ListeningRecord[]>;
  };
}

/** Chữ một chương trong kết quả `searchTexts`: chương nghe được thì các câu của kịch bản (chữ + dấu ngăn cảnh), chương chỉ-có-chữ (xin với
 *  `text: true`) thì chữ thô; `failed` khi chương không đọc được. Máy chủ có thể trả ít chương hơn số xin (chữ quá nhiều). */
export interface SearchText {
  id: number;
  segments?: { text: string; sceneBreak?: boolean }[];
  text?: string;
  failed?: boolean;
}

const SourceContext = createContext<ListenSource | null>(null);

function needsSpeech(book: ListenBook): boolean {
  return Boolean(book.chapters?.some((chapter) => chapter.state === "text"));
}

function markSpeech(book: ListenBook, can: boolean): ListenBook {
  if (!can || !book.chapters || !needsSpeech(book)) return book;
  return { ...book, chapters: book.chapters.map((chapter) => (chapter.state === "text" ? { ...chapter, speech: true } : chapter)) };
}

/** Nguồn có giọng đọc thì chương chỉ-có-chữ nghe được ngay: gắn `speech` vào chương ở MỌI nơi sách đi qua (thư viện, trang sách, trình phát) -
 *  chỗ nào cũng hỏi `canPlay(chapter)` thay vì tự biết giọng. Không giọng nào (offline mà máy cũng không có giọng): chương vẫn chỉ đọc. */
export function withReadAloud(source: ListenSource): ListenSource {
  if (!source.readAloudVoices) return source;
  const speaks = async () => (await voicesOf(source)).length > 0;
  return {
    ...source,
    readAloudVoices: () => voicesOf(source),
    book: async (id) => markSpeech(await source.book(id), await speaks()),
    library: async () => {
      // Hỏi giọng chỉ khi có cuốn mang chương chỉ-có-chữ (điện thoại: danh sách thư viện không kèm chương nên hầu như không bao giờ):
      // chờ danh sách giọng (lõi đọc to khởi động, hỏi cả dịch vụ trực tuyến) làm thư viện trống hiện skeleton cả chục giây (soát UX a9).
      const books = await source.library();
      if (!books.some(needsSpeech)) return books;
      const can = await speaks();
      return books.map((book) => markSpeech(book, can));
    },
  };
}

export function SourceProvider({ source, children }: { source: ListenSource; children: ReactNode }) {
  const wrapped = useMemo(() => withReadAloud(source), [source]);
  return <SourceContext.Provider value={wrapped}>{children}</SourceContext.Provider>;
}

export function useSource(): ListenSource {
  const source = useContext(SourceContext);
  if (!source) throw new Error("useSource ngoài SourceProvider");
  return source;
}

/** `poll`: hỏi lại theo nhịp (30 giây, 5 giây khi có sách đang làm). Chỗ chỉ cần danh sách MỘT lần (khôi phục cuốn đang nghe dở khi mở app, mời tập kế)
 *  truyền false - thư viện lớn (300 cuốn) mất ~1,3 giây mỗi lần hỏi, mà trang dự án đứng đó cả giờ vẫn bị hỏi mỗi 30 giây (soát a21). */
export function useListenLibrary(poll = true) {
  const source = useSource();
  return useQuery({
    queryKey: ["listen", "library"],
    queryFn: () => source.library(),
    refetchInterval: poll ? (query) => (query.state.data?.some((book) => book.producing) ? 5000 : 30000) : false,
  });
}

/** Sách không có (404) thì báo ngay, đừng thử lại ba lần rồi mới báo. */
function retryUnlessMissing(count: number, error: unknown): boolean {
  return !isMissing(error) && count < 2;
}

/** Lỗi "không có sách này" (404) của nguồn. */
export function isMissing(error: unknown): boolean {
  return (error as { status?: number } | null)?.status === 404;
}

/** `poll` false: chỉ đọc bản đã có và làm mới khi có chỗ báo đổi (thanh phát trên mọi trang, kể cả trang dự án: nó chỉ cần cờ bỏ qua của chương). */
export function useListenBook(id: string | undefined, poll = true) {
  const source = useSource();
  return useQuery({
    queryKey: ["listen", "book", id],
    enabled: Boolean(id),
    retry: retryUnlessMissing,
    queryFn: () => source.book(id!),
    // Sách đã bị xoá (404) thì thôi hỏi lại mỗi 30 giây - mỗi lần là một dòng đỏ trong console (soát UX a17).
    refetchInterval: poll ? (query) => (isMissing(query.state.error) ? false : query.state.data?.producing ? 5000 : 30000) : false,
  });
}

export function useScript(bookId: string | undefined, chapterId: number | undefined) {
  const source = useSource();
  return useQuery({
    queryKey: ["listen", "script", bookId, chapterId],
    enabled: Boolean(bookId && chapterId),
    queryFn: () => source.script(bookId!, chapterId!),
    staleTime: Infinity,
  });
}

/** Chương chỉ-có-chữ: màn đọc dựng các đoạn từ chữ thô (`textChapterScript`), không phải kịch bản của máy chủ. */
const isTextOnly = (chapter: ListenChapter) => chapter.state === "text";

/** Các đoạn màn đọc dựng từ chữ của một chương chỉ-có-chữ (bỏ các dòng người nghe đã bỏ khỏi phần đọc). */
function textChapterScript(chapter: ListenChapter, text: string): Script {
  return textScript(chapter.id, chapter.title, text, chapter.skip);
}

/** Chữ của nhiều chương qua `source.searchTexts` (ô "Tìm trong sách"): cùng các đoạn, cùng chỉ số đoạn với `chapterScriptQuery` của màn đọc.
 *  Chương không đọc được: null; chương máy chủ chưa trả (lô quá nặng) không có trong kết quả. */
export async function chapterTexts(source: ListenSource, bookId: string, chapters: readonly ListenChapter[]): Promise<Map<number, ChapterText | null>> {
  const byId = new Map(chapters.map((chapter) => [chapter.id, chapter]));
  const out = new Map<number, ChapterText | null>();
  for (const item of await source.searchTexts!(bookId, chapters.map((chapter) => ({ id: chapter.id, text: isTextOnly(chapter) })))) {
    const chapter = byId.get(item.id);
    if (!chapter) continue;
    if (!item.failed && typeof item.text === "string" && isTextOnly(chapter)) out.set(item.id, textChapterScript(chapter, item.text));
    else if (!item.failed && Array.isArray(item.segments)) out.set(item.id, { segments: item.segments });
    else out.set(item.id, null);
  }
  return out;
}

/** Truy vấn kịch bản của một chương: chương nghe được có mốc, chương chữ dựng từ chữ. Native trả cả chữ và mốc của bản đang nạp;
 *  desktop giữ snapshot đang phát ở khoá playing-script, tách khỏi bản dùng cho lần nạp sau. */
export function chapterScriptQuery(source: ListenSource, bookId: string, chapter: ListenChapter) {
  const textOnly = isTextOnly(chapter);
  return {
    queryKey: chapterScriptKey(bookId, chapter),
    queryFn: async (): Promise<Script> => {
      if (!textOnly) return source.script(bookId, chapter.id);
      const script = textChapterScript(chapter, await source.chapterText(bookId, chapter.id));
      // Chương đã được đọc to (lõi native tự đọc): mốc thời gian đã có thì gắn vào, màn đọc sáng đoạn / chữ ngay khi mở.
      const timings = await source.readAloudTimings?.(bookId, chapter.id).catch(() => null);
      return timings ? timedTextScript(script, timings) : script;
    },
    staleTime: Infinity,
  };
}

export function useChapterScript(bookId: string | undefined, chapter: ListenChapter | undefined) {
  const source = useSource();
  const active = useQuery<Script | null>({ queryKey: ["playing-script", bookId], queryFn: () => null, enabled: false, staleTime: Infinity });
  const query = useQuery({
    queryKey: chapterScriptKey(bookId, chapter),
    enabled: Boolean(bookId && chapter),
    queryFn: () => chapterScriptQuery(source, bookId!, chapter!).queryFn(),
    staleTime: Infinity,
    retry: retryChapterText,
  });
  return source.kind !== "android" && active.data && active.data.chapterId === chapter?.id ? { ...query, data: active.data } : query;
}

export function chapterScriptKey(bookId: string | undefined, chapter: ListenChapter | undefined) {
  const base = ["listen", "script", bookId, chapter?.id, chapter?.state === "text" ? "text" : "audio"] as const;
  return chapter?.state === "text" ? base : [...base, chapter?.available, chapter?.duration, chapter?.audioVersion, chapter?.wordsVersion];
}

/** Nhật ký đêm gần nhất (thẻ "Tối qua" ở Thư viện); null: máy này chưa có đêm nào ghi lại. */
export function useLastNight() {
  const source = useSource();
  return useQuery({ queryKey: ["listen", "night"], queryFn: () => source.lastNight(), staleTime: 60_000 });
}

/** Các giọng đọc của máy này (rỗng khi nguồn không có). */
export function useReadAloudVoices() {
  const source = useSource();
  return useQuery({
    queryKey: ["readaloud", "voices"],
    queryFn: () => voicesOf(source),
    staleTime: 60_000,
  });
}

export function useCast(bookId: string | undefined) {
  const source = useSource();
  return useQuery({
    queryKey: ["listen", "cast", bookId],
    enabled: Boolean(bookId),
    queryFn: () => source.cast(bookId!),
    staleTime: 60_000,
  });
}

/** Mọi thay đổi trạng thái nghe làm mới thư viện và trang sách. */
export function useListenMutations(bookId: string) {
  const source = useSource();
  const client = useQueryClient();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["listen", "book", bookId] });
    void client.invalidateQueries({ queryKey: ["listen", "library"] });
  };
  return {
    chapterDone: useMutation({
      mutationFn: ({ chapterId, done }: { chapterId: number; done: boolean }) => source.setChapterDone(bookId, chapterId, done),
      onSuccess: refresh,
    }),
    finished: useMutation({
      mutationFn: (finished: boolean) => source.setFinished(bookId, finished),
      onSuccess: refresh,
    }),
    addBookmark: useMutation({
      mutationFn: ({ chapterId, seconds, note, sentence }: { chapterId: number; seconds: number; note: string; sentence?: BookmarkSentence }) =>
        source.addBookmark(bookId, chapterId, seconds, note, undefined, sentence),
      onSuccess: refresh,
    }),
    updateBookmark: useMutation({
      mutationFn: ({ id, note }: { id: string; note: string }) => source.updateBookmark(bookId, id, note),
      onSuccess: refresh,
    }),
    deleteBookmark: useMutation({
      mutationFn: (id: string) => source.deleteBookmark(bookId, id),
      onSuccess: refresh,
    }),
    restoreBookmark: useMutation({
      mutationFn: (mark: Bookmark) => source.restoreBookmark(bookId, mark),
      onSuccess: refresh,
    }),
    createRecord: useMutation({
      mutationFn: (name: string) => source.records!.create(bookId, name),
      onSuccess: refresh,
    }),
    activateRecord: useMutation({
      mutationFn: (recordId: string) => source.records!.activate(bookId, recordId),
      onSuccess: refresh,
    }),
    renameRecord: useMutation({
      mutationFn: ({ recordId, name }: { recordId: string; name: string }) => source.records!.rename(bookId, recordId, name),
      onSuccess: refresh,
    }),
    removeRecord: useMutation({
      mutationFn: (recordId: string) => source.records!.remove(bookId, recordId),
      onSuccess: refresh,
    }),
    moveRecord: useMutation({
      mutationFn: ({ recordId, toBook }: { recordId: string; toBook: string }) => source.records!.move(bookId, recordId, toBook),
      onSuccess: (_records, { toBook }) => {
        refresh();
        void client.invalidateQueries({ queryKey: ["listen", "book", toBook] });
      },
    }),
  };
}

/** Vẽ lại khi người nghe đổi giọng đọc ở BẤT KỲ đâu (menu giọng khác, Cài đặt): mọi chỗ đọc `chosenVoice` lúc vẽ dùng cái này để không giữ giọng cũ. */
function useVoiceChanged(): void {
  const [, bump] = useReducer((count: number) => count + 1, 0);
  useEffect(() => {
    window.addEventListener(VOICE_CHANGED_EVENT, bump);
    return () => window.removeEventListener(VOICE_CHANGED_EVENT, bump);
  }, []);
}

/** Giọng đã chọn cho cuốn `bookId` ("" = mặc định của máy); đổi giọng ở nơi khác cũng cập nhật ngay. */
export function useChosenVoice(bookId: string | undefined): string {
  useVoiceChanged();
  return bookId ? chosenVoice(bookId) : "";
}

/** Giọng có engine nạp sẵn được: VieNeu, Supertonic (giọng của máy - TextToSpeech của hệ điều hành - không có gì để nạp). */
export function hasLocalEngine(voice: Pick<ReadAloudVoice, "online" | "provider"> | undefined): boolean {
  return runsOnThisMachine(voice) && (voice?.provider === "vieneu" || voice?.provider === "supertonic");
}

/** Trang sách / trình phát của cuốn `bookId` đang mở: giọng đang chọn chạy trên máy thì xin nạp sẵn model ([ListenSource.voiceWarm]) để bấm phát không phải chờ nạp. Đổi sang giọng khác
 *  cũng nạp giọng ấy; mỗi lần mở là một lần dùng (model nhả lại sau 3 phút không ai dùng). */
export function useWarmVoice(bookId: string | undefined): void {
  const source = useSource();
  const voices = useReadAloudVoices().data;
  useVoiceChanged();
  const voice = bookId && voices?.length ? resolveVoice(voices, chosenVoice(bookId)) : undefined;
  const id = hasLocalEngine(voice) ? voice!.id : "";
  useEffect(() => {
    if (id) source.voiceWarm?.(id);
  }, [source, id]);
}

/** Tên giọng đang đọc cuốn `bookId` ("Hoài My (Edge)", "Giọng đọc của máy"); "" khi máy chưa báo giọng nào. Đổi giọng giữa chừng thì cập nhật ngay. */
export function useBookVoice(bookId: string | undefined): string {
  const voices = useReadAloudVoices().data;
  useVoiceChanged();
  return bookId ? bookVoiceCaption(voices, bookId) : "";
}
