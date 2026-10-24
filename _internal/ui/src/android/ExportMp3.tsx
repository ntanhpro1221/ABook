import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { FolderDown } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "@/shared/toast";
import type { MusicExportState } from "@/desktop/listenExport";
import { MusicMixOption, useMusicChoice } from "@/desktop/musicMix";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { spokenProgress } from "@/shared/progressSpeech";
import { Button, Dialog } from "@/shared/ui";
import { BackgroundNote, ExportProgressText } from "./BackgroundNote";
import { chargerHint } from "./ExportAudiobook";
import { progressText } from "./ExportM4b";
import { isEnded, noteEnded, rejoinExports } from "./exportJobs";
import { EbookLibrary, type Mp3ExportEvent } from "./plugins";

// "Xuất MP3" trên điện thoại: cùng chữ, cùng bản xuất với máy tính (desktop/App.tsx ExportMenuItem). Việc chạy nền
// (Mp3ExportWorker.kt): app đang mở thì thông báo trong app theo tiến độ; ra ngoài app thì thông báo của hệ thống, có nút "Dừng".
// Cuốn có nhạc nền gắn theo chương (soát a99 V3): mục menu mở hộp nhỏ có ô "Kèm nhạc nền" như "Xuất M4B"; cuốn không có nhạc thì bấm là chạy.
// Điện thoại không có bộ mã hoá MP3, nên chương đã trộn nhạc ra file .m4a (hộp nói trước điều đó).

/** Hộp nhỏ "Kèm nhạc nền" được mở từ menu của trang sách. */
export const OPEN_MP3_EVENT = "abook-phone-mp3-dialog";

/**
 * Lượt đang theo dõi của mỗi cuốn: tin của lượt cũ (bị thay khi đổi thư mục) không được đè lên lượt mới. `book` không có khi lượt được nối lại sau
 * lúc giao diện mở lại giữa chừng (exportJobs chỉ biết mã cuốn) - khi ấy thông báo không có nút "Đổi thư mục".
 */
const runs = new Map<string, { run: string; folder: string; book?: ListenBook; music: boolean }>();

const toastId = (bookId: string) => `mp3-export-${bookId}`;

/** `fraction`: phần đã xong (0-1) - trình đọc màn hình chỉ đọc mốc 25 % (soát a31 A6). */
function showProgress(bookId: string, book: ListenBook | undefined, folder: string, progress: string, fraction?: number, music = false) {
  toast.loading("Đang xuất sách…", {
    id: toastId(bookId),
    description: folder ? (
      <ExportProgressText shown={`${progress} · vào ${folder}`} spoken={`${spokenProgress("Đang xuất sách", fraction)} vào ${folder}`} />
    ) : (
      <ExportProgressText shown={progress} spoken={spokenProgress("Đang xuất sách", fraction)} />
    ),
    action: book ? { label: "Đổi thư mục", onClick: () => void exportMp3(book, true, undefined, music) } : undefined,
  });
}

/** Bắt đầu xuất; `pick`: hỏi lại chỗ lưu (lượt đang chạy của cuốn này được thay bằng lượt mới). `music`: ô "Kèm nhạc nền". */
export async function exportMp3(book: ListenBook, pick = false, chapterIds?: number[], music = false) {
  try {
    if (chapterIds === undefined) {
      const history = await EbookLibrary.exportHistory({ bookId: book.id }).catch(() => ({ exports: [] }));
      const changed = [...new Set(history.exports.filter((item) => item.kind === "mp3").flatMap((item) => item.changed))];
      if (changed.length) {
        toast("Bản MP3 bạn đã xuất có chương đã đổi", {
          description: "Bạn muốn xuất riêng các chương đã đổi hay cả cuốn?", duration: Infinity,
          action: { label: `Chỉ ${changed.length} chương đổi`, onClick: () => void exportMp3(book, pick, changed, music) },
          cancel: { label: "Xuất cả cuốn", onClick: () => void exportMp3(book, pick, [], music) },
        });
        return;
      }
    }
    // Như máy tính: bìa tự vẽ chỉ dùng khi sách không có ảnh bìa thật.
    const result = await EbookLibrary.exportMp3({ bookId: book.id, cover: book.cover ? undefined : coverArtwork(book.title), pick,
      ...(chapterIds?.length ? { chapterIds } : {}), ...(music ? { music } : {}) });
    if (!result.started || !result.run) return;
    const folder = result.folder ?? "";
    runs.set(book.id, { run: result.run, folder, book, music });
    showProgress(book.id, book, folder, `${result.chapters ?? book.chaptersAvailable} chương`, undefined, music);
  } catch (error) {
    toast.error("Không xuất được", { id: toastId(book.id), description: (error as Error).message });
  }
}

