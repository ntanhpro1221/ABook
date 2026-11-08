import { S } from "../shared/strings.generated";
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
    <MotionRegion as="div" className="py-3 text-sm" role="group" aria-label={S.s_cong_cu_ghep_am_thanh_f56c00a0}>
      <p className="font-medium">{status.outdated ? S.s_cap_nhat_cong_cu_20b092d6 : remote ? S.s_thieu_cong_cu_ghep_1c3e0226 : S.s_thieu_cong_cu_ghep_1c3e0226}</p>
      <p className="mt-0.5 text-fg-2">{status.outdated ? S.s_co_ban_moi_de_ghep_loi_doc_thanh_file_mp3_e3f81f2c : S.s_tai_mot_lan_de_ghep_mp3_m4b_2e0a2a50}{S.s_khoang_05ede49e}{formatSize(status.bytes).replace(" ", "\u00a0")}).</p>
      {status.downloading ? (
        <div className="mt-2 flex items-center gap-3">
          <Progress value={ffmpegPercent(status) / 100} size="sm" running label={S.s_dang_tai_cong_cu_ghep_am_thanh_050601fc} />
          <span className="tabular shrink-0 text-xs text-fg-2">{status.retrying ? `${RETRYING_NOTE} ${ffmpegPercent(status)}%` : `${ffmpegPercent(status)}%`}</span>
          <Button size="sm" variant="ghost" onClick={onStop}>{S.s_dung_11554138}</Button>
        </div>
      ) : remote ? (
        <p className="mt-2">
          <OnComputerOnly verb={status.outdated ? S.s_cap_nhat_cong_cu_ghep_am_thanh_6fd454a5 : S.s_tai_cong_cu_ghep_am_thanh_1d4036fd} />
        </p>
      ) : status.blocked ? (
        <p className="mt-2 text-warning">{status.blocked}</p>
      ) : (
        <div className="mt-2 flex items-center gap-3">
          {/* Lời lỗi nói "bấm Thử lại" (studio_setup.download_failure): nút mang đúng tên ấy. */}
          <Button size="sm" onClick={onDownload}>
            {status.error ? S.s_thu_lai_c58d068c : status.outdated ? S.s_cap_nhat_cong_cu_20b092d6 : S.s_tai_cong_cu_83ce1fe8}
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
      <div role="radiogroup" aria-label={S.s_kieu_file_510afc1c} onKeyDown={radioGroupKeys(FORMATS, format, onFormat)} className="relative flex flex-wrap gap-6">
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
          <p>{S.s_giong_doc_34c62dcf}<span className="font-medium">{voiceCaption(voice)}</span>
            <span className="text-fg-3">{S.s_giong_dang_chon_cho_cuon_nay_doi_o_trinh_p_63b2e190}</span>
          </p>
        ) : (
          <p className="text-warning">{S.s_may_chua_co_giong_doc_nao_tai_giong_o_cai_aa7e4957}</p>
        )}
        <p className="mt-1 text-fg-2" aria-live="polite">
          {planError || (plan ? planText(plan) : voice ? S.s_dang_tinh_do_dai_408daa51 : "")}
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

      <p className="text-xs text-fg-3">{S.s_chay_nen_dung_van_giu_phan_da_lam_b5b35b4d}</p>
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
        const picked = await pickFolder(S.s_chon_noi_luu_2965936c, "").catch(() => null);
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
        <Button variant="ghost" onClick={() => setBook(null)}>{S.s_de_sau_9be0a7ab}</Button>
        <Button variant="primary" icon={Headphones} loading={busy} disabled={!voice || !ready || Boolean(plan.error)} onClick={() => void start()}>{S.s_bat_dau_b3cacc46}</Button>
      </DialogActions>}
      open={book !== null}
      onOpenChange={(open) => !open && setBook(null)}
      title={S.s_xuat_sach_noi_219fb12a}
      description={S.s_doc_ca_cuon_thanh_file_am_thanh_nghe_o_may_d043f850}
      width="max-w-[560px]"
    >
      <AudiobookForm
        format={format}
        onFormat={setFormat}
        voice={voice}
        plan={plan.data}
        planError={plan.error ? (plan.error as Error).message : ""}
        ffmpeg={ffmpeg.data}
        onDownload={() => void ffmpegStart().then(refresh, (error: Error) => toast.error(S.s_chua_tai_duoc_cong_cu_cfe422f9, { description: error.message }))}
        onStopDownload={() => void ffmpegCancel().then(refresh, () => undefined)}
        music={music}
        onMusic={setMusic}
      />

    </Dialog>
  );
}
