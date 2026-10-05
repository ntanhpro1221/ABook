import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Captions } from "lucide-react";
import { toast } from "sonner";
import { formatNumber } from "@/shared/format";
import { Button } from "@/shared/ui";
import { api } from "./api";

// Chữ sáng theo giọng đọc khi nghe (listen/words.ts). Sách mới tự có mốc từng chữ lúc đóng gói; sách đã làm từ trước cần căn một lần -
// việc chạy ngầm trên máy này (webui/word_timing.py), xong thì file sách của dự án được đóng lại kèm mốc chữ.

interface WordTimingsStatus {
  state: "idle" | "running" | "done" | "error";
  lines?: number;
  words?: number;
  done?: number;
  total?: number;
  error?: string;
  file?: string;
}

export function WordTimingsRow({ bookId, running }: { bookId: string; running: boolean }) {
  const client = useQueryClient();
  const key = ["word-timings", bookId];
  const status = useQuery({
    queryKey: key,
    queryFn: () => api<WordTimingsStatus>(`/api/books/${bookId}/word-timings`),
    refetchInterval: (query) => (query.state.data?.state === "running" ? 1000 : false),
  });
  const start = useMutation({
    mutationFn: () => api<WordTimingsStatus>(`/api/books/${bookId}/word-timings`, { method: "POST" }),
    onSuccess: (data) => client.setQueryData(key, data),
    onError: (error) => toast.error("Chưa thêm được chữ sáng", { description: (error as Error).message }),
  });
  const data = status.data;
  const busy = data?.state === "running" || start.isPending;
  const finished = data?.state === "done" && data.file;
  const lines = data?.lines ?? 0;
  const aligned = data?.words ?? 0;
  let note = "Tuỳ chọn: khi nghe, từng chữ sáng lên đúng lúc được đọc. Sách làm từ trước chưa có - thêm một lần, chạy ngầm, thường mất vài phút.";
  if (data?.state === "running") note = `Đang thêm chữ sáng… ${data.total ? Math.round(((data.done ?? 0) / data.total) * 100) : 0}%`;
  else if (data?.state === "error") note = data.error ?? "Chưa thêm được chữ sáng.";
  else if (finished) note = "Xong - file sách của dự án đã được làm lại kèm chữ sáng theo giọng đọc.";
  else if (lines > 0) note = `${formatNumber(aligned)}/${formatNumber(lines)} câu đã có chữ sáng theo giọng đọc.`;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-line p-3 text-sm">
      <Captions className="size-4 shrink-0 text-accent-text" />
      <span className="min-w-0 flex-1 basis-48">
        <span className="block font-semibold">Chữ sáng theo giọng đọc (tuỳ chọn)</span>
        <span className="block text-fg-2 text-pretty">{note}</span>
      </span>
      <Button size="sm" variant="secondary" loading={busy} disabled={running || (lines > 0 && aligned === lines && !finished)} onClick={() => start.mutate()}>
        Thêm chữ sáng
      </Button>
    </div>
  );
}
