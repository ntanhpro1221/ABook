import type { MusicCredit, MusicCue } from "./musicBed";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";
import type { Bookmark, Cast, ListenBook, ListeningRecord, ListeningSession, ListeningState, NightSession, Script } from "./model";

// Nguồn dữ liệu của phía Nghe. Giao diện chỉ nói chuyện với giao diện này:
// máy tính cài bằng HTTP tới server cục bộ, Android cài bằng file gói sách trên máy.

export interface ListenSource {
  kind: "desktop" | "android";
  library(): Promise<ListenBook[]>;
  book(id: string): Promise<ListenBook>;
  script(bookId: string, chapterId: number): Promise<Script>;
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
  /** Hồ sơ nghe (nguồn nào chưa có thì giao diện ẩn đi); mỗi lệnh trả danh sách hồ sơ mới của cuốn. */
  records?: {
    create(bookId: string, name: string): Promise<ListeningRecord[]>;
    activate(bookId: string, recordId: string): Promise<ListeningRecord[]>;
    rename(bookId: string, recordId: string, name: string): Promise<ListeningRecord[]>;
    remove(bookId: string, recordId: string): Promise<ListeningRecord[]>;
  };
}

const SourceContext = createContext<ListenSource | null>(null);

export function SourceProvider({ source, children }: { source: ListenSource; children: ReactNode }) {
  return <SourceContext.Provider value={source}>{children}</SourceContext.Provider>;
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
