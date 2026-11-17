import { S } from "../shared/strings.generated";
import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "@/shared/toast";
import { api, hasLocalTransport } from "@/studio/api";

/**
 * Người xem cấp app của các lượt thêm sách trên máy chủ (`GET /api/listen/import/jobs`, abook/webui/import_jobs.py) - như thông báo của điện thoại. Màn
 * "Thêm sách" chỉ là một người xem: đóng màn giữa chừng thì lượt vẫn chạy, và chính người xem này (ở thanh bên, sống suốt app) làm mới thư viện khi
 * lượt xong, không nhờ lời gọi lại của hộp đã đóng. Lượt lỗi hay dở (app đóng giữa chừng) ở lại kèm "Thử lại". Cùng chữ với Android (vi.json).
 */
export type ImportJob = {
  id: string;
  kind: "book" | "text";
  name: string;
  state: "running" | "done" | "failed" | "interrupted";
  problem: string;
  result: { id?: string; how?: string } | null;
};
export type ImportJobsView = { revision: number; jobs: ImportJob[] };

export const IMPORT_JOBS_KEY = ["import-jobs"] as const;
const LIVE_MS = 800;

let screens = 0;
/** "Thêm sách" đang mở thì nó tự báo kết quả; người xem cấp app chỉ báo những lượt xong khi không ai nhìn. Trả hàm gỡ. */
export function addBookOpened(): () => void {
  screens += 1;
  return () => { screens -= 1; };
}

/** Những lượt vừa kết thúc giữa hai lần hỏi (trước đó đang chạy, hay chưa từng thấy). Lần hỏi đầu tiên không tính: đó là sổ cũ, không phải tin mới. */
export function endedSince(before: ImportJobsView | undefined, after: ImportJobsView): ImportJob[] {
  if (!before) return [];
  const known = new Map(before.jobs.map((job) => [job.id, job.state]));
  return after.jobs.filter((job) => job.state !== "running" && (known.get(job.id) ?? "running") === "running");
}

/** Lời báo khi một lượt xong mà màn "Thêm sách" đã đóng: cùng chữ với thông báo "Đã thêm" / "Đã cập nhật" / lỗi của điện thoại. */
export function endedText(job: ImportJob): { ok: boolean; text: string; note?: string } {
  if (job.state === "done") {
    const how = job.result?.how;
    return { ok: true, text: how === "updated" ? S.s_da_cap_nhat_0_627a2681(job.name) : how === "existing" ? S.s_da_co_trong_thu_vien_3bb6eeb4 : S.s_da_them_0_ea40abe7(job.name) };
  }
  return { ok: false, text: S.s_chua_them_duoc_sach_b327e086, note: job.state === "interrupted" ? S.s_import_interrupted : job.problem };
}

export function useImportJobs() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: IMPORT_JOBS_KEY,
    queryFn: () => api<ImportJobsView>("/api/listen/import/jobs"),
    enabled: !hasLocalTransport(),
    // Không có nhịp hỏi suốt ngày: hỏi lúc mở app (lượt dở của lần trước), khi hộp "Thêm sách" đóng, và mỗi 800 ms khi còn lượt đang chạy.
    refetchInterval: (q) => (q.state.data?.jobs.some((job) => job.state === "running") ? LIVE_MS : false),
  });
  const last = useRef<ImportJobsView | undefined>(undefined);
  useEffect(() => {
    const view = query.data;
    if (!view || view.revision === last.current?.revision) return;
    const ended = endedSince(last.current, view);
    last.current = view;
    if (ended.some((job) => job.state === "done")) {
      void client.invalidateQueries({ queryKey: ["listen"] });
      void client.invalidateQueries({ queryKey: ["library"] });
    }
    if (screens > 0) return;
    for (const job of ended) {
      const said = endedText(job);
      if (said.ok) toast.success(said.text);
      else toast.error(said.text, { description: said.note });
    }
  }, [query.data, client]);
  const jobs = query.data?.jobs ?? [];
  return {
    running: jobs.filter((job) => job.state === "running"),
    problems: jobs.filter((job) => job.state === "failed" || job.state === "interrupted"),
    /** Gọi khi màn vừa gửi một lượt: hỏi ngay, khỏi chờ nhịp thưa. */
    watch: () => void client.invalidateQueries({ queryKey: IMPORT_JOBS_KEY }),
    retry: async (id: string) => {
      await api(`/api/listen/import/jobs/${id}/retry`, { method: "POST" });
      void client.invalidateQueries({ queryKey: IMPORT_JOBS_KEY });
    },
    dismiss: async (id: string) => {
      await api(`/api/listen/import/jobs/${id}`, { method: "DELETE" });
      void client.invalidateQueries({ queryKey: IMPORT_JOBS_KEY });
    },
  };
}
