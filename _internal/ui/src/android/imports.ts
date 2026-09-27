import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { EbookLibrary } from "./plugins";

// Mở một file sách .abook (BookFileImport.kt): từ trình quản lý file, Zalo, Drive ("Mở bằng") hay nút "Mở file sách".
// Nghe ở CẤP APP như lượt tải (downloads.ts): mở app bằng một file thì việc nhập có thể xong trước khi màn nào kịp mở.

/** Gọi một lần khi app mở. `open` mở trang sách vừa nhập. Trả về hàm gỡ. */
export function watchImports(client: QueryClient, open: (bookId: string) => void): () => void {
  const handle = EbookLibrary.addListener("import", (event) => {
    if (event.error || !event.bookId) {
      toast.error("Không mở được file sách", { description: event.error || "File không có sách nào." });
      return;
    }
    const bookId = event.bookId;
    void client.invalidateQueries({ queryKey: ["listen"] });
    void client.invalidateQueries({ queryKey: ["storage"] });
    toast.success("Đã thêm sách vào Thư viện", {
      description: event.title || undefined,
      action: { label: "Mở sách", onClick: () => open(bookId) },
    });
  });
  return () => void handle.then((listener) => listener.remove());
}

/** Nút "Mở file sách": bộ chọn file của hệ thống; kết quả về qua sự kiện "import". */
export async function pickBookFile(): Promise<void> {
  try {
    await EbookLibrary.pickBook();
  } catch (error) {
    toast.error("Không mở được bộ chọn file", { description: (error as Error).message });
  }
}
