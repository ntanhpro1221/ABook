import { useMotionState } from "@/shared/motion";
import { MotionPresence } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery } from "@tanstack/react-query";
import { Headphones } from "lucide-react";
import { useEffect, useState } from "react";
import { toast, toastDone } from "@/shared/toast";
import { jobView, type ExportJob } from "@/desktop/bookFileExport";
import { AUDIOBOOK_COPY, planText, resumeText, wholeBookNotice } from "@/desktop/listenExport";
import { MusicMixOption, useMusicChoice } from "@/desktop/musicMix";
import type { ListenBook } from "@/listen/model";
import type { ReadAloudVoice } from "@/listen/readAloud";
import { chosenVoice, resolveVoice, voiceCaption } from "@/listen/readAloudVoice";
import { useReadAloudVoices } from "@/listen/source";
import { coverArtwork } from "@/shared/cover";
import { formatSize } from "@/shared/format";
import { DialogActions, Button, Dialog } from "@/shared/ui";
import { BackgroundNote, ExportProgressText } from "./BackgroundNote";
import { isEnded, noteEnded, rejoinExports } from "./exportJobs";
import { EbookLibrary, type AudiobookExportEvent, type AudiobookPhonePlan } from "./plugins";

// "Xuất sách nói" của sách Nghe ngay (chỉ có chữ) trên điện thoại: cùng việc với máy tính (desktop/AudiobookDialog.tsx) - điện thoại đọc cả cuốn bằng giọng đã chọn cho cuốn
// rồi ghép thành MỘT file .m4b có mục lục chương (ListenExportWorker.kt). Chỉ M4B: điện thoại không có bộ mã hoá MP3. Chữ trong hộp và thông báo dùng chung với máy tính
// (desktop/listenExport.ts, bookFileExport.ts jobView); việc chạy nền nên thông báo của hệ thống có tiến độ và nút "Dừng". Cuốn có nhạc nền gắn theo chương thì
// hộp có ô "Kèm nhạc nền" như máy tính (desktop/musicMix.tsx).

/** Hộp được mở từ menu của trang sách (ExportAudiobookMenuItem). */
export const OPEN_AUDIOBOOK_EVENT = "abook-phone-audiobook-dialog";

/** Lượt đang theo dõi của mỗi cuốn: tin của lượt cũ (bị thay bằng lượt mới) không được đè lên lượt mới. */
const runs = new Map<string, string>();

const toastId = (bookId: string) => `audiobook-export-${bookId}`;

type ProgressFields = Pick<AudiobookExportEvent, "phase" | "chapter" | "chapters" | "percent" | "secondsLeft" | "waiting" | "done" | "total" | "peakRound" | "peakOver">;

/**
 * Tin tiến độ thành việc đang chạy của máy tính: cùng chữ "Chương 3/12 · 27% · còn 2 giờ" / "nhường cho chương đang nghe" / "Đang ghép file âm thanh"; kèm nhạc nền
 * thêm "Đang trộn nhạc chương 3/12", "Đang kiểm đỉnh âm…", "Mã hoá lại vì 1 chương vượt đỉnh (lượt 1)".
 */
export function progressView(event: ProgressFields) {
  const job: ExportJob = {
    state: "running",
    phase: event.phase,
    chapter: event.chapter,
    chapters: event.chapters,
    percent: event.percent,
    secondsLeft: event.secondsLeft,
    waiting: event.waiting,
    done: event.done,
    total: event.total,
    peakRound: event.peakRound,
    peakOver: event.peakOver,
  };
  return jobView(job, 0, false, AUDIOBOOK_COPY);
}

/** Thông báo "xong": tên file · cỡ · lưu ý khi còn chương chưa làm xong · đoạn thiếu nhạc - như máy tính. */
export function finishedView(event: Pick<AudiobookExportEvent, "name" | "size" | "chapters" | "chaptersTotal" | "musicMissing">) {
  const job: ExportJob = {
    state: "done",
    result: { folder: "", file: event.name, size: event.size, chapters: event.chapters, chaptersTotal: event.chaptersTotal, musicMissing: event.musicMissing },
  };
  return jobView(job, 0, false, AUDIOBOOK_COPY);
}

