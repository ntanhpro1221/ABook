import { useQueryClient } from "@tanstack/react-query";
import { Download, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { formatSize, formatWhen } from "@/shared/format";
import { Button, Dialog } from "@/shared/ui";
import { oldSaveTitle, refreshOldSaves, type OldSave } from "./oldSaveList";
import { EbookLibrary } from "./plugins";

// Danh sách "Bản lưu cũ" trong Cài đặt (nhóm do SettingsScreen vẽ, chỉ khi có file): mỗi dòng "Lưu ra…" và "Xoá…".

export const OLD_SAVES_HINT = "Bản trước của một lần lưu hỏng. Lưu ra để không mất.";

/** Hộp xác nhận xoá - nói rõ không lấy lại được. Không có trạng thái riêng: nơi gọi giữ `busy`. */
export function OldSaveDeleteDialog({ file, busy, onConfirm, onCancel }: { file: OldSave | null; busy: boolean; onConfirm: () => void; onCancel: () => void }) {
  return (
    <Dialog
      open={file !== null}
      onOpenChange={(open) => !open && !busy && onCancel()}
      title="Xoá bản lưu cũ?"
      description={file ? `“${oldSaveTitle(file.name)}” (${formatSize(file.size)}) sẽ bị xoá khỏi điện thoại và không lấy lại được.` : undefined}
      width="max-w-sm"
    >
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          Giữ lại
        </Button>
        <Button variant="danger" icon={Trash2} loading={busy} onClick={onConfirm}>
          Xoá
        </Button>
      </div>
    </Dialog>
  );
}

/** Lưu bản cũ ra chỗ người dùng chọn (hộp của hệ thống). Trả true khi đã lưu; bỏ qua hộp thì false, im lặng. */
export async function exportOldSave(file: OldSave): Promise<boolean> {
  try {
    const { saved } = await EbookLibrary.exportOldSave({ name: file.name });
    if (saved) toast.success("Đã lưu bản cũ ra chỗ bạn chọn");
    return saved;
  } catch (error) {
    toast.error("Chưa lưu ra được", { description: error instanceof Error ? error.message : String(error) });
    return false;
  }
}

/** Xoá hẳn bản cũ (đã xác nhận). Trả true khi xoá xong. */
export async function deleteOldSave(file: OldSave): Promise<boolean> {
  try {
    await EbookLibrary.deleteOldSave({ name: file.name });
    toast("Đã xoá bản lưu cũ");
    return true;
  } catch (error) {
    toast.error("Chưa xoá được", { description: error instanceof Error ? error.message : String(error) });
    return false;
  }
}

export function OldSavesList({ files }: { files: OldSave[] }) {
  const client = useQueryClient();
  const [asking, setAsking] = useState<OldSave | null>(null);
  const [busy, setBusy] = useState(false);
  const confirm = async () => {
    if (!asking) return;
    setBusy(true);
    const done = await deleteOldSave(asking);
    setBusy(false);
    if (done) setAsking(null);
    void refreshOldSaves(client);
  };
  return (
    <>
      <p className="px-4 py-3 text-xs leading-snug text-fg-2">{OLD_SAVES_HINT}</p>
      {files.map((file) => (
        <div key={file.name} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3.5">
          <div className="min-w-0 flex-[1_1_12rem]">
            <div className="truncate text-[0.9375rem] font-medium">{oldSaveTitle(file.name)}</div>
            <div className="mt-0.5 text-xs text-fg-2">
              {formatSize(file.size)} · {formatWhen(file.modified)}
            </div>
          </div>
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="secondary" icon={Download} onClick={() => void exportOldSave(file)}>
              Lưu ra…
            </Button>
            <Button size="sm" variant="secondary" icon={Trash2} onClick={() => setAsking(file)}>
              Xoá…
            </Button>
          </div>
        </div>
      ))}
      <OldSaveDeleteDialog file={asking} busy={busy} onConfirm={() => void confirm()} onCancel={() => setAsking(null)} />
    </>
  );
}
