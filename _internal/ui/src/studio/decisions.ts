import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "./api";

/** Làm mới mọi chỗ một quyết định của người nghe (người nói, giới, cách đọc tên) chạm tới. */
export function refreshAfterDecision(client: QueryClient, bookId: string) {
  void client.invalidateQueries({ queryKey: ["work", bookId] });
  void client.invalidateQueries({ queryKey: ["book", bookId] });
  void client.invalidateQueries({ queryKey: ["library"] });
  void client.invalidateQueries({ queryKey: ["listen", "cast", bookId] });
  void client.invalidateQueries({ queryKey: ["cast", bookId] });
  void client.invalidateQueries({ queryKey: ["pronunciations", bookId] });
  void client.invalidateQueries({ queryKey: ["casting", bookId] });
}

// Bấm nhầm ("Nữ" cạnh "Nam", nhầm người, nhầm cách đọc) sửa ngay trên thông báo: "Hoàn tác" gửi lại đúng lần bấm ấy
// (`requestedAt` máy chủ trả) để máy chủ trả yêu cầu trước đó về chỗ. Dây chuyền đã kịp đưa quyết định vào sách (ranh
// giới chương rơi đúng mấy giây ấy) thì máy chủ nói thật, và thông báo lỗi nói chỗ đổi lại.
export const UNDO_MS = 8000;

/** `message`: điều gì trở lại, nói cụ thể ("“Lucien” lại đọc là “Lu-si-en”") - soát UX 29-09: "Việc trở lại như trước khi
 *  bấm" quá chung. */
export function undoAction(client: QueryClient, bookId: string, endpoint: string, decisions: Record<string, unknown>[], message?: string) {
  return {
    label: "Hoàn tác",
    onClick: () => {
      void (async () => {
        try {
          let restored = false;
          for (const decision of decisions) {
            const answer = await api<{ undone: number; restored: boolean }>(`/api/books/${bookId}/${endpoint}`, {
              method: "POST",
              body: { ...decision, withdraw: true },
            });
            restored ||= answer.restored;
          }
          toast.success("Đã hoàn tác", {
            description: restored
              ? "Máy vừa đưa cách đọc mới vào sách, nên sẽ đọc lại theo cách cũ."
              : (message ?? "Việc trở lại như trước khi bấm."),
          });
        } catch (error) {
          toast.error("Không hoàn tác được", { description: (error as Error).message });
        } finally {
          refreshAfterDecision(client, bookId);
        }
      })();
    },
  };
}
