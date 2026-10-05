import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileAudio } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { useMatch } from "react-router";
import { toast } from "sonner";
import type { ListenBook } from "@/listen/model";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo, usePreferences } from "@/studio/data";
import { exportWhereHint, jobView, lastExportHint, type ExportJob } from "./bookFileExport";

// "Xuất file sách" chạy nền ở máy chủ (webui/export_jobs.py): menu chỉ chọn nơi lưu rồi báo cho BookFileExportHost; host (sống suốt
// phiên, ngoài menu) bắt đầu việc, hỏi trạng thái và giữ thông báo - tải lại trang thì mở trang sách là thấy lại tiến độ / kết quả.

const START_EVENT = "abook-bookfile-export";
const POLL_MS = 1000;
const jobUrl = (id: string) => `/api/books/${id}/bookfile-job`;
const toastId = (id: string) => `bookfile-export-${id}`;
/** Việc xong đã nhắc trong lần tải trang này (mất khi tải lại - khi ấy nhắc lại là đúng ý). */
const announced = new Set<string>();

interface StartDetail {
  id: string;
  chapters: number;
  target: string;
}

/** Cuốn đang xuất? Menu dùng để khoá mục và hiện "lần xuất gần nhất". */
function useBookFileJob(id: string) {
  return useQuery({ queryKey: ["bookfile-job", id], queryFn: () => api<ExportJob>(jobUrl(id)), staleTime: 0, gcTime: 0 });
}

export function BookFileMenuItem({ book }: { book: ListenBook }) {
  const { data: info } = useAppInfo();
  const { data: preferences } = usePreferences();
  const { data: job } = useBookFileJob(book.id);
  const run = async () => {
    let target = "";
    if (info?.dialogs) {
      const picked = await pickFolder("Chọn nơi lưu file sách", "").catch(() => null);
      if (!picked) return;
      target = picked;
    }
    window.dispatchEvent(new CustomEvent<StartDetail>(START_EVENT, { detail: { id: book.id, chapters: book.chaptersAvailable, target } }));
  };
  return (
    <DropdownMenu.Item
      // Chưa có chương nào nghe được thì không có gì để xuất (soát UX 29-09: bấm được rồi nhận lỗi 409); đang đóng gói thì chờ xong.
      disabled={!book.chaptersAvailable || job?.state === "running"}
      onSelect={() => void run()}
      className="flex h-auto cursor-default items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <FileAudio className="mt-0.5 size-4 shrink-0 self-start" />
      <span className="min-w-0">
        <span className="block">Xuất file sách (mở bằng app ở máy khác)</span>
        <span className="block truncate text-xs text-fg-3">
          {lastExportHint(job) ?? exportWhereHint(Boolean(info?.dialogs), preferences?.libraryRoot)}
        </span>
      </span>
    </DropdownMenu.Item>
  );
}

export function BookFileExportHost() {
  const { data: info } = useAppInfo();
  const client = useQueryClient();
  const pageId = useMatch("/book/:id")?.params.id;
  const timers = useRef(new Map<string, number>());
  const remote = Boolean(info?.remote);

  /** Hiện thông báo cho trạng thái hiện có của cuốn; trả true khi việc còn chạy. */
  const show = useCallback(
    (id: string, job: ExportJob, chapters: number, announce: boolean) => {
      const view = jobView(job, chapters, announce);
      void client.invalidateQueries({ queryKey: ["bookfile-job", id] });
      if (view.kind === "none") return job.state === "running";
      if (view.kind === "loading") {
        toast.loading(view.title, { id: toastId(id), description: view.description, duration: Infinity });
        return true;
      }
      if (view.kind === "success" && job.result) {
        const folder = job.result.folder;
        toast.success(view.title, {
          id: toastId(id),
          description: view.description,
          duration: 15000,
          // Studio từ xa: thư mục nằm trên máy tính, không mở được từ máy đang xem.
          action: remote ? undefined : { label: "Mở thư mục", onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder } }) },
        });
      } else {
        toast.error(view.title, { id: toastId(id), description: view.description, duration: 15000 });
      }
      return false;
    },
    [client, remote],
  );

  const track = useCallback(
    (id: string, chapters: number) => {
      if (timers.current.has(id)) return;
      const tick = async () => {
        let job: ExportJob;
        try {
          job = await api<ExportJob>(jobUrl(id));
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
    [show],
  );

  // Menu chọn xong thì bắt đầu: máy chủ trả ngay một mã, rồi host hỏi trạng thái.
  useEffect(() => {
    const listener = (event: Event) => {
      const { id, chapters, target } = (event as CustomEvent<StartDetail>).detail;
      toast.loading("Đang đóng gói sách…", { id: toastId(id), duration: Infinity });
      api<ExportJob>(jobUrl(id), { method: "POST", body: { target } })
        .then(() => track(id, chapters))
        .catch((error: Error) => toast.error("Không xuất được file sách", { id: toastId(id), description: error.message }));
    };
    window.addEventListener(START_EVENT, listener);
    return () => window.removeEventListener(START_EVENT, listener);
  }, [track]);

  // Mở (hay tải lại) trang sách: việc còn chạy thì theo tiếp, vừa xong thì nhắc lại nơi file nằm.
  useEffect(() => {
    if (!pageId) return;
    let alive = true;
    api<ExportJob>(jobUrl(pageId))
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
  }, [pageId, track, show]);

  useEffect(() => {
    const open = timers.current;
    return () => open.forEach((timer) => window.clearInterval(timer));
  }, []);
  return null;
}
