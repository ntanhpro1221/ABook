import { Save } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { Button } from "@/shared/ui";
import { MoreInfo } from "@/shared/SettingsNav";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo } from "@/studio/data";

/** Cài đặt → Chẩn đoán: "Gửi nhật ký" của chính máy tính - gói .zip (thông tin máy, phiên bản, đuôi nhật ký của app) ghi vào thư mục bạn chọn để bạn
 *  tự gửi cho người sửa lỗi. App không gửi gì đi (webui/diagnostics.py). */
export const OWN_DIAGNOSTICS_HINT = "Xem lại trước khi gửi; bạn tự gửi đi.";
/** Quyền riêng tư của gói nhật ký: gập sau "Tìm hiểu thêm". */
export const OWN_DIAGNOSTICS_MORE =
  "Gồm thông tin máy và nhật ký gần nhất; tự che khoá, mã ghép, đường dẫn và IP nhận ra được.";

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
      toast.success(done.folder ? `Đã lưu gói nhật ký trong ${done.folder}` : "Đã lưu gói nhật ký");
    } catch (error) {
      toast.error("Chưa lưu được gói nhật ký", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex items-center justify-between gap-6">
      <div className="min-w-0 text-[0.8125rem] text-fg-2 text-pretty">
        {OWN_DIAGNOSTICS_HINT}
        <MoreInfo className="mt-1">{OWN_DIAGNOSTICS_MORE}</MoreInfo>
      </div>
      <Button size="sm" variant="secondary" icon={Save} loading={busy} onClick={() => void send()} className="shrink-0">
        Gửi nhật ký
      </Button>
    </div>
  );
}
