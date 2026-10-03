/**
 * PDF có lớp chữ -> các dòng của từng trang, cho bộ nhập sách của điện thoại (docs/LISTEN_ANYTHING.md mục 2).
 *
 * Đây là LỚP THÔ duy nhất cần thư viện PDF (pdf.js, Apache-2.0, tải lười - chỉ khi người dùng mở một file PDF). LỚP LUẬT - bỏ tiêu
 * đề chạy và số trang, nối dòng thành đoạn, chia chương - nằm ở Kotlin (`BookImport.fromPdfPages`) và Python
 * (`abook/importers.import_pdf_pages`) cùng bộ ví dụ `tests/fixtures/import/`: pypdf và pdf.js phải ra đúng các dòng của
 * `pages/*.pages.json`, nên luật chỉ có MỘT đặc tả. App máy tính không cần bản này (Studio chạy bản Python ở máy tính).
 */

export interface PdfPages {
  title: string;
  author: string;
  /** Mỗi trang: các dòng CÓ CHỮ, đã gộp khoảng trắng (như `importers._page_lines`). */
  pages: string[][];
}

/** Khoảng trắng của Python `str.split()` (rồi NFC): để dòng ra giống hệt `importers._words`. */
const PYTHON_SPACE = /[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/;

export function words(text: string): string {
  return text.split(PYTHON_SPACE).filter(Boolean).join(" ").normalize("NFC");
}

interface TextItem {
  str: string;
  hasEOL?: boolean;
}

/** `workerSrc`: địa chỉ file pdf.worker (app: `import url from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url"`). */
export async function pdfPages(data: ArrayBuffer | Uint8Array, workerSrc: string): Promise<PdfPages> {
  // Bản "legacy": chạy được trên WebView Android cũ; dynamic import để pdf.js (~540 KB nén) không nằm trong gói khởi động.
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;
  // Bản sao thường (không phải Buffer): pdf.js chuyển bộ đệm sang worker và làm nó rỗng.
  const bytes = Uint8Array.from(data instanceof Uint8Array ? data : new Uint8Array(data));
  const task = pdfjs.getDocument({ data: bytes, useSystemFonts: false, disableFontFace: true, verbosity: 0 });
  const doc = await task.promise.catch((error: { name?: string }) => {
    throw new Error(error?.name === "PasswordException" ? "PDF này có mật khẩu - ABook chưa mở được" : "không phải file PDF thật hoặc bị hỏng");
  });
  try {
    const pages: string[][] = [];
    for (let number = 1; number <= doc.numPages; number++) {
      const page = await doc.getPage(number);
      const content = await page.getTextContent();
      const lines: string[] = [];
      let current = "";
      for (const item of content.items as TextItem[]) {
        if (typeof item.str !== "string") continue;
        current += item.str;
        if (item.hasEOL) {
          lines.push(current);
          current = "";
        }
      }
      lines.push(current);
      pages.push(lines.map(words).filter(Boolean));
      page.cleanup();
    }
    const info = ((await doc.getMetadata().catch(() => null))?.info ?? {}) as { Title?: string; Author?: string };
    return { title: words(String(info.Title ?? "")), author: words(String(info.Author ?? "")), pages };
  } finally {
    await task.destroy();
  }
}
