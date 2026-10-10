import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookAudio, FileAudio, Headphones, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { useMatch } from "react-router";
import { toast } from "sonner";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { Progress } from "@/shared/ui";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo, usePreferences } from "@/studio/data";
import { BOOK_FILE_COPY, exportWhereHint, jobView, lastExportHint, M4B_COPY, type ExportCopy, type ExportJob } from "./bookFileExport";
import { AUDIOBOOK_COPY } from "./listenExport";

// "Xuất file sách", "Xuất M4B" và "Xuất sách nói" (sách Nghe ngay) chạy nền ở máy chủ (webui/export_jobs.py): menu (hay hộp Xuất sách nói) chỉ chọn
// nơi lưu rồi báo cho ExportJobHost cùng kiểu; host (sống suốt phiên, ngoài menu) bắt đầu việc, hỏi trạng thái và giữ thông báo - tải lại trang
// thì mở trang sách là thấy lại tiến độ / kết quả. Mỗi kiểu có bản ghi riêng ở máy chủ, chạy cùng lúc được. Sách nói báo thêm tiến độ và có Huỷ.

export type ExportKind = "bookfile" | "m4b" | "audiobook";

const KINDS: Record<ExportKind, { copy: ExportCopy; pick: string; url: (id: string) => string; cancel?: (id: string) => string }> = {
  bookfile: { copy: BOOK_FILE_COPY, pick: "Chọn nơi lưu file sách", url: (id) => `/api/books/${id}/bookfile-job` },
  m4b: { copy: M4B_COPY, pick: "Chọn nơi lưu file M4B", url: (id) => `/api/books/${id}/m4b-job` },
  audiobook: {
    copy: AUDIOBOOK_COPY,
    pick: "Chọn nơi lưu sách nói",
    url: (id) => `/api/listen/books/${id}/audiobook`,
    cancel: (id) => `/api/listen/books/${id}/audiobook/cancel`,
  },
};

const POLL_MS = 1000;
const startEvent = (kind: ExportKind) => `abook-${kind}-export`;
const jobUrl = (kind: ExportKind, id: string) => KINDS[kind].url(id);
const jobKey = (kind: ExportKind, id: string) => [`${kind}-job`, id];
const toastId = (kind: ExportKind, id: string) => `${kind}-export-${id}`;
/** Việc xong đã nhắc trong lần tải trang này (mất khi tải lại - khi ấy nhắc lại là đúng ý). Mã việc không trùng giữa hai kiểu. */
const announced = new Set<string>();

export interface StartDetail {
  id: string;
  chapters: number;
  target: string;
  /** Bìa tự vẽ (M4B gắn vào file khi sách chưa có ảnh bìa thật - như "Xuất MP3"). */
  cover?: string;
  /** Thêm vào thân yêu cầu (sách nói: định dạng + giọng). */
  extra?: Record<string, unknown>;
}

/** Báo cho host của `kind` bắt đầu một lượt xuất (menu và hộp Xuất sách nói dùng chung). */
export function startExport(kind: ExportKind, detail: StartDetail): void {
  window.dispatchEvent(new CustomEvent<StartDetail>(startEvent(kind), { detail }));
}