/** Lượt kèm nhạc dài (trên 20 chương) tốn pin đáng kể (PHONE_EXPORT_MIX mục 7): gợi ý cắm sạc, không chặn. Rỗng khi không cần. */
export function chargerHint(music: boolean, chapters: number): string {
  return music && chapters > 20 ? "Cuốn dài: nên cắm sạc trong lúc làm - trộn nhạc tốn pin." : "";
}

/** "12 đoạn phải đọc lại" khi đổi nhạc nền buộc ghép lại chương đã làm mà bản đọc của đoạn ấy không còn trong máy; rỗng khi không có. */
export function rereadText(plan: Pick<AudiobookPhonePlan, "rereads">): string {
  return plan.rereads ? `${plan.rereads} đoạn phải đọc lại vì đổi nhạc nền (bản đọc cũ đã được dọn khỏi máy).` : "";
}

function cancel(bookId: string) {
  void EbookLibrary.cancelAudiobookExport({ bookId });
}

function showProgress(event: ProgressFields & Pick<AudiobookExportEvent, "bookId">) {
  const view = progressView(event);
  if (view.kind === "none") return;
  toast.loading(AUDIOBOOK_COPY.busy, {
    id: toastId(event.bookId),
    // Thông báo nằm trong vùng aria-live: trình đọc màn hình chỉ đọc pha / mốc 25 %, không đọc lại mỗi lần số đổi (soát a31 A6).
    description: <ExportProgressText shown={view.description} spoken={view.spoken ?? ""} />,
    duration: Infinity,
    action: { label: "Dừng", onClick: () => cancel(event.bookId) },
  });
}

/** Theo dõi các lượt xuất sách nói từ lúc app mở (App.tsx): tiến độ, xong, dừng, lỗi - và lượt đang chạy từ trước (mở lại app giữa chừng). */
export function watchAudiobookExports(): () => void {
  const handle = EbookLibrary.addListener("audiobookExport", (event) => {
    if (event.finished || event.stopped || event.error) noteEnded(event.run);
    else if (isEnded(event.run)) return; // tin muộn của lượt đã kết thúc
    const current = runs.get(event.bookId);
    if (current !== undefined && current !== event.run) return;
    const id = toastId(event.bookId);
    if (event.finished) {
      runs.delete(event.bookId);
      const view = finishedView(event);
      const uri = event.uri;
      if (view.kind === "success") {
        toastDone(view.title, view.note, {
          id,
          duration: 20000,
          action: uri
            ? {
                label: "Mở",
                onClick: () =>
                  void EbookLibrary.openFile({ uri }).then((result) => {
                    if (!result.opened) toast.warning("Không mở được từ đây - mở file bằng app Tệp");
                  }),
              }
            : undefined,
        });
      }
    } else if (event.stopped) {
      runs.delete(event.bookId);
      toast(AUDIOBOOK_COPY.stopped, { id, action: undefined });
    } else if (event.error) {
      runs.delete(event.bookId);
      toast.error(AUDIOBOOK_COPY.failed, { id, description: event.error, action: undefined });
    } else if (event.chapters || event.phase) {
      runs.set(event.bookId, event.run);
      showProgress(event);
    }
  });
  // Mở lại (hay tải lại) app khi việc nền đang chạy: hỏi tin cuối của từng lượt để hiện lại thông báo.
  rejoinExports("audiobook", (job) => {
    if (runs.has(job.bookId)) return;
    runs.set(job.bookId, job.run);
    showProgress(job);
  });
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
  /** "Kèm nhạc nền": ô chỉ hiện khi `plan.music.available`. */
  music?: boolean;
  onMusic?: (on: boolean) => void;
}

