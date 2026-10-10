import { toast } from "sonner";
import { api } from "@/studio/api";

/** Khớp `trash_pending.UNDO_SECONDS` của máy tính và `TrashPending.UNDO_SECONDS` của điện thoại: hết chừng này giây cuốn vừa xoá mới đi tiếp (Thùng rác / xoá hẳn). */
export const UNDO_SECONDS = 30;
/** Nút "Hoàn tác" sống ngắn hơn hạn của máy chủ một chút: bấm ở giây chót không bị 404 vì độ trễ. */
export const UNDO_TOAST_MS = (UNDO_SECONDS - 2) * 1000;

type Restored = { ok: boolean; title?: string; wasQueued?: boolean };

/** Lời dưới "Đã khôi phục": cuốn từng xếp hàng chờ thì nói rõ là hàng chờ không tự xếp lại. */
export function restoredNote(result: Partial<Pick<Restored, "wasQueued">>): string | undefined {
  return result.wasQueued ? "Cuốn này đã bị bỏ khỏi hàng chờ làm sách - bấm Bắt đầu nếu muốn xếp lại." : undefined;
}

/** Cuốn đi đâu sau hạn Hoàn tác: máy tính - Thùng rác của Windows (khôi phục từ đó được); điện thoại không có Thùng rác - xoá hẳn. */
export type RemovedTo = "bin" | "gone";

/** Lời dưới toast xoá: `note` là điều riêng của từng nơi (file gốc không bị đụng...), phần sau hạn thì theo `to`. */
export function removedDescription(note: string, hasUndo: boolean, to: RemovedTo = "bin"): string {
  const after =
    to === "gone"
      ? hasUndo
        ? `Hoàn tác được trong ${UNDO_SECONDS} giây; sau đó cuốn bị xoá hẳn khỏi điện thoại.`
        : "Cuốn đã bị xoá hẳn khỏi điện thoại."
      : hasUndo
        ? `Hoàn tác được trong ${UNDO_SECONDS} giây; sau đó cuốn nằm trong Thùng rác của Windows, khôi phục từ đó được.`
        : "Cuốn đã vào Thùng rác của Windows, khôi phục từ đó được.";
  return [note, after].filter(Boolean).join(" ");
}

/**
 * Báo đã xoá một sách / dự án (`message`: "Đã xoá dự án “X”"). Nơi xoá trả `undo` (mã hoàn tác) thì toast có nút "Hoàn tác" trong
 * `UNDO_TOAST_MS`; bấm là cuốn về đúng chỗ cũ rồi `onRestored` tải lại danh sách. Không có mã (máy tính: thư mục khác ổ với thư
 * viện, vào Thùng rác ngay; điện thoại: xoá thẳng) thì chỉ báo. `restore` thay đường hoàn tác qua máy chủ (điện thoại gọi plugin);
 * `to` nói cuốn đi đâu sau hạn.
 */
export function toastRemoved(options: {
  message: string;
  title: string;
  undo?: string;
  note: string;
  onRestored: () => void;
  restore?: (token: string) => Promise<unknown>;
  to?: RemovedTo;
}): void {
  const { message, title, undo, note, onRestored, to } = options;
  const restore = options.restore ?? ((token: string) => api<Restored>(`/api/trash/${token}/undo`, { method: "POST", body: {} }));
  toast.success(message, {
    description: removedDescription(note, Boolean(undo), to),
    ...(undo
      ? {
          duration: UNDO_TOAST_MS,
          action: {
            label: "Hoàn tác",
            onClick: () => {
              Promise.resolve(restore(undo))
                .then((result) => {
                  toast.success(`Đã khôi phục “${title}”`, { description: restoredNote((result ?? {}) as Partial<Restored>) });
                  onRestored();
                })
                .catch((error: Error) => toast.error("Chưa hoàn tác được", { description: error.message }));
            },
          },
        }
      : {}),
  });
}
