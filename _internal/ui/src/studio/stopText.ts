import { S } from "../shared/strings.generated";
import type { BookSummary } from "./api";

// Dừng rồi làm tiếp giữa pha phân tích là đổi quyển sách, không phải tạm nghỉ (AGENTS.md, thí nghiệm 07-09: chạy liền 23 nhân
// vật, dừng rồi làm tiếp 19 - 18 đoạn khác người nói, toàn bộ sau mốc bị ngắt; kéo theo sổ nhân vật, giọng, mọi phán quyết trên
// các đoạn ấy). Mọi chữ nói về điều ấy dùng chung một câu, nói đúng mức - không "hơi khác" (soát UX a23 B15).

/** Hệ quả, đứng sau "… thì" / "… sẽ". */
export const ANALYSIS_CUT_COST = S.s_co_the_ra_mot_cuon_khac_nguoi_noi_o_doan_s_4a2e8f6b;

/** Câu đầu hộp Dừng lúc phân tích: nói đúng cả hai nửa sự thật - phần đã phân tích còn nguyên trong sách, nhưng làm tiếp từ chỗ ấy
 *  mới là điều có giá (soát a88 T2: hộp từng nói "mất phần đã làm" trong khi lời khuyên ngay dưới nói "không mất"). Đứng trước
 *  `ANALYSIS_CUT_COST`. */
export const ANALYSIS_STOP_FACT = S.s_phan_da_phan_tich_duoc_giu_nguyen_nhung_la_7b0b4096;

/** Câu cuối hộp Dừng lúc phân tích: đang tạm dừng thì nói sách đang yên ở đâu, không mời "bấm Tạm dừng" - không có nút ấy (soát
 *  UX a23 B14). Không tạm dừng được: không nói gì. */
export function stopAnalysisAdvice(book: Pick<BookSummary, "paused" | "canPause">): string {
  if (book.paused) return S.s_sach_dang_tam_dung_dung_yen_dung_cho_phan_7bfd81b4;
  if (book.canPause) return S.s_can_nghi_thi_bam_tam_dung_sach_dung_yen_ro_0d5d0ddd;
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
      title: S.s_dang_tam_dung_e40cc1b7,
      description:
        S.s_sach_dung_lai_sau_phan_dang_lam_do_luc_pha_330de94c,
      warn: false,
    };
  }
  if (book.paused) {
    return {
      title: S.s_sach_van_dang_tam_dung_1d8dc8ed,
      description:
        book.paused === "battery"
          ? S.s_may_dang_chay_pin_nen_studio_van_giu_sach_13fd5894
          : S.s_sach_chua_lam_tiep_duoc_doi_vai_giay_roi_x_129b7133,
      warn: true,
    };
  }
  return {
    title: S.s_dang_lam_tiep_013b8524,
    description: onBattery
      ? S.s_sach_lam_tiep_ngay_tren_pin_cham_va_hao_pi_7d1a8968
      : S.s_sach_lam_tiep_dung_cho_da_tam_dung_3d848ab8,
    warn: false,
  };
}

/** Cuốn xếp hàng đứng sau một cuốn đang tạm dừng: hàng không tự đi tiếp (soát a88 T5). */
export function queueWaitNotice(waitsOn: NonNullable<BookSummary["queueWaitsOn"]>): string {
  return waitsOn.paused === "battery"
    ? S.s_0_dang_tam_dung_vi_may_chay_pin_nen_cuon_n_a3f87494(waitsOn.title)
    : S.s_0_dang_tam_dung_nen_cuon_nay_chua_toi_luot_e8965d5e(waitsOn.title);
}

/** "Tiếp tục" phải hỏi trước: pha phân tích đã bị ngắt (tiến trình chết giữa chừng). Sau pha phân tích thì làm tiếp trung thành
 *  từng byte - không hỏi (soát UX a23 B16). */
export function asksBeforeResume(book: Pick<BookSummary, "phase" | "analysisInterrupted">): boolean {
  return book.phase !== "done" && Boolean(book.analysisInterrupted);
}
