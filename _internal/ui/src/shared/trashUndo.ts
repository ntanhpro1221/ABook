import { toast, toastDone } from "@/shared/toast";
import { moveBookStorage } from "@/shared/bookStorage";
import { api } from "@/studio/api";

/** Khớp `trash_pending.UNDO_SECONDS` của máy tính và `TrashPending.UNDO_SECONDS` của điện thoại: hết chừng này giây cuốn vừa xoá mới đi tiếp (Thùng rác / xoá hẳn). */
export const UNDO_SECONDS = 30;
/** Nút "Hoàn tác" sống ngắn hơn hạn của máy chủ một chút: bấm ở giây chót không bị 404 vì độ trễ. */
export const UNDO_TOAST_MS = (UNDO_SECONDS - 2) * 1000;

/** `renamed`: chỗ cũ đã có cuốn cùng tên nên cuốn về dưới tên khác (`title` - tên thư mục mới, "<tên> (2)"). Máy chủ đã chuyển chỗ nghe
 *  sang mã sách mới thì kèm `oldId`/`newId` (máy này chuyển theo những gì nó nhớ theo mã sách); `dataLeft`: chưa chuyển được. */
type Restored = { ok: boolean; title?: string; renamed?: boolean; wasQueued?: boolean; oldId?: string; newId?: string; dataLeft?: boolean };

/** "Đã khôi phục “X”" - hay "… vào thư mục “X (2)”" khi chỗ cũ đã có cuốn cùng tên (thư viện vẫn hiện tên sách, không phải tên thư mục). */
export function restoredMessage(title: string, result: Partial<Pick<Restored, "title" | "renamed">>): string {
  return result.renamed && result.title ? `Đã khôi phục “${title}” vào thư mục “${result.title}”` : `Đã khôi phục “${title}”`;
}

/** Lưu ý của "Đã khôi phục" (khôi phục thiếu gì đó thì thành cảnh báo): thư viện có hai cuốn trùng tên (tên mới đã nằm trong chữ chính); chỗ nghe
 *  chưa mang theo; cuốn từng xếp hàng chờ thì hàng chờ không tự xếp lại. */
export function restoredNote(result: Partial<Pick<Restored, "renamed" | "wasQueued" | "dataLeft">>): string | undefined {
  const notes = [
    result.renamed ? "Thư viện có hai cuốn trùng tên." : "",
    result.dataLeft ? "Chưa mang theo chỗ nghe." : "",
    result.wasQueued ? "Chưa xếp lại hàng chờ làm sách." : "",
  ].filter(Boolean);
  return notes.length ? notes.join(" ") : undefined;
}

/**
 * Báo đã xoá một sách / dự án (`message`: "Đã xoá dự án “X”"). Nơi xoá trả `undo` (mã hoàn tác) thì toast có nút "Hoàn tác" trong
 * `UNDO_TOAST_MS`; các lần xoá dùng chung một toast, mỗi mã giữ hạn riêng. Bấm hoàn tác mọi mã còn hạn rồi tải lại danh sách.
 * Không có mã (máy tính: thư mục khác ổ với thư
 * viện, vào Thùng rác ngay; điện thoại: xoá thẳng) thì chỉ báo. `restore` thay đường hoàn tác qua máy chủ (điện thoại gọi plugin).
 * Thông báo là MỘT dòng + nút Hoàn tác: cuốn đi đâu sau hạn đã nói ở hộp xác nhận trước khi xoá.
 */
type RemovedOptions = {
  message: string;
  title: string;
  undo?: string;
  onRestored: () => void;
  restore?: (token: string) => Promise<unknown>;
};

const pending = new Map<string, RemovedOptions & { expires: number }>();
let timer: ReturnType<typeof setTimeout> | undefined;
let restoring = false;
/** Mã toast đổi sau mỗi cú bấm Hoàn tác: Sonner gỡ toast vừa bấm theo mã của nó ~200 ms sau cú bấm, nên toast hiện lại trong lúc ấy
 *  (hoàn tác lỗi nhanh, cuốn vừa bỏ thêm) mà dùng mã cũ thì bị gỡ theo - cuốn còn chờ mà không còn nút Hoàn tác. */
let generation = 0;
const toastId = () => `trash-undo-${generation}`;

function showPending(): void {
  clearTimeout(timer);
  const now = Date.now();
  for (const [token, item] of pending) if (item.expires <= now) pending.delete(token);
  const items = [...pending.values()];
  if (!items.length) {
    toast.dismiss(toastId());
    generation += 1; // Sonner còn giữ toast đang thoát ~200 ms: lần bỏ kế hiện dưới mã mới, không gộp vào toast đang biến mất
    return;
  }
  const firstExpiry = Math.min(...items.map((item) => item.expires));
  const last = items[items.length - 1];
  const id = toastId();
  const shown = [...pending.keys()];
  timer = setTimeout(showPending, firstExpiry - now);
  toast.success(items.length === 1 ? last.message : `Đã bỏ ${items.length} cuốn`, {
    id,
    duration: firstExpiry - now,
    // Gạt / đóng toast = không hoàn tác những cuốn ấy: lần bỏ sau không gộp chúng vào "Đã bỏ N cuốn" và Hoàn tác không trả chúng về.
    onDismiss: () => {
      if (id !== toastId()) return;
      generation += 1; // như trên: toast này đang thoát
      for (const token of shown) pending.delete(token);
      if (!pending.size) clearTimeout(timer);
    },
    action: {
      label: "Hoàn tác",
      onClick: async () => {
        generation += 1;
        if (restoring) return;
        restoring = true;
        try {
          // Lần lượt, cũ trước (thứ tự bỏ): xoá "X", thêm "X" mới rồi bỏ luôn nó - "X" cũ về đúng chỗ của nó, cuốn mới vào "X (2)". Chạy
          // cùng lúc thì ai về chỗ cũ là may rủi.
          for (const [token, item] of [...pending]) {
            if (item.expires <= Date.now()) { pending.delete(token); continue; }
            const restore = item.restore ?? ((value: string) => api<Restored>(`/api/trash/${value}/undo`, { method: "POST", body: {} }));
            try {
              const result = await restore(token);
              pending.delete(token);
              const restored = (result ?? {}) as Partial<Restored>;
              if (restored.oldId && restored.newId) moveBookStorage(restored.oldId, restored.newId);
              toastDone(restoredMessage(item.title, restored), restoredNote(restored));
              item.onRestored();
            } catch (error) {
              toast.error("Chưa hoàn tác được", { description: (error as Error).message });
            }
          }
        } finally {
          restoring = false;
          // Sonner gỡ toast có action sau cú bấm: dựng lại những mã chưa hoàn tác được (dưới mã toast mới).
          clearTimeout(timer);
          timer = setTimeout(showPending, 0);
        }
      },
    },
  });
}

export function toastRemoved(options: RemovedOptions): void {
  const { message, undo } = options;
  if (undo) {
    pending.set(undo, { ...options, expires: Date.now() + UNDO_TOAST_MS });
    showPending();
    return;
  }
  toast.success(message);
}
