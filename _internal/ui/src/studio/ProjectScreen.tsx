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
      <p className={cn("mt-2 text-xs leading-relaxed", state === "pending" ? "text-fg-3" : "text-fg-2")}>{detail}</p>
      {progress !== undefined && state !== "pending" && (
        <div className="mt-3 flex items-center gap-2">
          <Progress value={progress} running={state === "active"} tone={state === "done" ? "success" : state === "paused" ? "muted" : "accent"} size="sm" label={title} />
          <span className="tabular w-9 text-right text-xs font-semibold">{formatPercent(progress)}</span>
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
      <span className="min-w-0 flex-1">Không khởi động được: {book.startError}</span>
      {!book.starting && !book.running && (
        <Button variant="ghost" size="sm" icon={RotateCcw} loading={start.isPending} onClick={() => start.mutate(book.id)}>
          Thử lại
        </Button>
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
            <summary className="cursor-pointer select-none">Chi tiết</summary>
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
  const detail = [end.detail, end.exitCode ? `mã thoát ${end.exitCode}` : ""].filter(Boolean).join(" - ");
  const shown = friendlyError(detail, Boolean(info), redo, Boolean(info?.damagedSteps?.includes("llm")));
  const summary =
    end.state === "lost"
      ? "Lần chạy trước bị ngắt đột ngột (tiến trình làm sách bị tắt, máy khởi động lại hay hết điện)."
      : shown.summary === "Có lỗi khi làm sách."
        ? "Lần chạy trước dừng vì sự cố."
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
            <summary className="cursor-pointer select-none">Chi tiết</summary>
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
      <>
        Giọng kể chọn lúc tạo sách, đổi được vì cuốn này chưa bắt đầu chạy.{" "}
        <button type="button" onClick={() => navigate(`/studio/new?redo=${book.id}`)} className="font-medium text-accent-text underline underline-offset-2">
          Đổi giọng kể
        </button>
      </>
    );
  }
  if (book.castLocked) return <>Đổi giọng kể không phải tạo lại sách: câu kể đã thu sẽ được thu lại bằng giọng mới.</>;
  return <>Đổi được giọng kể khi máy phân vai xong (ngay sau bước phân tích truyện).</>;
}

/** Dòng nói còn bao lâu của cả lượt làm sách (hay vì sao đang đứng); "" khi không có gì để nói. */
function progressNote(book: BookSummary): string {
  const live = book.running || book.starting;
  // Giữ chờ duyệt (precast.held) cũng là `paused` nhưng là đợi người nghe, không phải ai bấm Tạm dừng (soát UX a23: "47% tổng"
  // đứng yên không nói vì sao). Tạm dừng thường (pin, người bấm) đã nói ở trạng thái đầu trang - không nói lại ở đây (soát 24-10 T19).
  return book.stopping ? "đang dừng" : book.paused ? (book.precast?.held ? "chờ bạn duyệt rồi bấm Thu âm" : "") : etaOf(book) ?? (live ? "đang ước tính thời gian…" : "");
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
          <Progress value={book.progress.overall} running={running} tone={running ? "accent" : "muted"} size="xs" label="Tiến độ cả sách" />
          <span className="tabular w-10 shrink-0 text-right text-sm font-medium">{formatPercent(book.progress.overall)}</span>
        </div>
        {note && <span className="text-sm text-fg-2">{note}</span>}
      </div>
    </MotionPresence>
  );
}

