import { toast } from "sonner";
import { api } from "@/studio/api";

/** Khớp `trash_pending.UNDO_SECONDS` của máy chủ: sau chừng này giây cuốn vừa xoá mới vào Thùng rác của Windows. */
export const UNDO_SECONDS = 30;
/** Nút "Hoàn tác" sống ngắn hơn hạn của máy chủ một chút: bấm ở giây chót không bị 404 vì độ trễ. */
export const UNDO_TOAST_MS = (UNDO_SECONDS - 2) * 1000;

type Restored = { ok: boolean; title?: string; wasQueued?: boolean };

/** Lời dưới "Đã khôi phục": cuốn từng xếp hàng chờ thì nói rõ là hàng chờ không tự xếp lại. */
export function restoredNote(result: Pick<Restored, "wasQueued">): string | undefined {
  return result.wasQueued ? "Cuốn này đã bị bỏ khỏi hàng chờ làm sách - bấm Bắt đầu nếu muốn xếp lại." : undefined;
}

/** Lời dưới toast xoá: `note` là điều riêng của từng nơi (file gốc không bị đụng...), phần Thùng rác thì giống nhau. */
export function removedDescription(note: string, hasUndo: boolean): string {
  const bin = hasUndo
    ? `Hoàn tác được trong ${UNDO_SECONDS} giây; sau đó cuốn nằm trong Thùng rác của Windows, khôi phục từ đó được.`
    : "Cuốn đã vào Thùng rác của Windows, khôi phục từ đó được.";
  return [note, bin].filter(Boolean).join(" ");
}

/**
 * Báo đã xoá một sách / dự án (`message`: "Đã xoá dự án “X”"). Máy chủ trả `undo` (mã hoàn tác) thì toast có nút "Hoàn tác" trong
 * `UNDO_TOAST_MS`; bấm là cuốn về đúng chỗ cũ rồi `onRestored` tải lại danh sách. Không có mã (thư mục khác ổ với thư viện: vào
 * Thùng rác ngay) thì chỉ báo.
 */
export function toastRemoved(options: { message: string; title: string; undo?: string; note: string; onRestored: () => void }): void {
  const { message, title, undo, note, onRestored } = options;
  toast.success(message, {
    description: removedDescription(note, Boolean(undo)),
    ...(undo
      ? {
          duration: UNDO_TOAST_MS,
          action: {
            label: "Hoàn tác",
            onClick: () => {
              api<Restored>(`/api/trash/${undo}/undo`, { method: "POST", body: {} })
                .then((result) => {
                  toast.success(`Đã khôi phục “${title}”`, { description: restoredNote(result) });
                  onRestored();
                })
                .catch((error: Error) => toast.error("Chưa hoàn tác được", { description: error.message }));
            },
          },
        }
      : {}),
  });
}