/** Cuốn đang xuất? Menu dùng để khoá mục và hiện "lần xuất gần nhất". */
export function useExportJob(kind: ExportKind, id: string) {
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
    startExport(kind, { id: book.id, chapters: book.chaptersAvailable, target, cover });
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

/** Mở hộp Xuất sách nói (AudiobookDialogHost) cho cuốn này. */
export const OPEN_AUDIOBOOK_EVENT = "abook-audiobook-dialog";

/** Sách Nghe ngay (chỉ có chữ) thành sách nói MP3 / M4B để nghe ở trình phát khác. Định dạng, giọng và nơi lưu chọn trong hộp. */
export function AudiobookMenuItem({ book }: { book: ListenBook }) {
  const { data: job } = useExportJob("audiobook", book.id);
  return (
    <DropdownMenu.Item
      disabled={!book.chaptersTotal || job?.state === "running"}
      onSelect={() => window.dispatchEvent(new CustomEvent<ListenBook>(OPEN_AUDIOBOOK_EVENT, { detail: book }))}
      className="flex h-auto cursor-default items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <Headphones className="mt-0.5 size-4 shrink-0 self-start" />
      <span className="min-w-0">
        <span className="block">Xuất sách nói (MP3 / M4B)…</span>
        <span className="block truncate text-xs text-fg-3">
          {lastExportHint(job, KINDS.audiobook.copy) ?? "Mang sang điện thoại, xe hơi, trình phát khác"}
        </span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Thông báo đang làm có thanh tiến độ dưới dòng mô tả. */
function ProgressNote({ text, fraction }: { text: string; fraction: number }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span>{text}</span>
      <Progress value={fraction} size="sm" running label={text} />
    </div>
  );
}

const STOPPING = { title: "Đang dừng…", note: "Dừng sau đoạn đang đọc - phần đã làm được giữ." };

/** Thông báo cùng mã thay nhau (đang làm -> đang dừng -> đã dừng / xong / lỗi): sonner giữ nút của lần trước nếu lần sau không nói rõ `action`,
 *  nên mọi lần cập nhật không có nút phải ghi `action: undefined` (soát 10-10: "Đã dừng xuất sách nói" còn nút Huỷ cũ). */
const NO_ACTION = { action: undefined } as const;

export function ExportJobHost({ kind }: { kind: ExportKind }) {
  const { data: info } = useAppInfo();
  const client = useQueryClient();
  const pageId = useMatch("/book/:id")?.params.id;
  const timers = useRef(new Map<string, number>());
  /** Cuốn đã bấm Huỷ mà máy chủ chưa dừng (dừng sau đoạn đang đọc): thông báo nói "Đang dừng…" thay vì tiến độ. */
  const stopping = useRef(new Set<string>());
  const remote = Boolean(info?.remote);
  const { copy, cancel } = KINDS[kind];

  /** Hiện thông báo cho trạng thái hiện có của cuốn; trả true khi việc còn chạy. */
  const show = useCallback(
    (id: string, job: ExportJob, chapters: number, announce: boolean) => {
      const view = jobView(job, chapters, announce, copy);
      void client.invalidateQueries({ queryKey: jobKey(kind, id) });
      if (view.kind === "none") return job.state === "running";
      if (view.kind === "loading") {
        if (stopping.current.has(id)) {
          toast.loading(STOPPING.title, { id: toastId(kind, id), description: STOPPING.note, duration: Infinity, ...NO_ACTION });
          return true;
        }
        toast.loading(view.title, {
          id: toastId(kind, id),
          description: view.progress !== undefined ? <ProgressNote text={view.description} fraction={view.progress} /> : view.description,
          duration: Infinity,
          action: cancel
            ? {
                label: "Huỷ",
                onClick: () => {
                  stopping.current.add(id);
                  toast.loading(STOPPING.title, { id: toastId(kind, id), description: STOPPING.note, duration: Infinity, ...NO_ACTION });
                  void api(cancel(id), { method: "POST", body: {} }).catch(() => stopping.current.delete(id));
                },
              }
            : undefined,
        });
        return true;
      }
      stopping.current.delete(id);
      if (view.kind === "info") {
        toast.info(view.title, { id: toastId(kind, id), description: view.description, duration: 15000, ...NO_ACTION });
        return false;
      }
      if (view.kind === "success" && job.result) {
        const folder = job.result.folder;
        toast.success(view.title, {
          id: toastId(kind, id),
          // Thông báo chỉ nói tên file; đường đầy đủ hiện khi rê chuột (nút “Mở thư mục” đưa tới đúng chỗ).
          description: view.place ? <span title={view.place}>{view.description}</span> : view.description,
          duration: 15000,
          // Studio từ xa: thư mục nằm trên máy tính, không mở được từ máy đang xem.
          action: remote ? undefined : { label: "Mở thư mục", onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder } }) },
        });
      } else {
        toast.error(view.title, { id: toastId(kind, id), description: view.description, duration: 15000, ...NO_ACTION });
      }
      return false;
    },
    [client, remote, kind, copy, cancel],
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
      const { id, chapters, target, cover, extra } = (event as CustomEvent<StartDetail>).detail;
      stopping.current.delete(id);
      toast.loading(copy.busy, { id: toastId(kind, id), duration: Infinity, ...NO_ACTION });
      api<ExportJob>(jobUrl(kind, id), { method: "POST", body: { target, cover, ...extra } })
        .then(() => track(id, chapters))
        .catch((error: Error) => toast.error(copy.failed, { id: toastId(kind, id), description: error.message, ...NO_ACTION }));
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
