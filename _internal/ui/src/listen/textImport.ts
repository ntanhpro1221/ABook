// "Thêm sách từ file…": đưa EPUB / DOCX / PDF / thư mục TXT vào thư viện thành sách CHỈ-CÓ-CHỮ (docs/LISTEN_ANYTHING.md mục 1 và 2).
// Máy tính: máy chủ cục bộ chạy `abook/importers.py` (webui/textbook.py). Điện thoại: `BookImport.kt` ở native; PDF thì pdf.js trong
// WebView lấy chữ từng trang rồi đưa sang Kotlin (android/textImport.ts).

/** Danh sách chương của bước xem trước - cùng hàng chữ với danh sách chương của trình tạo sách Studio. */
export interface ImportPreview {
  title: string;
  author: string | null;
  chapters: { index: number; title: string; firstLine: string; words: number; chars: number }[];
  /** Gợi ý của máy (vd dòng ghi công ở đầu chương): hiện ra, KHÔNG BAO GIỜ tự áp. */
  notes: string[];
  hasCover: boolean;
  totals: { chapters: number; words: number };
}

/** Thứ người dùng đã chọn: máy tính - đường dẫn; điện thoại - mã của bản sao tạm do native giữ. */
export interface ImportChoice {
  ref: string;
  /** Tên hiện cho người dùng (tên file hay thư mục). */
  name: string;
}

export type ImportKind = "file" | "folder";

export interface AddedBook {
  id: string;
  /** "new" (cuốn mới), "existing" (đúng cuốn này đã có trong thư viện), "updated". */
  how: "new" | "existing" | "updated";
  chapters: number;
}

export interface TextImport {
  /** Mở bộ chọn của máy; `null` khi người dùng bỏ qua. Máy tính không có hộp thoại (chạy trong trình duyệt): không có `choose`. */
  choose?(kind: ImportKind): Promise<ImportChoice | null>;
  /** Máy tính dán được đường dẫn thay cho hộp thoại. */
  typedPath?: boolean;
  preview(choice: ImportChoice): Promise<ImportPreview>;
  add(choice: ImportChoice, title: string): Promise<AddedBook>;
  /** Bỏ thứ tạm đã giữ cho lần chọn này (điện thoại: bản sao file); nguồn nào không giữ gì thì không có. */
  discard?(choice: ImportChoice): Promise<void>;
}