/** Phần thân của hộp (thuần hiển thị): giọng đang chọn cho cuốn, dài bao nhiêu, làm tiếp từ đâu, ô "Kèm nhạc nền", lời cảnh báo giọng trực tuyến. */
export function AudiobookPhoneForm({ voice, plan, planError, music = false, onMusic }: AudiobookPhoneFormProps) {
  const notice = voice ? wholeBookNotice(voice) : "";
  const hint = plan ? chargerHint(music, plan.chapters) : "";
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-2">Máy đọc cả cuốn rồi ghép thành MỘT file M4B có mục lục chương: app nghe sách nói nào cũng mở được, nhớ chỗ nghe dở.</p>
      {/* Ước tính về muộn ("Đang tính độ dài…" -> số liệu, làm tiếp, chỗ trống): mờ qua tại chỗ, cao đổi dần - như hai form nhạc. */}
      <MotionRegion className="text-sm">
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
      </MotionRegion>
      <MotionPresence open={Boolean(plan?.music?.available && onMusic)}>
        {plan && onMusic && <MotionRegion className="flex flex-col gap-1">
          <MusicMixOption checked={music} onChange={onMusic} />
          {rereadText(plan) && <p className="pl-6.5 text-xs text-warning">{rereadText(plan)}</p>}
          {hint && <p className="pl-6.5 text-xs text-fg-3">{hint}</p>}
        </MotionRegion>}
      </MotionPresence>
      <MotionPresence open={Boolean(notice)}>
        <p role="note" className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
          {notice}
        </p>
      </MotionPresence>
      <p className="text-xs text-fg-3">
        Xuất chạy nền, nhường lúc nghe; dừng rồi làm tiếp được.
      </p>
      <BackgroundNote />
    </div>
  );
}

/** Nghe hộp mở từ menu của sách và dựng hộp; "Bắt đầu" để hệ thống hỏi tên + nơi lưu file rồi giao cho việc nền. */
export function AudiobookPhoneDialogHost() {
  const [book, setBook] = useState<ListenBook | null>(null);
  const [busy, setBusy] = useState(false);
  // Ô "Kèm nhạc nền" theo lượt ước đầu (mặc định của cuốn); người dùng đổi ô thì ước lại (chương làm sẵn, đoạn phải đọc lại theo lựa chọn nhạc).
  const [state, setState, resetState] = useMotionState<AudiobookPhonePlan["music"]>(undefined);
  const { data: voices } = useReadAloudVoices();
  useEffect(() => {
    const listener = (event: Event) => {
      resetState(undefined); // ô của cuốn trước không áp sang cuốn này; hộp tự có chuyển động mở.
      setBook((event as CustomEvent<ListenBook>).detail);
    };
    window.addEventListener(OPEN_AUDIOBOOK_EVENT, listener);
    return () => window.removeEventListener(OPEN_AUDIOBOOK_EVENT, listener);
  }, []);

  const voice = book && voices?.length ? resolveVoice(voices, chosenVoice(book.id)) : undefined;
  const [music, setMusic] = useMusicChoice(state, book?.id ?? "");
  // Khác mặc định của cuốn thì hỏi ước theo lựa chọn ấy; bằng mặc định thì lượt ước đầu (máy tự theo công tắc) đã đúng.
  const asked = state && music !== state.enabled ? music : null;
  const plan = useQuery({
    queryKey: ["audiobook-phone-plan", book?.id, voice?.id, asked],
    enabled: Boolean(book && voice),
    queryFn: () => EbookLibrary.audiobookPlan({ bookId: book!.id, voice: voice!.id, ...(asked === null ? {} : { music: asked }) }),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  const shown = plan.data?.music;
  useEffect(() => {
    if (book && shown && (shown.available !== state?.available || shown.enabled !== state?.enabled)) setState(shown);
  }, [book, shown, state, setState]);

  const start = async () => {
    if (!book || !voice) return;
    setBusy(true);
    try {
      // Như xuất M4B: bìa tự vẽ chỉ dùng khi sách không có ảnh bìa thật.
      const result = await EbookLibrary.exportAudiobook({
        bookId: book.id,
        voice: voice.id,
        cover: book.cover ? undefined : coverArtwork(book.title),
        music: Boolean(state?.available) && music,
      });
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
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => setBook(null)}>
          Để sau
        </Button>
        <Button variant="primary" icon={Headphones} loading={busy} disabled={!voice || !plan.data || plan.data.chapters === 0 || Boolean(plan.error)} onClick={() => void start()}>
          Bắt đầu
        </Button>
      </DialogActions>}
      open={book !== null}
      onOpenChange={(open) => !open && setBook(null)}
      title={`Xuất sách nói “${book?.title ?? ""}”`}
      description="Để nghe ở app sách nói khác, trên xe hơi hay máy khác."
      width="max-w-[560px]"
    >
      <AudiobookPhoneForm voice={voice} plan={plan.data} planError={plan.error ? (plan.error as Error).message : ""} music={music} onMusic={setMusic} />

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
