import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  api,
  type ActivityItem,
  type AppInfo,
  type BookSummary,
  type Cast,
  type Chapter,
  type ContinuationPlan,
  type RedoPlan,
  type FirstPersonHint,
  type Preferences,
  type ScanResult,
  type Script,
  type Voice,
} from "./api";
import type { Phase } from "./api";
import type { Tone } from "@/shared/ui";
import { pollDelay, retryUnlessGone } from "./polling";

export function phaseTone(phase: Phase, running: boolean): Tone {
  if (phase === "done") return "success";
  if (phase === "error") return "danger";
  if (running) return "accent";
  // Làm dở mà không chạy: cần người dùng để ý (bấm Tiếp tục) - không phải trạng thái trung tính.
  if (phase === "analysis" || phase === "casting" || phase === "synthesis" || phase === "stopped") return "warning";
  return "muted";
}

// Nhịp hỏi server: sách đang chạy thì 2 giây (thanh tiến độ phải sống), không thì thưa hẳn.
const LIVE_MS = 2000;
const IDLE_MS = 15000;

export function useAppInfo() {
  return useQuery({ queryKey: ["app"], queryFn: () => api<AppInfo>("/api/app"), staleTime: Infinity });
}

/** App đóng gói chưa cài (hay cần cập nhật) Studio: xem, nghe, sửa cách đọc / nhạc nền / bìa, xuất sách vẫn làm được - chỉ phần
 *  phân tích và thu âm cần Studio. Bấm chúng thì nói rõ điều đó và chỉ chỗ cài, thay vì để lỗi khởi động hiện ra sau. */
export function useStudioMissing(): { missing: boolean; update: boolean } {
  const studio = useAppInfo().data?.studio;
  return { missing: Boolean(studio && (!studio.installed || studio.outdated)), update: Boolean(studio?.installed && studio.outdated) };
}

/** `live`: đang ở Studio thì tiến độ sách đang chạy cập nhật 5 giây một lần; ở nơi khác (thanh bên) thì thưa hẳn -
 *  app có thể mở suốt nhiều giờ sản xuất, và mỗi lần hỏi là một lượt đọc DB của sách đang chạy. */
export function useLibrary({ live = true }: { live?: boolean } = {}) {
  return useQuery({
    queryKey: ["library"],
    queryFn: () => api<{ root: string; books: BookSummary[] }>("/api/library"),
    refetchInterval: (query) =>
      query.state.data?.books.some((book) => book.running || book.starting) ? (live ? 5000 : 20000) : IDLE_MS,
  });
}

export function fetchBook(id: string | undefined) {
  return api<{ book: BookSummary; chapters: Chapter[] }>(`/api/books/${id}`);
}

/** Đọc bản của trang dự án trong bộ nhớ đệm mà không thêm nhịp hỏi máy chủ. Vẫn mang queryFn thật (enabled: false thay vì
 *  skipToken): React Query chạy lại khoá này bằng tuỳ chọn của người quan sát gặp sau cùng, nên một người quan sát skipToken
 *  làm lần làm mới sau một quyết định ném "Missing queryFn" và trang dự án chết (soát UX a8). */
export function useCachedBook(id: string | undefined) {
  return useQuery({ queryKey: ["book", id], queryFn: () => fetchBook(id), enabled: false });
}

export function useBook(id: string | undefined) {
  return useQuery({
    queryKey: ["book", id],
    enabled: Boolean(id),
    queryFn: () => fetchBook(id),
    retry: retryUnlessGone,
    // Sách đã mất (404) thì thôi hỏi; máy chủ lỗi thì lùi dần (polling.ts).
    refetchInterval: (query) => pollDelay(query.state.data?.book.running || query.state.data?.book.starting ? LIVE_MS * 1.5 : IDLE_MS, query.state),
  });
}

export function useCast(id: string | undefined, live: boolean) {
  return useQuery({
    queryKey: ["cast", id],
    enabled: Boolean(id),
    queryFn: () => api<Cast>(`/api/books/${id}/cast`),
    retry: retryUnlessGone,
    refetchInterval: (query) => pollDelay(live ? 20000 : false, query.state),
  });
}

export function useActivity(id: string | undefined, technical: boolean, live: boolean) {
  return useQuery({
    queryKey: ["activity", id, technical],
    enabled: Boolean(id),
    queryFn: () => api<ActivityItem[]>(`/api/books/${id}/activity${technical ? "?technical=1" : ""}`),
    retry: retryUnlessGone,
    refetchInterval: (query) => pollDelay(live ? 5000 : false, query.state),
  });
}

