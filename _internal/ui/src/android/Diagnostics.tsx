import { MotionRegion } from "@/shared/MotionRegion";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { DiagnosticsView } from "@/shared/DiagnosticsView";
import type { DiagnosticsReport } from "@/shared/diagnostics";
import { Skeleton } from "@/shared/ui";
import { EbookLibrary } from "./plugins";

// Cài đặt → Chẩn đoán (Diagnostics.kt, AppLog.kt): xem nhật ký của app, gửi nhật ký, xoá nhật ký. Khi điện thoại ở xa Wi-Fi nhà và không có cáp,
// đây là cách đưa nhật ký cho người sửa lỗi: bạn tự bấm "Gửi nhật ký" rồi chọn gửi qua đâu (Zalo, Drive, email…). App không tự gửi đi đâu.

export const DIAGNOSTICS_HINT = "Việc app làm gần đây, để tìm lỗi. Xem lại trước khi gửi.";
/** Quyền riêng tư của nhật ký: gập sau "Tìm hiểu thêm". */
export const DIAGNOSTICS_MORE =
  "Có tên sách; che khoá, mã ghép, IP và đường dẫn nhận ra được. Máy ghép đọc được khi bật “Cho máy khác nghe thư viện này”.";
export const SEND_HINT = "Bạn chọn gửi cho ai; app không tự gửi.";
export const CLEAR_HINT = "Gồm cả các lần văng đã ghi.";
export const VIEW_LINES = 500;

/** Trạng thái và ba việc của mục Chẩn đoán: xem (tải bản chẩn đoán), gửi (bảng chia sẻ), xoá. */
export function useDiagnostics() {
  const [open, setOpen] = useState(false);
  const [report, setReport] = useState<DiagnosticsReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setReport(await EbookLibrary.diagnostics({ lines: VIEW_LINES }));
    } catch (failure) {
      setError((failure as Error).message || "Không đọc được nhật ký");
    } finally {
      setLoading(false);
    }
  };
  const send = async () => {
    setSending(true);
    try {
      await EbookLibrary.shareDiagnostics();
    } catch (failure) {
      toast.error("Chưa gửi được nhật ký", { description: (failure as Error).message });
    } finally {
      setSending(false);
    }
  };
  const clear = async () => {
    try {
      await EbookLibrary.clearDiagnostics();
      toast.success("Đã xoá nhật ký");
      if (open) await load();
    } catch (failure) {
      toast.error("Chưa xoá được nhật ký", { description: (failure as Error).message });
    }
  };
  const changeOpen = (next: boolean) => {
    setOpen(next);
    if (next) void load();
  };
  return { open, changeOpen, report, error, loading, sending, load, send, clear };
}

/** Nội dung tấm trượt "Nhật ký của ABook": lỗi (nếu có) rồi tóm tắt + nhật ký cuộn được. */
export function DiagnosticsPanel({ report, error, loading }: { report: DiagnosticsReport | null; error: string; loading: boolean }) {
  return (
    <MotionRegion>
      {error && (
        <p role="alert" className="text-sm text-danger [overflow-wrap:anywhere]">
          {error}
        </p>
      )}
      {loading && !report ? <Skeleton className="h-40" /> : report && <DiagnosticsView report={report} />}
    </MotionRegion>
  );
}
