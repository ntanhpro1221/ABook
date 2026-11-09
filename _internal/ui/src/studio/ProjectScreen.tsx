import { S } from "../shared/strings.generated";
import { TickingValue } from "@/shared/TickingValue";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { MoreInfo } from "@/shared/SettingsNav";
import { DotJoin } from "@/shared/DotJoin";
import { LoadingCrossfade, MotionPresence } from "@/shared/MotionPresence";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpenText,
  BookPlus,
  Headphones,
  Check,
  Info,
  ChevronDown,
  CircleAlert,
  Download,
  FolderDown,
  FolderOpen,
  Mic2,
  MoreHorizontal,
  Pause,
  TextCursorInput,
  Play,
  SlidersHorizontal,
  RefreshCw,
  RotateCcw,
  Square,
  Trash2,
  Users,
  Wand2,
} from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { useListPresence } from "@/shared/motion";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "@/shared/toast";
import { DialogActions,
  Button,
  Dialog,
  EmptyState,
  Progress,
  Skeleton,
  StatusPill,
  StatusText,
  TabLabel,
  Tabs,
  TabsContent,
  TabsList,
  TabsPanels,
  TabsTrigger,
  Vu,
 } from "@/shared/ui";
import { api, type BookSummary, type Chapter } from "@/studio/api";
import { cn } from "@/shared/cn";
import { SCREEN_TITLE, ScreenHeader } from "@/shared/ScreenHeader";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { usePageTitle } from "@/shared/title";
import { Windowed } from "@/shared/Windowed";
import { useScrollMemory } from "@/shared/scrollMemory";
import { toastRemoved } from "@/shared/trashUndo";
import {
  projectStatus,
  useActivity,
  useAppInfo,
  useBook,
  useContinuation,
  useLeaveQueue,
  useParts,
  usePause,
  useReveal,
  useStart,
  useStudioMissing,
  useStop,
} from "@/studio/data";
import {
  formatDate,
  etaOf,
  formatLength,
  formatNumber,
  formatPercent,
  formatRelative,
  formatTime,
} from "@/shared/format";
import { CastList } from "@/listen/BookScreen";
import { analyzerLabel } from "./analyzerLabel";
import { ProjectInfoDialog } from "./ProjectInfo";
import { ApplyChangesDialog } from "./ApplyChanges";
import { useUnmerge } from "./useUnmerge";
import { CoverEditor } from "./CoverEditor";
import { ChapterError } from "./ChapterError";
import { friendlyError } from "./errorText";
import { ANALYSIS_CUT_COST, ANALYSIS_STOP_FACT, asksBeforeResume, queueWaitNotice, stopAnalysisAdvice } from "./stopText";
import { bookFailure, failureText, isListenOnly, isOffline, useSideError } from "./polling";
import { ReviewQueue, useReviewCount } from "./ReviewQueue";
import { PhoneEdits, useInboxCount } from "./PhoneEdits";
import { WorkInbox, useWorkCount } from "./WorkInbox";
import { ScriptTab, useCastingContents } from "./ScriptTab";
import { MusicTab } from "./MusicTab";
import { NameReadings } from "./NameReadings";
import { VoicePicker } from "./VoicePicker";
import { usePlayer } from "@/listen/player";
import { useCast, useSource } from "@/listen/source";
import type { CastMember } from "@/listen/model";
import { GenderDialog, RenamePersonDialog } from "@/studio/CastEdits";
import { MergeDialog } from "@/studio/MergePeople";
import { ExportDialog } from "@/studio/ExportBook";
import { PrecastBanner, PrecastReview, PrecastWaitSwitch, usePrecastKeys } from "./PrecastReview";
import { TellerModeSwitch } from "./TellerModeSwitch";
import { canReview } from "./precast";
import { useFadeScroller } from "@/shared/scrollFade";

/** Phát một chương ngay trong Studio (nghe kiểm tra) bằng chính trình phát của phía Nghe - ở chế độ "nghe kiểm":
 *  không ghi đè chỗ đang nghe dở, tốc độ hay nhật ký đêm của người nghe. */
function usePlayChapter() {
  const source = useSource();
  const player = usePlayer();
  return async (bookId: string, chapterId: number) => {
    const book = await source.book(bookId);
    player.play(book, book.chapters ?? [], chapterId, 0, { purpose: "review" });
  };
}

// ---- Sản xuất -------------------------------------------------------------------------------------------

type StepState = "done" | "active" | "paused" | "pending";

function stepStates(book: BookSummary): [StepState, StepState, StepState] {
  const live = (book.running || book.starting) && !book.paused && !book.stopping;
  const now: StepState = live ? "active" : "paused";
  if (book.phase === "done") return ["done", "done", "done"];
  if (book.phase === "idle") return ["pending", "pending", "pending"];
  if (book.phase === "analysis") return [now, "pending", "pending"];
  if (book.phase === "casting") return ["done", now, "pending"];
  if (book.phase === "synthesis") return ["done", "done", now];
  // Đã dừng / lỗi: suy từ tiến độ.
  if (book.progress.analysis < 1) return [now, "pending", "pending"];
  if (book.progress.synthesis <= 0) return ["done", now, "pending"];
  return ["done", "done", now];
}

function Step({
  index,
  state,
  title,
  detail,
  progress,
  icon: Icon,
}: {
  index: number;
  state: StepState;
  title: string;
  detail: string;
  progress?: number;
  icon: typeof Wand2;
}) {
  return (
    // Phẳng, không khung: ba bước đứng trong khối "Các bước" (đã là một khối), nhóm bằng khoảng trắng (DESIGN.md mục 4.2).
    <MotionRegion as="div" className="relative min-w-0 flex-1">
      <div className="flex items-center gap-2.5">
        <div
          className={cn(
            "grid size-7 place-items-center rounded-full text-xs font-bold",
            state === "done" && "bg-success text-success-ink",
            state === "active" && "bg-accent text-accent-ink",
            state === "paused" && "bg-fg-3 text-bg",
            state === "pending" && "bg-hover text-fg-2", // số bước: --fg-3 trên --hover chỉ 4,46:1 (soát a31 C2)
          )}
        >
          {state === "done" ? <Check className="size-4" strokeWidth={3} /> : state === "active" ? <Icon className="size-3.5" /> : index}
        </div>
        <div className={cn("text-sm font-semibold", state === "pending" && "text-fg-3")}>{title}</div>
        {state === "active" && <Vu className="ml-auto h-3 text-accent" />}
        {state === "paused" && <Pause className="ml-auto size-3.5 text-fg-3" />}
      </div>
      <p data-motion-live className={cn("mt-2 text-xs leading-relaxed", state === "pending" ? "text-fg-3" : "text-fg-2")}>{detail}</p>
      {progress !== undefined && state !== "pending" && (
        <div className="mt-3 flex items-center gap-2">
          <Progress value={progress} running={state === "active"} tone={state === "done" ? "success" : state === "paused" ? "muted" : "accent"} size="sm" label={title} />
          <span className="tabular w-9 text-right text-xs font-semibold"><TickingValue>{formatPercent(progress)}</TickingValue></span>
        </div>
      )}
    </MotionRegion>
  );
}

/** Lần bấm chạy gần nhất không khởi động được (chưa cài Studio, thiếu Ollama...). Hiện cả ở sách đã xong - nơi "Áp dụng N thay đổi"
 *  là cách duy nhất để chạy lại, và sửa chờ áp vẫn còn đó (máy chủ không ghi mốc "đã áp" khi khởi động hỏng) - kèm "Thử lại". */
function StartError({ book }: { book: BookSummary }) {
  const start = useStart();
  if (!book.startError) return null;
  return (
    <div role="alert" className="mt-3 flex flex-wrap items-start gap-2 py-3 text-sm text-danger">
      <CircleAlert className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0 flex-1">{S.s_chua_khoi_dong_duoc_41fc29a4}{book.startError}</span>
      {!book.starting && !book.running && (
        <Button variant="ghost" size="sm" icon={RotateCcw} loading={start.isPending} onClick={() => start.mutate(book.id)}>{S.s_thu_lai_c58d068c}</Button>
      )}
    </div>
  );
}

/** Lỗi của lần làm sách: câu cho người nghe + việc nên làm; nguyên văn kỹ thuật thu vào "Chi tiết". */
function LastError({ raw, redo = false }: { raw: string; redo?: boolean }) {
  const studio = useAppInfo().data?.studio;
  const shown = friendlyError(raw, Boolean(studio), redo, Boolean(studio?.damagedSteps?.includes("llm")));
  return (
    <div className="mt-3 flex gap-2 py-3 text-sm text-danger">
      <CircleAlert className="mt-line-icon size-4 shrink-0" />
      <div className="min-w-0">
        <p>
          {shown.summary} {shown.hint}
        </p>
        {shown.detail && (
          <details className="mt-1 text-xs">
            <summary className="cursor-pointer select-none">{S.s_chi_tiet_e762d926}</summary>
            <p className="mt-1 select-text break-words font-mono">{shown.detail}</p>
          </details>
        )}
      </div>
    </div>
  );
}

/** Lượt chạy gần nhất chết vì sự cố mà sổ không có lỗi nào để hiện (tiến trình bị tắt, worker sập): nói nguyên nhân do supervisor ghi
 *  thay vì im lặng (soát a88 T4). Bạn bấm Dừng thì không phải sự cố - máy chủ không gửi `runEnd`. */
export function RunEnd({ end, redo }: { end: NonNullable<BookSummary["runEnd"]>; redo: boolean }) {
  const info = useAppInfo().data?.studio;
  const detail = [end.detail, end.exitCode ? S.s_ma_thoat_0_5004088f(end.exitCode) : ""].filter(Boolean).join(" - ");
  const shown = friendlyError(detail, Boolean(info), redo, Boolean(info?.damagedSteps?.includes("llm")));
  const summary =
    end.state === "lost"
      ? S.s_lan_chay_truoc_bi_ngat_dot_ngot_tien_trinh_48f760d3
      : shown.summary === S.s_co_loi_khi_lam_sach_469057f5
        ? S.s_lan_chay_truoc_dung_vi_su_co_edbb6146
        : shown.summary;
  return (
    <MotionRegion as="div" role="alert" className="mt-3 flex gap-2 py-3 text-sm text-danger">
      <CircleAlert className="mt-line-icon size-4 shrink-0" />
      <div className="min-w-0">
        <p>
          {summary} {shown.hint}
        </p>
        {shown.detail && (
          <details className="mt-1 text-xs">
            <summary className="cursor-pointer select-none">{S.s_chi_tiet_e762d926}</summary>
            <p className="mt-1 select-text break-words font-mono">{shown.detail}</p>
          </details>
        )}
      </div>
    </MotionRegion>
  );
}

