import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { FolderDown } from "lucide-react";
import { toast } from "sonner";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { EbookLibrary, type Mp3ExportEvent } from "./plugins";

// "Xuất MP3 để nghe ở app khác" trên điện thoại: cùng chữ, cùng bản xuất với máy tính (desktop/App.tsx ExportMenuItem). Việc chạy nền
// (Mp3ExportWorker.kt): app đang mở thì thông báo trong app theo tiến độ; ra ngoài app thì thông báo của hệ thống, có nút "Dừng".

/** Lượt đang theo dõi của mỗi cuốn: tin của lượt cũ (bị thay khi đổi thư mục) không được đè lên lượt mới. */
const runs = new Map<string, { run: string; folder: string; book: ListenBook }>();

const toastId = (bookId: string) => `mp3-export-${bookId}`;

function showProgress(book: ListenBook, folder: string, progress: string) {
  toast.loading("Đang xuất sách…", {
    id: toastId(book.id),
    description: `${progress} · vào ${folder}`,
    action: { label: "Đổi thư mục", onClick: () => void exportMp3(book, true) },
  });
}

/** Bắt đầu xuất; `pick`: hỏi lại chỗ lưu (lượt đang chạy của cuốn này được thay bằng lượt mới). */
async function exportMp3(book: ListenBook, pick = false) {
  try {
    // Như máy tính: bìa tự vẽ chỉ dùng khi sách không có ảnh bìa thật.
    const result = await EbookLibrary.exportMp3({ bookId: book.id, cover: book.cover ? undefined : coverArtwork(book.title), pick });
    if (!result.started || !result.run) return;
    const folder = result.folder ?? "";
    runs.set(book.id, { run: result.run, folder, book });
    showProgress(book, folder, `${result.chapters ?? book.chaptersAvailable} chương`);
  } catch (error) {
    toast.error("Không xuất được", { id: toastId(book.id), description: (error as Error).message });
  }
}

/** Lời của thông báo "xong": nói chỗ lưu (thư mục) trước, rồi mới tới lưu ý còn chương chưa làm xong. */
export function finishedToast(event: Pick<Mp3ExportEvent, "files" | "chaptersTotal" | "folder" | "uri">): { title: string; description: string; uri?: string } {
  const files = event.files ?? 0;
  const where = event.folder ? `Lưu ở ${event.folder}.` : "";
  const partial = files < (event.chaptersTotal ?? 0) ? "Các chương chưa làm xong sẽ không có trong bản xuất." : "";
  return { title: `Đã xuất ${files} chương`, description: [where, partial].filter(Boolean).join(" "), uri: event.uri || undefined };
}

async function openFolder(uri: string, folder: string) {
  const opened = await EbookLibrary.openFolder({ uri }).then((reply) => reply.opened, () => false);
  if (!opened) toast("Máy không mở được thư mục", { description: folder ? `Mở app Tệp rồi vào ${folder}.` : "Mở app Tệp rồi vào thư mục đã chọn." });
}

/** Theo dõi các lượt xuất từ lúc app mở (App.tsx): tiến độ, xong, dừng, lỗi. */
export function watchMp3Exports(): () => void {
  const handle = EbookLibrary.addListener("mp3Export", (event) => {
    const current = runs.get(event.bookId);
    if (!current || current.run !== event.run) return;
    const id = toastId(event.bookId);
    if (event.finished) {
      runs.delete(event.bookId);
      const done = finishedToast(event);
      toast.success(done.title, {
        id,
        description: done.description,
        // Chỗ lưu nằm ngay trong thông báo; nút mở app Tệp tới đúng thư mục ấy (máy không mở được thì nói đường đi bằng chữ).
        action: done.uri ? { label: "Mở thư mục", onClick: () => void openFolder(done.uri!, event.folder ?? "") } : undefined,
      });
    } else if (event.stopped) {
      runs.delete(event.bookId);
      toast("Đã dừng xuất", { id, description: `Đã xuất ${event.files ?? 0} chương · ${current.folder}`, action: undefined });
    } else if (event.error) {
      runs.delete(event.bookId);
      toast.error("Không xuất được", { id, description: event.error, action: undefined });
    } else if (event.total) {
      showProgress(current.book, current.folder, `${event.done ?? 0}/${event.total} chương`);
    }
  });
  return () => void handle.then((listener) => listener.remove());
}

/** Mục "…" của trang sách trên điện thoại. Sách chỉ có chữ thì không có (không có audio để xuất). */
export function ExportMp3MenuItem({ book }: { book: ListenBook }) {
  if (book.stage === "text") return null;
  return (
    <DropdownMenu.Item
      // Chưa có chương nào nghe được thì không có gì để xuất (như máy tính).
      disabled={!book.chaptersAvailable}
      onSelect={() => void exportMp3(book)}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <FolderDown className="size-4" /> Xuất MP3 để nghe ở app khác
    </DropdownMenu.Item>
  );
}
