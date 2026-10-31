import { MotionRegion } from "@/shared/MotionRegion";
import { SlidingIndicator } from "@/shared/SlidingIndicator";
import { useMotionState } from "@/shared/motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Headphones } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "@/shared/toast";
import type { ReadAloudVoice } from "@/listen/readAloud";
import { chosenVoice, resolveVoice, voiceCaption } from "@/listen/readAloudVoice";
import type { ListenBook } from "@/listen/model";
import { useReadAloudVoices } from "@/listen/source";
import { coverArtwork } from "@/shared/cover";
import { cn } from "@/shared/cn";
import { ErrorDetails } from "@/shared/ErrorDetails";
import { formatSize } from "@/shared/format";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { DialogActions, Button, Dialog, Progress, radioGroupKeys, radioTabIndex } from "@/shared/ui";
import { pickFolder, useAppInfo } from "@/studio/data";
import { RETRYING_NOTE } from "@/studio/musicLocal";
import { OPEN_AUDIOBOOK_EVENT, startExport } from "./ExportBookFileJob";
import { MusicMixOption, useMusicChoice } from "./musicMix";
import {
  audiobookBody,
  fetchPlan,
  ffmpegCancel,
  ffmpegPercent,
  ffmpegStart,
  ffmpegStatus,
  FORMAT_CHOICES,
  planText,
  resumeText,
  wholeBookNotice,
  type AudiobookFormat,
  type AudiobookPlan,
  type FfmpegStatus,
} from "./listenExport";

// Hộp "Xuất sách nói (MP3 / M4B)…" của sách Nghe ngay: chọn định dạng, xem giọng + thời gian ước + lời cảnh báo giọng trực tuyến, rồi "Bắt đầu".
// Việc chạy nền ở ExportJobHost kind="audiobook" (thông báo có % và Huỷ). Phần thân (`AudiobookForm`) thuần hiển thị để thử được không cần hộp.

const FORMATS = FORMAT_CHOICES.map((choice) => choice.id);

/** Khối "máy chưa có ffmpeg": mời tải, hiện tiến độ tải, báo lỗi. `remote`: đang ở máy khác điều khiển máy tính - công cụ nằm ở máy tính, tải ở đó. */
export function FfmpegNeeded({ status, onDownload, onStop, remote = false }: { status: FfmpegStatus; onDownload: () => void; onStop: () => void; remote?: boolean }) {
  if (status.ready && !status.outdated) return <MotionRegion />;
  return (
    <MotionRegion as="div" className="py-3 text-sm" role="group" aria-label="Công cụ ghép âm thanh">
      <p className="font-medium">{status.outdated ? "Cập nhật công cụ" : remote ? "Thiếu công cụ ghép" : "Thiếu công cụ ghép"}</p>
      <p className="mt-0.5 text-fg-2">{status.outdated ? "Có bản mới để ghép lời đọc thành file MP3 / M4B" : "Tải một lần để ghép MP3 / M4B"} (khoảng {formatSize(status.bytes).replace(" ", "\u00a0")}).</p>
      {status.downloading ? (
        <div className="mt-2 flex items-center gap-3">
          <Progress value={ffmpegPercent(status) / 100} size="sm" running label="Đang tải công cụ ghép âm thanh" />
          <span className="tabular shrink-0 text-xs text-fg-2">{status.retrying ? `${RETRYING_NOTE} ${ffmpegPercent(status)}%` : `${ffmpegPercent(status)}%`}</span>
          <Button size="sm" variant="ghost" onClick={onStop}>
            Dừng
          </Button>
        </div>
      ) : remote ? (
        <p className="mt-2">
          <OnComputerOnly verb={status.outdated ? "Cập nhật công cụ ghép âm thanh" : "Tải công cụ ghép âm thanh"} />
        </p>
      ) : status.blocked ? (
        <p className="mt-2 text-warning">{status.blocked}</p>
      ) : (
        <div className="mt-2 flex items-center gap-3">
          {/* Lời lỗi nói "bấm Thử lại" (studio_setup.download_failure): nút mang đúng tên ấy. */}
          <Button size="sm" onClick={onDownload}>
            {status.error ? "Thử lại" : status.outdated ? "Cập nhật công cụ" : "Tải công cụ"}
          </Button>
          {status.error && (
            <div className="text-xs text-danger">
              <span>{status.error}</span>
              <ErrorDetails technical={status.errorDetail} />
            </div>
          )}
        </div>
      )}
    </MotionRegion>
  );
}

export interface AudiobookFormProps {
  format: AudiobookFormat;
  onFormat: (format: AudiobookFormat) => void;
  voice: ReadAloudVoice | undefined;
  /** undefined: chưa có kết quả ước; `planError`: lý do máy chủ từ chối ước (rỗng nếu không). */
  plan: AudiobookPlan | undefined;
  planError: string;
  ffmpeg: FfmpegStatus | undefined;
  onDownload: () => void;
  onStopDownload: () => void;
  /** "Kèm nhạc nền": chỉ hiện khi `plan.music.available`. */
  music?: boolean;
  onMusic?: (on: boolean) => void;
}