/** Lời của thông báo "xong": nói chỗ lưu (thư mục) trước, rồi mới tới lưu ý còn chương chưa làm xong. */
export function finishedToast(event: Pick<Mp3ExportEvent, "files" | "chaptersTotal" | "folder" | "uri" | "selection" | "mixed" | "musicMissing">): { title: string; description: string; uri?: string } {
  const files = event.files ?? 0;
  const where = event.folder ? `Lưu ở ${event.folder}.` : "";
  const partial = !event.selection && files < (event.chaptersTotal ?? 0) ? "Các chương chưa làm xong sẽ không có trong bản xuất." : "";
  const format = event.mixed ? "Các chương có nhạc nền là file .m4a." : "";
  const lost = event.musicMissing ? `${event.musicMissing} đoạn thiếu nhạc vì chưa tải được bài.` : "";
  return { title: `Đã xuất ${files} chương`, description: [where, format, partial, lost].filter(Boolean).join(" "), uri: event.uri || undefined };
}

async function openFolder(uri: string, folder: string) {
  const opened = await EbookLibrary.openFolder({ uri }).then((reply) => reply.opened, () => false);
  if (!opened) toast("Máy không mở được thư mục", { description: folder ? `Mở app Tệp rồi vào ${folder}.` : "Mở app Tệp rồi vào thư mục đã chọn." });
}

/** Theo dõi các lượt xuất từ lúc app mở (App.tsx): tiến độ, xong, dừng, lỗi - kể cả lượt đã chạy từ trước lúc giao diện mở lại (exportJobs). */
export function watchMp3Exports(): () => void {
  const handle = EbookLibrary.addListener("mp3Export", (event) => {
    if (event.finished || event.stopped || event.error) noteEnded(event.run);
    else if (isEnded(event.run)) return; // tin muộn của lượt đã kết thúc
    // Chưa theo dõi lượt nào của cuốn này (giao diện vừa mở lại giữa lúc việc nền chạy): nhận lượt ấy thay vì bỏ tin.
    const current = runs.get(event.bookId) ?? { run: event.run, folder: event.folder ?? "", book: undefined, music: false };
    if (current.run !== event.run) return;
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
      toast("Đã dừng xuất", { id, description: `Đã xuất ${event.files ?? 0} chương${current.folder ? ` · ${current.folder}` : ""}`, action: undefined });
    } else if (event.error) {
      runs.delete(event.bookId);
      toast.error("Không xuất được", { id, description: event.error, action: undefined });
    } else if (event.total || event.phase) {
      runs.set(event.bookId, current);
      showProgress(event.bookId, current.book, current.folder, progressText(event, current.book?.chaptersAvailable ?? 0),
        event.total ? (event.done ?? 0) / event.total : undefined, current.music);
    }
  });
  rejoinExports("mp3", (job) => {
    if (runs.has(job.bookId)) return;
    runs.set(job.bookId, { run: job.run, folder: job.folder ?? "", book: undefined, music: job.music ?? false });
    showProgress(job.bookId, undefined, job.folder ?? "", progressText(job, 0), job.total ? (job.done ?? 0) / job.total : undefined, job.music ?? false);
  });
  return () => void handle.then((listener) => listener.remove());
}

