import type { MusicCredit, MusicCue } from "./musicBed";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { Bookmark, Cast, ListenBook, ListenChapter, ListeningRecord, ListeningSession, ListeningState, NightSession, Script } from "./model";
import type { EditsSyncState } from "@/shared/editsSync";
import type { TextImport } from "./textImport";
import { textScript } from "./textScript";
import { mergeTimings, type ClipOptions, type ReadAloudClip, type ReadAloudTimings, type ReadAloudVoice } from "./readAloud";
import { voicesOf } from "./readAloudVoice";

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
  /** "Thêm sách từ file…" (textImport.ts); nguồn nào chưa có thì giao diện ẩn nút. */
  textImport?: TextImport;
  /** "Nghe ngay" (readAloud.ts): các giọng đọc có trên máy này và việc đọc một đoạn chữ thành clip (audio + mốc từng chữ). Nguồn nào chưa có
   *  thì chương chỉ-có-chữ chỉ đọc được bằng mắt. Android: lõi native tự đọc (plugin ReadAloud, android/readAloud.ts) nên không có `readAloudClip`. */
  readAloudVoices?(): Promise<ReadAloudVoice[]>;
  readAloudClip?(voice: string, text: string, options?: ClipOptions): Promise<ReadAloudClip>;
  /** Nơi tự đọc chương (lõi native Android) cho biết mốc thời gian câu / chữ đã có của một chương chỉ-có-chữ; chưa có gì thì null. */
  readAloudTimings?(bookId: string, chapterId: number): Promise<ReadAloudTimings | null>;
  cast(bookId: string): Promise<Cast>;
  /** Nhạc nền của một chương (rãnh nhạc của cuốn - webui/music_plan.py): mốc thời gian + đường lấy file. Nguồn nào
   *  chưa có thì trình phát không chơi nhạc nền. */
  musicCues?(bookId: string, chapterId: number): Promise<{ cues: MusicCue[]; levelDb: number; credits?: Record<string, MusicCredit> }>;
  audioUrl(bookId: string, chapterId: number): string;
  sampleUrl(bookId: string, sampleId: number): string;
  voiceUrl(name: string): string;
  /** `record`: hồ sơ nghe mà trình phát đang phát - ghi vào đúng hồ sơ ấy dù máy khác vừa đổi hồ sơ đang dùng. */
  saveProgress(bookId: string, chapterId: number, seconds: number, duration: number, record?: string): Promise<ListeningState | void>;
  setChapterDone(bookId: string, chapterId: number, done: boolean): Promise<ListeningState>;
  setFinished(bookId: string, finished: boolean): Promise<ListeningState>;
  setRate(bookId: string, rate: number): Promise<void>;
  addBookmark(bookId: string, chapterId: number, seconds: number, note: string, record?: string): Promise<Bookmark>;
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
  saveReading?(bookId: string, chapterId: number, index: number): Promise<void>;
  /** Lưu cuốn nhập từ file (kèm thay đổi của người nghe) thành file `.abook` mới: máy tính ghi vào thư mục xuất (hay
   *  `folder`), điện thoại hỏi chỗ lưu bằng hộp thoại của hệ thống. `saved: false` khi người dùng bỏ qua. */
  saveBook?(bookId: string, options?: { folder?: string; as?: "abook" | "abookproj" }): Promise<SavedBook>;
  /** Điện thoại: gửi ngay phần sửa của cuốn tải từ máy tính về máy tính (EditsSync.kt); trả trạng thái mới, lỗi thì nói lý do. */
  sendEdits?(bookId: string): Promise<EditsSyncState>;
  /** Hồ sơ nghe (nguồn nào chưa có thì giao diện ẩn đi); mỗi lệnh trả danh sách hồ sơ mới của cuốn. */
  records?: {
    create(bookId: string, name: string): Promise<ListeningRecord[]>;
    activate(bookId: string, recordId: string): Promise<ListeningRecord[]>;
    rename(bookId: string, recordId: string, name: string): Promise<ListeningRecord[]>;
    remove(bookId: string, recordId: string): Promise<ListeningRecord[]>;
  };
}

const SourceContext = createContext<ListenSource | null>(null);

function markSpeech(book: ListenBook, can: boolean): ListenBook {
  if (!can || !book.chapters?.some((chapter) => chapter.state === "text")) return book;
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
      const [books, can] = await Promise.all([source.library(), speaks()]);
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

export function useListenLibrary() {
  const source = useSource();
  return useQuery({
    queryKey: ["listen", "library"],
    queryFn: () => source.library(),
    refetchInterval: (query) => (query.state.data?.some((book) => book.producing) ? 5000 : 30000),
  });
}

/** Sách không có (404) thì báo ngay, đừng thử lại ba lần rồi mới báo. */
function retryUnlessMissing(count: number, error: unknown): boolean {
  return (error as { status?: number } | null)?.status !== 404 && count < 2;
}

export function useListenBook(id: string | undefined) {
  const source = useSource();
  return useQuery({
    queryKey: ["listen", "book", id],
    enabled: Boolean(id),
    retry: retryUnlessMissing,
    queryFn: () => source.book(id!),
    refetchInterval: (query) => (query.state.data?.producing ? 5000 : 30000),
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

/** Truy vấn kịch bản để ĐỌC của một chương: chương nghe được thì kịch bản có mốc thời gian, chương chỉ-có-chữ thì các đoạn dựng từ chữ. Dùng chung với
 *  trình phát (nó đọc to chương chữ và ghi mốc thời gian vào đúng khoá này - readAloud.ts). */
export function chapterScriptQuery(source: ListenSource, bookId: string, chapter: ListenChapter) {
  const textOnly = chapter.state === "text";
  return {
    queryKey: ["listen", "script", bookId, chapter.id, textOnly ? "text" : "audio"] as const,
    queryFn: async (): Promise<Script> => {
      if (!textOnly) return source.script(bookId, chapter.id);
      const script = textScript(chapter.id, chapter.title, await source.chapterText(bookId, chapter.id));
      // Chương đã được đọc to (lõi native tự đọc): mốc thời gian đã có thì gắn vào, màn đọc sáng đoạn / chữ ngay khi mở.
      const timings = await source.readAloudTimings?.(bookId, chapter.id).catch(() => null);
      return timings ? mergeTimings(script, timings) : script;
    },
    staleTime: Infinity,
  };
}

export function useChapterScript(bookId: string | undefined, chapter: ListenChapter | undefined) {
  const source = useSource();
  return useQuery({
    queryKey: ["listen", "script", bookId, chapter?.id, chapter?.state === "text" ? "text" : "audio"] as const,
    enabled: Boolean(bookId && chapter),
    queryFn: () => chapterScriptQuery(source, bookId!, chapter!).queryFn(),
    staleTime: Infinity,
  });
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
      mutationFn: ({ chapterId, seconds, note }: { chapterId: number; seconds: number; note: string }) =>
        source.addBookmark(bookId, chapterId, seconds, note),
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
  };
}