/** Dưới hàng "Người kể chuyện" của tab Nhân vật. Cuốn chưa chạy: đổi giọng kể qua "Sửa thiết lập" (trình tạo điền sẵn mọi lựa chọn
 *  cũ). Đã phân vai: nút "Đổi giọng người kể" ở hàng ấy, như nhân vật (soát UX a23, B21). Đang phân tích: nói khi nào đổi được. */
function NarratorNote({ book }: { book: BookSummary }) {
  const navigate = useNavigate();
  if (book.phase === "idle") {
    return (
      <>{S.s_giong_ke_chon_luc_tao_sach_doi_duoc_vi_cuo_7293eb77}{" "}
        <button type="button" onClick={() => navigate(`/studio/new?redo=${book.id}`)} className="font-medium text-accent-text underline underline-offset-2">{S.s_doi_giong_ke_bbebd2a5}</button>
      </>
    );
  }
  if (book.castLocked) return <>{S.s_doi_giong_ke_khong_phai_tao_lai_sach_cau_k_bee3443c}</>;
  return <>{S.s_doi_duoc_giong_ke_khi_may_phan_vai_xong_ng_d2298cde}</>;
}

/** Dòng nói còn bao lâu của cả lượt làm sách (hay vì sao đang đứng); "" khi không có gì để nói. */
function progressNote(book: BookSummary): string {
  const live = book.running || book.starting;
  // Giữ chờ duyệt (precast.held) cũng là `paused` nhưng là đợi người nghe, không phải ai bấm Tạm dừng (soát UX a23: "47% tổng"
  // đứng yên không nói vì sao). Tạm dừng thường (pin, người bấm) đã nói ở trạng thái đầu trang - không nói lại ở đây (soát 24-10 T19).
  return book.stopping ? S.s_dang_dung_cd5f369b : book.paused ? (book.precast?.held ? S.s_cho_ban_duyet_roi_bam_thu_am_5f91fe4f : "") : etaOf(book) ?? (live ? S.s_dang_uoc_tinh_thoi_gian_6e128147 : "");
}

/** Tiến độ cả sách ở đầu trang dự án: thanh mảnh + phần trăm, kèm còn bao lâu (soát 25-10: trước là chữ "45% tổng" không có thanh, cách hàng tab một
 *  khoảng khác mọi màn). Sách chưa chạy / đã xong không có gì để đo - khối khép lại. */
export function HeaderProgress({ book }: { book: BookSummary }) {
  const running = (book.running || book.starting) && !book.paused && !book.stopping;
  const note = progressNote(book);
  return (
    <MotionPresence open={book.phase !== "done" && book.phase !== "idle"}>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <div className="flex min-w-0 flex-1 basis-48 items-center gap-3 sm:max-w-xs">
          <Progress value={book.progress.overall} running={running} tone={running ? "accent" : "muted"} size="xs" label={S.s_tien_do_ca_sach_25195f69} />
          <span className="tabular w-10 shrink-0 text-right text-sm font-medium"><TickingValue>{formatPercent(book.progress.overall)}</TickingValue></span>
        </div>
        {note && <TickingValue className="text-sm text-fg-2">{note}</TickingValue>}
      </div>
    </MotionPresence>
  );
}

export function ProductionPanel({ book }: { book: BookSummary }) {
  const [analysis, casting, synthesis] = stepStates(book);
  const live = book.running || book.starting;
  // Dòng phụ "Các bước" nói bước đang tới - cả khi đang tạm dừng; lý do dừng đã ở trên.
  const current = [analysis, casting, synthesis].findIndex((state) => state === "active" || state === "paused");
  const stepSummary = current >= 0 ? [S.s_phan_tich_truyen_36344512, S.s_phan_vai_b490d45b, S.s_thu_am_va_kiem_tra_313021dd][current] : book.statusLabel;
  return (
    <MotionRegion as="section" className="mt-6">
      {live && book.logLost && (
        <p role="status" className="mb-3 flex gap-2 py-2 text-sm text-warning">
          <CircleAlert className="mt-line-icon size-4 shrink-0" />
          <span>{S.s_sach_van_dang_chay_binh_thuong_nhung_nhat_5dd24dc3}{book.logLost.lines}{S.s_dong_da_bo_thuong_do_phan_mem_diet_virus_d_9d4ae9c8}</span>
        </p>
      )}
      <Fold storageKey={`project.${book.id}.steps`} title={S.s_cac_buoc_93e33a59} summary={stepSummary}>
      <div className="flex flex-col gap-6 sm:flex-row sm:gap-8">
        <Step
          index={1}
          state={analysis}
          icon={BookOpenText}
          title={S.s_phan_tich_truyen_36344512}
          detail={
            book.speakerPass?.active
              ? S.s_xac_dinh_nguoi_noi_tung_cau_0_1_chuong_fa4492bd(book.speakerPass.done, book.speakerPass.total)
              : book.settings.analyzer
                ? S.s_doc_ca_truyen_de_nhan_ra_loi_thoai_ai_dang_25589143(analyzerLabel(book.settings.analyzer))
                : S.s_doc_ca_truyen_de_nhan_ra_loi_thoai_ai_dang_46dad1fa
          }
          progress={book.progress.analysis}
        />
        <Step
          index={2}
          state={casting}
          icon={Users}
          title={S.s_phan_vai_b490d45b}
          detail={S.s_trao_cho_moi_nhan_vat_mot_giong_rieng_va_k_9788a813}
        />
        <Step
          index={3}
          state={synthesis}
          icon={Mic2}
          title={S.s_thu_am_va_kiem_tra_313021dd}
          detail={S.s_doc_tung_cau_nghe_lai_bang_nhan_dang_giong_a58b69c7}
          progress={book.progress.synthesis}
        />
      </div>
      </Fold>
      {/* Trước mốc phân tích xong: đặt sẵn "Chờ tôi duyệt trước khi thu" cho cuốn này (webui/precast.py). */}
      {!book.castLocked && book.precast && <PrecastWaitSwitch book={book} className="mt-2" />}
      <StartError book={book} />
      {book.lastError && book.phase === "error" && <LastError raw={book.lastError} redo={asksBeforeResume(book)} />}
      {book.runEnd && !book.running && !book.starting && !(book.lastError && book.phase === "error") && (
        <RunEnd end={book.runEnd} redo={asksBeforeResume(book)} />
      )}
    </MotionRegion>
  );
}

// ---- Nút hành động ---------------------------------------------------------------------------------------

/** "Tiếp tục" một cuốn mà pha phân tích bị ngắt (soát UX a23 B16: một bấm là chạy, dù làm tiếp = cuốn khác): nói thẳng hệ quả,
 *  nút chính là làm lại từ đầu, "Vẫn tiếp tục" là phụ. Studio từ xa không tạo lại sách được - chỉ còn "Vẫn tiếp tục". */
function ResumeAnalysisDialog({ book, open, onOpenChange, onRedo, onResume }: {
  book: BookSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRedo: () => void;
  onResume: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={S.s_tiep_tuc_phan_tich_6d773a52}>
      <div className="mb-5 flex gap-3 py-4 text-sm leading-relaxed text-fg">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" />
        <div className="text-pretty">
          <p>
            <span className="font-semibold">{S.s_phan_tich_cua_4a395adb}{book.title}{S.s_da_dung_giua_chung_df1e44a8}</span>{S.s_lam_tiep_tu_cho_ay_c42ae1b1}{ANALYSIS_CUT_COST}{S.s_khac_voi_khi_phan_tich_lien_mot_mach_a389d2e0}</p>
          <p className="mt-2 text-fg-2">{S.s_muon_chac_nhu_chay_lien_mach_lam_lai_phan_856b2309}</p>
        </div>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>{S.s_de_sau_9be0a7ab}</Button>
        <Button
          variant="ghost"
          icon={Play}
          onClick={() => {
            onOpenChange(false);
            onResume();
          }}
        >{S.s_van_tiep_tuc_8ba2321f}</Button>
        <Button
          variant="primary"
          icon={RotateCcw}
          autoFocus
          onClick={() => {
            onOpenChange(false);
            onRedo();
          }}
        >{S.s_phan_tich_lai_745c8437}</Button>
      </div>
    </Dialog>
  );
}

