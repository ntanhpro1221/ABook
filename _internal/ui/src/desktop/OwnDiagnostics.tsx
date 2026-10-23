import { Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/shared/ui";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo } from "@/studio/data";

/** Cài đặt → Chẩn đoán: "Gửi nhật ký" của chính máy tính - gói .zip (thông tin máy, phiên bản, đuôi nhật ký của app) ghi vào thư mục bạn chọn để bạn
 *  tự gửi cho người sửa lỗi. App không gửi gì đi (webui/diagnostics.py). */
export const OWN_DIAGNOSTICS_HINT =
  "Gói nhật ký của app trên máy tính này (phiên bản, hệ điều hành, các dòng nhật ký gần nhất). Có tên máy bạn đã ghép; app che các dạng khóa, mã ghép, đường dẫn riêng, địa chỉ IP nhận diện được. Bạn nên xem lại trước khi gửi. App chỉ lưu thành file - bạn tự gửi đi.";

export function OwnDiagnostics() {
  const { data: info } = useAppInfo();
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      let target = "";
      if (info?.dialogs) {
        const picked = await pickFolder("Chọn nơi lưu gói nhật ký", "").catch(() => null);
        if (!picked) return;
        target = picked;
      }
      const done = await api<{ name: string; folder: string }>("/api/diagnostics/save", { method: "POST", body: target ? { target } : {} });
      toast.success("Đã lưu gói nhật ký", { description: `${done.name}${done.folder ? ` - trong ${done.folder}` : ""}` });
    } catch (error) {
      toast.error("Chưa lưu được gói nhật ký", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex max-w-2xl items-start justify-between gap-6">
      <p className="min-w-0 text-[0.8125rem] text-fg-2 text-pretty">{OWN_DIAGNOSTICS_HINT}</p>
      <Button size="sm" variant="secondary" icon={Save} loading={busy} onClick={() => void send()} className="shrink-0">
        Gửi nhật ký
      </Button>
    </div>
  );
}
