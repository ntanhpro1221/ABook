import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { BookAudio } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "@/shared/toast";
import { jobView, M4B_COPY, type ExportJob } from "@/desktop/bookFileExport";
import type { MusicExportState } from "@/desktop/listenExport";
import { MusicMixOption, useMusicChoice } from "@/desktop/musicMix";
import type { ListenBook } from "@/listen/model";
import { coverArtwork } from "@/shared/cover";
import { spokenProgress } from "@/shared/progressSpeech";
import { Button, Dialog } from "@/shared/ui";
import { BackgroundNote, ExportProgressText } from "./BackgroundNote";
import { chargerHint } from "./ExportAudiobook";
import { isEnded, noteEnded, rejoinExports } from "./exportJobs";
import { EbookLibrary, type M4bExportEvent } from "./plugins";

// "Xuất M4B" trên điện thoại: cùng chữ, cùng file với máy tính (desktop/ExportBookFileJob.tsx M4bMenuItem). Việc chạy
// nền (M4bExportWorker.kt): app đang mở thì thông báo trong app theo tiến độ; ra ngoài app thì thông báo của hệ thống, có nút "Dừng".
// Khác xuất MP3: một file duy nhất, nên mỗi lần hệ thống hỏi tên và chỗ lưu (không nhớ thư mục). Cuốn có nhạc nền gắn theo chương thì
// mục menu mở một hộp nhỏ có ô "Kèm nhạc nền" (M4bMusicDialogHost); cuốn không có nhạc thì bấm là chạy như trước.

/** Hộp nhỏ "Kèm nhạc nền" được mở từ menu của trang sách. */
export const OPEN_M4B_EVENT = "abook-phone-m4b-dialog";

/** Lượt đang theo dõi của mỗi cuốn: tin của lượt cũ (bị thay bằng lượt mới) không được đè lên lượt mới. */
const runs = new Map<string, { run: string; book?: ListenBook }>();

const toastId = (bookId: string) => `m4b-export-${bookId}`;

type ProgressFields = Pick<M4bExportEvent, "done" | "total" | "percent" | "phase" | "chapter" | "chapters" | "peakRound" | "peakOver">;

/**
 * "3/10 chương · 27%" lúc đang làm; trước tin đầu chỉ có số chương. Lượt kèm nhạc báo pha như máy tính: "Đang tải nhạc nền 1/3 bài",
 * "Đang trộn nhạc chương 3/10", "Đang kiểm đỉnh âm…", "Mã hoá lại vì 2 chương vượt đỉnh (lượt 1)".
 */
export function progressText(event: ProgressFields, chapters: number): string {
  if (event.phase) {
    const job: ExportJob = { state: "running", ...event };
    const view = jobView(job, 0, false, M4B_COPY);
    if (view.kind === "loading") return view.description;
  }
  if (!event.total) return chapters ? `${chapters} chương` : "Đang chuẩn bị…";
  const percent = event.percent === undefined ? "" : ` · ${Math.max(0, Math.min(99, event.percent))}%`;
  return `${event.done ?? 0}/${event.total} chương${percent}`;
}

/** Thông báo "xong": cùng chữ với máy tính (tên file · cỡ · lưu ý khi còn chương chưa làm xong · đoạn thiếu nhạc). */
export function finishedView(event: Pick<M4bExportEvent, "name" | "size" | "chapters" | "chaptersTotal" | "musicMissing">) {
  const job: ExportJob = {
    state: "done",
    result: { folder: "", file: event.name, size: event.size, chapters: event.chapters, chaptersTotal: event.chaptersTotal, musicMissing: event.musicMissing },
  };
  return jobView(job, 0, false, M4B_COPY);
}

/** `fraction`: phần đã xong (0-1) - trình đọc màn hình chỉ đọc mốc 25 % (soát a31 A6). */
function showProgress(bookId: string, progress: string, fraction?: number) {
  toast.loading(M4B_COPY.busy, {
    id: toastId(bookId),
    description: <ExportProgressText shown={progress} spoken={spokenProgress(M4B_COPY.busy, fraction)} />,
    duration: Infinity,
    action: { label: "Dừng", onClick: () => void EbookLibrary.cancelM4bExport({ bookId }) },
  });
}

/** Bắt đầu xuất: hệ thống hỏi tên và chỗ lưu file; huỷ ở bước ấy thì không có gì xảy ra. `music`: ô "Kèm nhạc nền". */
export async function exportM4b(book: ListenBook, music = false) {
  try {
    // Như máy tính: bìa tự vẽ chỉ dùng khi sách không có ảnh bìa thật.
    const result = await EbookLibrary.exportM4b({ bookId: book.id, cover: book.cover ? undefined : coverArtwork(book.title), music });
    if (!result.started || !result.run) return;
    runs.set(book.id, { run: result.run, book });
    showProgress(book.id, progressText({}, result.chapters ?? book.chaptersAvailable));
  } catch (error) {
    toast.error(M4B_COPY.failed, { id: toastId(book.id), description: (error as Error).message });
  }
}

