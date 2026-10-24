import { MotionRegion } from "@/shared/MotionRegion";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { DiagnosticsView } from "@/shared/DiagnosticsView";
import { downloadText, reportFileName, type DiagnosticsReport } from "@/shared/diagnostics";
import { Button, Dialog, Skeleton } from "@/shared/ui";
import { ApiError, api } from "@/studio/api";
import { pickFolder, useAppInfo } from "@/studio/data";

// Hộp "Chẩn đoán" của một điện thoại đã ghép (OtherComputers): máy tính hỏi điện thoại qua cổng đồng bộ (webui/remote_books.py `diagnostics`) nên đi được
// cả khi điện thoại ở mạng khác (Tailscale, 4G) - không cần cáp hay adb. Điện thoại phải mở ABook và bật "Cho máy khác nghe thư viện này".

/** Số dòng nhật ký hộp xem (đủ để đọc; "Lưu nhật ký" lấy nhiều hơn). */
export const VIEW_LINES = 400;
export const SAVE_LINES = 2000;

const UNREACHABLE_HELP = "Trên điện thoại: Tải sách › bật “Cho máy khác nghe thư viện này”. Cùng Wi-Fi hay Tailscale.";

/** Lời báo cho một lần hỏi hỏng: câu của máy chủ (đã nói tên máy và lý do) và, nếu đáng, điều bạn có thể làm. */
export function failureView(error: unknown): { title: string; help: string } {
  const message = error instanceof Error ? error.message : String(error);
  const conflict = error instanceof ApiError && (error.status === 409 || error.status === 404);
  return { title: message, help: conflict ? "" : UNREACHABLE_HELP };
}

export function DiagnosticsBody({ report, error, loading }: { report?: DiagnosticsReport; error?: unknown; loading?: boolean }) {
  if (loading && !report) return <MotionRegion><Skeleton className="h-40" /></MotionRegion>;
  if (error) {
    const { title, help } = failureView(error);
    return (
      <MotionRegion as="div" role="alert" className="space-y-2 rounded-xl border border-line p-3 text-sm">
        <p className="font-medium text-danger [overflow-wrap:anywhere]">{title}</p>
        {help && <p className="text-xs text-fg-2 text-pretty">{help}</p>}
      </MotionRegion>
    );
  }
  return <MotionRegion>{report ? <DiagnosticsView report={report} /> : null}</MotionRegion>;
}

export function PhoneDiagnostics({ computer, open, onOpenChange }: { computer: { id: string; name: string }; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data: info } = useAppInfo();
  const query = useQuery({
    queryKey: ["phone-diagnostics", computer.id],
    queryFn: () => api<DiagnosticsReport>(`/api/remote/${computer.id}/diagnostics?lines=${VIEW_LINES}`),
    enabled: open,
    retry: false,
    staleTime: 0,
    gcTime: 0,
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      if (info?.dialogs) {
        const target = await pickFolder("Chọn nơi lưu nhật ký", "").catch(() => null);
        if (!target) return;
        const done = await api<{ name: string; folder: string }>(`/api/remote/${computer.id}/diagnostics/save`, { method: "POST", body: { lines: SAVE_LINES, target } });
        toast.success("Đã lưu nhật ký", { description: done.name });
      } else {
        // Trình duyệt: không có hộp chọn thư mục - tải về qua thanh tải của trình duyệt.
        const full = await api<DiagnosticsReport>(`/api/remote/${computer.id}/diagnostics?lines=${SAVE_LINES}`);
        downloadText(reportFileName(computer.name), JSON.stringify(full, null, 2));
        toast.success("Đã tải nhật ký về");
      }
    } catch (error) {
      toast.error("Chưa lưu được nhật ký", { description: failureView(error).title });
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Chẩn đoán ${computer.name}`}
      description="Nhật ký của điện thoại, có tên cuốn đang nghe; khoá, mã ghép, đường dẫn, IP đã được che. Xem lại trước khi gửi."
      width="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" icon={RefreshCw} loading={query.isFetching} onClick={() => void query.refetch()}>
            Làm mới
          </Button>
          <Button size="sm" variant="secondary" icon={Save} loading={saving} disabled={Boolean(query.error)} onClick={() => void save()}>
            Lưu nhật ký
          </Button>
        </div>
        <DiagnosticsBody report={query.data} error={query.error} loading={query.isLoading} />
      </div>
    </Dialog>
  );
}
