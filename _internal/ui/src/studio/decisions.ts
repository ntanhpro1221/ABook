import { useQuery, type QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type BookSummary } from "./api";

/** Thay đổi của người nghe vào sách lúc nào - lời báo chỉ nói vế đúng với sách này (soát UX 29-09: mọi thông báo nói cả
 *  "thu lại khi sách chạy tiếp" lẫn "sách đã xong thì bấm…"). Đang chạy: dây chuyền áp ở ranh giới chương kế tiếp và thu
 *  lại cả chương đã qua (pipeline._process_all_chapters); trước khi phân vai khoá thì yêu cầu nằm chờ; sách ĐÃ XONG không
 *  tự chạy lại. */
type ApplyWhen = "cast" | "running" | "done" | "paused";

export function applyWhen(book: Pick<BookSummary, "phase" | "running" | "starting"> | undefined): ApplyWhen {
  if (!book) return "paused";
  if (book.phase === "analysis" || book.phase === "casting") return "cast";
  if (book.running || book.starting) return "running";
  return book.phase === "done" ? "done" : "paused";
}

/** Câu đứng riêng, cho thông báo. */
const SENTENCE: Record<ApplyWhen, string> = {
  cast: "Áp dụng khi phân vai xong.",
  running: "Máy áp ở ranh giới chương kế tiếp, không phải dừng sách.",
  done: "Bấm “Áp dụng thay đổi” ở trang dự án để thu lại.",
  paused: "Thu lại khi sách chạy tiếp.",
};

/** Vế sau gạch nối, cho dòng "Đã ghi … - {vế}." trên thẻ và trên câu. */
export const PENDING_NOTE: Record<ApplyWhen, string> = {
  cast: "chờ phân vai xong",
  running: "máy áp ở ranh giới chương kế tiếp",
  done: "bấm “Áp dụng thay đổi” ở đầu trang để áp",
  paused: "chờ áp dụng khi sách chạy tiếp",
};

/** Chỉ đọc bản của trang dự án trong bộ nhớ đệm - không thêm một nhịp hỏi máy chủ. */
function useApplyWhen(bookId: string): ApplyWhen {
  return applyWhen(useQuery<{ book: BookSummary }>({ queryKey: ["book", bookId], enabled: false }).data?.book);
}

export function useWhenApplied(bookId: string): string {
  return SENTENCE[useApplyWhen(bookId)];
}

export function usePendingNote(bookId: string): string {
  return PENDING_NOTE[useApplyWhen(bookId)];
}

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
