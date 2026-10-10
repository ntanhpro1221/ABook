import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery } from "@tanstack/react-query";
import { Headphones } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { jobView, type ExportJob } from "@/desktop/bookFileExport";
import { AUDIOBOOK_COPY, planText, resumeText, wholeBookNotice } from "@/desktop/listenExport";
import type { ListenBook } from "@/listen/model";
import type { ReadAloudVoice } from "@/listen/readAloud";
import { chosenVoice, resolveVoice, voiceCaption } from "@/listen/readAloudVoice";
import { useReadAloudVoices } from "@/listen/source";
import { coverArtwork } from "@/shared/cover";
import { formatSize } from "@/shared/format";
import { Button, Dialog } from "@/shared/ui";
import { EbookLibrary, type AudiobookExportEvent, type AudiobookPhonePlan } from "./plugins";

// "Xuất sách nói" của sách Nghe ngay (chỉ có chữ) trên điện thoại: cùng việc với máy tính (desktop/AudiobookDialog.tsx) - điện thoại đọc cả cuốn bằng giọng đã chọn cho cuốn
// rồi ghép thành MỘT file .m4b có mục lục chương (ListenExportWorker.kt). Chỉ M4B: điện thoại không có bộ mã hoá MP3. Chữ trong hộp và thông báo dùng chung với máy tính
// (desktop/listenExport.ts, bookFileExport.ts jobView); việc chạy nền nên thông báo của hệ thống có tiến độ và nút "Dừng".

/** Hộp được mở từ menu của trang sách (ExportAudiobookMenuItem). */
export const OPEN_AUDIOBOOK_EVENT = "abook-phone-audiobook-dialog";

/** Lượt đang theo dõi của mỗi cuốn: tin của lượt cũ (bị thay bằng lượt mới) không được đè lên lượt mới. */
const runs = new Map<string, string>();

const toastId = (bookId: string) => `audiobook-export-${bookId}`;

/** Tin tiến độ thành việc đang chạy của máy tính: cùng chữ "Chương 3/12 · 27% · còn 2 giờ" / "nhường cho chương đang nghe" / "Đang ghép file âm thanh". */
export function progressView(event: Pick<AudiobookExportEvent, "phase" | "chapter" | "chapters" | "percent" | "secondsLeft" | "waiting">) {
  const job: ExportJob = {
    state: "running",
    phase: event.phase,
    chapter: event.chapter,
    chapters: event.chapters,
    percent: event.percent,
    secondsLeft: event.secondsLeft,
    waiting: event.waiting,
  };
  return jobView(job, 0, false, AUDIOBOOK_COPY);
}

/** Thông báo "xong": tên file · cỡ · lưu ý khi còn chương chưa làm xong - như máy tính. */
export function finishedView(event: Pick<AudiobookExportEvent, "name" | "size" | "chapters" | "chaptersTotal">) {
  const job: ExportJob = {
    state: "done",
    result: { folder: "", file: event.name, size: event.size, chapters: event.chapters, chaptersTotal: event.chaptersTotal },
  };
  return jobView(job, 0, false, AUDIOBOOK_COPY);
}

function cancel(bookId: string) {
  void EbookLibrary.cancelAudiobookExport({ bookId });
}

function showProgress(event: Pick<AudiobookExportEvent, "bookId" | "phase" | "chapter" | "chapters" | "percent" | "secondsLeft" | "waiting">) {
  const view = progressView(event);
  if (view.kind === "none") return;
  toast.loading(AUDIOBOOK_COPY.busy, {
    id: toastId(event.bookId),
    description: view.description,
    duration: Infinity,
    action: { label: "Dừng", onClick: () => cancel(event.bookId) },
  });
}

/** Theo dõi các lượt xuất sách nói từ lúc app mở (App.tsx): tiến độ, xong, dừng, lỗi - và lượt đang chạy từ trước (mở lại app giữa chừng). */
export function watchAudiobookExports(): () => void {
  const handle = EbookLibrary.addListener("audiobookExport", (event) => {
    const current = runs.get(event.bookId);
    if (current !== undefined && current !== event.run) return;
    const id = toastId(event.bookId);
    if (event.finished) {
      runs.delete(event.bookId);
      const view = finishedView(event);
      const uri = event.uri;
      if (view.kind === "success") {
        toast.success(view.title, {
          id,
          description: view.description,
          duration: 20000,
          action: uri
            ? {
                label: "Mở",
                onClick: () =>
                  void EbookLibrary.openFile({ uri }).then((result) => {
                    if (!result.opened) toast("Không mở được từ đây", { description: "Mở file ở nơi bạn đã lưu bằng app Tệp hay app nghe sách nói." });
                  }),
              }
            : undefined,
        });
      }
    } else if (event.stopped) {
      runs.delete(event.bookId);
      toast(AUDIOBOOK_COPY.stopped, { id, description: AUDIOBOOK_COPY.stoppedNote, action: undefined });
    } else if (event.error) {
      runs.delete(event.bookId);
      toast.error(AUDIOBOOK_COPY.failed, { id, description: event.error, action: undefined });
    } else if (event.chapters) {
      runs.set(event.bookId, event.run);
      showProgress(event);
    }
  });
  // Mở lại (hay tải lại) app khi việc nền đang chạy: hỏi tin cuối của từng lượt để hiện lại thông báo.
  void EbookLibrary.audiobookJobs().then(
    ({ jobs }) =>
      jobs.forEach((job) => {
        if (runs.has(job.bookId)) return;
        runs.set(job.bookId, job.run);
        showProgress(job);
      }),
    () => undefined,
  );
  return () => void handle.then((listener) => listener.remove());
}

