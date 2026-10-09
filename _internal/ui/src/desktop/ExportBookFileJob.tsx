import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookAudio, FileAudio, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { useMatch } from "react-router";
import { toast } from "sonner";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo, usePreferences } from "@/studio/data";
import { BOOK_FILE_COPY, exportWhereHint, jobView, lastExportHint, M4B_COPY, type ExportCopy, type ExportJob } from "./bookFileExport";

// "Xuất file sách" và "Xuất M4B" chạy nền ở máy chủ (webui/export_jobs.py): menu chỉ chọn nơi lưu rồi báo cho ExportJobHost cùng
// kiểu; host (sống suốt phiên, ngoài menu) bắt đầu việc, hỏi trạng thái và giữ thông báo - tải lại trang thì mở trang sách là thấy
// lại tiến độ / kết quả. Hai kiểu có bản ghi riêng ở máy chủ (`<kiểu>-job`), chạy cùng lúc được.

export type ExportKind = "bookfile" | "m4b";

const KINDS: Record<ExportKind, { copy: ExportCopy; pick: string }> = {
  bookfile: { copy: BOOK_FILE_COPY, pick: "Chọn nơi lưu file sách" },
  m4b: { copy: M4B_COPY, pick: "Chọn nơi lưu file M4B" },
};

const POLL_MS = 1000;
const startEvent = (kind: ExportKind) => `abook-${kind}-export`;
const jobUrl = (kind: ExportKind, id: string) => `/api/books/${id}/${kind}-job`;
const jobKey = (kind: ExportKind, id: string) => [`${kind}-job`, id];
const toastId = (kind: ExportKind, id: string) => `${kind}-export-${id}`;
/** Việc xong đã nhắc trong lần tải trang này (mất khi tải lại - khi ấy nhắc lại là đúng ý). Mã việc không trùng giữa hai kiểu. */
const announced = new Set<string>();

interface StartDetail {
  id: string;
  chapters: number;
  target: string;
  /** Bìa tự vẽ (M4B gắn vào file khi sách chưa có ảnh bìa thật - như "Xuất MP3"). */
  cover?: string;
}

/** Cuốn đang xuất? Menu dùng để khoá mục và hiện "lần xuất gần nhất". */
function useExportJob(kind: ExportKind, id: string) {
  return useQuery({ queryKey: jobKey(kind, id), queryFn: () => api<ExportJob>(jobUrl(kind, id)), staleTime: 0, gcTime: 0, retry: false });
}

function ExportJobMenuItem({ book, kind, icon: Icon, label }: { book: ListenBook; kind: ExportKind; icon: LucideIcon; label: string }) {
  const { data: info } = useAppInfo();
  const { data: preferences } = usePreferences();
  const { data: job } = useExportJob(kind, book.id);
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder(KINDS[kind].pick, "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    const cover = kind === "m4b" ? coverArtwork(book.title) : undefined;
    window.dispatchEvent(new CustomEvent<StartDetail>(startEvent(kind), { detail: { id: book.id, chapters: book.chaptersAvailable, target, cover } }));
  };
  return (
    <DropdownMenu.Item
      // Chưa có chương nào nghe được thì không có gì để xuất (soát UX 29-09: bấm được rồi nhận lỗi 409); đang làm thì chờ xong.
      disabled={!book.chaptersAvailable || job?.state === "running"}
      onSelect={() => void run()}
      className="flex h-auto cursor-default items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <Icon className="mt-0.5 size-4 shrink-0 self-start" />
      <span className="min-w-0">
        <span className="block">{label}</span>
        <span className="block truncate text-xs text-fg-3">
          {lastExportHint(job, KINDS[kind].copy) ?? exportWhereHint(Boolean(info?.dialogs), preferences?.libraryRoot)}
        </span>
      </span>
    </DropdownMenu.Item>
  );
}

export function BookFileMenuItem({ book }: { book: ListenBook }) {
  return <ExportJobMenuItem book={book} kind="bookfile" icon={FileAudio} label="Xuất file sách (mở bằng app ở máy khác)" />;
}