function StopDialog({ book, open, onOpenChange }: { book: BookSummary; open: boolean; onOpenChange: (open: boolean) => void }) {
  const stop = useStop();
  const pause = usePause();
  const inAnalysis = book.phase === "analysis";
  const eta = etaOf(book);
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={inAnalysis ? S.s_dung_phan_tich_3fae0cc9 : S.s_dung_thu_am_c0b08972}
      description={
        // Không nêu tên nút làm tiếp: sau khi dừng nó là "Tiếp tục tạo", "Bắt đầu thu" hay "Áp dụng N thay đổi"
        // tuỳ sách đã tới đâu (soát UX 30-09). Đang tạm dừng thì nói Dừng khác Tạm dừng ở chỗ nào.
        inAnalysis
          ? undefined
          : book.paused
            ? S.s_tam_dung_van_giu_bo_nho_card_do_hoa_dung_h_5c49cc06
            : S.s_moi_chuong_va_cau_da_xong_duoc_giu_nguyen_295ff27b
      }
    >
      <MotionRegion>
      {inAnalysis && (
        <div className="mb-5 flex gap-3 py-4 text-sm leading-relaxed text-fg">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" />
          <div className="text-pretty">
            <p>
              <span className="font-semibold">{ANALYSIS_STOP_FACT}</span> - {ANALYSIS_CUT_COST}.
            </p>
            <p data-motion-live className="mt-2 text-fg-2">{S.s_nen_de_chay_het_buoc_nay_55b34878}{eta ? ` (${eta})` : ""}. {stopAnalysisAdvice(book)}
            </p>
          </div>
        </div>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          {book.paused ? S.s_de_nguyen_2f029b4a : S.s_de_chay_tiep_28b8b5b6}
        </Button>
        {inAnalysis && !book.paused && book.canPause && (
          <Button
            variant="primary"
            icon={Pause}
            loading={pause.isPending}
            onClick={() => pause.mutate({ id: book.id, paused: true }, { onSettled: () => onOpenChange(false) })}
          >{S.s_tam_dung_67635815}</Button>
        )}
        <Button
          variant="danger"
          icon={Square}
          loading={stop.isPending}
          disabled={stop.isPending}
          onClick={() => stop.mutate({ id: book.id, paused: Boolean(book.paused) }, { onSettled: () => onOpenChange(false) })}
        >
          {inAnalysis ? S.s_van_dung_f9d19e87 : S.s_dung_11554138}
        </Button>
      </div>
      </MotionRegion>
    </Dialog>
  );
}

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[highlighted]:bg-hover";

// Đổi tên chỉ đổi tên HIỆN (store.TITLE_FILE): thư mục dự án và sổ của dây chuyền giữ nguyên, nên làm được cả lúc chạy.
function RenameDialog({ book, open, onOpenChange }: { book: BookSummary; open: boolean; onOpenChange: (open: boolean) => void }) {
  const dialogForm1 = useId();
  const client = useQueryClient();
  const [title, setTitle] = useState(book.title);
  useEffect(() => {
    if (open) setTitle(book.title);
  }, [open, book.title]);
  const rename = useMutation({
    mutationFn: (value: string) => api<BookSummary>(`/api/books/${book.id}/title`, { method: "PUT", body: { title: value } }),
    onSuccess: (summary) => {
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: ["book", book.id] });
      void client.invalidateQueries({ queryKey: ["listen"] });
      toast.success(S.s_da_doi_ten_thanh_0_268ec88c(summary.title));
      onOpenChange(false);
    },
    onError: (error: Error) => toast.error(S.s_chua_doi_duoc_ten_ad5b4df1, { description: error.message }),
  });
  const typed = title.trim();
  return (
    <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>{S.s_huy_96732485}</Button>
          <Button type="submit" form={dialogForm1} variant="primary" loading={rename.isPending} disabled={!typed || typed === book.title}>{S.s_doi_ten_a2a0dc70}</Button>
        </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      title={S.s_doi_ten_sach_bfe95826}
      description={S.s_ten_moi_hien_o_thu_vien_dien_thoai_va_file_a0f15560}
    >
      <form id={dialogForm1}
        onSubmit={(event) => {
          event.preventDefault();
          if (typed && typed !== book.title) rename.mutate(typed);
        }}
      >
        <label htmlFor="rename-book-title" className="text-sm font-medium">{S.s_ten_sach_d54846eb}</label>
        <input
          id="rename-book-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={160}
          data-autofocus
          autoComplete="off"
          className="mt-1.5 h-10 w-full rounded-control border border-line bg-panel px-3 text-sm text-fg outline-none focus-visible:border-focus"
        />

      </form>
    </Dialog>
  );
}

// Xoá = chuyển cả thư mục dự án vào Thùng rác của Windows (khôi phục được); file truyện gốc nằm ngoài, không bị đụng.
function DeleteDialog({ book, open, onOpenChange }: { book: BookSummary; open: boolean; onOpenChange: (open: boolean) => void }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const player = usePlayer();
  const busy = book.running || book.starting;
  const remove = useMutation({
    mutationFn: () => api<{ ok: boolean; undo?: string }>(`/api/books/${book.id}`, { method: "DELETE" }),
    onSuccess: (result) => {
      onOpenChange(false);
      navigate("/studio", { replace: true });
      client.removeQueries({ queryKey: ["book", book.id] });
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: ["listen"] });
      // "Hoàn tác" (trash_pending.py): thư mục nằm chờ vài chục giây trước khi vào Thùng rác.
      toastRemoved({
        message: S.s_da_xoa_du_an_0_45456313(book.title),
        title: book.title,
        undo: result.undo,
        onRestored: () => {
          void client.invalidateQueries({ queryKey: ["library"] });
          void client.invalidateQueries({ queryKey: ["listen"] });
        },
      });
    },
    onError: (error: Error) => toast.error(S.s_chua_xoa_duoc_b872fff6, { description: error.message }),
  });
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>{S.s_de_sau_9be0a7ab}</Button>
        <Button
          variant="danger"
          icon={Trash2}
          loading={remove.isPending}
          disabled={busy}
          onClick={() => {
            // Cuốn đang nghe giữ file chương mở - đóng trình phát trước (nó lưu chỗ nghe lúc sách còn đó).
            if (player.track?.bookId === book.id) player.close();
            remove.mutate();
          }}
        >{S.s_chuyen_vao_thung_rac_8fdb5a40}</Button>
      </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      title={S.s_xoa_du_an_0_6f17ec46(book.title)}
      description={S.s_ca_thu_muc_du_an_vao_thung_rac_cua_windows_6f78dcf8}
    >
      <MotionRegion>
      {/* Studio từ xa không nhận đường dẫn trên máy tính (soát a27 lỗi 10). */}
      {book.path && <p className="break-all py-2 text-xs text-fg-2">{book.path}</p>}
      {busy && <p className="mt-3 text-sm text-warning">{S.s_sach_dang_chay_dung_sach_truoc_roi_moi_xoa_a7d1bac1}</p>}

      </MotionRegion>
    </Dialog>
  );
}

/** Một dòng của menu "…" (dự án, hàng dự án). */
export function MenuItem({ icon: Icon, onSelect, danger = false, disabled = false, children }: {
  icon: typeof Wand2;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <DropdownMenu.Item disabled={disabled} onSelect={onSelect} className={cn(MENU_ITEM, "data-[disabled]:opacity-50", danger && "text-danger")}>
      <Icon className="size-4" /> {children}
    </DropdownMenu.Item>
  );
}

/** "…" của một dự án: việc ít dùng của đầu trang (`children`, đứng trên), rồi đổi tên, làm tiếp, xoá. `rename={false}` cho dự án hỏng
 *  (không đọc được - chỉ còn xoá). */