/** Lời nói chỗ trống cần trong máy lúc làm (file tạm xoá khi xong). */
export function spaceText(plan: Pick<AudiobookPhonePlan, "bytes">): string {
  return `Lúc làm cần khoảng ${formatSize(plan.bytes).replace(" ", " ")} trống trong điện thoại (file tạm, xoá khi xong).`;
}

export interface AudiobookPhoneFormProps {
  voice: ReadAloudVoice | undefined;
  /** undefined: chưa có kết quả ước; `planError`: lý do bị từ chối (rỗng nếu không). */
  plan: AudiobookPhonePlan | undefined;
  planError: string;
}

/** Phần thân của hộp (thuần hiển thị): giọng đang chọn cho cuốn, dài bao nhiêu, làm tiếp từ đâu, lời cảnh báo giọng trực tuyến. */
export function AudiobookPhoneForm({ voice, plan, planError }: AudiobookPhoneFormProps) {
  const notice = voice ? wholeBookNotice(voice) : "";
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-2">Máy đọc cả cuốn rồi ghép thành MỘT file M4B có mục lục chương: app nghe sách nói nào cũng mở được, nhớ chỗ nghe dở.</p>
      <div className="text-sm">
        {voice ? (
          <p>
            Giọng đọc: <span className="font-medium">{voiceCaption(voice)}</span>
            <span className="text-fg-3"> - giọng đang chọn cho cuốn này; đổi ở trình phát.</span>
          </p>
        ) : (
          <p className="text-warning">Máy chưa có giọng đọc nào - tải giọng ở Cài đặt → Giọng đọc rồi quay lại.</p>
        )}
        <p className="mt-1 text-fg-2" aria-live="polite">
          {planError || (plan ? planText(plan) : voice ? "Đang tính độ dài…" : "")}
        </p>
        {plan && resumeText(plan) && <p className="mt-1 text-fg-2">{resumeText(plan)}</p>}
        {plan && plan.chapters > 0 && <p className="mt-1 text-fg-3">{spaceText(plan)}</p>}
      </div>
      {notice && (
        <p role="note" className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
          {notice}
        </p>
      )}
      <p className="text-xs text-fg-3">
        Việc chạy nền, bạn cứ dùng điện thoại như thường - lúc bạn đang nghe sách, việc xuất nhường chỗ. Dừng bất cứ lúc nào: phần đã làm được giữ, xuất lại là làm tiếp.
      </p>
    </div>
  );
}

/** Nghe hộp mở từ menu của sách và dựng hộp; "Bắt đầu" để hệ thống hỏi tên + nơi lưu file rồi giao cho việc nền. */
export function AudiobookPhoneDialogHost() {
  const [book, setBook] = useState<ListenBook | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: voices } = useReadAloudVoices();
  useEffect(() => {
    const listener = (event: Event) => setBook((event as CustomEvent<ListenBook>).detail);
    window.addEventListener(OPEN_AUDIOBOOK_EVENT, listener);
    return () => window.removeEventListener(OPEN_AUDIOBOOK_EVENT, listener);
  }, []);

  const voice = book && voices?.length ? resolveVoice(voices, chosenVoice(book.id)) : undefined;
  const plan = useQuery({
    queryKey: ["audiobook-phone-plan", book?.id, voice?.id],
    enabled: Boolean(book && voice),
    queryFn: () => EbookLibrary.audiobookPlan({ bookId: book!.id, voice: voice!.id }),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });

  const start = async () => {
    if (!book || !voice) return;
    setBusy(true);
    try {
      // Như xuất M4B: bìa tự vẽ chỉ dùng khi sách không có ảnh bìa thật.
      const result = await EbookLibrary.exportAudiobook({ bookId: book.id, voice: voice.id, cover: book.cover ? undefined : coverArtwork(book.title) });
      if (!result.started || !result.run) return; // không chọn chỗ lưu: hộp ở lại để chọn lại
      runs.set(book.id, result.run);
      showProgress({ bookId: book.id, phase: "voice", chapter: 1, chapters: plan.data?.chapters ?? book.chaptersTotal, percent: 0 });
      setBook(null);
    } catch (error) {
      toast.error(AUDIOBOOK_COPY.failed, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open={book !== null}
      onOpenChange={(open) => !open && setBook(null)}
      title={`Xuất sách nói “${book?.title ?? ""}”`}
      description="Để nghe ở app sách nói khác, trên xe hơi hay máy khác."
      width="max-w-xl"
    >
      <AudiobookPhoneForm voice={voice} plan={plan.data} planError={plan.error ? (plan.error as Error).message : ""} />
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => setBook(null)}>
          Để sau
        </Button>
        <Button variant="primary" icon={Headphones} loading={busy} disabled={!voice || !plan.data || plan.data.chapters === 0 || Boolean(plan.error)} onClick={() => void start()}>
          Bắt đầu
        </Button>
      </div>
    </Dialog>
  );
}

/** Mục "…" của trang sách trên điện thoại: chỉ sách chỉ có chữ (sách đã có tiếng thì xuất MP3 / M4B có sẵn). */
export function ExportAudiobookMenuItem({ book }: { book: ListenBook }) {
  if (book.stage !== "text") return null;
  return (
    <DropdownMenu.Item
      disabled={!book.chaptersTotal}
      onSelect={() => window.dispatchEvent(new CustomEvent<ListenBook>(OPEN_AUDIOBOOK_EVENT, { detail: book }))}
      className="flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover"
    >
      <Headphones className="size-4" /> Xuất sách nói (M4B)…
    </DropdownMenu.Item>
  );
}
