import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, Progress } from "@/shared/ui";
import { api } from "./api";
import { STUDENT_SIZE_LABEL, studentLabel, studentPercent, type LocalMusicView } from "./musicLocal";

/** Điện thoại: bài nhập vào chưa phân tích vì bộ phân tích âm thanh chưa có trên máy. Người dùng thấy dung lượng và bấm mới tải (không tự
 *  tải, nhất là khi đang dùng dữ liệu di động); tải xong máy tự phân tích nốt các bài đã nhập. Máy tính không có `student`: không hiện gì. */
export function MusicStudentNotice({ view, queryKey }: { view: LocalMusicView | undefined; queryKey: readonly unknown[] }) {
  const client = useQueryClient();
  const student = view?.student;
  const [starting, setStarting] = useState(false);
  const busy = student?.state === "downloading" || Boolean(student?.analysing);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => {
      void api<LocalMusicView>("/api/music/local").then((next) => client.setQueryData(queryKey, next));
    }, 1000);
    return () => clearInterval(timer);
  }, [busy, client, queryKey]);
  if (!student || (view?.analyzer && !student.analysing)) return null;
  const start = async () => {
    setStarting(true);
    try {
      client.setQueryData(queryKey, await api<LocalMusicView>("/api/music/local/student", { method: "POST" }));
    } finally {
      setStarting(false);
    }
  };
  const failed = student.state === "error";
  return (
    <div role="status" className="space-y-1.5 text-xs text-fg-2">
      <p className={failed ? "text-danger" : undefined}>{studentLabel(student)}</p>
      {student.state === "downloading" ? (
        <Progress value={studentPercent(student) / 100} size="sm" running label="Đang tải bộ phân tích nhạc" />
      ) : student.analysing ? null : (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" loading={starting} onClick={() => void start()}>
            {failed ? "Thử lại" : `Tải bộ phân tích (${STUDENT_SIZE_LABEL})`}
          </Button>
          {student.metered && !failed && <span className="text-warning">Bạn đang dùng dữ liệu di động - nên đợi khi có Wi-Fi.</span>}
        </div>
      )}
    </div>
  );
}
