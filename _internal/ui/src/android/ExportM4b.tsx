import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { BookAudio } from "lucide-react";
import { toast } from "sonner";
import { jobView, M4B_COPY, type ExportJob } from "@/desktop/bookFileExport";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { EbookLibrary, type M4bExportEvent } from "./plugins";

// "Xuất M4B cho app sách nói" trên điện thoại: cùng chữ, cùng file với máy tính (desktop/ExportBookFileJob.tsx M4bMenuItem). Việc chạy
// nền (M4bExportWorker.kt): app đang mở thì thông báo trong app theo tiến độ; ra ngoài app thì thông báo của hệ thống, có nút "Dừng".
// Khác xuất MP3: một file duy nhất, nên mỗi lần hệ thống hỏi tên và chỗ lưu (không nhớ thư mục).

/** Lượt đang theo dõi của mỗi cuốn: tin của lượt cũ (bị thay bằng lượt mới) không được đè lên lượt mới. */
const runs = new Map<string, { run: string; book: ListenBook }>();

const toastId = (bookId: string) => `m4b-export-${bookId}`;

/** "3/10 chương · 27%" lúc đang làm; trước tin đầu chỉ có số chương. */
export function progressText(event: Pick<M4bExportEvent, "done" | "total" | "percent">, chapters: number): string {
  if (!event.total) return `${chapters} chương`;
  const percent = event.percent === undefined ? "" : ` · ${Math.max(0, Math.min(99, event.percent))}%`;
  return `${event.done ?? 0}/${event.total} chương${percent}`;
}

/** Thông báo "xong": cùng chữ với máy tính (tên file · cỡ · lưu ý khi còn chương chưa làm xong). */
export function finishedView(event: Pick<M4bExportEvent, "name" | "size" | "chapters" | "chaptersTotal">) {
  const job: ExportJob = {
    state: "done",
    result: { folder: "", file: event.name, size: event.size, chapters: event.chapters, chaptersTotal: event.chaptersTotal },
  };
  return jobView(job, 0, false, M4B_COPY);
}

function showProgress(book: ListenBook, progress: string) {
  toast.loading(M4B_COPY.busy, {
    id: toastId(book.id),
    description: progress,
    duration: Infinity,
    action: { label: "Dừng", onClick: () => void EbookLibrary.cancelM4bExport({ bookId: book.id }) },
  });
}

/** Bắt đầu xuất: hệ thống hỏi tên và chỗ lưu file; huỷ ở bước ấy thì không có gì xảy ra. */
async function exportM4b(book: ListenBook) {
  try {
    // Như máy tính: bìa tự vẽ chỉ dùng khi sách không có ảnh bìa thật.
    const result = await EbookLibrary.exportM4b({ bookId: book.id, cover: book.cover ? undefined : coverArtwork(book.title) });
    if (!result.started || !result.run) return;
    runs.set(book.id, { run: result.run, book });
    showProgress(book, progressText({}, result.chapters ?? book.chaptersAvailable));
  } catch (error) {
    toast.error(M4B_COPY.failed, { id: toastId(book.id), description: (error as Error).message });
  }
}

/** Theo dõi các lượt xuất từ lúc app mở (App.tsx): tiến độ, xong, dừng, lỗi. */
export function watchM4bExports(): () => void {
  const handle = EbookLibrary.addListener("m4bExport", (event) => {
    const current = runs.get(event.bookId);
    if (!current || current.run !== event.run) return;
    const id = toastId(event.bookId);
    if (event.finished) {
      runs.delete(event.bookId);
      const view = finishedView(event);
      if (view.kind === "success") toast.success(view.title, { id, description: view.description, duration: 15000, action: undefined });
    } else if (event.stopped) {
      runs.delete(event.bookId);
      toast("Đã dừng xuất M4B", { id, description: "File dở đã được xoá", action: undefined });
    } else if (event.error) {
      runs.delete(event.bookId);
      toast.error(M4B_COPY.failed, { id, description: event.error, action: undefined });
    } else if (event.total) {
      showProgress(current.book, progressText(event, current.book.chaptersAvailable));
    }
  });
  return () => void handle.then((listener) => listener.remove());
}

/** Mục "…" của trang sách trên điện thoại. Sách chỉ có chữ thì không có (không có audio để xuất). */
export function ExportM4bMenuItem({ book }: { book: ListenBook }) {
  if (book.stage === "text") return null;
  return (
    <DropdownMenu.Item
      // Chưa có chương nào nghe được thì không có gì để xuất (như máy tính).
      disabled={!book.chaptersAvailable}
      onSelect={() => void exportM4b(book)}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <BookAudio className="size-4" /> Xuất M4B cho app sách nói
    </DropdownMenu.Item>
  );
}