export function ProjectMenu({ book, rename = true, className, children }: { book: BookSummary; rename?: boolean; className?: string; children?: ReactNode }) {
  const [dialog, setDialog] = useState<"rename" | "delete" | null>(null);
  const navigate = useNavigate();
  // Studio từ xa: đổi tên và làm tiếp chạy được; xoá dự án chỉ làm được trên máy tính (DELETE không nằm trong remote_studio.ALLOWED).
  const remote = Boolean(useAppInfo().data?.remote);
  // `?.`: tóm tắt của dự án hỏng là {broken: "..."} - không có segments.
  const analyzed = (book.segments?.analyzed ?? 0) > 0;
  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={S.s_tuy_chon_du_an_0_bd8165fe(book.title)}
            className={cn(
              "touch-box inline-flex size-9 shrink-0 items-center justify-center rounded-control text-fg-2 transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover",
              className,
            )}
          >
            <MoreHorizontal className="glyph ink-end" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-52 rounded-cover border border-line bg-panel p-1.5 shadow-float">
            {children && (
              <>
                {children}
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
              </>
            )}
            {rename && <MenuItem icon={TextCursorInput} onSelect={() => setDialog("rename")}>{S.s_doi_ten_a2a0dc70}</MenuItem>}
            {/* Truyện dài làm nhiều đợt: phần mới giữ giọng, cách đọc tên, ghim của phần này (continuation.py). Dự án chưa
                phân tích câu nào thì không có gì để mang theo - mờ kèm lý do thay vì dẫn tới một phần mới trống (soát UX 29-09). */}
            {/* Dự án hỏng (`broken`) không có `segments` và không có gì để mang theo: chỉ còn xoá. */}
            {!book.broken && (
              <DropdownMenu.Item
                disabled={!analyzed}
                onSelect={() => navigate(`/studio/new?continue=${book.id}`)}
                className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
              >
                <BookPlus className="size-4" />{S.s_lam_tiep_cuon_nay_c6fc93ac}{!analyzed && <span className="ml-auto pl-3 text-xs text-fg-3">{S.s_chay_phan_nay_truoc_73213667}</span>}
              </DropdownMenu.Item>
            )}
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
            {remote ? (
              <div className="px-2 py-1.5">
                <OnComputerOnly verb={S.s_xoa_du_an_6b9e7c0b} />
              </div>
            ) : (
              <MenuItem icon={Trash2} danger onSelect={() => setDialog("delete")}>{S.s_xoa_du_an_6b9e7c0b}</MenuItem>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <RenameDialog book={book} open={dialog === "rename"} onOpenChange={(open) => setDialog(open ? "rename" : null)} />
      {!remote && <DeleteDialog book={book} open={dialog === "delete"} onOpenChange={(open) => setDialog(open ? "delete" : null)} />}
    </>
  );
}

/** MỘT nút chính của đầu trang dự án, chọn theo trạng thái (DESIGN.md mục 7); `null` = lúc ấy không có việc gì để bấm (xếp hàng mà chưa có
 *  chương nào nghe được). Mọi việc khác vào "…". */
export type PrimaryKind =
  | "starting"
  | "stopping"
  | "unpause"
  | "pause"
  | "start"
  | "record"
  | "reanalyze"
  | "continue"
  | "apply"
  | "listen";

export function primaryKind(book: BookSummary): PrimaryKind | null {
  const listen = book.chapters.completed > 0 ? "listen" : null;
  const redoWaiting = book.phase === "done" ? (book.chapters.redo ?? 0) : 0;
  if (book.queuePosition) return listen;
  if (book.starting) return "starting";
  if (book.running) {
    if (book.stopping) return "stopping";
    if (book.paused) return "unpause";
    return book.canPause ? "pause" : listen;
  }
  if (book.phase === "idle") return "start";
  // Sách đang chờ duyệt mà tiến trình đã chết (máy chủ khởi động lại): vẫn là "Thu âm" (soát UX a8).
  if (book.precast?.held && book.phase !== "done") return "record";
  // Phân tích bị ngắt: chạy tiếp ra MỘT CUỐN KHÁC (AGENTS.md) - việc chính là làm lại từ đầu; "Tiếp tục" lùi vào "…" và hỏi lại.
  if (asksBeforeResume(book)) return "reanalyze";
  if (book.phase !== "done") return "continue";
  // Sách đã xong không tự chạy lại: sửa của người nghe chờ ở đây (Pipeline._recover chỉ thu lại câu bị ảnh hưởng).
  if (book.pendingChanges) return "apply";
  // Chương chờ thu lại mà không còn yêu cầu nào để "áp" (soát UX a32, #1).
  if (redoWaiting > 0) return "continue";
  return "listen";
}

export function Actions({ book }: { book: BookSummary }) {
  const start = useStart();
  const reveal = useReveal();
  const remote = Boolean(useAppInfo().data?.remote);
  const navigate = useNavigate();
  const studio = useStudioMissing();
  // Phân tích và thu âm chạy bằng Studio: máy chưa có thì giải thích ở đây, không gửi lệnh rồi nhận lỗi.
  const begin = (id: string) => {
    if (!studio.missing) return start.mutate(id);
    toast.error(studio.repair ? S.s_can_sua_studio_a65aa0f0 : studio.update ? S.s_can_cap_nhat_studio_0018e420 : S.s_can_cai_studio_1599eed5, {
      description: S.s_phan_tich_va_thu_am_chay_bang_studio_ea5c7b5c,
      action: remote ? undefined : { label: studio.action, onClick: () => navigate("/studio") },
    });
  };
  const [confirmStop, setConfirmStop] = useState(false);
  const [confirmApply, setConfirmApply] = useState(false);
  const [confirmResume, setConfirmResume] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [details, setDetails] = useState(false);
  const live = book.running;
  const leaveQueue = useLeaveQueue();
  const pause = usePause();
  // Phân tích xong thì sổ nhân vật đã đủ để làm tiếp; mục chỉ hiện khi thư mục truyện có chương mới sau chương cuối.
  const analyzed = book.segments.total > 0 && book.segments.analyzed === book.segments.total;
  const next = useContinuation(book.id, analyzed).data?.paths.length ?? 0;
  const redoWaiting = book.phase === "done" ? (book.chapters.redo ?? 0) : 0;
  const kind = primaryKind(book);
  const unpause = () => pause.mutate({ id: book.id, paused: false, battery: book.paused === "battery" });
  // Một nút, nhãn và biểu tượng đổi theo trạng thái: Button mờ chéo chữ / biểu tượng tại chỗ, không thay cả nút.
  const primary: Record<PrimaryKind, { label: string; icon?: typeof Wand2; loading?: boolean; run?: () => void }> = {
    starting: { label: S.s_dang_khoi_dong_e7a9b0e5, loading: true },
    // Đã bấm Dừng: sách còn chạy tới chỗ dừng sạch kế - tạm dừng / dừng thêm lần nữa không còn nghĩa (soát a88 V1).
    stopping: { label: S.s_dang_dung_9b35aeb5, loading: true },
    // Giữ chờ duyệt: "Tiếp tục" và "Thu âm" là MỘT việc - tên là "Thu âm" (soát UX a8 05-10, mục 12).
    unpause: { label: book.precast?.held ? S.s_thu_am_db588c2e : S.s_tiep_tuc_87a7ae88, icon: book.precast?.held ? Mic2 : Play, loading: pause.isPending, run: unpause },
    // Tạm dừng giữ tiến trình sống, làm tiếp đúng chỗ - an toàn cả giữa lúc phân tích; "Dừng" (kết thúc lượt chạy) ở "…".
    pause: { label: S.s_tam_dung_67635815, icon: Pause, loading: pause.isPending, run: () => pause.mutate({ id: book.id, paused: true }) },
    start: { label: S.s_bat_dau_b3cacc46, icon: Wand2, loading: start.isPending, run: () => begin(book.id) },
    record: { label: S.s_thu_am_db588c2e, icon: Mic2, loading: start.isPending, run: () => begin(book.id) },
    reanalyze: { label: S.s_phan_tich_lai_745c8437, icon: RotateCcw, run: () => navigate(`/studio/new?redo=${book.id}`) },
    continue: { label: S.s_tiep_tuc_87a7ae88, icon: Play, loading: start.isPending, run: () => begin(book.id) },
    apply: { label: S.s_ap_dung_0_thay_doi_fdb3a048(book.pendingChanges ?? 0), icon: RefreshCw, loading: start.isPending, run: () => setConfirmApply(true) },
    listen: { label: S.s_nghe_trong_thu_vien_c0d6771a, icon: Headphones, run: () => navigate(`/book/${book.id}`) },
  };
  const shown = kind ? primary[kind] : null;
  const pending = book.segments.pending ?? book.segments.total - book.segments.analyzed;
  return (
    <MotionRegion as="div" className="flex flex-wrap items-center gap-2">
      <MotionPresence open={Boolean(shown)}>
        {shown && (
          <Button variant="primary" size="lg" icon={shown.icon} loading={shown.loading} disabled={!shown.run} onClick={shown.run} className="max-sm:basis-full">
            {shown.label}
          </Button>
        )}
      </MotionPresence>
      <ProjectMenu book={book}>
        {book.chapters.completed > 0 && kind !== "listen" && (
          <MenuItem icon={Headphones} onSelect={() => navigate(`/book/${book.id}`)}>{S.s_nghe_trong_thu_vien_c0d6771a}</MenuItem>
        )}
        {asksBeforeResume(book) && !live && !book.starting && !book.queuePosition && (
          <MenuItem icon={Play} onSelect={() => setConfirmResume(true)}>{S.s_van_tiep_tuc_8ba2321f}</MenuItem>
        )}
        {live && !book.stopping && <MenuItem icon={Square} onSelect={() => setConfirmStop(true)}>{S.s_dung_11554138}</MenuItem>}
        {/* Thay đổi chờ áp khi máy đang chạy: xem được, và bỏ được khi đã tạm dừng tới checkpoint (soát a83 B5). */}
        {live && book.pendingChanges ? (
          <MenuItem icon={RefreshCw} onSelect={() => setConfirmApply(true)}>{book.pendingChanges}{S.s_thay_doi_cho_ap_e4e2c5a3}</MenuItem>
        ) : null}
        {book.queuePosition ? <MenuItem icon={Square} onSelect={() => leaveQueue.mutate({ id: book.id })}>{S.s_bo_xep_hang_e797cd68}</MenuItem> : null}
        {/* Chưa chạy bước nào: chọn lại chương, giọng kể, chất lượng, "tôi" (soát UX a5 01-10, #4) - trình tạo điền sẵn mọi lựa chọn cũ. */}
        {book.phase === "idle" && !live && !book.queuePosition && (
          <MenuItem icon={SlidersHorizontal} onSelect={() => navigate(`/studio/new?redo=${book.id}`)}>{S.s_sua_thiet_lap_96fa3435}</MenuItem>
        )}
        {book.chapters.completed > 0 && <MenuItem icon={FolderDown} onSelect={() => setExporting(true)}>{S.s_xuat_b2ebc56b}</MenuItem>}
        {next > 0 && <MenuItem icon={BookPlus} onSelect={() => navigate(`/studio/new?continue=${book.id}`)}>{S.s_them_3f5e8c43}{next}{S.s_chuong_9e6a01dc}</MenuItem>}
        {/* Mở thư mục chỉ có trên máy tính. */}
        {!remote && <MenuItem icon={FolderOpen} onSelect={() => reveal.mutate(book.id)}>{S.s_mo_thu_muc_4bf5b127}</MenuItem>}
        <MenuItem icon={Info} onSelect={() => setDetails(true)}>{S.s_chi_tiet_e762d926}</MenuItem>
      </ProjectMenu>
      <ProjectInfoDialog book={book} open={details} onOpenChange={setDetails} />
      {/* key: chuyển Phần 1 -> Phần 2 là một hộp mới - không mang `busy`, nút Huỷ, kết quả của cuốn trước sang cuốn này. */}
      <ExportDialog key={book.id} book={book} open={exporting} onOpenChange={setExporting} onApplyFirst={() => setConfirmApply(true)} />
      <MotionRegion as="div" className="basis-full text-pretty text-sm text-fg-2">
        {book.queuePosition ? (
          <p>{S.s_cho_luot_7ff91550}{book.queuePosition}{S.s_tu_chay_khi_cuon_truoc_xong_b1556944}{book.seedPending ? S.s_giu_giong_va_cach_doc_ten_993d1078 : ""}.
            {/* Cuốn đang giữ máy tạm dừng thì hàng không tự đi: nói vì sao chờ và làm gì (soát a88 T5). */}
            {book.queueWaitsOn && <> {queueWaitNotice(book.queueWaitsOn)}</>}
          </p>
        ) : live && book.stopping ? (
          <p>{S.s_dung_o_checkpoint_ke_giu_phan_da_xong_co_t_37dd2329}</p>
        ) : kind === "reanalyze" ? (
          <p data-motion-live>{S.s_phan_tich_da_dung_giua_chung_6971e0d3}{book.segments.total ? S.s_con_0_1_cau_3ea208e0(formatNumber(pending), formatNumber(book.segments.total)) : ""}{S.s_phan_tich_lai_de_giu_ket_qua_lien_mach_tie_bdf01f74}{ANALYSIS_CUT_COST}.
          </p>
        ) : redoWaiting > 0 && kind === "continue" ? (
          <p>
            {redoWaiting === 1 ? S.s_1_chuong_dang_cho_thu_lai_b9da1ca4 : S.s_0_chuong_dang_cho_thu_lai_c577313b(redoWaiting)}{S.s_theo_sua_cua_ban_ban_cu_van_nghe_duoc_cho_6adf5ab2}</p>
        ) : null}
        {studio.missing && !live && (book.phase !== "done" || Boolean(book.pendingChanges) || redoWaiting > 0) && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span>{S.s_may_nay_ee46aadd}{studio.repair ? S.s_can_sua_16c9c3dd : studio.update ? S.s_can_cap_nhat_8d5ac598 : S.s_chua_cai_bd3c52e9}{S.s_studio_nen_chua_lam_tiep_duoc_phan_phan_ti_7dcb6e58}</span>
            {!remote && (
              <Button variant="ghost" size="sm" icon={Download} onClick={() => navigate("/studio")}>
                {studio.action}
              </Button>
            )}
          </p>
        )}
        {live && book.paused === "battery" && (
          <div>
            <p>{S.s_studio_tam_dung_cam_sac_de_tiep_tuc_5704e36a}</p>
            <MoreInfo label={S.s_dung_pin_d9d66b55}>{S.s_lam_sach_tren_pin_cham_va_hao_pin_bam_tiep_c6ccaf1c}{remote ? "." : S.s_hoac_doi_o_cai_dat_studio_2fab1ca2}</MoreInfo>
          </div>
        )}
      </MotionRegion>
      <StopDialog book={book} open={confirmStop} onOpenChange={setConfirmStop} />
      <ResumeAnalysisDialog
        book={book}
        open={confirmResume}
        onOpenChange={setConfirmResume}
        onRedo={() => navigate(`/studio/new?redo=${book.id}`)}
        onResume={() => begin(book.id)}
      />
      <ApplyChangesDialog
        bookId={book.id}
        count={book.pendingChanges ?? 0}
        open={confirmApply}
        onOpenChange={setConfirmApply}
        onApply={() => begin(book.id)}
        running={live ? (book.paused && book.status === "paused" ? "checkpoint" : "busy") : undefined}
      />
    </MotionRegion>
  );
}