export function ProductionPanel({ book }: { book: BookSummary }) {
  const [analysis, casting, synthesis] = stepStates(book);
  const live = book.running || book.starting;
  // Dòng phụ "Các bước" nói bước đang tới - cả khi đang tạm dừng; lý do dừng đã ở trên.
  const current = [analysis, casting, synthesis].findIndex((state) => state === "active" || state === "paused");
  const stepSummary = current >= 0 ? ["Phân tích truyện", "Phân vai", "Thu âm và kiểm tra"][current] : book.statusLabel;
  return (
    <MotionRegion as="section" className="mt-6">
      {live && book.logLost && (
        <p role="status" className="mb-3 flex gap-2 py-2 text-sm text-warning">
          <CircleAlert className="mt-line-icon size-4 shrink-0" />
          <span>
            Sách vẫn đang chạy bình thường, nhưng nhật ký làm sách không ghi được ({book.logLost.lines} dòng đã bỏ) - thường do phần mềm diệt virus,
            đồng bộ đám mây giữ file hoặc ổ đĩa gần đầy. Kiểm lại chỗ trống ở ổ chứa thư viện.
          </span>
        </p>
      )}
      <Fold storageKey={`project.${book.id}.steps`} title="Các bước" summary={stepSummary} heading="h3">
      <div className="flex flex-col gap-6 sm:flex-row sm:gap-8">
        <Step
          index={1}
          state={analysis}
          icon={BookOpenText}
          title="Phân tích truyện"
          detail={
            book.speakerPass?.active
              ? `Xác định người nói từng câu: ${book.speakerPass.done}/${book.speakerPass.total} chương.`
              : book.settings.analyzer
                ? `Đọc cả truyện để nhận ra lời thoại, ai đang nói và cảm xúc từng câu. ${analyzerLabel(book.settings.analyzer)}.`
                : "Đọc cả truyện để nhận ra lời thoại, ai đang nói và cảm xúc từng câu."
          }
          progress={book.progress.analysis}
        />
        <Step
          index={2}
          state={casting}
          icon={Users}
          title="Phân vai"
          detail="Trao cho mỗi nhân vật một giọng riêng và khoá cách đọc tên."
        />
        <Step
          index={3}
          state={synthesis}
          icon={Mic2}
          title="Thu âm và kiểm tra"
          detail="Đọc từng câu, nghe lại bằng nhận dạng giọng nói, thu lại câu lệch."
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
    <Dialog open={open} onOpenChange={onOpenChange} title="Tiếp tục phân tích?">
      <div className="mb-5 flex gap-3 py-4 text-sm leading-relaxed text-fg">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" />
        <div className="text-pretty">
          <p>
            <span className="font-semibold">Phân tích của “{book.title}” đã dừng giữa chừng.</span> Làm tiếp từ chỗ ấy {ANALYSIS_CUT_COST} - khác
            với khi phân tích liền một mạch.
          </p>
          <p className="mt-2 text-fg-2">Muốn chắc như chạy liền mạch: làm lại phân tích từ đầu.</p>
        </div>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Để sau
        </Button>
        <Button
          variant="ghost"
          icon={Play}
          onClick={() => {
            onOpenChange(false);
            onResume();
          }}
        >
          Vẫn tiếp tục
        </Button>
        <Button
          variant="primary"
          icon={RotateCcw}
          autoFocus
          onClick={() => {
            onOpenChange(false);
            onRedo();
          }}
        >
          Phân tích lại
        </Button>
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
      title={inAnalysis ? "Dừng phân tích?" : "Dừng thu âm?"}
      description={
        // Không nêu tên nút làm tiếp: sau khi dừng nó là "Tiếp tục tạo", "Bắt đầu thu" hay "Áp dụng N thay đổi"
        // tuỳ sách đã tới đâu (soát UX 30-09). Đang tạm dừng thì nói Dừng khác Tạm dừng ở chỗ nào.
        inAnalysis
          ? undefined
          : book.paused
            ? "Tạm dừng vẫn giữ bộ nhớ card đồ hoạ. Dừng hẳn thì nhả ra; việc đã xong giữ nguyên."
            : "Mọi chương và câu đã xong được giữ nguyên - làm tiếp lúc nào cũng được, từ đúng chỗ dừng."
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
            <p className="mt-2 text-fg-2">
              Nên để chạy hết bước này{eta ? ` (${eta})` : ""}. {stopAnalysisAdvice(book)}
            </p>
          </div>
        </div>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          {book.paused ? "Để nguyên" : "Để chạy tiếp"}
        </Button>
        {inAnalysis && !book.paused && book.canPause && (
          <Button
            variant="primary"
            icon={Pause}
            loading={pause.isPending}
            onClick={() => pause.mutate({ id: book.id, paused: true }, { onSettled: () => onOpenChange(false) })}
          >
            Tạm dừng
          </Button>
        )}
        <Button
          variant="danger"
          icon={Square}
          loading={stop.isPending}
          disabled={stop.isPending}
          onClick={() => stop.mutate({ id: book.id, paused: Boolean(book.paused) }, { onSettled: () => onOpenChange(false) })}
        >
          {inAnalysis ? "Vẫn dừng" : "Dừng"}
        </Button>
      </div>
      </MotionRegion>
    </Dialog>
  );
}

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

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
      toast.success(`Đã đổi tên thành “${summary.title}”`);
      onOpenChange(false);
    },
    onError: (error: Error) => toast.error("Chưa đổi được tên", { description: error.message }),
  });
  const typed = title.trim();
  return (
    <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Huỷ
          </Button>
          <Button type="submit" form={dialogForm1} variant="primary" loading={rename.isPending} disabled={!typed || typed === book.title}>
            Đổi tên
          </Button>
        </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      title="Đổi tên sách"
      description="Tên mới hiện ở thư viện, điện thoại và file xuất."
    >
      <form id={dialogForm1}
        onSubmit={(event) => {
          event.preventDefault();
          if (typed && typed !== book.title) rename.mutate(typed);
        }}
      >
        <label htmlFor="rename-book-title" className="text-sm font-medium">
          Tên sách
        </label>
        <input
          id="rename-book-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={160}
          data-autofocus
          autoComplete="off"
          className="mt-1.5 h-10 w-full rounded-lg border border-line bg-panel px-3 text-sm text-fg outline-none focus-visible:border-focus"
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
        message: `Đã xoá dự án “${book.title}”`,
        title: book.title,
        undo: result.undo,
        onRestored: () => {
          void client.invalidateQueries({ queryKey: ["library"] });
          void client.invalidateQueries({ queryKey: ["listen"] });
        },
      });
    },
    onError: (error: Error) => toast.error("Chưa xoá được", { description: error.message }),
  });
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Để sau
        </Button>
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
        >
          Chuyển vào Thùng rác
        </Button>
      </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      title={`Xoá dự án “${book.title}”?`}
      description="Cả thư mục dự án vào Thùng rác của Windows, khôi phục được. File truyện gốc và sách đã xuất giữ nguyên."
    >
      <MotionRegion>
      {/* Studio từ xa không nhận đường dẫn trên máy tính (soát a27 lỗi 10). */}
      {book.path && <p className="break-all py-2 text-xs text-fg-2">{book.path}</p>}
      {busy && <p className="mt-3 text-sm text-warning">Sách đang chạy - dừng sách trước rồi mới xoá được.</p>}

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
            aria-label={`Tuỳ chọn dự án ${book.title}`}
            className={cn(
              "touch-box inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-fg-2 transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover",
              className,
            )}
          >
            <MoreHorizontal className="glyph ink-end" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-52 rounded-xl border border-line bg-panel p-1.5 shadow-float">
            {children && (
              <>
                {children}
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
              </>
            )}
            {rename && <MenuItem icon={TextCursorInput} onSelect={() => setDialog("rename")}>Đổi tên…</MenuItem>}
            {/* Truyện dài làm nhiều đợt: phần mới giữ giọng, cách đọc tên, ghim của phần này (continuation.py). Dự án chưa
                phân tích câu nào thì không có gì để mang theo - mờ kèm lý do thay vì dẫn tới một phần mới trống (soát UX 29-09). */}
            {/* Dự án hỏng (`broken`) không có `segments` và không có gì để mang theo: chỉ còn xoá. */}
            {!book.broken && (
              <DropdownMenu.Item
                disabled={!analyzed}
                onSelect={() => navigate(`/studio/new?continue=${book.id}`)}
                className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
              >
                <BookPlus className="size-4" /> Làm tiếp cuốn này…
                {!analyzed && <span className="ml-auto pl-3 text-xs text-fg-3">chạy phần này trước</span>}
              </DropdownMenu.Item>
            )}
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
            {remote ? (
              <div className="px-2 py-1.5">
                <OnComputerOnly verb="Xoá dự án" />
              </div>
            ) : (
              <MenuItem icon={Trash2} danger onSelect={() => setDialog("delete")}>Xoá dự án…</MenuItem>
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
    toast.error(studio.repair ? "Cần sửa Studio" : studio.update ? "Cần cập nhật Studio" : "Cần cài Studio", {
      description: "Phân tích và thu âm chạy bằng Studio.",
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
    starting: { label: "Đang khởi động", loading: true },
    // Đã bấm Dừng: sách còn chạy tới chỗ dừng sạch kế - tạm dừng / dừng thêm lần nữa không còn nghĩa (soát a88 V1).
    stopping: { label: "Đang dừng…", loading: true },
    // Giữ chờ duyệt: "Tiếp tục" và "Thu âm" là MỘT việc - tên là "Thu âm" (soát UX a8 05-10, mục 12).
    unpause: { label: book.precast?.held ? "Thu âm" : "Tiếp tục", icon: book.precast?.held ? Mic2 : Play, loading: pause.isPending, run: unpause },
    // Tạm dừng giữ tiến trình sống, làm tiếp đúng chỗ - an toàn cả giữa lúc phân tích; "Dừng" (kết thúc lượt chạy) ở "…".
    pause: { label: "Tạm dừng", icon: Pause, loading: pause.isPending, run: () => pause.mutate({ id: book.id, paused: true }) },
    start: { label: "Bắt đầu", icon: Wand2, loading: start.isPending, run: () => begin(book.id) },
    record: { label: "Thu âm", icon: Mic2, loading: start.isPending, run: () => begin(book.id) },
    reanalyze: { label: "Phân tích lại", icon: RotateCcw, run: () => navigate(`/studio/new?redo=${book.id}`) },
    continue: { label: "Tiếp tục", icon: Play, loading: start.isPending, run: () => begin(book.id) },
    apply: { label: `Áp dụng ${book.pendingChanges ?? 0} thay đổi`, icon: RefreshCw, loading: start.isPending, run: () => setConfirmApply(true) },
    listen: { label: "Nghe trong Thư viện", icon: Headphones, run: () => navigate(`/book/${book.id}`) },
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
          <MenuItem icon={Headphones} onSelect={() => navigate(`/book/${book.id}`)}>Nghe trong Thư viện</MenuItem>
        )}
        {asksBeforeResume(book) && !live && !book.starting && !book.queuePosition && (
          <MenuItem icon={Play} onSelect={() => setConfirmResume(true)}>Vẫn tiếp tục…</MenuItem>
        )}
        {live && !book.stopping && <MenuItem icon={Square} onSelect={() => setConfirmStop(true)}>Dừng…</MenuItem>}
        {/* Thay đổi chờ áp khi máy đang chạy: xem được, và bỏ được khi đã tạm dừng tới checkpoint (soát a83 B5). */}
        {live && book.pendingChanges ? (
          <MenuItem icon={RefreshCw} onSelect={() => setConfirmApply(true)}>{book.pendingChanges} thay đổi chờ áp</MenuItem>
        ) : null}
        {book.queuePosition ? <MenuItem icon={Square} onSelect={() => leaveQueue.mutate({ id: book.id })}>Bỏ xếp hàng</MenuItem> : null}
        {/* Chưa chạy bước nào: chọn lại chương, giọng kể, chất lượng, "tôi" (soát UX a5 01-10, #4) - trình tạo điền sẵn mọi lựa chọn cũ. */}
        {book.phase === "idle" && !live && !book.queuePosition && (
          <MenuItem icon={SlidersHorizontal} onSelect={() => navigate(`/studio/new?redo=${book.id}`)}>Sửa thiết lập</MenuItem>
        )}
        {book.chapters.completed > 0 && <MenuItem icon={FolderDown} onSelect={() => setExporting(true)}>Xuất…</MenuItem>}
        {next > 0 && <MenuItem icon={BookPlus} onSelect={() => navigate(`/studio/new?continue=${book.id}`)}>Thêm {next} chương</MenuItem>}
        {/* Mở thư mục chỉ có trên máy tính. */}
        {!remote && <MenuItem icon={FolderOpen} onSelect={() => reveal.mutate(book.id)}>Mở thư mục</MenuItem>}
        <MenuItem icon={Info} onSelect={() => setDetails(true)}>Chi tiết</MenuItem>
      </ProjectMenu>
      <ProjectInfoDialog book={book} open={details} onOpenChange={setDetails} />
      {/* key: chuyển Phần 1 -> Phần 2 là một hộp mới - không mang `busy`, nút Huỷ, kết quả của cuốn trước sang cuốn này. */}
      <ExportDialog key={book.id} book={book} open={exporting} onOpenChange={setExporting} onApplyFirst={() => setConfirmApply(true)} />
      <MotionRegion as="div" className="basis-full text-pretty text-sm text-fg-2">
        {book.queuePosition ? (
          <p>
            Chờ lượt {book.queuePosition}, tự chạy khi cuốn trước xong{book.seedPending ? ", giữ giọng và cách đọc tên" : ""}.
            {/* Cuốn đang giữ máy tạm dừng thì hàng không tự đi: nói vì sao chờ và làm gì (soát a88 T5). */}
            {book.queueWaitsOn && <> {queueWaitNotice(book.queueWaitsOn)}</>}
          </p>
        ) : live && book.stopping ? (
          <p>Dừng ở checkpoint kế, giữ phần đã xong; có thể mất vài phút.</p>
        ) : kind === "reanalyze" ? (
          <p>
            Phân tích đã dừng giữa chừng
            {book.segments.total ? ` (còn ${formatNumber(pending)}/${formatNumber(book.segments.total)} câu)` : ""}; phân tích lại để giữ kết quả liền mạch,
            tiếp tục thì {ANALYSIS_CUT_COST}.
          </p>
        ) : redoWaiting > 0 && kind === "continue" ? (
          <p>
            {redoWaiting === 1 ? "1 chương đang chờ thu lại" : `${redoWaiting} chương đang chờ thu lại`} theo sửa của bạn. Bản cũ vẫn nghe được cho tới khi thu xong.
          </p>
        ) : null}
        {studio.missing && !live && (book.phase !== "done" || Boolean(book.pendingChanges) || redoWaiting > 0) && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span>
              Máy này {studio.repair ? "cần sửa" : studio.update ? "cần cập nhật" : "chưa cài"} Studio nên chưa làm tiếp được phần phân tích và thu âm (nghe, xem,
              sửa cách đọc, nhạc nền, bìa và xuất sách vẫn được).
            </span>
            {!remote && (
              <Button variant="ghost" size="sm" icon={Download} onClick={() => navigate("/studio")}>
                {studio.action}
              </Button>
            )}
          </p>
        )}
        {live && book.paused === "battery" && (
          <div>
            <p>Studio tạm dừng; cắm sạc để tiếp tục.</p>
            <MoreInfo label="Dùng pin">Làm sách trên pin chậm và hao pin. Bấm “Tiếp tục” để làm ngay trên pin{remote ? "." : ", hoặc đổi ở Cài đặt › Studio."}</MoreInfo>
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
      <span className="font-medium text-fg">
        Phần {here.part}/{parts.length}
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
            {part.part < here.part ? "← " : ""}Phần {part.part}
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
  if (chapter.statusLabel === "Mất file audio") return { label: chapter.statusLabel, tone: "warning" }; // soát UX a6 01-10: cùng màu cam với đầu trang
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
      toast.success(`Đã ghi: thu lại ${lines} câu của ${chapter.displayTitle}`);
      void client.invalidateQueries({ queryKey: ["book", book.id] });
      void client.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (error: Error) => toast.error("Chưa ghi được", { description: error.message }),
  });
  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={`Tuỳ chọn ${chapter.displayTitle}`}
            className="touch-box inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-fg-2 opacity-0 transition-[opacity,color,background-color] duration-motion-fast transition-colors hover:bg-panel hover:text-fg focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:bg-panel data-[state=open]:opacity-100 max-md:opacity-100"
          >
            <MoreHorizontal className="glyph ink-end" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-56 rounded-xl border border-line bg-panel p-1.5 shadow-float">
            {chapter.playable && (
              <DropdownMenu.Item onSelect={onPlay} className={MENU_ITEM}>
                <Play className="size-4" /> Nghe chương
              </DropdownMenu.Item>
            )}
            <DropdownMenu.Item
              onSelect={() => setParams({ tab: "script", chapter: String(chapter.id) })}
              className={MENU_ITEM}
            >
              <BookOpenText className="size-4" /> Kịch bản chương này
            </DropdownMenu.Item>
            {recorded > 0 && (
              <>
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
                <DropdownMenu.Item onSelect={() => setConfirm(true)} className={MENU_ITEM}>
                  <RefreshCw className="size-4" /> Thu lại cả chương…
                </DropdownMenu.Item>
              </>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setConfirm(false)}>
            Thôi
          </Button>
          <Button
            variant="primary"
            icon={RefreshCw}
            loading={retake.isPending}
            onClick={() => {
              setConfirm(false);
              retake.mutate();
            }}
          >
            Thu lại {recorded} câu
          </Button>
        </DialogActions>}
        open={confirm}
        onOpenChange={setConfirm}
        title={`Thu lại cả ${chapter.displayTitle}?`}
        description={`Thu lại ${recorded} câu; giọng giữ nguyên, cách nói đổi.`}
      >
        <Button variant="ghost" onClick={() => { setConfirm(false); setParams({ tab: "script", chapter: String(chapter.id) }); }}>Sửa chữ</Button>
        <MoreInfo label="Thu lại chương">Dùng hạt giống mới cho cả chương. Sai người nói hoặc chữ thì sửa Kịch bản trước; thu lại cùng chữ không chữa được.</MoreInfo>

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
        "group grid h-14 grid-cols-[40px_minmax(0,1fr)_auto_32px] lg:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px_32px] items-baseline gap-3 rounded-lg px-2 text-sm",
        current ? "text-accent-text" : "hover:bg-hover",
      )}
    >
      <div role="cell" className="flex">
        {chapter.playable ? (
          <button
            type="button"
            onClick={onPlay}
            aria-label={current && player.playing ? `Tạm dừng ${chapter.displayTitle}` : `Nghe ${chapter.displayTitle}`}
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
          <div className="flex items-baseline gap-2" title={book.running ? "Đang thu âm" : "Tạm dừng giữa chương"}>
            <Progress className="self-center" value={recorded} running={book.running} tone={book.running ? "accent" : "muted"} size="xs" label="Đã thu âm" />
            <span className="tabular text-xs text-fg-2">
              {book.running ? "" : "dừng ở "}
              {chapter.segments.finished}/{chapter.segments.total}
            </span>
          </div>
        ) : mark ? (
          <StatusPill label={mark.label} tone={mark.tone} />
        ) : (
          <span className="sr-only">{chapter.statusLabel}</span>
        )}
      </div>
      <div role="cell" className="tabular hidden text-right text-xs text-fg-2 lg:block">
        {chapter.status === "completed" || chapter.redo ? formatLength(chapter.seconds) : chapter.segments.total ? `${formatNumber(chapter.segments.total)} câu` : ""}
      </div>
      <div role="cell" className="tabular hidden whitespace-nowrap text-right text-xs text-fg-3 lg:block">
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
    <div ref={table} role="table" className="-mx-2" aria-label="Danh sách chương" aria-rowcount={chapters.length + 1}
      style={{ "--chapter-number": `${String(chapters.length).length}ch` } as CSSProperties}>
      <div
        role="row"
        aria-rowindex={1}
        className="grid h-9 grid-cols-[40px_minmax(0,1fr)_auto_32px] lg:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px_32px] items-center gap-3 border-b border-line mx-2 label-section text-fg-2"
      >
        <span role="columnheader">
          <span aria-hidden>#</span>
          <span className="sr-only">Số chương</span>
        </span>
        <span role="columnheader">Chương</span>
        <span role="columnheader">Trạng thái</span>
        {/* Màn hẹp (điện thoại, Studio từ xa) chỉ còn #, chương, trạng thái - soát UX 29-09: 5 cột cố định vỡ ở 375px. */}
        <span role="columnheader" className="hidden text-right lg:block" title="Số phút khi chương đã có audio; chưa có thì số câu của chương">Độ dài</span>
        <span role="columnheader" className="hidden text-right lg:block">Xong lúc</span>
        <span role="columnheader">
          <span className="sr-only">Thêm</span>
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
        <MotionRegion as="span" className="text-xs text-fg-2">{data ? `${data.length} mục gần nhất` : ""}</MotionRegion>
        <button
          type="button"
          aria-pressed={mode === "technical"}
          onClick={() => setMode(mode === "technical" ? "story" : "technical")}
          className="touch-row -mr-2 inline-flex items-center rounded-lg px-2 text-xs font-medium text-accent-text hover:underline"
        >
          {mode === "technical" ? "Ẩn chi tiết kỹ thuật" : "Chi tiết kỹ thuật"}
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
        <EmptyState icon={BookOpenText} title="Chưa có gì" className="mt-4">
          Diễn biến sẽ hiện ở đây khi sách bắt đầu chạy.
        </EmptyState>
      ) : mode === "technical" ? (
        <div className="mt-4 max-h-[560px] overflow-auto py-3 font-mono text-[0.75rem] leading-relaxed">
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
              <h4 className="label-section mb-2 text-fg-2">{group.day}</h4>
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
  chapters: "Chương",
  precast: "Duyệt trước khi thu",
  work: "Việc cần duyệt",
  script: "Kịch bản",
  review: "Cần nghe lại",
  cast: "Nhân vật",
  music: "Nhạc nền",
  activity: "Nhật ký",
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
    <TabsList label="Mục của dự án">
      {MAIN_TABS.map((key) => (
        <TabsTrigger key={key} value={key} count={counts[key]}>
          {TAB_LABEL[key]}
        </TabsTrigger>
      ))}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            data-active={inMore || undefined}
            className="touch-row relative -mb-px inline-flex h-11 shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent text-sm font-medium text-fg-2 transition-colors hover:text-fg data-[active]:border-accent data-[active]:text-fg data-[state=open]:text-fg"
          >
            <TabLabel count={moreCount}>
              <MotionRegion as="span" motionKey={inMore ? tab : "more"}>{inMore ? TAB_LABEL[tab] : "Thêm"}</MotionRegion>
            </TabLabel>
            <ChevronDown className="fold-chevron size-3.5 text-fg-3" aria-hidden />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content collisionPadding={12} align="start" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] min-w-52 overflow-y-auto overscroll-contain rounded-xl border border-line bg-panel p-1.5 shadow-float">
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
const FROM_LABEL: Record<string, string> = { work: "Việc cần duyệt", review: "Cần nghe lại", precast: "Duyệt trước khi thu" };

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
        <ScreenHeader back={{ label: "Về Studio", onClick: () => navigate("/studio") }} />
        <div className="mt-5 flex gap-7">
          <Skeleton className="size-44 rounded-lg" />
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
        title="Dự án này không còn"
        className="mt-20"
        action={<Button onClick={() => navigate("/studio")}>Về danh sách dự án</Button>}
      >
        Cuốn này đã bị xoá hoặc chuyển đi khỏi thư viện.
      </EmptyState>
    );
  }
  // Chỉ khi chưa từng có bản nào của sách; đã có thì giữ trang và báo bằng dải bên dưới (bookFailure).
  if (failure === "error" || !data) {
    return (
      <EmptyState
        icon={CircleAlert}
        title="Không mở được sách"
        className="mt-20"
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Button variant="ghost" loading={isFetching} onClick={() => void refetch()}>
              Thử lại
            </Button>
            <Button onClick={() => navigate("/studio")}>Về Studio</Button>
          </div>
        }
      >
        {failureText(error)}
      </EmptyState>
    );
  }

  const { book, chapters } = data;
  const status = projectStatus(book);
  // MỘT dòng cho người nghe: trạng thái · số chương · độ dài (+ việc cần để ý). Giọng kể, chất lượng, model, ngày tạo, lần nghe cuối ở "Chi tiết" trong "…" -
  // dòng 12-13 mẩu từng làm đầu trang nặng, và viên trạng thái trên tiêu đề làm tiêu đề lệch 2 px giữa các trạng thái (soát 25-10).
  const meta = [
    <StatusText key="status" label={status.label} tone={status.tone} live={status.live} />,
    book.phase !== "done" && book.chapters.total ? `${book.chapters.completed}/${book.chapters.total} chương` : `${book.chapters.total} chương`,
    book.audioSeconds > 0 && formatLength(book.audioSeconds),
    book.chapters.missingAudio ? <span key="missing" className="font-medium text-warning">{book.chapters.missingAudio} chương mất file audio</span> : false,
    book.chapters.redo ? `${book.chapters.redo} chương chờ thu lại` : false,
  ];

  return (
    <div className="motion-reveal page-x mx-auto max-w-[1180px] pb-16">
      {/* Nút ← chung của màn con (ScreenHeader) đứng riêng một hàng: tên dự án nằm cạnh bìa bên dưới. */}
      <ScreenHeader back={{ label: "Về Studio", onClick: () => navigate("/studio") }} />
      {failure === "stale" && !isListenOnly(error) && (
        <div role="status" className="mt-4 flex flex-wrap items-center gap-2 py-3 text-sm">
          <CircleAlert className="size-4 shrink-0 text-warning" />
          <span className="min-w-0 flex-1 text-pretty">
            {isOffline(error) ? "Mất kết nối tới ABook, đang thử lại…" : `Chưa tải lại được sách: ${failureText(error)} Đang thử lại…`}
          </span>
          <Button size="sm" variant="ghost" loading={isFetching} onClick={() => void refetch()}>
            Thử lại
          </Button>
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
          <span className="text-pretty">
            Chưa tải được {sideError}; tự thử lại, hoặc làm mới trang.
          </span>
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
            <ArrowLeft className="ink-start size-4" /> Về màn trước
          </button>
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
            <p className="mt-6 text-sm text-fg-2">Màn duyệt mở được khi máy đã phân tích xong và phân vai.</p>
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
            onPickNarrator={book.castLocked ? () => setPicking({ name: "NARRATOR", displayName: "người kể" }) : undefined}
            onMerge={setMerging}
            onUnmerge={(person) => unmerge.mutate(person)}
            onRename={setRenaming}
            onGender={setGendering}
            narratorNote={<><NarratorNote book={book} /><TellerModeSwitch book={book} /></>}
          />
          <NameReadings bookId={book.id} focus={params.get("focus") === "names"} name={params.get("name") ?? ""} />
        </TabsContent>
        <TabsContent value="music">
          <MusicTab bookId={book.id} chapterTitle={(id) => chapters.find((chapter) => chapter.id === id)?.fullTitle ?? `Chương ${id}`} />
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