/** Mục menu: cuốn có nhạc nền theo chương thì mở hộp nhỏ; không thì chạy ngay (không thêm bước). */
export async function chooseMp3(book: ListenBook) {
  let state: MusicExportState | undefined;
  try {
    state = await EbookLibrary.m4bMusicState({ bookId: book.id });
  } catch {
    state = undefined; // không hỏi được: xuất như trước
  }
  if (state?.available) window.dispatchEvent(new CustomEvent<Mp3DialogDetail>(OPEN_MP3_EVENT, { detail: { book, state } }));
  else void exportMp3(book);
}

export interface Mp3DialogDetail {
  book: ListenBook;
  state: MusicExportState;
}

/** Thân hộp nhỏ (thuần hiển thị): ô "Kèm nhạc nền", lời báo định dạng file khi tích, và gợi ý cắm sạc khi cuốn dài. */
export function Mp3MusicForm({ music, onMusic, chapters }: { music: boolean; onMusic: (on: boolean) => void; chapters: number }) {
  const hint = chargerHint(music, chapters);
  return (
    <MotionRegion as="div" className="flex flex-col gap-3">
      <p className="text-sm text-fg-2">Mỗi chương một file, kèm bìa và danh sách phát: app nghe nhạc nào cũng mở được.</p>
      <MusicMixOption checked={music} onChange={onMusic} />
      {music && <p className="text-xs text-fg-3">Có nhạc nền thì mỗi chương là file .m4a thay vì .mp3 (điện thoại không ghi được MP3 có trộn nhạc). Âm thanh y như bản M4B.</p>}
      {hint && <p className="text-xs text-fg-3">{hint}</p>}
      <BackgroundNote />
    </MotionRegion>
  );
}

/** Hộp nhỏ của "Xuất MP3" cho cuốn có nhạc nền (App.tsx): ô "Kèm nhạc nền" (mặc định theo công tắc Nhạc nền của cuốn) + "Bắt đầu". */
export function Mp3MusicDialogHost() {
  const [open, setOpen] = useState<Mp3DialogDetail | null>(null);
  const [music, setMusic] = useMusicChoice(open?.state, open?.book.id ?? "");
  useEffect(() => {
    const listener = (event: Event) => setOpen((event as CustomEvent<Mp3DialogDetail>).detail);
    window.addEventListener(OPEN_MP3_EVENT, listener);
    return () => window.removeEventListener(OPEN_MP3_EVENT, listener);
  }, []);
  const start = () => {
    if (!open) return;
    setOpen(null);
    void exportMp3(open.book, false, undefined, music);
  };
  return (
    <Dialog open={open !== null} onOpenChange={(next) => !next && setOpen(null)} title={`Xuất MP3 “${open?.book.title ?? ""}”`} width="max-w-md">
      <Mp3MusicForm music={music} onMusic={setMusic} chapters={open?.book.chaptersAvailable ?? 0} />
      <div className="mt-5 dialog-actions">
        <Button variant="ghost" onClick={() => setOpen(null)}>
          Để sau
        </Button>
        <Button variant="primary" icon={FolderDown} onClick={start}>
          Bắt đầu
        </Button>
      </div>
    </Dialog>
  );
}

/** Mục "…" của trang sách trên điện thoại. Sách chỉ có chữ thì không có (không có audio để xuất). */
export function ExportMp3MenuItem({ book }: { book: ListenBook }) {
  if (book.stage === "text") return null;
  return (
    <DropdownMenu.Item
      // Chưa có chương nào nghe được thì không có gì để xuất (như máy tính).
      disabled={!book.chaptersAvailable}
      onSelect={() => void chooseMp3(book)}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <FolderDown className="size-4" /> Xuất MP3
    </DropdownMenu.Item>
  );
}
