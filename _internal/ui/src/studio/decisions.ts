import { type QueryClient } from "@tanstack/react-query";
import { useCachedBook } from "./data";
import { toast } from "@/shared/toast";
import { api, type BookSummary } from "./api";

/** Thay đổi của người nghe vào sách lúc nào - lời báo chỉ nói vế đúng với sách này (soát UX 29-09: mọi thông báo nói cả
 *  "thu lại khi sách chạy tiếp" lẫn "sách đã xong thì bấm…"). Đang chạy: dây chuyền áp ở ranh giới chương kế tiếp và thu
 *  lại cả chương đã qua (pipeline._process_all_chapters); trước khi phân vai khoá thì yêu cầu nằm chờ; sách ĐÃ XONG không
 *  tự chạy lại. Sách bấm "Tạm dừng" vẫn `running` (tiến trình sống) nhưng không tới ranh giới chương nào tới khi làm tiếp. */
type ApplyWhen = "start" | "cast" | "running" | "done" | "paused";

export function applyWhen(
  book: Pick<BookSummary, "phase" | "running" | "starting" | "paused" | "castLocked"> | undefined,
): ApplyWhen {
  if (!book) return "paused";
  // Sách chưa bắt đầu: chưa có câu nào để thu lại, cũng chưa có gì để "làm tiếp" (soát UX 01-10).
  if (book.phase === "idle" && !book.running && !book.starting) return "start";
  // Phân vai đã khoá (lúc "Duyệt trước khi thu"): yêu cầu áp ở ranh giới chương đầu, không còn "chờ phân vai xong".
  if (book.phase === "analysis" || (book.phase === "casting" && !book.castLocked)) return "cast";
  if (book.paused) return "paused";
  if (book.running || book.starting) return "running";
  return book.phase === "done" ? "done" : "paused";
}

/** Câu đứng riêng, cho thông báo - đứng sau câu nói cái giá ("Câu đã thu sẽ được thu lại."), nên không nhắc "thu lại"
 *  lần nữa; thông báo hiện trên chính trang dự án nên chỉ "đầu trang", không "trang dự án" (soát UX 30-09). */
export const SENTENCE: Record<ApplyWhen, string> = {
  start: "Máy dùng ngay từ khi bắt đầu làm sách.",
  cast: "Áp dụng khi phân vai xong.",
  running: "Máy áp từ chương sau, không phải dừng sách.",
  done: "Bấm “Áp dụng thay đổi” ở đầu trang để đưa vào sách.",
  paused: "Máy áp dụng khi sách làm tiếp.",
};

/** Vế sau gạch nối, cho dòng "Đã ghi … - {vế}." trên thẻ và trên câu. */
export const PENDING_NOTE: Record<ApplyWhen, string> = {
  start: "dùng khi bắt đầu làm sách",
  cast: "chờ phân vai xong",
  running: "áp từ chương sau",
  done: "bấm “Áp dụng thay đổi” ở đầu trang để áp",
  paused: "chờ áp dụng khi sách chạy tiếp",
};

/** Cuốn không có xưởng (mở từ file .abook): thay đổi chỉ được ghi lại, Studio mới đưa vào giọng đọc - nói thế, không nói "áp ở
 *  ranh giới chương" như dự án. */
export const WAITING_STUDIO = "Đang chờ máy làm sách - giọng đọc chưa đổi gì. Lưu file thì thay đổi đi cùng; mở file bằng ABook Studio trên máy tính để áp.";

/** Lời hứa sau khi ghi một thay đổi chờ Studio. `holder`: cuốn tải từ máy khác (điện thoại, `caps.sync`) - tên máy ấy: thay đổi tự gửi sang và áp
 *  ngay ở đó (máy tính nhận vào chính sách ấy, không chờ ai duyệt), chỉ phần thu lại giọng chờ Studio trên máy ấy (soát a70: lời báo cũ bảo "mở
 *  file bằng Studio" với sách đã liên kết). Không có: `WAITING_STUDIO`. */
export function waitingStudio(holder?: string | null): string {
  return holder
    ? `Đã gửi sang ${holder}, áp ngay ở đó. Giọng đọc chưa đổi: Studio sẽ thu lại khi bạn mở dự án trên ${holder}.`
    : WAITING_STUDIO;
}

/** Câu đã thu được thu lại khi nào - vế cho dòng "N câu đã thu sẽ được thu lại …" của hộp sửa cách đọc, CÙNG lời hứa với `waitingStudio` (soát
 *  a70: hộp hứa "sẽ được thu lại" trong khi thông báo nói "giọng đọc chưa đổi gì"). */
export function retakeWhen(holder?: string | null): string {
  return holder ? `khi bạn mở dự án trên ${holder}` : "khi mở file bằng ABook Studio trên máy tính";
}

/** Chỉ đọc bản của trang dự án trong bộ nhớ đệm - không thêm một nhịp hỏi máy chủ. */
export function useApplyWhen(bookId: string): ApplyWhen {
  return applyWhen(useCachedBook(bookId).data?.book);
}

export function useWhenApplied(bookId: string): string {
  return SENTENCE[useApplyWhen(bookId)];
}

export function usePendingNote(bookId: string): string {
  return PENDING_NOTE[useApplyWhen(bookId)];
}

/** Sửa lạc quan trên bộ nhớ đệm của một truy vấn: đổi ngay khi bấm, và trả `restore` để `onError` đặt lại đúng bản trước (máy
 *  chủ từ chối, mất kết nối). Không đặt lại thì câu vẫn hiện "Đã ghi … - chờ áp dụng" cạnh thông báo lỗi (soát UX a23). */