/** Truyện dài làm nhiều đợt: "Phần 2/3 · Phần 1 · Phần 3" - chỉ sang các phần kia của cuốn (soát UX 29-09: phần 1 không nói
 *  đã có phần 2, phần 2 không nói nối tiếp cuốn nào). */
function PartLinks({ id }: { id: string }) {
  const parts = useParts(id).data?.parts ?? [];
  const navigate = useNavigate();
  const here = parts.find((part) => part.current);
  // Tự lấy dữ liệu nên tự mang chuyển động: dòng tới sau tiêu đề mở ra, không bật vào đẩy hàng nút và tab xuống.
  return (
    <MotionPresence open={parts.length >= 2 && Boolean(here)}>
    {here && <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-fg-2">
      <span className="font-medium text-fg">{S.s_phan_a17569d5}{here.part}/{parts.length}
      </span>
      {parts
        .filter((part) => !part.current)
        .map((part) => (
          <button
            key={part.id}
            type="button"
            onClick={() => navigate(`/studio/${part.id}`)}
            className="font-medium text-accent-text underline-offset-2 hover:underline"
          >
            {part.part < here.part ? "← " : ""}{S.s_phan_a17569d5}{part.part}
            {part.part > here.part ? " →" : ""}
          </button>
        ))}
    </p>}
    </MotionPresence>
  );
}

// ---- Chương ------------------------------------------------------------------------------------------------

/** Dấu nhỏ trên một hàng chương, hay null. Xong (và chờ tới lượt) là mặc định: 30 viên "Đã xong" xếp cột là nhiễu che mất chương thật sự cần để ý, nên
 *  chỉ chương LỆCH khỏi mặc định mới có dấu - mất file audio, lỗi, cần xem lại, chờ thu lại theo sửa của bạn (soát 25-10). Chương đang thu có thanh riêng. */
export function chapterMark(chapter: Pick<Chapter, "status" | "statusLabel" | "redo">): { label: string; tone: "warning" | "danger" | "muted" } | null {
  if (chapter.statusLabel === S.s_mat_file_audio_b2b0802b) return { label: chapter.statusLabel, tone: "warning" }; // soát UX a6 01-10: cùng màu cam với đầu trang
  if (chapter.status === "completed" && !chapter.redo) return null;
  if (chapter.status === "pending" || chapter.status === "analyzed" || chapter.status === "synthesizing" || chapter.status === "verifying") return null;
  return { label: chapter.statusLabel, tone: chapter.status === "failed" ? "danger" : chapter.status === "warning" ? "warning" : "muted" };
}

// Menu "…" của một chương (soát UX a5/a6 01-10: trên bảng chương chỉ nghe được - muốn đọc kịch bản chương ấy, hay thu lại
// cả chương nghe không ổn, phải đi vòng qua tab khác và bấm từng câu).
function ChapterMenu({ book, chapter, onPlay }: { book: BookSummary; chapter: Chapter; onPlay: () => void }) {
  const [, setParams] = useSearchParams();
  const client = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const recorded = chapter.segments.finished;
  const retake = useMutation({
    mutationFn: () => api<{ lines: number }>(`/api/books/${book.id}/chapters/${chapter.id}/retake`, { method: "POST" }),
    onSuccess: ({ lines }) => {
      toast.success(S.s_da_ghi_thu_lai_0_cau_cua_1_4380d2b8(lines, chapter.displayTitle));
      void client.invalidateQueries({ queryKey: ["book", book.id] });
      void client.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (error: Error) => toast.error(S.s_chua_ghi_duoc_9fa87a7d, { description: error.message }),
  });
  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={S.s_tuy_chon_0_1f5bbd67(chapter.displayTitle)}
            className="touch-box inline-flex size-8 shrink-0 items-center justify-center rounded-control text-fg-2 opacity-0 transition-[opacity,color,background-color] duration-motion-fast transition-colors hover:bg-panel hover:text-fg focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:bg-panel data-[state=open]:opacity-100 max-md:opacity-100"
          >
            <MoreHorizontal className="glyph ink-end" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-56 rounded-cover border border-line bg-panel p-1.5 shadow-float">
            {chapter.playable && (
              <DropdownMenu.Item onSelect={onPlay} className={MENU_ITEM}>
                <Play className="size-4" />{S.s_nghe_chuong_a61f17fb}</DropdownMenu.Item>
            )}
            <DropdownMenu.Item
              onSelect={() => setParams({ tab: "script", chapter: String(chapter.id) })}
              className={MENU_ITEM}
            >
              <BookOpenText className="size-4" />{S.s_kich_ban_chuong_nay_ea890099}</DropdownMenu.Item>
            {recorded > 0 && (
              <>
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
                <DropdownMenu.Item onSelect={() => setConfirm(true)} className={MENU_ITEM}>
                  <RefreshCw className="size-4" />{S.s_thu_lai_ca_chuong_d415ce8c}</DropdownMenu.Item>
              </>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setConfirm(false)}>{S.s_thoi_e68f9e88}</Button>
          <Button
            variant="primary"
            icon={RefreshCw}
            loading={retake.isPending}
            onClick={() => {
              setConfirm(false);
              retake.mutate();
            }}
          >{S.s_thu_lai_bceb80c2}{recorded}{S.s_cau_b07e1008}</Button>
        </DialogActions>}
        open={confirm}
        onOpenChange={setConfirm}
        title={S.s_thu_lai_ca_0_8a3b8fe9(chapter.displayTitle)}
        description={S.s_thu_lai_0_cau_giong_giu_nguyen_cach_noi_do_3e72c667(recorded)}
      >
        <Button variant="ghost" onClick={() => { setConfirm(false); setParams({ tab: "script", chapter: String(chapter.id) }); }}>{S.s_sua_chu_53abcaeb}</Button>
        <MoreInfo label={S.s_thu_lai_chuong_c286c5e4}>{S.s_dung_hat_giong_moi_cho_ca_chuong_sai_nguoi_a37ff623}</MoreInfo>

      </Dialog>
    </>
  );
}

function ChapterRow({ book, chapter, rowIndex }: { book: BookSummary; chapter: Chapter; rowIndex?: number }) {
  const player = usePlayer();
  const hasStudio = Boolean(useAppInfo().data?.studio);
  const playChapter = usePlayChapter();
  const current = player.track?.bookId === book.id && player.track.chapterId === chapter.id;
  const working = chapter.status === "synthesizing" || chapter.status === "verifying";
  const mark = chapterMark(chapter);
  const recorded = chapter.segments.total ? chapter.segments.finished / chapter.segments.total : 0;
  const onPlay = () => {
    if (!chapter.playable) return;
    if (current) player.toggle();
    else void playChapter(book.id, chapter.id);
  };
  return (
    <MotionRegion as="div"
      role="row"
      aria-rowindex={rowIndex}
      onDoubleClick={onPlay}
      className={cn(
        "group grid h-14 grid-cols-[40px_minmax(0,1fr)_auto_32px] lg:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px_32px] items-baseline gap-3 rounded-control px-2 text-sm",
        current ? "text-accent-text" : "hover:bg-hover",
      )}
    >
      <div role="cell" className="flex">
        {chapter.playable ? (
          <button
            type="button"
            onClick={onPlay}
            aria-label={current && player.playing ? S.s_tam_dung_0_43ccbbf2(chapter.displayTitle) : S.s_nghe_0_42d1e966(chapter.displayTitle)}
            className="touch-hit relative -ml-[9px] grid h-8 min-w-8 items-center justify-items-start rounded-full px-[9px] text-fg-2 hover:bg-panel hover:text-fg"
          >
            {/* Mực của Play / Pause bắt đầu 3,5 px trong ô 14 px: đặt ở 5,5 px để mực đứng đúng chỗ chữ số (đệm 9 px). */}
            {current && player.playing ? (
              <>
                <Vu className="h-3 text-accent transition-opacity duration-motion-fast group-hover:opacity-0" />
                <Pause className="absolute left-[5.5px] top-1/2 size-4 -translate-y-1/2 opacity-0 transition-opacity duration-motion-fast group-hover:opacity-100" fill="currentColor" strokeWidth={0} />
              </>
            ) : (
              <>
                <span className="tabular w-[var(--chapter-number)] text-left text-xs text-fg-3 transition-opacity duration-motion-fast group-hover:opacity-0">{chapter.index}</span>
                <Play className="absolute left-[5.5px] top-1/2 size-4 -translate-y-1/2 opacity-0 transition-opacity duration-motion-fast group-hover:opacity-100" fill="currentColor" strokeWidth={0} />
              </>
            )}
          </button>
        ) : (
          <span className="tabular w-[var(--chapter-number)] text-xs text-fg-3">{chapter.index}</span>
        )}
      </div>
      <div role="cell" className="min-w-0">
        <div className={cn("truncate font-medium", current && "text-accent-text")}>{chapter.displayTitle}</div>
        {chapter.lastError ? (
          <ChapterError raw={chapter.lastError} studio={hasStudio} />
        ) : chapter.subtitle ? (
          <div className="truncate text-xs text-fg-2">{chapter.subtitle}</div>
        ) : null}
      </div>
      <div role="cell">
        {working ? (
          <div className="flex items-baseline gap-2" title={book.running ? S.s_dang_thu_am_96160328 : S.s_tam_dung_giua_chuong_f426a7e2}>
            <Progress className="self-center" value={recorded} running={book.running} tone={book.running ? "accent" : "muted"} size="xs" label={S.s_da_thu_am_1a6a3e8a} />
            <span className="tabular text-xs text-fg-2">
              {book.running ? "" : S.s_dung_o_f47312a8}
              <TickingValue>{chapter.segments.finished}/{chapter.segments.total}</TickingValue>
            </span>
          </div>
        ) : mark ? (
          <StatusPill label={mark.label} tone={mark.tone} />
        ) : (
          <span className="sr-only">{chapter.statusLabel}</span>
        )}
      </div>
      <div role="cell" className="tabular hidden text-right text-xs text-fg-2 lg:block">
        {chapter.status === "completed" || chapter.redo ? formatLength(chapter.seconds) : chapter.segments.total ? S.s_0_cau_2a1e6590(formatNumber(chapter.segments.total)) : ""}
      </div>
      <div data-motion-live role="cell" className="tabular hidden whitespace-nowrap text-right text-xs text-fg-3 lg:block">
        {chapter.completedAt ? formatRelative(chapter.completedAt) : ""}
      </div>
      <div role="cell" className="flex justify-end [&>button]:-mr-[5px]">
        <ChapterMenu book={book} chapter={chapter} onPlay={onPlay} />
      </div>
    </MotionRegion>
  );
}