/** Mục menu: cuốn có nhạc nền theo chương thì mở hộp nhỏ; không thì chạy ngay (không thêm bước). */
export async function chooseM4b(book: ListenBook) {
  let state: MusicExportState | undefined;
  try {
    state = await EbookLibrary.m4bMusicState({ bookId: book.id });
  } catch {
    state = undefined; // không hỏi được: xuất như trước
  }
  if (state?.available) window.dispatchEvent(new CustomEvent<M4bDialogDetail>(OPEN_M4B_EVENT, { detail: { book, state } }));
  else void exportM4b(book);
}

/** Theo dõi các lượt xuất từ lúc app mở (App.tsx): tiến độ, xong, dừng, lỗi - kể cả lượt đã chạy từ trước lúc giao diện mở lại (exportJobs). */
export function watchM4bExports(): () => void {
  const handle = EbookLibrary.addListener("m4bExport", (event) => {
    if (event.finished || event.stopped || event.error) noteEnded(event.run);
    else if (isEnded(event.run)) return; // tin muộn của lượt đã kết thúc
    // Chưa theo dõi lượt nào của cuốn này (giao diện vừa mở lại giữa lúc việc nền chạy): nhận lượt ấy thay vì bỏ tin.
    const current = runs.get(event.bookId) ?? { run: event.run, book: undefined };
    if (current.run !== event.run) return;
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
    } else if (event.total || event.phase) {
      runs.set(event.bookId, current);
      showProgress(event.bookId, progressText(event, current.book?.chaptersAvailable ?? 0), event.total ? (event.done ?? 0) / event.total : undefined);
    }
  });
  rejoinExports("m4b", (job) => {
    if (runs.has(job.bookId)) return;
    runs.set(job.bookId, { run: job.run });
    showProgress(job.bookId, progressText(job, 0), job.total ? (job.done ?? 0) / job.total : undefined);
  });
  return () => void handle.then((listener) => listener.remove());
}

export interface M4bDialogDetail {
  book: ListenBook;
  state: MusicExportState;
}

/** Thân hộp nhỏ (thuần hiển thị): ô "Kèm nhạc nền" và gợi ý cắm sạc khi cuốn dài. */
export function M4bMusicForm({ music, onMusic, chapters }: { music: boolean; onMusic: (on: boolean) => void; chapters: number }) {
  const hint = chargerHint(music, chapters);
  return (
    <MotionRegion as="div" className="flex flex-col gap-3">
      <p className="text-sm text-fg-2">Một file có mục lục chương: app nghe sách nói nào cũng mở được, nhớ chỗ nghe dở.</p>
      <MusicMixOption checked={music} onChange={onMusic} />
      {hint && <p className="text-xs text-fg-3">{hint}</p>}
      <BackgroundNote />
    </MotionRegion>
  );
}

/** Hộp nhỏ của "Xuất M4B" cho cuốn có nhạc nền (App.tsx): ô "Kèm nhạc nền" (mặc định theo công tắc Nhạc nền của cuốn) + "Bắt đầu". */
export function M4bMusicDialogHost() {
  const [open, setOpen] = useState<M4bDialogDetail | null>(null);
  const [music, setMusic] = useMusicChoice(open?.state, open?.book.id ?? "");
  useEffect(() => {
    const listener = (event: Event) => setOpen((event as CustomEvent<M4bDialogDetail>).detail);
    window.addEventListener(OPEN_M4B_EVENT, listener);
    return () => window.removeEventListener(OPEN_M4B_EVENT, listener);
  }, []);
  const start = () => {
    if (!open) return;
    setOpen(null);
    void exportM4b(open.book, music);
  };
  return (
    <Dialog open={open !== null} onOpenChange={(next) => !next && setOpen(null)} title={`Xuất M4B “${open?.book.title ?? ""}”`} width="max-w-md">
      <M4bMusicForm music={music} onMusic={setMusic} chapters={open?.book.chaptersAvailable ?? 0} />
      <div className="mt-5 dialog-actions">
        <Button variant="ghost" onClick={() => setOpen(null)}>
          Để sau
        </Button>
        <Button variant="primary" icon={BookAudio} onClick={start}>
          Bắt đầu
        </Button>
      </div>
    </Dialog>
  );
}

/** Mục "…" của trang sách trên điện thoại. Sách chỉ có chữ thì không có (không có audio để xuất). */
export function ExportM4bMenuItem({ book }: { book: ListenBook }) {
  if (book.stage === "text") return null;
  return (
    <DropdownMenu.Item
      // Chưa có chương nào nghe được thì không có gì để xuất (như máy tính).
      disabled={!book.chaptersAvailable}
      onSelect={() => void chooseM4b(book)}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <BookAudio className="size-4" /> Xuất M4B
    </DropdownMenu.Item>
  );
}