export function AudiobookForm({ format, onFormat, voice, plan, planError, ffmpeg, onDownload, onStopDownload, music = false, onMusic }: AudiobookFormProps) {
  const notice = voice ? wholeBookNotice(voice) : "";
  return (
    <MotionRegion className="flex flex-col gap-4">
      <div role="radiogroup" aria-label="Kiểu file" onKeyDown={radioGroupKeys(FORMATS, format, onFormat)} className="relative flex flex-wrap gap-6">
        <SlidingIndicator variant="line" />
        {FORMAT_CHOICES.map((choice, index) => (
          <button
            key={choice.id}
            type="button"
            role="radio"
            aria-checked={format === choice.id}
            tabIndex={radioTabIndex(FORMATS, format, index)}
            onClick={() => onFormat(choice.id)}
            className={cn(
              "relative min-h-10 border-b-2 border-transparent py-3 text-left transition-colors duration-motion-medium",
              format === choice.id ? "text-accent-text" : "text-fg-2 hover:bg-hover",
            )}
          >
            <span className="block text-sm font-medium">{choice.label}</span>
            <span className="mt-1 block text-xs text-fg-2">{choice.hint}</span>
          </button>
        ))}
      </div>

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
      </div>

      {plan?.music?.available && onMusic && <MusicMixOption checked={music} onChange={onMusic} />}

      {notice && (
        <p role="note" className="py-3 text-sm">
          {notice}
        </p>
      )}

      {ffmpeg && <FfmpegNeeded status={ffmpeg} onDownload={onDownload} onStop={onStopDownload} />}

      <p className="text-xs text-fg-3">
        Chạy nền; dừng vẫn giữ phần đã làm.
      </p>
    </MotionRegion>
  );
}

/** Nghe hộp mở từ menu của sách (OPEN_AUDIOBOOK_EVENT) và dựng hộp; "Bắt đầu" chọn nơi lưu rồi giao cho ExportJobHost. */
export function AudiobookDialogHost() {
  const [book, setBook] = useState<ListenBook | null>(null);
  const [format, setFormat] = useMotionState<AudiobookFormat>("mp3");
  const [busy, setBusy] = useState(false);
  const { data: info } = useAppInfo();
  const { data: voices } = useReadAloudVoices();
  const client = useQueryClient();
  useEffect(() => {
    const listener = (event: Event) => setBook((event as CustomEvent<ListenBook>).detail);
    window.addEventListener(OPEN_AUDIOBOOK_EVENT, listener);
    return () => window.removeEventListener(OPEN_AUDIOBOOK_EVENT, listener);
  }, []);

  const voice = book && voices?.length ? resolveVoice(voices, chosenVoice(book.id)) : undefined;
  const plan = useQuery({
    queryKey: ["audiobook-plan", book?.id, voice?.id],
    enabled: Boolean(book && voice),
    queryFn: () => fetchPlan(book!.id, voice!.id),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  const ffmpeg = useQuery({
    queryKey: ["ffmpeg"],
    enabled: book !== null,
    queryFn: ffmpegStatus,
    staleTime: 0,
    retry: false,
    refetchInterval: (query) => (query.state.data?.downloading ? 800 : false),
  });
  const refresh = () => void client.invalidateQueries({ queryKey: ["ffmpeg"] });
  const [music, setMusic] = useMusicChoice(plan.data?.music, book?.id ?? "");

  const start = async () => {
    if (!book || !voice) return;
    setBusy(true);
    try {
      let target = "";
      if (info?.dialogs) {
        const picked = await pickFolder("Chọn nơi lưu", "").catch(() => null);
        if (!picked) return;
        target = picked;
      }
      startExport("audiobook", {
        id: book.id,
        chapters: plan.data?.chapters ?? book.chaptersTotal,
        target,
        cover: coverArtwork(book.title),
        extra: audiobookBody(format, voice.id, music),
      });
      setBook(null);
    } finally {
      setBusy(false);
    }
  };
  const ready = ffmpeg.data?.ready ?? false;
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => setBook(null)}>
          Để sau
        </Button>
        <Button variant="primary" icon={Headphones} loading={busy} disabled={!voice || !ready || Boolean(plan.error)} onClick={() => void start()}>
          Bắt đầu
        </Button>
      </DialogActions>}
      open={book !== null}
      onOpenChange={(open) => !open && setBook(null)}
      title="Xuất sách nói"
      description="Đọc cả cuốn thành file âm thanh, nghe ở máy khác."
      width="max-w-[560px]"
    >
      <AudiobookForm
        format={format}
        onFormat={setFormat}
        voice={voice}
        plan={plan.data}
        planError={plan.error ? (plan.error as Error).message : ""}
        ffmpeg={ffmpeg.data}
        onDownload={() => void ffmpegStart().then(refresh, (error: Error) => toast.error("Chưa tải được công cụ", { description: error.message }))}
        onStopDownload={() => void ffmpegCancel().then(refresh, () => undefined)}
        music={music}
        onMusic={setMusic}
      />

    </Dialog>
  );
}
