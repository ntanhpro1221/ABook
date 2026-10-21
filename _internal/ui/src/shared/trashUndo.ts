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
 * `UNDO_TOAST_MS`; các lần xoá dùng chung một toast, mỗi mã giữ hạn riêng. Bấm hoàn tác mọi mã còn hạn rồi tải lại danh sách.
 * Không có mã (máy tính: thư mục khác ổ với thư
 * viện, vào Thùng rác ngay; điện thoại: xoá thẳng) thì chỉ báo. `restore` thay đường hoàn tác qua máy chủ (điện thoại gọi plugin);
 * `to` nói cuốn đi đâu sau hạn.
 */
type RemovedOptions = {
  message: string;
  title: string;
  undo?: string;
  note: string;
  onRestored: () => void;
  restore?: (token: string) => Promise<unknown>;
  to?: RemovedTo;
};

const pending = new Map<string, RemovedOptions & { expires: number }>();
let timer: ReturnType<typeof setTimeout> | undefined;
let restoring = false;
const TOAST_ID = "trash-undo";

function showPending(): void {
  clearTimeout(timer);
  const now = Date.now();
  for (const [token, item] of pending) if (item.expires <= now) pending.delete(token);
  const items = [...pending.values()];
  if (!items.length) {
    toast.dismiss(TOAST_ID);
    return;
  }
  const firstExpiry = Math.min(...items.map((item) => item.expires));
  const last = items[items.length - 1];
  timer = setTimeout(showPending, firstExpiry - now);
  toast.success(items.length === 1 ? last.message : `Đã bỏ ${items.length} cuốn`, {
    id: TOAST_ID,
    description: items.length === 1 ? removedDescription(last.note, true, last.to) : `Bạn có thể hoàn tác mỗi cuốn trong ${UNDO_SECONDS} giây kể từ lúc bỏ.`,
    duration: firstExpiry - now,
    action: {
      label: "Hoàn tác",
      onClick: async () => {
        if (restoring) return;
        restoring = true;
        try {
          await Promise.all([...pending].map(async ([token, item]) => {
            if (item.expires <= Date.now()) { pending.delete(token); return; }
            const restore = item.restore ?? ((value: string) => api<Restored>(`/api/trash/${value}/undo`, { method: "POST", body: {} }));
            try {
              const result = await restore(token);
              pending.delete(token);
              toast.success(`Đã khôi phục “${item.title}”`, { description: restoredNote((result ?? {}) as Partial<Restored>) });
              item.onRestored();
            } catch (error) {
              toast.error("Chưa hoàn tác được", { description: (error as Error).message });
            }
          }));
        } finally {
          restoring = false;
          // Sonner gỡ toast có action sau cú bấm: dựng lại những mã chưa hoàn tác được ở nhịp kế.
          clearTimeout(timer);
          timer = setTimeout(showPending, 0);
        }
      },
    },
  });
}

export function toastRemoved(options: RemovedOptions): void {
  const { message, undo, note, to } = options;
  if (undo) {
    pending.set(undo, { ...options, expires: Date.now() + UNDO_TOAST_MS });
    showPending();
    return;
  }
  toast.success(message, {
    description: removedDescription(note, Boolean(undo), to),
  });
}
