import { useQuery, type QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type BookSummary } from "./api";

/** Thay đổi của người nghe vào sách lúc nào - lời báo chỉ nói vế đúng với sách này (soát UX 29-09: mọi thông báo nói cả
 *  "thu lại khi sách chạy tiếp" lẫn "sách đã xong thì bấm…"). Đang chạy: dây chuyền áp ở ranh giới chương kế tiếp và thu
 *  lại cả chương đã qua (pipeline._process_all_chapters); trước khi phân vai khoá thì yêu cầu nằm chờ; sách ĐÃ XONG không
 *  tự chạy lại. Sách bấm "Tạm dừng" vẫn `running` (tiến trình sống) nhưng không tới ranh giới chương nào tới khi làm tiếp. */
type ApplyWhen = "start" | "cast" | "running" | "done" | "paused";

export function applyWhen(book: Pick<BookSummary, "phase" | "running" | "starting" | "paused"> | undefined): ApplyWhen {
  if (!book) return "paused";
  // Sách chưa bắt đầu: chưa có câu nào để thu lại, cũng chưa có gì để "làm tiếp" (soát UX 01-10).
  if (book.phase === "idle" && !book.running && !book.starting) return "start";
  if (book.phase === "analysis" || book.phase === "casting") return "cast";
  if (book.paused) return "paused";
  if (book.running || book.starting) return "running";
  return book.phase === "done" ? "done" : "paused";
}

/** Câu đứng riêng, cho thông báo - đứng sau câu nói cái giá ("Câu đã thu sẽ được thu lại."), nên không nhắc "thu lại"
 *  lần nữa; thông báo hiện trên chính trang dự án nên chỉ "đầu trang", không "trang dự án" (soát UX 30-09). */
const SENTENCE: Record<ApplyWhen, string> = {
  start: "Máy dùng ngay từ khi bắt đầu làm sách.",
  cast: "Áp dụng khi phân vai xong.",
  running: "Máy áp ở ranh giới chương kế tiếp, không phải dừng sách.",
  done: "Bấm “Áp dụng thay đổi” ở đầu trang để đưa vào sách.",
  paused: "Máy áp dụng khi sách làm tiếp.",
};

/** Vế sau gạch nối, cho dòng "Đã ghi … - {vế}." trên thẻ và trên câu. */
export const PENDING_NOTE: Record<ApplyWhen, string> = {
  start: "dùng khi bắt đầu làm sách",
  cast: "chờ phân vai xong",
  running: "máy áp ở ranh giới chương kế tiếp",
  done: "bấm “Áp dụng thay đổi” ở đầu trang để áp",
  paused: "chờ áp dụng khi sách chạy tiếp",
};

/** Chỉ đọc bản của trang dự án trong bộ nhớ đệm - không thêm một nhịp hỏi máy chủ. */
export function useApplyWhen(bookId: string): ApplyWhen {
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
  void client.invalidateQueries({ queryKey: ["voice-choices", bookId] });
  // Cả danh sách cách đọc chung lẫn gợi ý "Dùng N cách đọc chung" của mọi cuốn (hoàn tác có thể gỡ một mục chung).
  void client.invalidateQueries({ queryKey: ["shared-readings"] });
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
