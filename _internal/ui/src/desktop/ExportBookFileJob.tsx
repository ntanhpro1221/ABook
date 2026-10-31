import { MotionRegion } from "@/shared/MotionRegion";
import { Collapse } from "@/shared/Collapse";
import type { ReactNode } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookAudio, CheckCircle2, CircleAlert, FileAudio, FolderDown, Headphones, Info, Loader2, TriangleAlert, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { useMatch } from "react-router";
import { toast, type ToastOptions } from "@/shared/toast";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { Button, LiveText, Progress } from "@/shared/ui";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo, usePreferences } from "@/studio/data";
import { listenOnlyOwner } from "@/shared/peerStudio";
import { BOOK_FILE_COPY, exportable, exportedOnComputer, exportWhereHint, jobView, lastExportHint, lastExportPlace, M4B_COPY, MP3_COPY, PROJECT_FILE_COPY, runningExports, type ExportCopy, type ExportJob } from "./bookFileExport";
import { AUDIOBOOK_COPY } from "./listenExport";

// "Xuất file sách", "Xuất M4B", "Xuất MP3" và "Xuất sách nói" (sách Nghe ngay) chạy nền ở máy chủ (webui/export_jobs.py): menu (hay hộp Xuất sách nói) chỉ chọn
// nơi lưu rồi báo cho ExportJobHost cùng kiểu; host (sống suốt phiên, ngoài menu) bắt đầu việc, hỏi trạng thái và giữ thông báo - tải lại trang
// thì mở trang sách là thấy lại tiến độ / kết quả. Mỗi kiểu có bản ghi riêng ở máy chủ, chạy cùng lúc được. Sách nói, M4B, MP3 và gói dự án báo thêm tiến độ và có Huỷ.

export type ExportKind = "bookfile" | "m4b" | "mp3" | "audiobook" | "projectfile";

const KINDS: Record<ExportKind, { copy: ExportCopy; pick: string; url: (id: string) => string; cancel?: (id: string) => string }> = {
  bookfile: { copy: BOOK_FILE_COPY, pick: "Chọn nơi lưu", url: (id) => `/api/books/${id}/bookfile-job`, cancel: (id) => `/api/books/${id}/bookfile-job/cancel` },
  m4b: { copy: M4B_COPY, pick: "Chọn nơi lưu", url: (id) => `/api/books/${id}/m4b-job`, cancel: (id) => `/api/books/${id}/m4b-job/cancel` },
  // Thư mục MP3 của Studio (hộp Xuất) và của menu Thư viện: cùng việc nền, cả bộ thì thêm `extra.series`.
  mp3: { copy: MP3_COPY, pick: "Chọn nơi lưu", url: (id) => `/api/books/${id}/mp3-job`, cancel: (id) => `/api/books/${id}/mp3-job/cancel` },
  audiobook: {
    copy: AUDIOBOOK_COPY,
    pick: "Chọn nơi lưu",
    url: (id) => `/api/listen/books/${id}/audiobook`,
    cancel: (id) => `/api/listen/books/${id}/audiobook/cancel`,
  },
  // Hộp Xuất của Studio (studio/ExportBook.tsx) bắt đầu và theo việc này khi còn mở; host nhận theo dõi khi hộp bị gỡ giữa chừng (`trackExport`) hay app mở lại lúc máy chủ còn gói.
  projectfile: {
    copy: PROJECT_FILE_COPY,
    pick: "Chọn nơi lưu",
    url: (id) => `/api/books/${id}/projectfile-job`,
    cancel: (id) => `/api/books/${id}/projectfile-job/cancel`,
  },
};

const POLL_MS = 1000;
const startEvent = (kind: ExportKind) => `abook-${kind}-export`;
const trackEvent = (kind: ExportKind) => `abook-${kind}-track`;
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

