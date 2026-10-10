import { Capacitor } from "@capacitor/core";
import type { ImportChoice, PickedItem, TextImport } from "@/listen/textImport";
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

/** Thứ native đã chép (bộ chọn, hay file app khác gửi tới - android/imports.ts) thành lựa chọn của bước xem trước. */
export function stagedChoice(picked: { ref: string; name?: string; pdf?: string }): ImportChoice {
  const choice: PickedPdf = { ref: picked.ref, name: picked.name ?? "Sách" };
  if (picked.pdf) choice.pdf = picked.pdf;
  return choice;
}

export const phoneTextImport: TextImport = {
  async choose(kind) {
    const picked = await EbookLibrary.pickSource({ kind });
    if (picked.picked && picked.book) return "opened";
    if (!picked.picked || !picked.ref) return null;
    return stagedChoice({ ref: picked.ref, name: picked.name, pdf: picked.pdf });
  },
  // Chọn nhiều file một lúc: mỗi file một mục của hàng xem trước (file không chép được ghi lỗi, không làm hỏng cả lượt).
  async chooseMany() {
    const picked = await EbookLibrary.pickSource({ kind: "file", multiple: true });
    if (!picked.picked) return [];
    return (picked.items ?? []).map((entry): PickedItem => {
      const name = entry.name ?? "Sách";
      if (entry.error) return { name, error: entry.error };
      if (entry.book) return { name, opened: true };
      if (!entry.ref) return { name, error: "Không đọc được file này." };
      return { name, choice: stagedChoice({ ref: entry.ref, name, pdf: entry.pdf }) };
    });
  },
  async preview(choice, options) {
    const pdf = (choice as PickedPdf).pdf;
    if (!pdf) {
      return EbookLibrary.previewImport({
        ref: choice.ref,
        ...(options?.splitChapters ? { splitChapters: true } : {}),
        ...(options?.footnotes ? { footnotes: options.footnotes } : {}),
      });
    }
    const pages = await readPdf(Capacitor.convertFileSrc(pdf)).catch((error: Error) => {
      throw new Error(`Không đọc được PDF này: ${error.message}`);
    });
    return EbookLibrary.previewImport({ ref: choice.ref, pages: pages.pages, title: pages.title, author: pages.author });
  },
  // Native giữ cuốn của lần xem trước cuối (đã tách hay chưa, kèm cả mục rất ngắn chưa tích), nên chỉ phần chọn chương + đổi tên đi tiếp.
  add: (choice, title, separate, options) =>
    EbookLibrary.createImport({ ref: choice.ref, title, separate: Boolean(separate), ...(options?.chapters ? { chapters: options.chapters } : {}) }),
  discard: (choice) => EbookLibrary.discardImport({ ref: choice.ref }),
};
