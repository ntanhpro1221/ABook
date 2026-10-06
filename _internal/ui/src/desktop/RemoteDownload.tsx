import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Download, Square } from "lucide-react";
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import type { ListenBook } from "@/listen/model";
import { cn } from "@/shared/cn";
import { Button, Progress } from "@/shared/ui";
import { api } from "@/studio/api";
import { downloadFraction, downloadMenuLabel, downloadNote, type RemoteDownload } from "./remoteDownloadState";

// "Tải về máy" cho sách "Trên máy khác" trên máy tính - như mục "Tải về máy" của điện thoại (android/App.tsx DownloadMenuItem):
// tải nền cả cuốn, xem tiến độ ngay dưới tên sách, dừng / tải tiếp được; xong thì nghe được cả khi máy kia tắt.

const MENU_ITEM = "flex h-auto cursor-default items-start gap-2 rounded-lg px-2 py-1.5 text-sm outline-none data-[disabled]:opacity-60 data-[highlighted]:bg-hover";

function computerOf(book: ListenBook): string {
  return typeof book.remote === "object" ? book.remote.computer : "";
}

function useRemoteDownload(book: ListenBook) {
  const client = useQueryClient();
  const key = ["listen", "download", book.id];
  const query = useQuery({
    queryKey: key,
    queryFn: () => api<RemoteDownload>(`/api/listen/books/${book.id}/download`),
    refetchInterval: (current) => (current.state.data?.state === "running" ? 1000 : false),
  });
  const start = useMutation({
    mutationFn: () => api<RemoteDownload>(`/api/listen/books/${book.id}/download`, { method: "POST" }),
    onSuccess: (status) => {
      client.setQueryData(key, status);
      toast("Đang tải về máy", { description: "Xem tiến độ ngay dưới tên sách" });
    },
    onError: (error: Error) => toast.error("Không tải được", { description: error.message }),
  });
  const cancel = useMutation({
    mutationFn: () => api<RemoteDownload>(`/api/listen/books/${book.id}/download`, { method: "DELETE" }),
    onSuccess: (status) => client.setQueryData(key, status),
  });
  // Tải xong (hay hỏng) khi người dùng đang ở trang sách: báo một lần.
  const previous = useRef(query.data?.state);
  useEffect(() => {
    const now = query.data?.state;
    if (previous.current === "running" && now === "done") {
      toast.success(`Đã tải “${book.title}” về máy`, { description: `Nghe được cả khi ${computerOf(book) || "máy kia"} tắt` });
    } else if (previous.current === "running" && now === "failed") {
      toast.error("Chưa tải xong về máy", { description: `${query.data?.error ?? ""} Phần đã tải vẫn giữ trên máy này.`.trim() });
    }
    previous.current = now;
  }, [query.data?.state, query.data?.error, book]);
  return { status: query.data, start: () => start.mutate(), cancel: () => cancel.mutate(), busy: start.isPending || cancel.isPending };
}

/** Mục trong menu của sách "Trên máy khác": tải về / dừng tải / đã tải (mờ đi). */
export function RemoteDownloadMenuItem({ book }: { book: ListenBook }) {
  const { status, start, cancel, busy } = useRemoteDownload(book);
  const { label, hint, disabled } = downloadMenuLabel(status, computerOf(book));
  const Icon = status?.state === "running" ? Square : status?.state === "done" ? CircleCheck : Download;
  return (
    <DropdownMenu.Item disabled={disabled || busy} onSelect={status?.state === "running" ? cancel : start} className={MENU_ITEM}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">{label}</span>
        <span className="block text-xs text-fg-3">{hint}</span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Dòng tình trạng dưới tên sách: đang tải bao nhiêu (kèm nút dừng), đã xong, hay đã dừng / hỏng (kèm nút tải tiếp). */
export function RemoteDownloadStatus({ book }: { book: ListenBook }) {
  const { status, start, cancel, busy } = useRemoteDownload(book);
  const note = downloadNote(status, computerOf(book));
  if (!status || !note) return null;
  const Icon = note.tone === "error" ? CircleAlert : note.tone === "done" ? CircleCheck : Download;
  return (
    <div
      role="status"
      className={cn(
        "mt-2 max-w-md rounded-xl px-3 py-2 text-xs max-sm:mx-auto max-sm:text-left",
        note.tone === "error" ? "bg-danger-soft text-danger" : "bg-info-soft text-info",
      )}
    >
      <p className="inline-flex items-center gap-1.5 font-medium">
        <Icon className="size-3.5 shrink-0" /> {note.title}
      </p>
      {note.detail && <p className="mt-0.5 text-pretty">{note.detail}</p>}
      {note.tone === "running" && <Progress value={downloadFraction(status)} size="xs" className="mt-2" label="Đã tải về máy" />}
      {note.action && (
        <Button
          size="sm"
          variant="secondary"
          className="mt-2"
          icon={note.action === "cancel" ? Square : Download}
          loading={busy}
          onClick={note.action === "cancel" ? cancel : start}
        >
          {note.action === "cancel" ? "Dừng tải" : "Tải tiếp"}
        </Button>
      )}
    </div>
  );
}