/** Báo cho host của `kind` theo tiếp một việc ĐÃ chạy ở máy chủ (hộp Xuất bị gỡ giữa chừng): host hỏi trạng thái, giữ thông báo, báo khi xong. */
export function trackExport(kind: ExportKind, id: string): void {
  window.dispatchEvent(new CustomEvent<string>(trackEvent(kind), { detail: id }));
}

/** Cuốn đang xuất? Menu dùng để khoá mục và hiện "lần xuất gần nhất". */
export function useExportJob(kind: ExportKind, id: string) {
  return useQuery({ queryKey: jobKey(kind, id), queryFn: () => api<ExportJob>(jobUrl(kind, id)), staleTime: 0, gcTime: 0, retry: false });
}

function ExportJobMenuItem({ book, kind, icon: Icon, label }: { book: ListenBook; kind: ExportKind; icon: LucideIcon; label: string }) {
  const { data: info } = useAppInfo();
  const { data: preferences } = usePreferences();
  const { data: job, dataUpdatedAt } = useExportJob(kind, book.id);
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder(KINDS[kind].pick, "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    const cover = kind === "m4b" || kind === "mp3" ? coverArtwork(book.title) : undefined;
    startExport(kind, { id: book.id, chapters: book.chaptersAvailable, target, cover });
  };
  return (
    <DropdownMenu.Item
      // Chưa có gì để xuất thì khoá (soát UX 29-09: bấm được rồi nhận lỗi 409); file sách mang cả chữ chương chưa có audio (a99 V5); đang làm thì chờ xong.
      disabled={!exportable(kind, book) || job?.state === "running"}
      onSelect={() => void run()}
      className="flex h-auto cursor-default items-center gap-2 rounded-control px-2 py-1.5 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <Icon className="mt-line-icon size-4 shrink-0 self-start" />
      <span className="min-w-0">
        <span className="block">{label}</span>
        <MotionRegion as="span" className="block text-pretty text-xs text-fg-3" title={lastExportPlace(job)}>
          {lastExportHint(job, KINDS[kind].copy, dataUpdatedAt) ??
            (kind === "bookfile" && !book.chaptersAvailable && book.chaptersTotal ? "Chưa có audio: file chỉ mang chữ của các chương" : kind === "mp3" ? "Mỗi chương một file." : kind === "m4b" ? "Một file có mục lục." : exportWhereHint(Boolean(info?.dialogs), preferences?.libraryRoot))}
        </MotionRegion>
      </span>
    </DropdownMenu.Item>
  );
}

export function BookFileMenuItem({ book }: { book: ListenBook }) {
  return <ExportJobMenuItem book={book} kind="bookfile" icon={FileAudio} label="Xuất file sách" />;
}

/** Cả cuốn trong một file `.m4b` có mục lục chương - app sách nói (Apple Books, Smart AudioBook Player...) mở là thấy đủ chương. */
export function M4bMenuItem({ book }: { book: ListenBook }) {
  return <ExportJobMenuItem book={book} kind="m4b" icon={BookAudio} label="Xuất M4B" />;
}

/** Thư mục MP3 có tên sách, tên chương, bìa - nghe được bằng mọi trình phát khác. */
export function Mp3MenuItem({ book }: { book: ListenBook }) {
  return <ExportJobMenuItem book={book} kind="mp3" icon={FolderDown} label="Xuất MP3" />;
}

/** Mở hộp Xuất sách nói (AudiobookDialogHost) cho cuốn này. */
export const OPEN_AUDIOBOOK_EVENT = "abook-audiobook-dialog";