export function useScript(bookId: string | undefined, chapterId: number | undefined) {
  return useQuery({
    queryKey: ["script", bookId, chapterId],
    enabled: Boolean(bookId && chapterId),
    queryFn: () => api<Script>(`/api/books/${bookId}/chapters/${chapterId}/script`),
    staleTime: Infinity,
  });
}

export function useVoices() {
  return useQuery({ queryKey: ["voices"], queryFn: () => api<Voice[]>("/api/voices"), staleTime: Infinity });
}

function useRefresh() {
  const client = useQueryClient();
  return (id?: string) => {
    void client.invalidateQueries({ queryKey: ["library"] });
    if (id) void client.invalidateQueries({ queryKey: ["book", id] });
  };
}

export function useStart() {
  const refresh = useRefresh();
  return useMutation({
    scope: { id: "start-stop" },
    mutationFn: (id: string) => api<BookSummary>(`/api/books/${id}/start`, { method: "POST" }),
    onSuccess: (book, id) => {
      refresh(id);
      if (book.queuePosition) {
        toast("Đã xếp hàng", {
          description: "Một cuốn khác đang chạy - cuốn này tự bắt đầu khi cuốn kia xong (app cần đang mở).",
        });
        return;
      }
      toast.success("Đang khởi động", { description: "Sách chạy nền - đóng cửa sổ cũng không dừng." });
    },
    onError: (error: Error) => toast.error("Không bắt đầu được", { description: error.message }),
  });
}

/** `paused` / `queued`: sách đang ở trạng thái nào lúc bấm - thông báo nói đúng điều xảy ra (soát UX 30-09: dừng một sách
 *  đang tạm dừng vẫn báo "dừng ở câu đang làm dở", bỏ xếp hàng cũng vậy). */
export function useStop() {
  const refresh = useRefresh();
  return useMutation({
    scope: { id: "start-stop" },
    mutationFn: ({ id }: { id: string; paused?: boolean; queued?: boolean }) =>
      api<BookSummary>(`/api/books/${id}/stop`, { method: "POST" }),
    onSuccess: (_book, { id, paused, queued }) => {
      refresh(id);
      if (queued) {
        toast("Đã bỏ xếp hàng", { description: "Cuốn này không tự bắt đầu nữa." });
        return;
      }
      toast("Đang dừng", {
        description: paused
          ? "Sách dừng hẳn và nhả bộ nhớ card đồ hoạ; mọi thứ đã xong được giữ nguyên."
          : "Sách sẽ dừng ở câu đang làm dở; mọi thứ đã xong được giữ nguyên.",
      });
    },
    onError: (error: Error) => toast.error("Không dừng được", { description: error.message }),
  });
}

/** "Tạm dừng" / "Tiếp tục" cuốn đang chạy: tiến trình vẫn sống, làm tiếp đúng chỗ - an toàn cả giữa lúc phân tích truyện. */
export function usePause() {
  const refresh = useRefresh();
  return useMutation({
    scope: { id: "start-stop" },
    mutationFn: ({ id, paused }: { id: string; paused: boolean }) =>
      api<BookSummary>(`/api/books/${id}/pause`, { method: "POST", body: { paused } }),
    onSuccess: (_book, { id, paused }) => {
      refresh(id);
      toast(paused ? "Đang tạm dừng" : "Đang làm tiếp", {
        description: paused
          ? "Sách đứng lại sau phần đang làm dở (lúc phân tích có thể mất vài phút) và giữ nguyên mọi thứ - bấm “Tiếp tục” là làm tiếp đúng chỗ ấy."
          : "Sách làm tiếp đúng chỗ đã tạm dừng.",
      });
    },
    onError: (error: Error, { paused }) =>
      toast.error(paused ? "Không tạm dừng được" : "Không làm tiếp được", { description: error.message }),
  });
}

export function useReveal() {
  return useMutation({
    mutationFn: (id: string) => api(`/api/books/${id}/reveal`, { method: "POST" }),
    onError: (error: Error) => toast.error("Không mở được thư mục", { description: error.message }),
  });
}

/** `seedFrom` ("Làm tiếp cuốn này"): Studio từ xa chỉ được đọc chương kế tiếp của đúng dự án ấy, ngoài các chương đã gửi lên. */
export function useScan() {
  return useMutation({
    mutationFn: ({ paths, seedFrom }: { paths: string[]; seedFrom?: string }) =>
      api<ScanResult>("/api/scan", { method: "POST", body: { paths, ...(seedFrom ? { seedFrom } : {}) } }),
  });
}

