import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { ImportChoice } from "@/listen/textImport";
import { keptEditsTitle } from "@/shared/editsKept";
import { EbookLibrary } from "./plugins";
import { stagedChoice } from "./textImport";

// Mở một file sách .abook (BookFileImport.kt): từ trình quản lý file, Zalo, Drive ("Mở bằng") hay nút "Mở file sách". File EPUB / DOCX /
// PDF / TXT gửi tới theo cùng đường thì vào bước xem trước của "Thêm sách từ file…" (LibraryPlugin.openFrom).
// Nghe ở CẤP APP như lượt tải (downloads.ts): mở app bằng một file thì việc nhập có thể xong trước khi màn nào kịp mở.

/** Gọi một lần khi app mở. `open` mở trang sách vừa nhập; `preview` mở bước xem trước cho file chữ app khác gửi tới. Trả về hàm gỡ. */
export function watchImports(client: QueryClient, open: (bookId: string) => void, preview: (choice: ImportChoice) => void): () => void {
  const text = EbookLibrary.addListener("textPicked", (event) => {
    if (event.error || !event.ref) {
      toast.error("Không mở được file", { description: event.error || "File này không có chữ để đọc." });
      return;
    }
    preview(stagedChoice({ ref: event.ref, name: event.name, pdf: event.pdf }));
  });
  const handle = EbookLibrary.addListener("import", (event) => {
    if (event.error || !event.bookId) {
      toast.error("Không mở được file sách", { description: event.error || "File không có sách nào." });
      return;
    }
    const bookId = event.bookId;
    void client.invalidateQueries({ queryKey: ["listen"] });
    void client.invalidateQueries({ queryKey: ["storage"] });
    toast.success(keptEditsTitle(event.keptEdits) ?? "Đã thêm sách vào Thư viện", {
      description: event.title || undefined,
      action: { label: "Mở sách", onClick: () => open(bookId) },
    });
  });
  return () => {
    void handle.then((listener) => listener.remove());
    void text.then((listener) => listener.remove());
  };
}

/** Nút "Mở file sách": bộ chọn file của hệ thống; kết quả về qua sự kiện "import". */
export async function pickBookFile(): Promise<void> {
  try {
    await EbookLibrary.pickBook();
  } catch (error) {
    toast.error("Không mở được bộ chọn file", { description: (error as Error).message });
  }
}