/** Sách Nghe ngay (chỉ có chữ) thành sách nói MP3 / M4B để nghe ở trình phát khác. Định dạng, giọng và nơi lưu chọn trong hộp. */
export function AudiobookMenuItem({ book }: { book: ListenBook }) {
  const { data: job, dataUpdatedAt } = useExportJob("audiobook", book.id);
  return (
    <DropdownMenu.Item
      disabled={!book.chaptersTotal || job?.state === "running"}
      onSelect={() => window.dispatchEvent(new CustomEvent<ListenBook>(OPEN_AUDIOBOOK_EVENT, { detail: book }))}
      className="flex h-auto cursor-default items-center gap-2 rounded-control px-2 py-1.5 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <Headphones className="mt-line-icon size-4 shrink-0 self-start" />
      <span className="min-w-0">
        <span className="block">Xuất sách nói</span>
        <MotionRegion as="span" className="block text-pretty text-xs text-fg-3" title={lastExportPlace(job)}>
          {lastExportHint(job, KINDS.audiobook.copy, dataUpdatedAt) ?? "Mang sang điện thoại, xe hơi, trình phát khác"}
        </MotionRegion>
      </span>
    </DropdownMenu.Item>
  );
}

/** Thông báo đang làm có thanh tiến độ dưới dòng mô tả. Thông báo nằm trong vùng aria-live: trình đọc màn hình chỉ đọc `spoken` (pha / mốc
 *  25 %), không đọc dòng chữ và thanh đổi mỗi giây (soát a31 A6). */
export function ProgressNote({ text, spoken, fraction, label }: { text: string; spoken: string; fraction?: number; label: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span>
        <LiveText shown={text} spoken={spoken} />
      </span>
      <Collapse open={fraction !== undefined}>
        <div aria-hidden>
          {/* Tên thanh là tên việc, không phải lời đọc có mốc % (đứng yên ở 0 % trong khi thanh chạy tới 14 - soát a67). */}
          <Progress value={fraction ?? 0} size="sm" running label={label} />
        </div>
      </Collapse>
    </div>
  );
}

const STOPPING = { title: "Đang dừng…", note: "Phần đã làm được giữ." };
/** Lời "Đang dừng…" của kiểu xuất này (M4B: không giữ gì - `ExportCopy.stopping`). */
const stoppingNote = (copy: ExportCopy) => copy.stopping ?? STOPPING.note;

/** Thông báo cùng mã thay nhau (đang làm -> đang dừng -> đã dừng / xong / lỗi): sonner giữ nút của lần trước nếu lần sau không nói rõ `action`,
 *  nên mọi lần cập nhật không có nút phải ghi `action: undefined` (soát 10-10: "Đã dừng xuất sách nói" còn nút Huỷ cũ). */
const NO_ACTION = { action: undefined } as const;

/** Cùng một kiểu toast suốt vòng đời (cùng nút DOM khi đổi từ đang làm sang xong / lỗi): chữ, biểu tượng và nút giữ vùng fade riêng.
 *  MỘT dòng + tối đa MỘT nút (DESIGN 6): tiến độ / cảnh báo / lỗi đưa lời dài vào Chi tiết; "xong" và "đã dừng" chỉ còn tiêu đề.
 *  `hint`: đường đầy đủ của file, hiện khi rê chuột lên tiêu đề. */
type ExportToastKind = "loading" | "success" | "warning" | "info" | "error";
const say = toast.message as unknown as (message: ReactNode, data?: ToastOptions) => string | number; // toast.message nhận cả mô tả; kiểu hẹp của nó chặn nhầm, nên chỉ `described` dưới đây được đưa vào
function exportToast(kind: ExportToastKind, title: string, options: {
  id: string; description?: ReactNode; hint?: string; duration?: number;
  action?: { label: string; onClick: () => void };
}) {
  const Icon = kind === "loading" ? Loader2 : kind === "success" ? CheckCircle2 : kind === "error" ? CircleAlert : kind === "warning" ? TriangleAlert : Info;
  const described = kind === "loading" || kind === "warning" || kind === "error";
  const { hint, description, ...rest } = options;
  return say(<MotionRegion as="span" motionKey={[kind, title]} className="flex items-center gap-2" title={hint}>
    <Icon className={kind === "loading" ? "size-4 shrink-0 animate-spin" : "size-4 shrink-0"} />{title}
  </MotionRegion>, {
    ...rest,
    className: described && description ? undefined : "toast-one-line",
    icon: null,
    description: described && description ? <MotionRegion>{description}</MotionRegion> : undefined,
    action: <MotionRegion as="span" motionKey={options.action?.label ?? ""}>{options.action &&
      <Button data-button="" size="sm" variant="primary" onClick={options.action.onClick}>{options.action.label}</Button>}
    </MotionRegion>,
  });
}

