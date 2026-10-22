import type { BookSummary } from "./api";

// Dừng rồi làm tiếp giữa pha phân tích là đổi quyển sách, không phải tạm nghỉ (AGENTS.md, thí nghiệm 07-09: chạy liền 23 nhân
// vật, dừng rồi làm tiếp 19 - 18 đoạn khác người nói, toàn bộ sau mốc bị ngắt; kéo theo sổ nhân vật, giọng, mọi phán quyết trên
// các đoạn ấy). Mọi chữ nói về điều ấy dùng chung một câu, nói đúng mức - không "hơi khác" (soát UX a23 B15).

/** Hệ quả, đứng sau "… thì" / "… sẽ". */
export const ANALYSIS_CUT_COST = "có thể ra một cuốn khác: người nói ở đoạn sau chỗ dừng có thể đổi, kéo theo nhân vật và giọng đọc";

/** Câu đầu hộp Dừng lúc phân tích: nói đúng cả hai nửa sự thật - phần đã phân tích còn nguyên trong sách, nhưng làm tiếp từ chỗ ấy
 *  mới là điều có giá (soát a88 T2: hộp từng nói "mất phần đã làm" trong khi lời khuyên ngay dưới nói "không mất"). Đứng trước
 *  `ANALYSIS_CUT_COST`. */
export const ANALYSIS_STOP_FACT = "Phần đã phân tích được giữ nguyên, nhưng làm tiếp từ chỗ dừng";

/** Câu cuối hộp Dừng lúc phân tích: đang tạm dừng thì nói sách đang yên ở đâu, không mời "bấm Tạm dừng" - không có nút ấy (soát
 *  UX a23 B14). Lượt chạy bằng bản app cũ không tạm dừng được: không nói gì. */
export function stopAnalysisAdvice(book: Pick<BookSummary, "paused" | "canPause">): string {
  if (book.paused) return "Sách đang tạm dừng - đứng yên đúng chỗ, phần đã phân tích không mất. Cứ để tạm dừng tới khi muốn làm tiếp.";
  if (book.canPause) return "Cần nghỉ thì bấm Tạm dừng: sách đứng yên rồi làm tiếp đúng chỗ, phần đã phân tích không mất.";
  return "";
}

/** Toast sau khi bấm "Tạm dừng" / "Tiếp tục": nói đúng điều máy chủ vừa trả lời, không điều người dùng mong. `book` là phản hồi;
 *  `onBattery`: lúc bấm "Tiếp tục" sách đang dừng vì máy chạy pin (soát a88 T1). */
export function pauseNotice(
  paused: boolean,
  book: Pick<BookSummary, "paused">,
  onBattery: boolean,
): { title: string; description: string; warn: boolean } {
  if (paused) {
    return {
      title: "Đang tạm dừng",
      description:
        "Sách đứng lại sau phần đang làm dở (lúc phân tích có thể mất vài phút) và giữ nguyên mọi thứ - bấm “Tiếp tục” là làm tiếp đúng chỗ ấy.",
      warn: false,
    };
  }
  if (book.paused) {
    return {
      title: "Sách vẫn đang tạm dừng",
      description:
        book.paused === "battery"
          ? "Máy đang chạy pin nên Studio vẫn giữ sách. Cắm sạc là tự làm tiếp."
          : "Sách chưa làm tiếp được. Đợi vài giây rồi xem lại; nếu vẫn đứng, bấm “Tiếp tục” lần nữa.",
      warn: true,
    };
  }
  return {
    title: "Đang làm tiếp",
    description: onBattery
      ? "Sách làm tiếp ngay trên pin - chậm và hao pin hơn. Cắm sạc rồi rút lại thì sách sẽ tạm dừng lại."
      : "Sách làm tiếp đúng chỗ đã tạm dừng.",
    warn: false,
  };
}

/** Cuốn xếp hàng đứng sau một cuốn đang tạm dừng: hàng không tự đi tiếp (soát a88 T5). */
export function queueWaitNotice(waitsOn: NonNullable<BookSummary["queueWaitsOn"]>): string {
  return waitsOn.paused === "battery"
    ? `“${waitsOn.title}” đang tạm dừng vì máy chạy pin nên cuốn này chưa tới lượt - cắm sạc là cuốn kia tự làm tiếp, hay bấm “Tiếp tục” ở cuốn kia để làm tiếp ngay trên pin.`
    : `“${waitsOn.title}” đang tạm dừng nên cuốn này chưa tới lượt - bấm “Tiếp tục” ở cuốn kia để hàng chạy tiếp.`;
}

/** "Tiếp tục" phải hỏi trước: pha phân tích đã bị ngắt (tiến trình chết giữa chừng). Sau pha phân tích thì làm tiếp trung thành
 *  từng byte - không hỏi (soát UX a23 B16). */
export function asksBeforeResume(book: Pick<BookSummary, "phase" | "analysisInterrupted">): boolean {
  return book.phase !== "done" && Boolean(book.analysisInterrupted);
}