/** Cả cuốn trong một file `.m4b` có mục lục chương - app sách nói (Apple Books, Smart AudioBook Player...) mở là thấy đủ chương. */
export function M4bMenuItem({ book }: { book: ListenBook }) {
  return <ExportJobMenuItem book={book} kind="m4b" icon={BookAudio} label="Xuất M4B cho app sách nói" />;
}

export function ExportJobHost({ kind }: { kind: ExportKind }) {
  const { data: info } = useAppInfo();
  const client = useQueryClient();
  const pageId = useMatch("/book/:id")?.params.id;
  const timers = useRef(new Map<string, number>());
  const remote = Boolean(info?.remote);
  const { copy } = KINDS[kind];

  /** Hiện thông báo cho trạng thái hiện có của cuốn; trả true khi việc còn chạy. */
  const show = useCallback(
    (id: string, job: ExportJob, chapters: number, announce: boolean) => {
      const view = jobView(job, chapters, announce, copy);
      void client.invalidateQueries({ queryKey: jobKey(kind, id) });
      if (view.kind === "none") return job.state === "running";
      if (view.kind === "loading") {
        toast.loading(view.title, { id: toastId(kind, id), description: view.description, duration: Infinity });
        return true;
      }
      if (view.kind === "success" && job.result) {
        const folder = job.result.folder;
        toast.success(view.title, {
          id: toastId(kind, id),
          description: view.description,
          duration: 15000,
          // Studio từ xa: thư mục nằm trên máy tính, không mở được từ máy đang xem.
          action: remote ? undefined : { label: "Mở thư mục", onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder } }) },
        });
      } else {
        toast.error(view.title, { id: toastId(kind, id), description: view.description, duration: 15000 });
      }
      return false;
    },
    [client, remote, kind, copy],
  );

  const track = useCallback(
    (id: string, chapters: number) => {
      if (timers.current.has(id)) return;
      const tick = async () => {
        let job: ExportJob;
        try {
          job = await api<ExportJob>(jobUrl(kind, id));
        } catch {
          return; // một lần hỏi hụt (mạng chớp) không phải là việc hỏng - hỏi lại ở nhịp sau
        }
        if (!show(id, job, chapters, false)) {
          window.clearInterval(timers.current.get(id));
          timers.current.delete(id);
          if (job.id) announced.add(job.id);
        }
      };
      timers.current.set(id, window.setInterval(() => void tick(), POLL_MS));
      void tick();
    },
    [show, kind],
  );

  // Menu chọn xong thì bắt đầu: máy chủ trả ngay một mã, rồi host hỏi trạng thái.
  useEffect(() => {
    const listener = (event: Event) => {
      const { id, chapters, target, cover } = (event as CustomEvent<StartDetail>).detail;
      toast.loading(copy.busy, { id: toastId(kind, id), duration: Infinity });
      api<ExportJob>(jobUrl(kind, id), { method: "POST", body: { target, cover } })
        .then(() => track(id, chapters))
        .catch((error: Error) => toast.error(copy.failed, { id: toastId(kind, id), description: error.message }));
    };
    window.addEventListener(startEvent(kind), listener);
    return () => window.removeEventListener(startEvent(kind), listener);
  }, [track, kind, copy]);

  // Mở (hay tải lại) trang sách: việc còn chạy thì theo tiếp, vừa xong thì nhắc lại nơi file nằm.
  useEffect(() => {
    if (!pageId) return;
    let alive = true;
    api<ExportJob>(jobUrl(kind, pageId))
      .then((job) => {
        if (!alive || job.state === "idle") return;
        if (job.state === "running") track(pageId, 0);
        else if (!job.id || !announced.has(job.id)) {
          if (job.id) announced.add(job.id);
          show(pageId, job, 0, true);
        }
      })
      .catch(() => undefined); // sách nhập từ file / máy khác không có việc xuất - không có gì để nhắc
    return () => {
      alive = false;
    };
  }, [pageId, track, show, kind]);

  useEffect(() => {
    const open = timers.current;
    return () => open.forEach((timer) => window.clearInterval(timer));
  }, []);
  return null;
}