/** Truyện kể ngôi thứ nhất? - đọc ~20 chương đầu một lần cho mỗi bộ file đã chọn. */
export function useFirstPersonHint(paths: string[], seedFrom?: string) {
  return useQuery({
    queryKey: ["first-person", paths.join("\n"), seedFrom ?? ""],
    queryFn: () =>
      api<FirstPersonHint>("/api/first-person", { method: "POST", body: { paths, ...(seedFrom ? { seedFrom } : {}) } }),
    enabled: paths.length > 0,
    staleTime: Infinity,
  });
}

/** Phần kế tiếp của một dự án ("Làm tiếp cuốn này"): chương mới trong thư mục truyện + thứ sẽ mang theo. */
/** Các phần của cuốn mà sách này thuộc về (server.App.parts): phần đầu trước, `current` là sách đang xem; phần lẻ thì rỗng. */
export function useParts(id: string | undefined) {
  return useQuery({
    queryKey: ["parts", id],
    enabled: Boolean(id),
    queryFn: () => api<{ parts: { id: string; title: string; part: number; current: boolean }[] }>(`/api/books/${id}/parts`),
    // Ngắn: vừa tạo phần sau thì trang phần trước phải thấy ngay.
    staleTime: 5_000,
  });
}

export function useContinuation(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["continuation", id],
    enabled: Boolean(id) && enabled,
    queryFn: () => api<ContinuationPlan>(`/api/books/${id}/continuation`),
    staleTime: 60_000,
  });
}

export function useRedo(id: string | undefined) {
  return useQuery({
    queryKey: ["redo", id],
    enabled: Boolean(id),
    queryFn: () => api<RedoPlan>(`/api/books/${id}/redo`),
    staleTime: 0,
  });
}

export function useCreateBook() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: {
      paths: string[];
      title: string;
      profile: string;
      narrator: string;
      firstPerson: string;
      firstPersonChapters?: Record<string, string>;
      /** "Làm tiếp cuốn này": id dự án phần trước - giọng, cách đọc tên, ghim được gieo sang trước khi chạy. */
      seedFrom?: string;
      /** "Sửa thiết lập": cuốn chưa bắt đầu được thay - tạo xong thì nó vào Thùng rác (bìa đi theo). */
      replaces?: string;
      /** "Chia thành nhiều tập": số chương đầu (từ 1) của mỗi tập trong `paths` - tập 1 là sách thường, các tập sau là phần
       *  nối tiếp xếp hàng sau nó (App._create_volumes). */
      volumeStarts?: number[];
      start: boolean;
      /** "Chờ tôi duyệt trước khi thu" (webui/precast.py): phân tích xong thì tạm dừng chờ người duyệt. */
      precastWait?: boolean;
    }) =>
      // `sharedReadings`: các từ của cách đọc chung có trong truyện - sách mới nhận luôn (webui/shared_readings.py).
      // `parts`: các tập đã tạo theo thứ tự (chỉ khi chia nhiều tập), `queued` là chỗ của từng tập trong hàng chờ.
      api<{
        id: string;
        sharedReadings?: string[];
        queued?: number;
        replaceError?: string;
        unchanged?: boolean;
        parts?: { id: string; part: number; queued: number }[];
      }>("/api/books", {
        method: "POST",
        body,
      }),
    onSuccess: () => refresh(),
  });
}

export function useOpenBook() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (path: string) => api<{ id: string }>("/api/books/open", { method: "POST", body: { path } }),
    onSuccess: () => refresh(),
  });
}

export function usePreferences() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["preferences"], queryFn: () => api<Preferences>("/api/preferences") });
  const mutation = useMutation({
    mutationFn: (changes: Partial<Preferences>) => api<Preferences>("/api/preferences", { method: "PUT", body: changes }),
    onSuccess: (data) => {
      client.setQueryData(["preferences"], data);
      void client.invalidateQueries({ queryKey: ["library"] });
    },
  });
  return { ...query, update: mutation.mutate, updating: mutation.isPending };
}

export async function pickFolder(title: string, start = ""): Promise<string | null> {
  const result = await api<{ path: string | null }>("/api/dialog/folder", { method: "POST", body: { title, start } });
  return result.path;
}

/** `kind`: loại file hộp chọn cho xem - chương truyện (TXT, EPUB, DOCX, PDF; mặc định) hay nhạc ("Nhập nhạc của tôi"). */
export async function pickFiles(title: string, start = "", kind: "chapters" | "music" = "chapters"): Promise<string[]> {
  const result = await api<{ paths: string[] }>("/api/dialog/files", { method: "POST", body: { title, start, kind } });
  return result.paths;
}
