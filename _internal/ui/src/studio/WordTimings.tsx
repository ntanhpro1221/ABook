import { S } from "../shared/strings.generated";
import { TickingValue } from "@/shared/TickingValue";
import { MotionRegion } from "@/shared/MotionRegion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Captions } from "lucide-react";
import { toast } from "@/shared/toast";
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
    onError: (error) => toast.error(S.s_chua_them_duoc_chu_sang_ab107f49, { description: (error as Error).message }),
  });
  const data = status.data;
  const busy = data?.state === "running" || start.isPending;
  const finished = data?.state === "done" && data.file;
  const lines = data?.lines ?? 0;
  const aligned = data?.words ?? 0;
  let note: string = S.s_them_chu_sang_theo_giong_doc_chay_nen_vai_161ec74e;
  if (data?.state === "running") note = S.s_dang_them_chu_sang_0_7874b215(data.total ? Math.round(((data.done ?? 0) / data.total) * 100) : 0);
  else if (data?.state === "error") note = data.error ?? S.s_chua_them_duoc_chu_sang_a019d5cb;
  else if (finished) note = S.s_xong_file_sach_cua_du_an_da_duoc_lam_lai_k_a150d813;
  else if (lines > 0) note = S.s_0_1_cau_da_co_chu_sang_theo_giong_doc_1f88eb97(formatNumber(aligned), formatNumber(lines));
  return (
    <MotionRegion as="div" className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 py-3 text-sm">
      <Captions className="size-4 shrink-0 text-accent-text" />
      <span className="min-w-0 flex-1 basis-48">
        <span className="block font-semibold">{S.s_chu_sang_02de067c}</span>
        <TickingValue className="block text-fg-2 text-pretty">{note}</TickingValue>
      </span>
      <Button size="sm" variant="ghost" loading={busy} disabled={running || (lines > 0 && aligned === lines && !finished)} onClick={() => start.mutate()}>{S.s_them_chu_sang_9bfff902}</Button>
    </MotionRegion>
  );
}
