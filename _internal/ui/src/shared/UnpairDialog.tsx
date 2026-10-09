import { Button, Dialog } from "./ui";
import type { UnpairChoice, UnpairCopy } from "./unpair";

/** Hộp hỏi khi gỡ ghép một máy còn sửa chưa gửi (copy từ `unpairCopy`): gửi trước rồi gỡ / vẫn gỡ, bỏ thay đổi / huỷ. Lỗi lần gửi trước
 *  hiện ngay trong hộp, hộp ở nguyên để chọn lại - không gỡ gì khi gửi hỏng. */
export function UnpairDialog({
  copy,
  busy,
  error,
  onChoose,
  onCancel,
}: {
  copy: UnpairCopy | null;
  busy: UnpairChoice | null;
  error: string | null;
  onChoose: (choice: UnpairChoice) => void;
  onCancel: () => void;
}) {
  return (
    <Dialog open={copy !== null} onOpenChange={(open) => !open && !busy && onCancel()} title={copy?.title ?? ""}>
      <div className="space-y-2 text-sm leading-snug text-fg-2">
        {copy?.lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
        {error && (
          <p role="alert" className="text-danger">
            {error}
          </p>
        )}
      </div>
      <div className="mt-5 flex flex-col gap-2">
        {copy?.send && (
          <Button variant="primary" loading={busy === "send"} disabled={busy !== null} onClick={() => onChoose("send")}>
            {copy.send}
          </Button>
        )}
        <Button variant="danger" loading={busy === "discard"} disabled={busy !== null} onClick={() => onChoose("discard")}>
          {copy?.discard}
        </Button>
        <Button variant="ghost" disabled={busy !== null} onClick={onCancel}>
          {copy?.cancel}
        </Button>
      </div>
    </Dialog>
  );
}
