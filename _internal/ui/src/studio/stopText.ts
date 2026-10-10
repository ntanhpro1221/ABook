import type { BookSummary } from "./api";

// Dừng rồi làm tiếp giữa pha phân tích là đổi quyển sách, không phải tạm nghỉ (AGENTS.md, thí nghiệm 07-09: chạy liền 23 nhân
// vật, dừng rồi làm tiếp 19 - 18 đoạn khác người nói, toàn bộ sau mốc bị ngắt; kéo theo sổ nhân vật, giọng, mọi phán quyết trên
// các đoạn ấy). Mọi chữ nói về điều ấy dùng chung một câu, nói đúng mức - không "hơi khác" (soát UX a23 B15).

/** Hệ quả, đứng sau "… thì" / "… sẽ". */
export const ANALYSIS_CUT_COST = "có thể ra một cuốn khác: người nói ở đoạn sau chỗ dừng có thể đổi, kéo theo nhân vật và giọng đọc";

/** Câu cuối hộp Dừng lúc phân tích: đang tạm dừng thì nói sách đang yên ở đâu, không mời "bấm Tạm dừng" - không có nút ấy (soát
 *  UX a23 B14). Lượt chạy bằng bản app cũ không tạm dừng được: không nói gì. */
export function stopAnalysisAdvice(book: Pick<BookSummary, "paused" | "canPause">): string {
  if (book.paused) return "Sách đang tạm dừng - đứng yên đúng chỗ, phần đã phân tích không mất. Cứ để tạm dừng tới khi muốn làm tiếp.";
  if (book.canPause) return "Cần nghỉ thì bấm Tạm dừng: sách đứng yên rồi làm tiếp đúng chỗ, phần đã phân tích không mất.";
  return "";
}

/** "Tiếp tục" phải hỏi trước: pha phân tích đã bị ngắt (tiến trình chết giữa chừng). Sau pha phân tích thì làm tiếp trung thành
 *  từng byte - không hỏi (soát UX a23 B16). */
export function asksBeforeResume(book: Pick<BookSummary, "phase" | "analysisInterrupted">): boolean {
  return book.phase !== "done" && Boolean(book.analysisInterrupted);
}
