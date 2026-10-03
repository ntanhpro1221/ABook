import workerSrc from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";
import { pdfPages, type PdfPages } from "@/shared/pdfPages";

/**
 * Chữ của một file PDF trên điện thoại: từng dòng của từng trang (pdf.js chạy trong WebView, tải lười khi người dùng mở PDF đầu tiên).
 * Lớp luật (bỏ tiêu đề chạy, nối dòng, chia chương) là `BookImport.fromPdfPages` ở Kotlin - xem docs/LISTEN_ANYTHING.md mục 2.
 */
export function readPdfPages(data: ArrayBuffer | Uint8Array): Promise<PdfPages> {
  return pdfPages(data, workerSrc);
}
