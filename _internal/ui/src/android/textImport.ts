import { Capacitor } from "@capacitor/core";
import type { ImportChoice, TextImport } from "@/listen/textImport";
import { EbookLibrary } from "./plugins";

// "Thêm sách từ file…" trên điện thoại. Bộ chọn và luật nhập là native (BookImport.kt, TextBook.kt); riêng PDF cần pdf.js nên đi qua
// WebView: native chép PDF vào thư mục tạm của app, WebView đọc bản sao ấy (cùng đường với ảnh bìa và audio), lấy các dòng của từng
// trang (shared/pdfPages.ts) rồi đưa lại cho Kotlin chạy luật bỏ tiêu đề chạy / nối đoạn / chia chương (`BookImport.fromPdfPages`).

/** Chỗ gọi pdf.js: tải lười để gói khởi động không mang nó (importPdf.ts kéo cả file worker). */
async function readPdf(url: string): Promise<{ title: string; author: string; pages: string[][] }> {
  const data = await (await fetch(url)).arrayBuffer();
  const { readPdfPages } = await import("./importPdf");
  return readPdfPages(data);
}

interface PickedPdf extends ImportChoice {
  pdf?: string;
}

export const phoneTextImport: TextImport = {
  async choose(kind) {
    const picked = await EbookLibrary.pickSource({ kind });
    if (!picked.picked || !picked.ref) return null;
    const choice: PickedPdf = { ref: picked.ref, name: picked.name ?? "Sách" };
    if (picked.pdf) choice.pdf = picked.pdf;
    return choice;
  },
  async preview(choice) {
    const pdf = (choice as PickedPdf).pdf;
    if (!pdf) return EbookLibrary.previewImport({ ref: choice.ref });
    const pages = await readPdf(Capacitor.convertFileSrc(pdf)).catch((error: Error) => {
      throw new Error(`Không đọc được PDF này: ${error.message}`);
    });
    return EbookLibrary.previewImport({ ref: choice.ref, pages: pages.pages, title: pages.title, author: pages.author });
  },
  add: (choice, title, separate) => EbookLibrary.createImport({ ref: choice.ref, title, separate: Boolean(separate) }),
  discard: (choice) => EbookLibrary.discardImport({ ref: choice.ref }),
};