export function ExportJobHost({ kind }: { kind: ExportKind }) {
  const { data: info } = useAppInfo();
  const client = useQueryClient();
  const pageId = useMatch("/book/:id")?.params.id;
  const timers = useRef(new Map<string, number>());
  /** Cuốn đã bấm Huỷ mà máy chủ chưa dừng (dừng sau đoạn đang đọc): thông báo nói "Đang dừng…" thay vì tiến độ. */
  const stopping = useRef(new Set<string>());
  const remote = Boolean(info?.remote);
  // Thiết bị chỉ được nghe: máy tính từ chối mọi việc xuất (403) - không hỏi trạng thái, khỏi 403 mỗi lần mở trang sách.
  const listenOnly = Boolean(info?.listenOnly);
  const { copy, cancel } = KINDS[kind];

  /** Hiện thông báo cho trạng thái hiện có của cuốn; trả true khi việc còn chạy. */
  const show = useCallback(
    (id: string, job: ExportJob, chapters: number, announce: boolean) => {
      const view = jobView(job, chapters, announce, copy);
      void client.invalidateQueries({ queryKey: jobKey(kind, id) });
      if (view.kind === "none") return job.state === "running";
      if (view.kind === "loading") {
        if (stopping.current.has(id)) {
          exportToast("loading", STOPPING.title, { id: toastId(kind, id), description: stoppingNote(copy), duration: Infinity, ...NO_ACTION });
          return true;
        }
        exportToast("loading", view.title, {
          id: toastId(kind, id),
          description: <ProgressNote text={view.description} spoken={view.spoken ?? ""} fraction={view.progress} label={view.title} />,
          duration: Infinity,
          action: cancel
            ? {
                label: "Dừng",
                onClick: () => {
                  stopping.current.add(id);
                  exportToast("loading", STOPPING.title, { id: toastId(kind, id), description: stoppingNote(copy), duration: Infinity, ...NO_ACTION });
                  void api(cancel(id), { method: "POST", body: {} }).catch(() => stopping.current.delete(id));
                },
              }
            : undefined,
        });
        return true;
      }
      stopping.current.delete(id);
      if (view.kind === "info") {
        exportToast("info", view.title, { id: toastId(kind, id), duration: 15000, ...NO_ACTION });
        return false;
      }
      if (view.kind === "success" && job.result) {
        const folder = job.result.folder;
        // Xong trơn: một dòng; xong mà thiếu gì đó (chương, nhạc, nguồn, bìa): cảnh báo với đúng phần thiếu. Chỗ file nằm: nút “Mở thư mục”
        // (đường đầy đủ hiện khi rê chuột lên tiêu đề); Studio từ xa thì tiêu đề nói file nằm ở máy tính nào.
        exportToast(view.note ? "warning" : "success", remote ? exportedOnComputer(listenOnlyOwner(info ?? {}), "") : view.title, {
          id: toastId(kind, id),
          description: view.note,
          hint: view.place,
          duration: 15000,
          // Studio từ xa: thư mục nằm trên máy tính, không mở được từ máy đang xem.
          action: remote ? undefined : { label: "Mở thư mục", onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder } }) },
        });
      } else {
        exportToast("error", view.title, { id: toastId(kind, id), description: view.description, duration: 15000, ...NO_ACTION });
      }
      return false;
    },
    [client, remote, info, kind, copy, cancel],
  );
  // Nhịp hỏi sống lâu hơn một lần vẽ: luôn dùng `show` mới nhất (app biết máy này là Studio từ xa sau khi việc đã bắt đầu theo).
  const showLatest = useRef(show);
  showLatest.current = show;

  const track = useCallback(
    (id: string, chapters: number) => {
      if (timers.current.has(id)) return;
      // Máy chủ trả chậm hơn nhịp hỏi: không hỏi chồng. Hai lần hỏi chồng nhau thì câu "đang chạy" về sau câu "xong" dựng lại thông báo
      // tiến độ (có Huỷ, không tự tắt) mà không còn nhịp nào hỏi tiếp để sửa.
      let asking = false;
      const tick = async () => {
        if (asking) return;
        asking = true;
        let job: ExportJob;
        try {
          job = await api<ExportJob>(jobUrl(kind, id));
        } catch {
          return; // một lần hỏi hụt (mạng chớp) không phải là việc hỏng - hỏi lại ở nhịp sau
        } finally {
          asking = false;
        }
        if (!timers.current.has(id)) return; // đã thôi theo (xong ở lần hỏi khác, host gỡ)
        if (!showLatest.current(id, job, chapters, false)) {
          window.clearInterval(timers.current.get(id));
          timers.current.delete(id);
          if (job.id) announced.add(job.id);
        }
      };
      timers.current.set(id, window.setInterval(() => void tick(), POLL_MS));
      void tick();
    },
    [kind],
  );

  // Menu chọn xong thì bắt đầu: máy chủ trả ngay một mã, rồi host hỏi trạng thái.
  useEffect(() => {
    const listener = (event: Event) => {
      const { id, chapters, target, cover, extra } = (event as CustomEvent<StartDetail>).detail;
      stopping.current.delete(id);
      exportToast("loading", copy.busy, { id: toastId(kind, id), duration: Infinity, ...NO_ACTION });
      api<ExportJob>(jobUrl(kind, id), { method: "POST", body: { target, cover, ...extra } })
        .then(() => track(id, chapters))
        .catch((error: Error) => exportToast("error", copy.failed, { id: toastId(kind, id), description: error.message, ...NO_ACTION }));
    };
    window.addEventListener(startEvent(kind), listener);
    return () => window.removeEventListener(startEvent(kind), listener);
  }, [track, kind, copy]);

  // Hộp Xuất bị gỡ khi việc còn chạy ở máy chủ: theo tiếp.
  useEffect(() => {
    const listener = (event: Event) => {
      stopping.current.delete((event as CustomEvent<string>).detail);
      track((event as CustomEvent<string>).detail, 0);
    };
    window.addEventListener(trackEvent(kind), listener);
    return () => window.removeEventListener(trackEvent(kind), listener);
  }, [track, kind]);

  // Mở (hay tải lại) trang sách: việc còn chạy thì theo tiếp, vừa xong thì nhắc lại nơi file nằm.
  useEffect(() => {
    // Chờ app biết máy này là máy nào (Studio từ xa: thông báo xong không có "Mở thư mục"; chỉ nghe: không hỏi việc xuất - 403).
    if (!pageId || !info || listenOnly) return;
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
  }, [pageId, track, show, kind, listenOnly, info]);

  // Mở (hay tải lại) app ở trang không phải trang sách: máy chủ vẫn đang xuất thì hiện lại thông báo tiến độ (có % và Huỷ) như lúc bắt đầu.
  useEffect(() => {
    if (!info || info.listenOnly) return; // thông báo xong cần biết máy này có phải Studio từ xa không (nút "Mở thư mục"): chờ app biết đã; chỉ nghe thì không có việc xuất
    let alive = true;
    void runningExports(kind).then((ids) => {
      if (alive) ids.forEach((id) => track(id, 0));
    });
    return () => {
      alive = false;
    };
  }, [kind, track, info]);

  useEffect(() => {
    const open = timers.current;
    return () => {
      open.forEach((timer) => window.clearInterval(timer));
      open.clear();
    };
  }, []);
  return null;
}