export function optimistic<T>(client: QueryClient, key: readonly unknown[], change: (data: T) => T): { restore: () => void } {
  const previous = client.getQueryData<T>(key);
  if (previous !== undefined) client.setQueryData<T>(key, change(previous));
  return { restore: () => previous !== undefined && client.setQueryData<T>(key, previous) };
}

/** Làm mới mọi chỗ một quyết định của người nghe (người nói, giới, cách đọc tên) chạm tới. */
export function refreshAfterDecision(client: QueryClient, bookId: string) {
  void client.invalidateQueries({ queryKey: ["work", bookId] });
  void client.invalidateQueries({ queryKey: ["book", bookId] });
  void client.invalidateQueries({ queryKey: ["library"] });
  // Trang nghe: số thay đổi chưa lưu của cuốn không có xưởng.
  void client.invalidateQueries({ queryKey: ["listen", "book", bookId] });
  void client.invalidateQueries({ queryKey: ["listen", "cast", bookId] });
  void client.invalidateQueries({ queryKey: ["cast", bookId] });
  void client.invalidateQueries({ queryKey: ["pronunciations", bookId] });
  void client.invalidateQueries({ queryKey: ["casting", bookId] });
  void client.invalidateQueries({ queryKey: ["voice-choices", bookId] });
  // Cuốn không có xưởng: câu nào đang chờ Studio (trang đọc) và danh sách "Việc đang chờ Studio".
  void client.invalidateQueries({ queryKey: ["wishes", bookId] });
  void client.invalidateQueries({ queryKey: ["pending-changes", bookId] });
  // Cả danh sách cách đọc chung lẫn gợi ý "Dùng N cách đọc chung" của mọi cuốn (hoàn tác có thể gỡ một mục chung).
  void client.invalidateQueries({ queryKey: ["shared-readings"] });
}

// Bấm nhầm ("Nữ" cạnh "Nam", nhầm người, nhầm cách đọc) sửa ngay trên thông báo: "Hoàn tác" gửi lại đúng lần bấm ấy
// (`requestedAt` máy chủ trả) để máy chủ trả yêu cầu trước đó về chỗ. Dây chuyền đã kịp đưa quyết định vào sách (ranh
// giới chương rơi đúng mấy giây ấy) thì máy chủ nói thật, và thông báo lỗi nói chỗ đổi lại.
// 15 giây: đủ để đọc thông báo rồi mới nhận ra bấm nhầm (soát a70 - 8 giây thường đã tắt trước khi kịp bấm).
export const UNDO_MS = 15_000;

/** `message`: điều gì trở lại, nói cụ thể ("“Lucien” lại đọc là “Lu-si-en”") - soát UX 29-09: "Việc trở lại như trước khi
 *  bấm" quá chung. */
export function undoAction(client: QueryClient, bookId: string, endpoint: string, decisions: Record<string, unknown>[], message?: string) {
  return undoSteps(client, bookId, decisions.map((decision) => ({ endpoint, decision })), message);
}

/** Lời đáp của một bước hoàn tác. `sent`: lần bấm đã gửi sang máy giữ sách rồi - ở đây chỉ còn lời nhờ máy ấy rút lại. */
export type UndoAnswer = { undone: number; restored: boolean; sent?: boolean };

/** Thông báo sau khi hoàn tác - nói đúng điều đã xảy ra, không hứa hơn: lần bấm đã gửi sang máy giữ sách thì chưa chắc đã rút được. */
export function undoToast(restored: boolean, sent: boolean, message?: string): [string, { description: string }] {
  if (sent) {
    return [
      "Đã nhờ máy giữ sách rút lại",
      { description: "Lần bấm này đã gửi sang máy giữ sách. Mình đã nhờ máy ấy rút lại; nếu nó đã đưa vào sách thì bạn sẽ thấy báo ở đây và cần chọn lại ở máy đó." },
    ];
  }
  return [
    "Đã hoàn tác",
    { description: restored ? "Máy vừa đưa cách đọc mới vào sách, nên sẽ đọc lại theo cách cũ." : (message ?? "Việc trở lại như trước khi bấm.") },
  ];
}

/** `undoAction` cho lần bấm đã đi nhiều đường (sửa cách đọc câu kèm người mới: /line rồi /speaker): rút lần lượt từng bước, theo thứ tự đưa vào. */
export function undoSteps(client: QueryClient, bookId: string, steps: { endpoint: string; decision: Record<string, unknown> }[], message?: string) {
  return {
    label: "Hoàn tác",
    onClick: () => {
      void (async () => {
        let done = 0;
        try {
          let restored = false;
          let sent = false;
          for (const { endpoint, decision } of steps) {
            const answer = await api<UndoAnswer>(`/api/books/${bookId}/${endpoint}`, {
              method: "POST",
              body: { ...decision, withdraw: true },
            });
            restored ||= answer.restored;
            sent ||= answer.sent === true;
            done += 1;
          }
          toast.success(...undoToast(restored, sent, message));
        } catch (error) {
          // Nhiều quyết định gửi lần lượt: một cái lỗi giữa chừng thì những cái trước đã hoàn tác thật - nói đúng số.
          toast.error(done > 0 ? `Mới hoàn tác được ${done}/${steps.length} việc` : "Không hoàn tác được", { description: (error as Error).message });
        } finally {
          refreshAfterDecision(client, bookId);
        }
      })();
    },
  };
}