export function ChapterList({ book, chapters }: { book: BookSummary; chapters: Chapter[] }) {
  // Bấm một chương (sang tab Kịch bản) rồi Back: về đúng chỗ đang xem, không về đầu danh sách (soát a30 L3).
  const table = useRef<HTMLDivElement>(null);
  useScrollMemory(`project.${book.id}`, table);
  // Chương thêm / bớt (nhập thêm chữ, gộp chương): hàng mở ra / khép lại tại chỗ (useListPresence), không nhảy cả bảng.
  const rows = useListPresence(chapters, (chapter) => String(chapter.id));
  const positions = useMemo(() => new Map(chapters.map((chapter, index) => [chapter.id, index])), [chapters]);
  return (
    // Bảng ARIA đủ phần (soát a31 A4): hàng tiêu đề là columnheader, mỗi ô của hàng chương là cell - trình đọc màn hình đọc "Trạng thái:
    // Đang thu âm" khi đi theo cột, thay vì chuỗi chữ rời. Hàng tiêu đề là hàng 1, nên hàng chương đánh số từ 2.
    // Phẳng ngay dưới tab "Chương" - không gấp trong một khung "Danh sách chương" lặp lại tên tab (như trang sách, soát 24-10).
    // Lề âm bù đệm của dòng; số chương căn trái trong ô rộng đúng số chữ số của chương cuối (nút phát lùi 9 px), "…" bù nửa nền thừa: cột
    // đầu và cột cuối thẳng mép nội dung như tab phía trên (soát 24-10). Căn giữa thì "10" lấn 3,5 px ra ngoài mép mà "1" thì không (25-10).
    <div data-list-edges="studio-chapters" className="mt-2">
    <div ref={table} role="table" className="-mx-2" aria-label={S.s_danh_sach_chuong_7fa755f9} aria-rowcount={chapters.length + 1}
      style={{ "--chapter-number": `${String(chapters.length).length}ch` } as CSSProperties}>
      <div
        role="row"
        aria-rowindex={1}
        className="grid h-9 grid-cols-[40px_minmax(0,1fr)_auto_32px] lg:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px_32px] items-center gap-3 border-b border-line mx-2 label-section text-fg-2"
      >
        <span role="columnheader">
          <span aria-hidden>#</span>
          <span className="sr-only">{S.s_so_chuong_6e52dccd}</span>
        </span>
        <span role="columnheader">{S.s_chuong_2d157977}</span>
        <span role="columnheader">{S.s_trang_thai_cb31de81}</span>
        {/* Màn hẹp (điện thoại, Studio từ xa) chỉ còn #, chương, trạng thái - soát UX 29-09: 5 cột cố định vỡ ở 375px. */}
        <span role="columnheader" className="hidden text-right lg:block" title={S.s_so_phut_khi_chuong_da_co_audio_chua_co_thi_e936f4b1}>{S.s_do_dai_5e055f59}</span>
        <span role="columnheader" className="hidden text-right lg:block">{S.s_xong_luc_e527f5af}</span>
        <span role="columnheader">
          <span className="sr-only">{S.s_them_dd92626f}</span>
        </span>
      </div>
      {/* Dự án vài nghìn chương: chỉ dựng các dòng gần màn hình (shared/Windowed). */}
      <div role="rowgroup" className="mt-1">
        <Windowed
          items={rows}
          estimate={50}
          memory={`project.${book.id}`}
          className="rows-inset [--rows-inset:calc(var(--spacing)*2)]"
          row={({ key, item: chapter, state, ref }) => (
            <div key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}>
              <ChapterRow book={book} chapter={chapter} rowIndex={(positions.get(chapter.id) ?? 0) + 2} />
            </div>
          )}
        />
      </div>
    </div>
    </div>
  );
}

// ---- Nhật ký ---------------------------------------------------------------------------------------------------

const LEVEL_DOT: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-danger",
  info: "bg-fg-3",
};

function ActivityView({ book }: { book: BookSummary }) {
  const scrollFade = useFadeScroller<HTMLDivElement>();
  const [mode, setMode] = useState<"story" | "technical">("story");
  const { data, isLoading } = useActivity(book.id, mode === "technical", book.running);
  const groups = useMemo(() => {
    const result: { day: string; items: NonNullable<typeof data> }[] = [];
    for (const item of data ?? []) {
      const day = formatDate(item.at);
      const last = result[result.length - 1];
      if (last && last.day === day) last.items.push(item);
      else result.push({ day, items: [item] });
    }
    return result;
  }, [data]);
  return (
    <MotionRegion as="div" className="mt-5">
      {/* MỘT danh sách: diễn biến là mặc định, chi tiết kỹ thuật là phần mở thêm của chính nó - không tab lồng trong tab (DESIGN 6). */}
      <div className="flex items-center justify-between gap-3">
        <MotionRegion as="span" className="text-xs text-fg-2">{data ? S.s_0_muc_gan_nhat_fd2e30e0(data.length) : ""}</MotionRegion>
        <button
          type="button"
          aria-pressed={mode === "technical"}
          onClick={() => setMode(mode === "technical" ? "story" : "technical")}
          className="touch-row -mr-2 inline-flex items-center rounded-control px-2 text-xs font-medium text-accent-text hover:underline"
        >
          {mode === "technical" ? S.s_an_chi_tiet_5df2cd32 : S.s_chi_tiet_ky_thuat_f27eb5f6}
        </button>
      </div>
      <MotionRegion motionKey={[mode, isLoading, groups.length > 0]} slideIndex={mode === "story" ? 0 : 1}>
      {isLoading ? (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-5 w-2/3" />
          ))}
        </div>
      ) : !groups.length ? (
        <EmptyState icon={BookOpenText} title={S.s_chua_co_gi_adba6b1d} className="mt-4">{S.s_dien_bien_se_hien_o_day_khi_sach_bat_dau_c_7794dda1}</EmptyState>
      ) : mode === "technical" ? (
        <div ref={scrollFade.ref} style={scrollFade.style} className="mt-4 max-h-[560px] overflow-auto py-3 font-mono text-[0.75rem] leading-relaxed">
          <LogRows items={data ?? []}>
            {(item) => (
              <div className="flex gap-3 whitespace-pre-wrap break-words">
                <span className="shrink-0 text-fg-3">{formatTime(item.at)}</span>
                <span className={cn("shrink-0", item.level === "error" ? "text-danger" : item.level === "warning" ? "text-warning" : "text-fg-3")}>
                  {item.code}
                </span>
                <span className="text-fg-2">{item.text}</span>
              </div>
            )}
          </LogRows>
        </div>
      ) : (
        <div className="mt-4 space-y-6">
          {groups.map((group) => (
            <section key={group.day}>
              <h2 className="label-section mb-2 text-fg-2">{group.day}</h2>
              {/* Hàng lùi sang trái 8 đơn vị (rồi đệm lại) để chấm nằm TRONG hộp hàng: hàng mới mở ra (cắt chiều cao) không cắt mất chấm. */}
              <LogRows as="ol" items={group.items} className="relative space-y-1 border-l border-line pl-5" rowClassName="-ml-8">
                {(item) => (
                  <div className="relative py-1.5 pl-8 text-sm">
                    {/* Chấm đứng đúng TRÊN vạch: tâm chấm = tâm vạch (mép trái ol + 0,5 px): nội dung bắt đầu sau vạch 1 px + lề pl-5 (5 đơn vị), nửa chấm = 1 đơn vị, nên lùi 6 đơn vị + 0,5 px tính từ chữ - tức 2 đơn vị - 0,5 px từ mép hộp hàng (đã lùi 8); tâm dọc = tâm dòng chữ đầu (top-3.5). */}
                    <span className={cn("absolute left-[calc(var(--spacing)*2-0.5px)] top-3.5 size-2 rounded-full ring-4 ring-bg", LEVEL_DOT[item.level] ?? "bg-fg-3")} />
                    <span className="tabular mr-3 text-xs text-fg-3">{formatTime(item.at).split(" · ")[0]}</span>
                    <span className={cn(item.level === "warning" && "text-fg", item.level === "info" && "text-fg-2")}>{item.text}</span>
                  </div>
                )}
              </LogRows>
            </section>
          ))}
        </div>
      )}
      </MotionRegion>
    </MotionRegion>
  );
}

