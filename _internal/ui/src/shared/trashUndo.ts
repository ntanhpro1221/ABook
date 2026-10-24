import { toast } from "@/shared/toast";
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

/** Lời dưới "Đã khôi phục": vì sao cuốn về dưới tên khác; cuốn từng xếp hàng chờ thì nói rõ là hàng chờ không tự xếp lại. */
export function restoredNote(result: Partial<Pick<Restored, "renamed" | "wasQueued" | "dataLeft">>): string | undefined {
  const notes = [
    result.renamed ? "Chỗ cũ đã có một cuốn cùng tên, nên thư viện sẽ hiện hai cuốn trùng tên - bạn có thể đổi tên một cuốn cho dễ phân biệt." : "",
    result.dataLeft ? "Chưa mang theo được chỗ đang nghe và dấu trang của cuốn này." : "",
    result.wasQueued ? "Cuốn này đã bị bỏ khỏi hàng chờ làm sách - bấm Bắt đầu nếu muốn xếp lại." : "",
  ].filter(Boolean);
  return notes.length ? notes.join(" ") : undefined;
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
    description: items.length === 1 ? removedDescription(last.note, true, last.to) : `Bạn có thể hoàn tác mỗi cuốn trong ${UNDO_SECONDS} giây kể từ lúc bỏ.`,
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
              toast.success(restoredMessage(item.title, restored), { description: restoredNote(restored) });
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
