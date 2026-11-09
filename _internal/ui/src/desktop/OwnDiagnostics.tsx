import { S } from "../shared/strings.generated";
import { Save } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { Button } from "@/shared/ui";
import { MoreInfo } from "@/shared/SettingsNav";
import { api } from "@/studio/api";
import { pickFolder, useAppInfo } from "@/studio/data";

/** Cài đặt → Chẩn đoán: "Gửi nhật ký" của chính máy tính - gói .zip (thông tin máy, phiên bản, đuôi nhật ký của app) ghi vào thư mục bạn chọn để bạn
 *  tự gửi cho người sửa lỗi. App không gửi gì đi (webui/diagnostics.py). */
export const OWN_DIAGNOSTICS_HINT = S.s_xem_lai_truoc_khi_gui_ban_tu_gui_di_755dd05a;
/** Quyền riêng tư của gói nhật ký: gập sau "Tìm hiểu thêm". */
export const OWN_DIAGNOSTICS_MORE =
  S.s_gom_thong_tin_may_va_nhat_ky_gan_nhat_tu_c_888894b2;

export function OwnDiagnostics() {
  const { data: info } = useAppInfo();
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      let target = "";
      if (info?.dialogs) {
        const picked = await pickFolder(S.s_chon_noi_luu_goi_nhat_ky_17fab271, "").catch(() => null);
        if (!picked) return;
        target = picked;
      }
      const done = await api<{ name: string; folder: string }>("/api/diagnostics/save", { method: "POST", body: target ? { target } : {} });
      toast.success(done.folder ? S.s_da_luu_goi_nhat_ky_trong_0_cb2e175c(done.folder) : S.s_da_luu_goi_nhat_ky_82b1b295);
    } catch (error) {
      toast.error(S.s_chua_luu_duoc_goi_nhat_ky_ec27bfaf, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div>
    <div className="flex items-center justify-between gap-6">
      <div className="min-w-0 text-[0.8125rem] text-fg-2 text-pretty">
        {OWN_DIAGNOSTICS_HINT}
      </div>
      <Button size="sm" variant="ghost" icon={Save} loading={busy} onClick={() => void send()} className="shrink-0">{S.s_gui_nhat_ky_2e35a4f8}</Button>
    </div>
    <MoreInfo>{OWN_DIAGNOSTICS_MORE}</MoreInfo>
    </div>
  );
}