/** Mục nhật ký mới (sách đang chạy, hỏi lại theo nhịp) mở ra tại chỗ thay vì bật vào đẩy cả bảng; vùng ngoài khoá theo kiểu / pha. */
function LogRows<T extends { id: string | number }>({ items, children, className, rowClassName, as: List = "div" }: { items: readonly T[]; children: (item: T) => ReactNode; className?: string; rowClassName?: string; as?: "div" | "ol" }) {
  const rows = useListPresence(items, (item) => String(item.id));
  const Row = List === "ol" ? "li" : "div";
  return <List className={className}>{rows.map(({ key, item, state, ref }) => <Row key={key} ref={ref} className={cn("motion-row", rowClassName)} data-state={state} inert={state === "exit"}><div>{children(item)}</div></Row>)}</List>;
}

// ---- Trang -----------------------------------------------------------------------------------------------------------

const TAB_LABEL: Record<string, string> = {
  chapters: S.s_chuong_2d157977,
  precast: S.s_duyet_truoc_khi_thu_74c121d0,
  work: S.s_viec_can_duyet_5c0c3ce1,
  script: S.s_kich_ban_602e5f27,
  review: S.s_can_nghe_lai_d651f6ab,
  cast: S.s_nhan_vat_d4940c17,
  music: S.s_nhac_nen_271fb292,
  activity: S.s_nhat_ky_1e6c3c10,
};

/** Tab nằm trong "Thêm" không có nút tab riêng (aria-labelledby của Radix trỏ vào id không có): bảng tự mang tên. */
function moreTabName(key: string) {
  return { "aria-label": TAB_LABEL[key], "aria-labelledby": undefined };
}

/** Năm tab hiện thẳng, theo tần suất: Chương (nghe kiểm, thu lại), Việc cần duyệt và Cần nghe lại (hai hộp việc dây chuyền chờ bạn),
 *  Nhân vật (đổi giọng - việc hay làm nhất sau phân vai), Nhạc nền. Còn lại vào "Thêm" (DESIGN.md mục 4.3, 7). */
export const MAIN_TABS = ["chapters", "work", "review", "cast", "music"] as const;

/** Hàng tab của dự án. "Duyệt trước khi thu" chỉ có trong một khoảng ngắn (sau phân tích, trước khi thu) và đã có dải mời ở đầu
 *  trang; Kịch bản thường mở từ một thẻ / chương ("Kịch bản chương này"); Nhật ký hiếm khi cần. Tab đang chọn nằm trong "Thêm" thì
 *  nút "Thêm" mang tên tab ấy và gạch chân như tab thường. */
export function ProjectTabBar({ tab, onTab, precast, counts }: {
  tab: string;
  onTab: (tab: string) => void;
  precast: boolean;
  counts: Partial<Record<string, number>>;
}) {
  const more = [...(precast ? ["precast"] : []), "script", "activity"];
  const inMore = more.includes(tab);
  // Số cạnh "Thêm": cộng các tab bên trong (số của "Duyệt trước khi thu" không mất khi nó nằm trong "Thêm"); nút đang mang tên một tab
  // thì chỉ số của tab ấy - "Kịch bản 4" mà 4 là việc ở tab khác thì đọc sai.
  const moreCount = (inMore ? counts[tab] : more.reduce((sum, key) => sum + (counts[key] ?? 0), 0)) || undefined;
  return (
    <TabsList label={S.s_muc_cua_du_an_37a54f69}>
      {MAIN_TABS.map((key) => (
        <TabsTrigger key={key} value={key} count={counts[key]}>
          {TAB_LABEL[key]}
        </TabsTrigger>
      ))}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          {/* Nằm trong hàng tab (tablist chỉ được chứa tab): nút cũng là một tab - "đang chọn" khi tab đang mở nằm trong "Thêm". */}
          <button
            type="button"
            role="tab"
            aria-selected={inMore}
            data-active={inMore || undefined}
            className="touch-row relative -mb-px inline-flex h-11 shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent text-sm font-medium text-fg-2 transition-colors hover:text-fg data-[active]:border-accent data-[active]:text-fg data-[state=open]:text-fg"
          >
            <TabLabel count={moreCount}>
              <MotionRegion as="span" motionKey={inMore ? tab : "more"}>{inMore ? TAB_LABEL[tab] : S.s_them_dd92626f}</MotionRegion>
            </TabLabel>
            <ChevronDown className="fold-chevron size-3.5 text-fg-3" aria-hidden />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content collisionPadding={12} align="start" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] min-w-52 overflow-y-auto overscroll-contain rounded-cover border border-line bg-panel p-1.5 shadow-float">
            {more.map((key) => (
              <DropdownMenu.Item key={key} onSelect={() => onTab(key)} className={MENU_ITEM}>
                <span className="grid size-4 place-items-center" aria-hidden>{key === tab && <Check className="size-4 text-accent-text" />}</span>
                {TAB_LABEL[key]}
                {counts[key] ? <span className="tabular ml-auto pl-3 text-xs text-fg-2">{counts[key]}</span> : null}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </TabsList>
  );
}

/** Tab mở lối nhảy sang tab khác ("Đọc cả N câu trong Kịch bản") - nhãn nút "Về …" ở tab đích. */
const FROM_LABEL: Record<string, string> = { work: S.s_viec_can_duyet_5c0c3ce1, review: S.s_can_nghe_lai_d651f6ab, precast: S.s_duyet_truoc_khi_thu_74c121d0 };

export function ProjectScreen() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = ["chapters", "precast", "work", "script", "review", "cast", "music", "activity"].includes(params.get("tab") ?? "") ? params.get("tab")! : "chapters";
  const reviewCount = useReviewCount(id ?? "");
  const { data, isLoading, error, refetch, isFetching } = useBook(id);
  const failure = bookFailure(data, error);
  // Thẻ đã nằm ở "Duyệt trước khi thu" thì "Việc cần duyệt" không hiện lại và không đếm lại.
  const precastOn = Boolean(data && canReview(data.book));
  const precastKeys = usePrecastKeys(id ?? "", precastOn);
  // Danh sách đầy đủ chỉ tải khi có chỗ cần nó (tab Việc cần duyệt, màn Duyệt trước khi thu); còn lại chỉ hỏi con số cho nhãn tab.
  // Tab Kịch bản mở trước: số việc (cả cuốn phải soát lại, dự án 50.000 câu ~1,3 s) chờ mục lục về rồi mới hỏi, không tranh nhau.
  const scriptListed = useCastingContents(id ?? "", false).isFetched;
  const scriptFirst = tab === "script" && !failure && !scriptListed;
  // Việc từ điện thoại chờ duyệt (webui/edits_inbox.py) cộng vào số của tab; Studio từ xa duyệt được như chủ máy (remote_studio.ALLOWED).
  const workCount = Math.max(0, useWorkCount(id ?? "", precastOn || tab === "work" || tab === "precast", !scriptFirst) - (precastKeys?.size ?? 0)) + useInboxCount(id ?? "");
  const [picking, setPicking] = useState<{ name: string; displayName: string } | null>(null);
  const [merging, setMerging] = useState<CastMember | null>(null);
  const unmerge = useUnmerge(id ?? "");
  const [renaming, setRenaming] = useState<CastMember | null>(null);
  const [gendering, setGendering] = useState<CastMember | null>(null);
  const { data: cast } = useCast(id);
  const sideError = useSideError(id ?? "");
  usePageTitle(data ? `${data.book.title} · Studio` : undefined);
  const location = useLocation();
  // Đổi tab tại chỗ thay địa chỉ (không chất lịch sử), nhưng NHẢY từ một thẻ/câu sang tab khác là một bước điều hướng:
  // Back và nút "Về …" trở lại đúng thẻ vừa rời - thẻ và bộ lọc nằm trong địa chỉ (soát UX 30-09: Back sau "Đọc cả N
  // câu trong Kịch bản" về thẳng danh sách Dự án, mất cả bộ lọc lẫn chỗ đang duyệt).
  const jump = (next: Record<string, string>, from: string, card?: string) => {
    if (card) {
      setParams(
        (previous) => {
          const here = new URLSearchParams(previous);
          here.set("card", card);
          return here;
        },
        { replace: true },
      );
    }
    setParams({ ...next, from });
  };
  const from = params.get("from");
  const back = () => {
    if (location.key !== "default") navigate(-1);
    else setParams({ tab: from ?? "chapters" }, { replace: true });
  };

  const placeholder = (
      <div className="page-x mx-auto max-w-[1180px]">
        {/* Cùng đầu màn với trang đã tải: nút ← bấm được ngay, bìa không nhảy khi dữ liệu về. */}
        <ScreenHeader back={{ label: S.s_ve_studio_349a48c4, onClick: () => navigate("/studio") }} />
        <div className="mt-5 flex gap-7">
          <Skeleton className="size-44 rounded-control" />
          <div className="flex-1 space-y-3 pt-4">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-4 w-1/3" />
          </div>
        </div>
      </div>
  );
  const content = () => {

  if (failure === "gone") {
    // Sách đã bị xoá hay chuyển đi (tab mở từ trước): thôi hỏi máy chủ, nói thẳng và cho đường về.
    return (
      <EmptyState
        icon={CircleAlert}
        title={S.s_du_an_nay_khong_con_94194a30}
        className="mt-20"
        action={<Button onClick={() => navigate("/studio")}>{S.s_ve_studio_349a48c4}</Button>}
      >{S.s_cuon_nay_da_bi_xoa_hoac_chuyen_di_khoi_thu_7f90453a}</EmptyState>
    );
  }
  // Chỉ khi chưa từng có bản nào của sách; đã có thì giữ trang và báo bằng dải bên dưới (bookFailure).
  if (failure === "error" || !data) {
    return (
      <EmptyState
        icon={CircleAlert}
        title={S.s_chua_mo_duoc_sach_86cc68d3}
        className="mt-20"
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Button variant="ghost" loading={isFetching} onClick={() => void refetch()}>{S.s_thu_lai_c58d068c}</Button>
            <Button onClick={() => navigate("/studio")}>{S.s_ve_studio_349a48c4}</Button>
          </div>
        }
      >
        {failureText(error)}
      </EmptyState>
    );
  }

  const { book, chapters } = data;
  const status = projectStatus(book);
  // MỘT dòng cho người nghe: trạng thái · số chương · độ dài (+ việc cần để ý). Giọng kể, chất lượng, model, ngày tạo, lần nghe cuối ở "Chi tiếtS.s_copy_3481988241fe…" -
  // dòng 12-13 mẩu từng làm đầu trang nặng, và viên trạng thái trên tiêu đề làm tiêu đề lệch 2 px giữa các trạng thái (soát 25-10).
  const meta = [
    <StatusText key="status" label={status.label} tone={status.tone} live={status.live} />,
    book.phase !== "done" && book.chapters.total ? S.s_0_1_chuong_8d58e1df(book.chapters.completed, book.chapters.total) : S.s_0_chuong_04093412(book.chapters.total),
    book.audioSeconds > 0 && formatLength(book.audioSeconds),
    book.chapters.missingAudio ? <span key="missing" className="font-medium text-warning">{book.chapters.missingAudio}{S.s_chuong_mat_file_audio_3ef5ceaf}</span> : false,
    book.chapters.redo ? S.s_0_chuong_cho_thu_lai_043b38de(book.chapters.redo) : false,
  ];

  return (
    <div className="motion-reveal page-x mx-auto max-w-[1180px] pb-16">
      {/* Nút ← chung của màn con (ScreenHeader) đứng riêng một hàng: tên dự án nằm cạnh bìa bên dưới. */}
      <ScreenHeader back={{ label: S.s_ve_studio_349a48c4, onClick: () => navigate("/studio") }} />
      {failure === "stale" && !isListenOnly(error) && (
        <div role="status" className="mt-4 flex flex-wrap items-center gap-2 py-3 text-sm">
          <CircleAlert className="size-4 shrink-0 text-warning" />
          <span className="min-w-0 flex-1 text-pretty">
            {isOffline(error) ? S.s_mat_ket_noi_toi_abook_dang_thu_lai_3ea0ae2f : S.s_chua_tai_lai_duoc_sach_0_dang_thu_lai_cf6589ed(failureText(error))}
          </span>
          <Button size="sm" variant="ghost" loading={isFetching} onClick={() => void refetch()}>{S.s_thu_lai_c58d068c}</Button>
        </div>
      )}
      {/* Màn hẹp (điện thoại): bìa nhỏ cạnh tên sách, hàng nút nằm dưới cả hai (soát UX a8 05-10: bìa to + tên + 3 hàng nút
          chiếm ~590 px, tab bắt đầu ở cuối màn). Từ sm trở lên: bìa bên trái, tên và nút bên phải. `contents` làm cột phải biến
          mất khỏi lưới ở màn hẹp để hàng nút tự chiếm cả hai cột mà vẫn chỉ có một bản của các nút. */}
      <header className="mt-5 grid grid-cols-[6rem_minmax(0,1fr)] gap-x-4 gap-y-4 sm:flex sm:gap-7">
        <CoverEditor book={book} />
        <div className="contents sm:block sm:min-w-0 sm:flex-1 sm:pt-1">
          <div className="min-w-0 sm:contents">
          <h1 data-content-title="" className={cn(SCREEN_TITLE, "leading-tight")}>{book.title}</h1>
          <DotJoin className="tabular mt-2 text-sm text-fg-2" parts={meta} />
          <PartLinks id={book.id} />
          <HeaderProgress book={book} />
          </div>
          <div className="col-span-2 sm:col-auto sm:mt-6">
            <Actions book={book} />
          </div>
        </div>
      </header>

      {book.phase !== "done" && <ProductionPanel book={book} />}
      {book.phase === "done" && <StartError book={book} />}
      {/* Phân tích xong mà chưa thu bao nhiêu: lối vào "Duyệt trước khi thu" đúng lúc sửa còn miễn phí. */}
      {canReview(book) && tab !== "precast" && (book.precast?.held || book.chapters.completed === 0) && (
        <PrecastBanner book={book} onOpen={() => setParams({ tab: "precast" })} />
      )}

      {sideError && failure !== "stale" && (
        <div role="status" className="mt-4 flex gap-2 py-3 text-sm">
          <CircleAlert className="mt-line-icon size-4 shrink-0 text-warning" />
          <span className="text-pretty">{S.s_chua_tai_duoc_d5533c6e}{sideError}{S.s_tu_thu_lai_hoac_lam_moi_trang_6d8c2223}</span>
        </div>
      )}
      <Tabs value={tab} onValueChange={(value) => setParams({ tab: value }, { replace: true })} className="mt-8">
        <ProjectTabBar
          tab={tab}
          onTab={(value) => setParams({ tab: value }, { replace: true })}
          precast={canReview(book)}
          // Cùng phép đếm với "Việc cần duyệt" (thẻ ở màn duyệt trước khi thu không đếm lại bên kia): cộng hai nhãn = số việc điện thoại báo.
          counts={{ chapters: chapters.length, precast: precastKeys?.size || undefined, work: workCount || undefined, review: reviewCount || undefined }}
        />
        <TabsPanels value={tab}>
        {from && FROM_LABEL[from] && tab !== from && (
          <button type="button" onClick={back} className="touch-hit mt-4 inline-flex items-center gap-1.5 text-sm text-fg-2 hover:text-fg">
            <ArrowLeft className="ink-start size-4" />{S.s_ve_man_truoc_3be95078}</button>
        )}
        <TabsContent value="chapters">
          <ChapterList book={book} chapters={chapters} />
        </TabsContent>
        <TabsContent value="precast" {...moreTabName("precast")}>
          {canReview(book) ? (
            <PrecastReview
              book={book}
              onPickVoice={(person) => setPicking({ name: person.name, displayName: person.displayName })}
              onMerge={setMerging}
              onUnmerge={(person) => unmerge.mutate(person)}
              onRename={setRenaming}
              onGender={setGendering}
              onOpenReview={(card) => jump({ tab: "review" }, "precast", card)}
              onOpenScript={(chapterId, stableId, pick = true, card) =>
                jump({ tab: "script", chapter: String(chapterId), line: stableId, ...(pick ? {} : { pick: "0" }) }, "precast", card)
              }
              onOpenNames={(name, card) => jump({ tab: "cast", focus: "names", ...(name ? { name } : {}) }, "precast", card)}
              onClose={() => setParams({ tab: "chapters" }, { replace: true })}
              step={params.get("step")}
              onStep={(value) =>
                setParams(
                  (previous) => {
                    const here = new URLSearchParams(previous);
                    here.set("step", value);
                    here.delete("card");
                    return here;
                  },
                  { replace: true },
                )
              }
            />
          ) : (
            <p className="mt-6 text-sm text-fg-2">{S.s_man_duyet_mo_duoc_khi_may_da_phan_tich_xon_1220ed63}</p>
          )}
        </TabsContent>
        <TabsContent value="work">
          <PhoneEdits bookId={book.id} />
          <WorkInbox
            book={book}
            kind={params.get("kind")}
            focus={params.get("card")}
            inPrecast={precastKeys}
            onOpenPrecast={() => setParams({ tab: "precast" })}
            onKind={(value) =>
              setParams(
                (previous) => {
                  const here = new URLSearchParams(previous);
                  if (value === "all") here.delete("kind");
                  else here.set("kind", value);
                  here.delete("card");
                  return here;
                },
                { replace: true },
              )
            }
            onOpenReview={(card) => jump({ tab: "review" }, "work", card)}
            onOpenScript={(chapterId, stableId, pick = true, card) =>
              jump({ tab: "script", chapter: String(chapterId), line: stableId, ...(pick ? {} : { pick: "0" }) }, "work", card)
            }
            onOpenNames={(name, card) => jump({ tab: "cast", focus: "names", ...(name ? { name } : {}) }, "work", card)}
            onPickVoice={setPicking}
          />
        </TabsContent>
        <TabsContent value="script" {...moreTabName("script")}>
          <ScriptTab bookId={book.id} />
        </TabsContent>
        <TabsContent value="review">
          <ReviewQueue
            bookId={book.id}
            onOpenScript={(chapterId, stableId) => jump({ tab: "script", chapter: String(chapterId), line: stableId }, "review")}
          />
        </TabsContent>
        <TabsContent value="cast">
          <CastList
            bookId={book.id}
            onPickVoice={(person) => setPicking({ name: person.name, displayName: person.displayName })}
            onPickNarrator={book.castLocked ? () => setPicking({ name: "NARRATOR", displayName: S.s_nguoi_ke_50063a62 }) : undefined}
            onMerge={setMerging}
            onUnmerge={(person) => unmerge.mutate(person)}
            onRename={setRenaming}
            onGender={setGendering}
            narratorNote={<><NarratorNote book={book} /><TellerModeSwitch book={book} /></>}
          />
          <NameReadings bookId={book.id} focus={params.get("focus") === "names"} name={params.get("name") ?? ""} />
        </TabsContent>
        <TabsContent value="music">
          <MusicTab bookId={book.id} chapterTitle={(id) => chapters.find((chapter) => chapter.id === id)?.fullTitle ?? S.s_chuong_0_268b0521(id)} />
        </TabsContent>
        <TabsContent value="activity" {...moreTabName("activity")}>
          <ActivityView book={book} />
        </TabsContent>
        </TabsPanels>
      </Tabs>
      {/* Hộp đổi giọng / tên / giới / gộp người: mở từ tab Nhân vật và từ màn "Duyệt trước khi thu". */}
      <RenamePersonDialog bookId={book.id} person={renaming} onClose={() => setRenaming(null)} />
      <GenderDialog bookId={book.id} person={gendering} onClose={() => setGendering(null)} />
      <MergeDialog
        bookId={book.id}
        person={merging}
        people={[...(cast?.characters ?? []), ...(cast?.extras ?? [])]}
        onClose={() => setMerging(null)}
      />
      <VoicePicker bookId={book.id} person={picking} onClose={() => setPicking(null)} />
    </div>
  );
  };
  return <LoadingCrossfade loading={isLoading} placeholder={placeholder}><MotionRegion>{content()}</MotionRegion></LoadingCrossfade>;
}
