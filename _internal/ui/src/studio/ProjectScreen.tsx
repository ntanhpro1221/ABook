import {
  AlertTriangle,
  ArrowLeft,
  BookOpenText,
  BookPlus,
  Headphones,
  Check,
  CircleAlert,
  Download,
  FolderDown,
  FolderOpen,
  Mic2,
  MoreHorizontal,
  Pause,
  Pencil,
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
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import {
  Button,
  Dialog,
  EmptyState,
  IconButton,
  Progress,
  Segmented,
  Skeleton,
  StatusPill,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Vu,
} from "@/shared/ui";
import { api, type BookSummary, type Chapter } from "@/studio/api";
import { cn } from "@/shared/cn";
import { usePageTitle } from "@/shared/title";
import {
  phaseTone,
  useActivity,
  useAppInfo,
  useBook,
  useContinuation,
  useParts,
  usePause,
  useReveal,
  useStart,
  useStudioMissing,
  useStop,
} from "@/studio/data";
import {
  formatClock,
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
import { ApplyChangesDialog } from "./ApplyChanges";
import { CoverEditor } from "./CoverEditor";
import { ChapterError } from "./ChapterError";
import { friendlyError } from "./errorText";
import { isGone, useSideError } from "./polling";
import { ReviewQueue, useReviewCount } from "./ReviewQueue";
import { PhoneEdits, useInboxCount } from "./PhoneEdits";
import { WorkInbox, useWorkCount } from "./WorkInbox";
import { ScriptTab } from "./ScriptTab";
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
  const live = (book.running || book.starting) && !book.paused;
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
    <div className={cn("relative flex-1 rounded-xl border p-4", state === "active" ? "border-accent/40 bg-accent-soft" : "border-line bg-panel")}>
      <div className="flex items-center gap-2.5">
        <div
          className={cn(
            "grid size-7 place-items-center rounded-full text-xs font-bold",
            state === "done" && "bg-success text-white",
            state === "active" && "bg-accent text-accent-ink",
            state === "paused" && "bg-fg-3 text-bg",
            state === "pending" && "bg-hover text-fg-3",
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
          <Progress value={progress} running={state === "active"} tone={state === "done" ? "success" : state === "paused" ? "muted" : "accent"} size="sm" />
          <span className="tabular w-9 text-right text-xs font-semibold">{formatPercent(progress)}</span>
        </div>
      )}
    </div>
  );
}

/** Lỗi của lần làm sách: câu cho người nghe + việc nên làm; nguyên văn kỹ thuật thu vào "Chi tiết". */
function LastError({ raw }: { raw: string }) {
  const shown = friendlyError(raw);
  return (
    <div className="mt-3 flex gap-2 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
      <CircleAlert className="mt-0.5 size-4 shrink-0" />
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

/** Dưới hàng "Người kể chuyện" của tab Nhân vật: giọng kể chọn lúc tạo sách. Cuốn chưa chạy thì đổi được ngay qua "Sửa thiết lập"
 *  (trình tạo điền sẵn mọi lựa chọn cũ); đã chạy thì giọng kể gắn với cả cuốn - nói thẳng, đừng để người nghe tìm nút không có. */
function NarratorNote({ book }: { book: BookSummary }) {
  const navigate = useNavigate();
  const remote = Boolean(useAppInfo().data?.remote);
  if (book.phase === "idle" && !remote) {
    return (
      <>
        Giọng kể chọn lúc tạo sách, đổi được vì cuốn này chưa bắt đầu chạy.{" "}
        <button type="button" onClick={() => navigate(`/studio/new?redo=${book.id}`)} className="font-medium text-accent-text underline underline-offset-2">
          Đổi giọng kể
        </button>
      </>
    );
  }
  return <>Giọng kể chọn lúc tạo sách và giữ nguyên cho cả cuốn nên không đổi ở đây; muốn giọng kể khác thì tạo lại cuốn từ file truyện.</>;
}

function ProductionPanel({ book }: { book: BookSummary }) {
  const [analysis, casting, synthesis] = stepStates(book);
  const live = book.running || book.starting;
  const eta = book.paused ? "đang tạm dừng" : etaOf(book) ?? (live ? "đang ước tính thời gian…" : "");
  return (
    <section className="mt-8">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-base font-semibold">Tiến trình sản xuất</h2>
        <div className="tabular text-sm text-fg-2">
          {formatPercent(book.progress.overall)} tổng
          {eta && <span className="text-fg-3"> · {eta}</span>}
        </div>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Step
          index={1}
          state={analysis}
          icon={BookOpenText}
          title="Phân tích truyện"
          detail="Đọc cả truyện để nhận ra lời thoại, ai đang nói và cảm xúc từng câu."
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
      {/* Trước mốc phân tích xong: đặt sẵn "Chờ tôi duyệt trước khi thu" cho cuốn này (webui/precast.py). */}
      {!book.castLocked && book.precast && <PrecastWaitSwitch book={book} className="mt-3" />}
      {book.startError && (
        <div className="mt-3 flex gap-2 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span>Không khởi động được: {book.startError}</span>
        </div>
      )}
      {book.lastError && book.phase === "error" && <LastError raw={book.lastError} />}
    </section>
  );
}

// ---- Nút hành động ---------------------------------------------------------------------------------------

function StopDialog({ book, open, onOpenChange }: { book: BookSummary; open: boolean; onOpenChange: (open: boolean) => void }) {
  const stop = useStop();
  const pause = usePause();
  const inAnalysis = book.phase === "analysis";
  const eta = etaOf(book);
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={inAnalysis ? "Dừng giữa lúc phân tích truyện?" : "Dừng tạo sách nói?"}
      description={
        // Không nêu tên nút làm tiếp: sau khi dừng nó là "Tiếp tục tạo", "Bắt đầu tạo sách nói" hay "Áp dụng N thay đổi"
        // tuỳ sách đã tới đâu (soát UX 30-09). Đang tạm dừng thì nói Dừng khác Tạm dừng ở chỗ nào.
        inAnalysis
          ? undefined
          : book.paused
            ? "Sách đang tạm dừng và vẫn giữ bộ nhớ card đồ hoạ. Dừng hẳn thì nhả bộ nhớ ấy cho việc khác; mọi chương và câu đã xong vẫn giữ nguyên, làm tiếp lúc nào cũng được."
            : "Mọi chương và câu đã xong được giữ nguyên - làm tiếp lúc nào cũng được, từ đúng chỗ dừng."
      }
    >
      {inAnalysis && (
        <div className="mb-5 flex gap-3 rounded-xl bg-warning-soft p-4 text-sm leading-relaxed text-fg">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" />
          <div className="text-pretty">
            <p>
              <span className="font-semibold">Dừng giữa lúc phân tích thì mất phần đã làm,</span> và chạy lại sẽ ra một cuốn hơi
              khác: người nói ở đoạn sau chỗ dừng có thể đổi, kéo theo đổi giọng.
            </p>
            <p className="mt-2 text-fg-2">
              Nên để chạy hết bước này{eta ? ` (${eta})` : ""}.
              {book.canPause && (
                <>
                  {" "}
                  Cần nghỉ thì bấm <span className="font-medium text-fg">Tạm dừng</span>: sách đứng yên rồi làm tiếp đúng chỗ,
                  phần đã phân tích không mất.
                </>
              )}
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
    </Dialog>
  );
}

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

// Đổi tên chỉ đổi tên HIỆN (store.TITLE_FILE): thư mục dự án và sổ của dây chuyền giữ nguyên, nên làm được cả lúc chạy.
function RenameDialog({ book, open, onOpenChange }: { book: BookSummary; open: boolean; onOpenChange: (open: boolean) => void }) {
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
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Đổi tên sách"
      description="Tên mới hiện trong thư viện, trên điện thoại (lần đồng bộ tới) và trong file xuất. Thư mục dự án giữ nguyên."
    >
      <form
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
          className="mt-1.5 h-10 w-full rounded-lg border border-line bg-panel px-3 text-sm text-fg outline-none focus-visible:border-accent"
        />
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Huỷ
          </Button>
          <Button type="submit" variant="primary" loading={rename.isPending} disabled={!typed || typed === book.title}>
            Đổi tên
          </Button>
        </div>
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
    mutationFn: () => api<{ ok: boolean }>(`/api/books/${book.id}`, { method: "DELETE" }),
    onSuccess: () => {
      onOpenChange(false);
      navigate("/studio", { replace: true });
      client.removeQueries({ queryKey: ["book", book.id] });
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: ["listen"] });
      toast.success(`Đã chuyển “${book.title}” vào Thùng rác`, {
        description: "Cần lại thì khôi phục thư mục ấy từ Thùng rác của Windows.",
      });
    },
    onError: (error: Error) => toast.error("Chưa xoá được", { description: error.message }),
  });
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Xoá dự án “${book.title}”?`}
      description="Cả thư mục dự án - bản thu, phân tích, phân vai và mọi chỗ đã sửa - chuyển vào Thùng rác của Windows, khôi phục được từ đó. File truyện gốc và sách đã xuất ra thư mục khác không bị đụng tới."
    >
      <p className="break-all rounded-lg bg-panel-2 px-3 py-2 text-xs text-fg-2">{book.path}</p>
      {busy && <p className="mt-3 text-sm text-warning">Sách đang chạy - dừng sách trước rồi mới xoá được.</p>}
      <div className="mt-5 flex justify-end gap-2">
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
      </div>
    </Dialog>
  );
}

/** "…" của một dự án: đổi tên, xoá. `rename={false}` cho dự án hỏng (không đọc được - chỉ còn xoá). */
export function ProjectMenu({ book, rename = true, className }: { book: BookSummary; rename?: boolean; className?: string }) {
  const [dialog, setDialog] = useState<"rename" | "delete" | null>(null);
  const navigate = useNavigate();
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
            <MoreHorizontal className="size-[18px]" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-52 rounded-xl border border-line bg-panel p-1.5 shadow-float">
            {rename && (
              <>
                <DropdownMenu.Item onSelect={() => setDialog("rename")} className={MENU_ITEM}>
                  <Pencil className="size-4" /> Đổi tên…
                </DropdownMenu.Item>
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
              </>
            )}
            {/* Truyện dài làm nhiều đợt: phần mới giữ giọng, cách đọc tên, ghim của phần này (continuation.py). Dự án chưa
                phân tích câu nào thì không có gì để mang theo - mờ kèm lý do thay vì dẫn tới một phần mới trống (soát UX 29-09). */}
            {/* Dự án hỏng (`broken`) không có `segments` và không có gì để mang theo: chỉ còn xoá. */}
            {!book.broken && (
              <>
                <DropdownMenu.Item
                  disabled={!analyzed}
                  onSelect={() => navigate(`/studio/new?continue=${book.id}`)}
                  className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
                >
                  <BookPlus className="size-4" /> Làm tiếp cuốn này…
                  {!analyzed && <span className="ml-auto pl-3 text-xs text-fg-3">chạy phần này trước</span>}
                </DropdownMenu.Item>
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
              </>
            )}
            <DropdownMenu.Item onSelect={() => setDialog("delete")} className={cn(MENU_ITEM, "text-danger")}>
              <Trash2 className="size-4" /> Xoá dự án…
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <RenameDialog book={book} open={dialog === "rename"} onOpenChange={(open) => setDialog(open ? "rename" : null)} />
      <DeleteDialog book={book} open={dialog === "delete"} onOpenChange={(open) => setDialog(open ? "delete" : null)} />
    </>
  );
}

function Actions({ book }: { book: BookSummary }) {
  const start = useStart();
  const reveal = useReveal();
  const remote = Boolean(useAppInfo().data?.remote);
  const navigate = useNavigate();
  const studio = useStudioMissing();
  // Phân tích và thu âm chạy bằng Studio: máy chưa có thì giải thích ở đây, không gửi lệnh rồi nhận lỗi.
  const begin = (id: string) => {
    if (!studio.missing) return start.mutate(id);
    toast.error(studio.update ? "Cần cập nhật Studio" : "Cần cài Studio", {
      description: "Phân tích và thu âm chạy bằng Studio.",
      action: remote ? undefined : { label: studio.update ? "Cập nhật Studio" : "Cài Studio", onClick: () => navigate("/studio") },
    });
  };
  const [confirmStop, setConfirmStop] = useState(false);
  const [confirmApply, setConfirmApply] = useState(false);
  const [exporting, setExporting] = useState(false);
  const live = book.running;
  const stop = useStop();
  const pause = usePause();
  // Phân tích xong thì sổ nhân vật đã đủ để làm tiếp; nút chỉ hiện khi thư mục truyện có chương mới sau chương cuối.
  const analyzed = book.segments.total > 0 && book.segments.analyzed === book.segments.total;
  const next = useContinuation(book.id, analyzed).data?.paths.length ?? 0;
  return (
    <div className="flex flex-wrap items-center gap-2 sm:mt-5">
      {book.chapters.completed > 0 && (
        // Một nút chính mỗi lúc: sách xong mà còn thay đổi chờ áp thì "Áp dụng" là việc chính, không phải hai nút cam cạnh nhau
        // (soát UX 29-09).
        <Button
          variant={book.phase === "done" && !book.pendingChanges ? "primary" : "secondary"}
          size="lg"
          icon={Headphones}
          className="max-sm:basis-full"
          onClick={() => navigate(`/book/${book.id}`)}
        >
          Nghe trong Thư viện
        </Button>
      )}
      {book.chapters.completed > 0 && (
        <Button variant="ghost" size="lg" icon={FolderDown} onClick={() => setExporting(true)}>
          Xuất…
        </Button>
      )}
      <ExportDialog book={book} open={exporting} onOpenChange={setExporting} onApplyFirst={() => setConfirmApply(true)} />
      {book.queuePosition ? (
        <>
          <span className="inline-flex h-11 items-center gap-2 rounded-xl bg-warning-soft px-4 text-sm font-medium text-warning">
            Đang xếp hàng · thứ {book.queuePosition} - tự bắt đầu khi cuốn đang chạy xong
            {book.seedPending ? ", rồi mang giọng và cách đọc tên từ phần trước" : ""}
          </span>
          <Button variant="ghost" size="lg" onClick={() => stop.mutate({ id: book.id, queued: true })}>
            Bỏ xếp hàng
          </Button>
        </>
      ) : book.starting ? (
        <Button variant="primary" size="lg" loading>
          Đang khởi động
        </Button>
      ) : live ? (
        // Tạm dừng giữ tiến trình sống, làm tiếp đúng chỗ - an toàn cả giữa lúc phân tích; "Dừng" kết thúc lượt chạy.
        <>
          {book.paused ? (
            // Giữ chờ duyệt: "Tiếp tục" và "Thu âm" là MỘT việc - chỉ có nút này, tên là "Thu âm" (soát UX a8 05-10, mục 12).
            <Button
              variant="primary"
              size="lg"
              icon={book.precast?.held ? Mic2 : Play}
              loading={pause.isPending}
              onClick={() => pause.mutate({ id: book.id, paused: false })}
            >
              {book.precast?.held ? "Thu âm" : "Tiếp tục"}
            </Button>
          ) : book.canPause ? (
            <Button variant="outline" size="lg" icon={Pause} loading={pause.isPending} onClick={() => pause.mutate({ id: book.id, paused: true })}>
              Tạm dừng
            </Button>
          ) : null}
          {/* Lượt chạy bắt đầu bằng bản app cũ không tạm dừng được: "Dừng" là nút duy nhất, giữ như trước. */}
          <Button variant={book.canPause ? "ghost" : "outline"} size="lg" icon={Square} onClick={() => setConfirmStop(true)}>
            Dừng
          </Button>
        </>
      ) : book.phase === "idle" ? (
        <>
          <Button variant="primary" size="lg" icon={Wand2} loading={start.isPending} onClick={() => begin(book.id)}>
            Bắt đầu tạo sách nói
          </Button>
          {/* Chưa chạy bước nào: chọn lại chương, giọng kể, chất lượng, "tôi" (soát UX a5 01-10, #4). Cài đặt khoá theo sách
              nên là tạo lại - trình tạo điền sẵn mọi lựa chọn cũ, cuốn cũ vào Thùng rác khi cuốn mới tạo xong. */}
          {!remote && (
            <Button variant="ghost" size="lg" icon={SlidersHorizontal} onClick={() => navigate(`/studio/new?redo=${book.id}`)}>
              Sửa thiết lập
            </Button>
          )}
        </>
      ) : book.precast?.held && book.phase !== "done" ? (
        // Sách đang chờ duyệt mà tiến trình đã chết (máy chủ khởi động lại): vẫn là "Thu âm", không phải "Tiếp tục tạo" cạnh
        // một khung mời duyệt (soát UX a8) - cùng việc với nút "Thu âm" lúc sách đang giữ.
        <Button variant="primary" size="lg" icon={Mic2} loading={start.isPending} onClick={() => begin(book.id)}>
          Thu âm
        </Button>
      ) : book.phase !== "done" && book.analysisInterrupted ? (
        // Phân tích bị ngắt: chạy tiếp ra MỘT CUỐN KHÁC (AGENTS.md) - nút chính là làm lại từ đầu, "Tiếp tục" lùi xuống kèm
        // lời cảnh báo. Làm lại = dự án mới thay bản dở (cần máy tính: Studio từ xa không tạo lại sách được).
        <>
          {!remote && (
            <Button variant="primary" size="lg" icon={RotateCcw} onClick={() => navigate(`/studio/new?redo=${book.id}`)}>
              Làm lại phân tích từ đầu
            </Button>
          )}
          <Button variant={remote ? "primary" : "outline"} size="lg" icon={Play} loading={start.isPending} onClick={() => begin(book.id)}>
            Tiếp tục
          </Button>
          <p className="basis-full text-pretty text-sm text-fg-2">
            Phân tích đã dừng giữa chừng
            {book.segments.total ? ` (còn ${formatNumber(book.segments.pending ?? book.segments.total - book.segments.analyzed)}/${formatNumber(book.segments.total)} câu chưa phân tích)` : ""}.
            {remote
              ? " “Tiếp tục” vẫn chạy được nhưng ra một cuốn hơi khác so với chạy liền một mạch. Muốn làm lại từ đầu, mở trang này trên máy tính."
              : " Làm lại từ đầu cho kết quả như chạy liền một mạch (bản dở được cất đi); “Tiếp tục” vẫn chạy được nhưng ra một cuốn hơi khác - người nói ở đoạn sau chỗ dừng có thể đổi."}
          </p>
        </>
      ) : book.phase !== "done" ? (
        <Button variant="primary" size="lg" icon={Play} loading={start.isPending} onClick={() => begin(book.id)}>
          Tiếp tục tạo
        </Button>
      ) : book.pendingChanges ? (
        // Sách đã xong không tự chạy lại: sửa của người nghe chờ ở đây. Chạy lại áp chúng trước rồi chỉ thu lại câu bị ảnh
        // hưởng (Pipeline._recover) - không làm lại cả cuốn.
        <Button variant="primary" size="lg" icon={RefreshCw} loading={start.isPending} onClick={() => setConfirmApply(true)}>
          Áp dụng {book.pendingChanges} thay đổi
        </Button>
      ) : null}
      {next > 0 && (
        <Button variant="secondary" size="lg" icon={BookPlus} onClick={() => navigate(`/studio/new?continue=${book.id}`)}>
          Làm tiếp cuốn này · {next} chương mới
        </Button>
      )}
      {/* Hai nút biểu tượng đi thành một cụm: màn hẹp xuống dòng thì xuống cùng nhau, không để "…" đứng một mình một hàng.
          Đổi tên / xoá chỉ trên máy này - Studio từ xa không có hai đường ấy (remote_studio.ALLOWED). */}
      {!remote && (
        <span className="inline-flex items-center gap-2">
          <IconButton label="Mở thư mục sách" icon={FolderOpen} onClick={() => reveal.mutate(book.id)} />
          <ProjectMenu book={book} />
        </span>
      )}
      <StopDialog book={book} open={confirmStop} onOpenChange={setConfirmStop} />
      <ApplyChangesDialog
        bookId={book.id}
        count={book.pendingChanges ?? 0}
        open={confirmApply}
        onOpenChange={setConfirmApply}
        onApply={() => begin(book.id)}
      />
      {studio.missing && !live && (book.phase !== "done" || Boolean(book.pendingChanges)) && (
        <p className="flex basis-full flex-wrap items-center gap-x-3 gap-y-2 text-pretty text-sm text-fg-2">
          <span>
            Máy này {studio.update ? "cần cập nhật" : "chưa cài"} Studio nên chưa làm tiếp được phần phân tích và thu âm (nghe, xem,
            sửa cách đọc, nhạc nền, bìa và xuất sách vẫn được).
          </span>
          {!remote && (
            <Button variant="secondary" size="sm" icon={Download} onClick={() => navigate("/studio")}>
              {studio.update ? "Cập nhật Studio" : "Cài Studio"}
            </Button>
          )}
        </p>
      )}
      {live && book.paused === "battery" && (
        <p className="basis-full text-pretty text-sm text-fg-2">
          Máy tính đang chạy pin: tạo sách trên pin chậm hơn nhiều mà hao pin, nên Studio tạm dừng và tự làm tiếp khi cắm sạc.
          Bấm “Tiếp tục” để làm tiếp ngay trên pin{remote ? "" : ", hay tắt hẳn ở Cài đặt → Studio"}.
        </p>
      )}
    </div>
  );
}

/** Truyện dài làm nhiều đợt: "Phần 2/3 · Phần 1 · Phần 3" - chỉ sang các phần kia của cuốn (soát UX 29-09: phần 1 không nói
 *  đã có phần 2, phần 2 không nói nối tiếp cuốn nào). */
function PartLinks({ id }: { id: string }) {
  const parts = useParts(id).data?.parts ?? [];
  const navigate = useNavigate();
  const here = parts.find((part) => part.current);
  if (parts.length < 2 || !here) return null;
  return (
    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-fg-2">
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
    </p>
  );
}

// ---- Chương ------------------------------------------------------------------------------------------------

function chapterTone(chapter: Chapter) {
  // Soát UX a6 01-10: "Mất file audio" mang màu "xong" trong khi đầu trang tô cam cùng chuyện ấy.
  if (chapter.status === "completed") return chapter.statusLabel === "Mất file audio" ? ("warning" as const) : ("success" as const);
  if (chapter.status === "failed") return "danger" as const;
  if (chapter.status === "synthesizing" || chapter.status === "verifying") return "accent" as const;
  return "muted" as const;
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
      toast.success(`Đã ghi: thu lại ${lines} câu của ${chapter.displayTitle}`, {
        description: book.running
          ? "Máy thu lại từ chương sau. Bỏ được trong hộp “Áp dụng thay đổi”."
          : "Bấm “Áp dụng thay đổi” ở đầu trang để thu. Bỏ được trong hộp ấy.",
      });
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
            className="touch-box inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-fg-2 opacity-0 transition-colors hover:bg-panel hover:text-fg focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:bg-panel data-[state=open]:opacity-100 max-md:opacity-100"
          >
            <MoreHorizontal className="size-[18px]" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-56 rounded-xl border border-line bg-panel p-1.5 shadow-float">
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
      <Dialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Thu lại cả ${chapter.displayTitle}?`}
        description={`${recorded} câu đã thu được thu lại bằng hạt giống mới - giọng như cũ, cách nói mỗi câu khác đi một chút. Hợp khi cả chương nghe không ổn; sai người nói hay sai chữ thì sửa ở Kịch bản, thu lại y chữ không chữa được.`}
      >
        <div className="mt-5 flex justify-end gap-2">
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
        </div>
      </Dialog>
    </>
  );
}

function ChapterRow({ book, chapter }: { book: BookSummary; chapter: Chapter }) {
  const player = usePlayer();
  const playChapter = usePlayChapter();
  const current = player.track?.bookId === book.id && player.track.chapterId === chapter.id;
  const working = chapter.status === "synthesizing" || chapter.status === "verifying";
  const recorded = chapter.segments.total ? chapter.segments.finished / chapter.segments.total : 0;
  const onPlay = () => {
    if (!chapter.playable) return;
    if (current) player.toggle();
    else void playChapter(book.id, chapter.id);
  };
  return (
    <div
      role="row"
      onDoubleClick={onPlay}
      className={cn(
        "group grid h-14 grid-cols-[40px_minmax(0,1fr)_auto_32px] lg:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px_32px] items-center gap-3 rounded-lg px-2 text-sm",
        current ? "bg-accent-soft" : "hover:bg-hover",
      )}
    >
      <div className="flex justify-center">
        {chapter.playable ? (
          <button
            type="button"
            onClick={onPlay}
            aria-label={current && player.playing ? `Tạm dừng ${chapter.displayTitle}` : `Nghe ${chapter.displayTitle}`}
            className="grid size-8 place-items-center rounded-full text-fg-2 hover:bg-panel hover:text-fg"
          >
            {current && player.playing ? (
              <>
                <Vu className="h-3 text-accent group-hover:hidden" />
                <Pause className="hidden size-4 group-hover:block" fill="currentColor" strokeWidth={0} />
              </>
            ) : (
              <>
                <span className="tabular text-xs text-fg-3 group-hover:hidden">{chapter.index}</span>
                <Play className="hidden size-4 translate-x-[1px] group-hover:block" fill="currentColor" strokeWidth={0} />
              </>
            )}
          </button>
        ) : (
          <span className="tabular text-xs text-fg-3">{chapter.index}</span>
        )}
      </div>
      <div className="min-w-0">
        <div className={cn("truncate font-medium", current && "text-accent-text")}>{chapter.displayTitle}</div>
        {chapter.lastError ? (
          <ChapterError raw={chapter.lastError} />
        ) : chapter.subtitle ? (
          <div className="truncate text-xs text-fg-2">{chapter.subtitle}</div>
        ) : null}
      </div>
      <div>
        {working ? (
          <div className="flex items-center gap-2" title={book.running ? "Đang thu âm" : "Tạm dừng giữa chương"}>
            <Progress value={recorded} running={book.running} tone={book.running ? "accent" : "muted"} size="xs" />
            <span className="tabular text-xs text-fg-2">
              {book.running ? "" : "dừng ở "}
              {chapter.segments.finished}/{chapter.segments.total}
            </span>
          </div>
        ) : (
          <StatusPill label={chapter.statusLabel} tone={chapterTone(chapter)} />
        )}
      </div>
      <div className="tabular hidden text-right text-xs text-fg-2 lg:block">
        {chapter.status === "completed" ? formatLength(chapter.seconds) : chapter.segments.total ? `${formatNumber(chapter.segments.total)} câu` : ""}
      </div>
      <div className="tabular hidden whitespace-nowrap text-right text-xs text-fg-3 lg:block">
        {chapter.completedAt ? formatRelative(chapter.completedAt) : ""}
      </div>
      <ChapterMenu book={book} chapter={chapter} onPlay={onPlay} />
    </div>
  );
}

function ChapterList({ book, chapters }: { book: BookSummary; chapters: Chapter[] }) {
  return (
    <div role="table" aria-label="Danh sách chương" className="mt-2">
      <div className="grid h-9 grid-cols-[40px_minmax(0,1fr)_auto_32px] lg:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px_32px] items-center gap-3 border-b border-line px-2 text-[11px] font-semibold uppercase tracking-wider text-fg-3">
        <span className="text-center">#</span>
        <span>Chương</span>
        <span>Trạng thái</span>
        {/* Màn hẹp (điện thoại, Studio từ xa) chỉ còn #, chương, trạng thái - soát UX 29-09: 5 cột cố định vỡ ở 375px. */}
        <span className="hidden text-right lg:block" title="Số phút khi chương đã có audio; chưa có thì số câu của chương">Độ dài</span>
        <span className="hidden text-right lg:block">Xong lúc</span>
        <span />
      </div>
      <div className="mt-1 space-y-px">
        {chapters.map((chapter) => (
          <ChapterRow key={chapter.id} book={book} chapter={chapter} />
        ))}
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
    <div className="mt-5">
      <div className="flex items-center justify-between">
        <Segmented
          label="Kiểu nhật ký"
          value={mode}
          onChange={setMode}
          options={[
            { value: "story", label: "Diễn biến" },
            { value: "technical", label: "Chi tiết kỹ thuật" },
          ]}
        />
        <span className="text-xs text-fg-3">{data ? `${data.length} mục gần nhất` : ""}</span>
      </div>
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
        <div className="mt-4 max-h-[560px] overflow-auto rounded-xl border border-line bg-sunken p-3 font-mono text-[12px] leading-relaxed">
          {(data ?? []).map((item) => (
            <div key={item.id} className="flex gap-3 whitespace-pre-wrap break-words">
              <span className="shrink-0 text-fg-3">{formatTime(item.at)}</span>
              <span className={cn("shrink-0", item.level === "error" ? "text-danger" : item.level === "warning" ? "text-warning" : "text-fg-3")}>
                {item.code}
              </span>
              <span className="text-fg-2">{item.text}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 space-y-6">
          {groups.map((group) => (
            <section key={group.day}>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-fg-3">{group.day}</h4>
              <ol className="relative space-y-1 border-l border-line pl-5">
                {group.items.map((item) => (
                  <li key={item.id} className="relative py-1.5 text-sm">
                    <span className={cn("absolute -left-[25px] top-[13px] size-2 rounded-full ring-4 ring-bg", LEVEL_DOT[item.level] ?? "bg-fg-3")} />
                    <span className="tabular mr-3 text-xs text-fg-3">{formatTime(item.at).split(" · ")[0]}</span>
                    <span className={cn(item.level === "warning" && "text-fg", item.level === "info" && "text-fg-2")}>{item.text}</span>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- Trang -----------------------------------------------------------------------------------------------------------

/** Tab mở lối nhảy sang tab khác ("Đọc cả N câu trong Kịch bản") - nhãn nút "Về …" ở tab đích. */
const FROM_LABEL: Record<string, string> = { work: "Việc cần duyệt", review: "Cần nghe lại", precast: "Duyệt trước khi thu" };

export function ProjectScreen() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = ["chapters", "precast", "work", "script", "review", "cast", "music", "activity"].includes(params.get("tab") ?? "") ? params.get("tab")! : "chapters";
  const reviewCount = useReviewCount(id ?? "");
  const remoteStudio = Boolean(useAppInfo().data?.remote);
  // Việc từ điện thoại chờ duyệt (webui/edits_inbox.py) cộng vào số của tab: chỉ trên chính máy tính (Studio từ xa không có đường này).
  const { data, isLoading, error } = useBook(id);
  // Thẻ đã nằm ở "Duyệt trước khi thu" thì "Việc cần duyệt" không hiện lại và không đếm lại.
  const precastKeys = usePrecastKeys(id ?? "", Boolean(data && canReview(data.book)));
  const workCount = Math.max(0, useWorkCount(id ?? "") - (precastKeys?.size ?? 0)) + useInboxCount(id ?? "", !remoteStudio);
  const [picking, setPicking] = useState<{ name: string; displayName: string } | null>(null);
  const [merging, setMerging] = useState<CastMember | null>(null);
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

  if (isLoading) {
    return (
      <div className="mx-auto max-w-[1180px] px-10 pt-9">
        <Skeleton className="h-5 w-24" />
        <div className="mt-6 flex gap-7">
          <Skeleton className="size-44 rounded-lg" />
          <div className="flex-1 space-y-3 pt-4">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-4 w-1/3" />
          </div>
        </div>
      </div>
    );
  }
  if (isGone(error)) {
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
  if (error || !data) {
    return (
      <EmptyState
        icon={CircleAlert}
        title="Không mở được sách"
        className="mt-20"
        action={<Button onClick={() => navigate("/studio")}>Về Studio</Button>}
      >
        {(error as Error | null)?.message ?? "Sách có thể đã bị chuyển hoặc xoá."}
      </EmptyState>
    );
  }

  const { book, chapters } = data;
  const live = book.running || book.starting;
  const meta = [
    `${book.chapters.total} chương`,
    book.settings.narrator && `Giọng kể ${book.settings.narrator}`,
    book.settings.profileLabel,
    // Model đã phân tích cuốn này - đổi model mặc định thì biết cuốn nào làm bằng model cũ.
    book.settings.analyzer && analyzerLabel(book.settings.analyzer),
    book.createdAt && `Tạo ${formatDate(book.createdAt)}`,
  ].filter(Boolean);

  return (
    <div className="mx-auto max-w-[1180px] px-4 pb-16 pt-7 sm:px-10">
      <button type="button" onClick={() => navigate("/studio")} className="touch-hit inline-flex items-center gap-1.5 text-sm text-fg-2 hover:text-fg">
        <ArrowLeft className="size-4" /> Studio
      </button>
      {/* Màn hẹp (điện thoại): bìa nhỏ cạnh tên sách, hàng nút nằm dưới cả hai (soát UX a8 05-10: bìa to + tên + 3 hàng nút
          chiếm ~590 px, tab bắt đầu ở cuối màn). Từ sm trở lên: bìa bên trái, tên và nút bên phải. `contents` làm cột phải biến
          mất khỏi lưới ở màn hẹp để hàng nút tự chiếm cả hai cột mà vẫn chỉ có một bản của các nút. */}
      <header className="mt-5 grid grid-cols-[6rem_minmax(0,1fr)] gap-x-4 gap-y-4 sm:flex sm:gap-7">
        <CoverEditor book={book} />
        <div className="contents sm:block sm:min-w-0 sm:flex-1 sm:pt-1">
          <div className="min-w-0 sm:contents">
          <StatusPill
            label={book.queuePosition ? `Xếp hàng · thứ ${book.queuePosition}` : book.starting ? "Đang khởi động" : book.precast?.held ? "Chờ bạn duyệt" : book.statusLabel}
            tone={book.paused ? "warning" : phaseTone(book.phase, live)}
            live={live && !book.paused}
          />
          <h1 className="mt-3 text-2xl font-bold leading-tight tracking-tight sm:text-[30px]">{book.title}</h1>
          {/* Điện thoại: một dòng gọn (số chương) + "Chi tiết" gập - giọng kể, chất lượng, model, ngày tạo từng chiếm 3 dòng đầu
              trang (soát UX a8 07-10). */}
          <p className="mt-2 text-sm text-fg-2">
            {meta[0]}
            <span className="max-sm:hidden">{meta.slice(1).map((part) => ` · ${part}`)}</span>
          </p>
          {meta.length > 1 && (
            <details className="mt-1 text-sm text-fg-2 sm:hidden">
              <summary className="touch-hit cursor-pointer text-fg-3">Chi tiết</summary>
              <p className="mt-1">{meta.slice(1).join(" · ")}</p>
            </details>
          )}
          <PartLinks id={book.id} />
          {book.phase === "done" || book.audioSeconds > 0 ? (
            <p className="tabular mt-1 text-sm text-fg-2">
              {formatLength(book.audioSeconds)} audio · {book.chapters.completed - (book.chapters.missingAudio ?? 0)}/{book.chapters.total} chương nghe được
              {book.chapters.missingAudio ? (
                <span className="font-medium text-warning"> · {book.chapters.missingAudio} chương mất file audio</span>
              ) : null}
              {book.position && (
                <span className="text-fg-3 max-sm:hidden"> · lần nghe cuối {formatRelative(book.position.at)} ở {formatClock(book.position.seconds)}</span>
              )}
            </p>
          ) : null}
          </div>
          <div className="col-span-2 sm:col-auto">
            <Actions book={book} />
          </div>
        </div>
      </header>

      {book.phase !== "done" && <ProductionPanel book={book} />}
      {/* Phân tích xong mà chưa thu bao nhiêu: lối vào "Duyệt trước khi thu" đúng lúc sửa còn miễn phí. */}
      {canReview(book) && tab !== "precast" && (book.precast?.held || book.chapters.completed === 0) && (
        <PrecastBanner book={book} onOpen={() => setParams({ tab: "precast" })} />
      )}

      {sideError && (
        <div role="status" className="mt-4 flex gap-2 rounded-xl bg-warning-soft px-4 py-3 text-sm">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" />
          <span className="text-pretty">
            Một phần của trang này chưa tải được: {sideError} Máy thử lại thưa dần; làm mới trang để thử ngay.
          </span>
        </div>
      )}
      <Tabs value={tab} onValueChange={(value) => setParams({ tab: value }, { replace: true })} className="mt-9">
        <TabsList>
          <TabsTrigger value="chapters" count={chapters.length}>
            Chương
          </TabsTrigger>
          {canReview(book) && <TabsTrigger value="precast">Duyệt trước khi thu</TabsTrigger>}
          <TabsTrigger value="work" count={workCount || undefined}>
            Việc cần duyệt
          </TabsTrigger>
          <TabsTrigger value="script">Kịch bản</TabsTrigger>
          <TabsTrigger value="review" count={reviewCount || undefined}>
            Cần nghe lại
          </TabsTrigger>
          <TabsTrigger value="cast">Nhân vật</TabsTrigger>
          <TabsTrigger value="music">Nhạc nền</TabsTrigger>
          <TabsTrigger value="activity">Nhật ký</TabsTrigger>
        </TabsList>
        {from && FROM_LABEL[from] && tab !== from && (
          <button type="button" onClick={back} className="touch-hit mt-4 inline-flex items-center gap-1.5 text-sm text-fg-2 hover:text-fg">
            <ArrowLeft className="size-4" /> Về {FROM_LABEL[from]}
          </button>
        )}
        <TabsContent value="chapters">
          <ChapterList book={book} chapters={chapters} />
        </TabsContent>
        <TabsContent value="precast">
          {canReview(book) ? (
            <PrecastReview
              book={book}
              onPickVoice={(person) => setPicking({ name: person.name, displayName: person.displayName })}
              onMerge={setMerging}
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
          {!remoteStudio && <PhoneEdits bookId={book.id} />}
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
          />
        </TabsContent>
        <TabsContent value="script">
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
            onMerge={setMerging}
            onRename={setRenaming}
            onGender={setGendering}
            narratorNote={<NarratorNote book={book} />}
          />
          <NameReadings bookId={book.id} focus={params.get("focus") === "names"} name={params.get("name") ?? ""} />
        </TabsContent>
        <TabsContent value="music">
          <MusicTab bookId={book.id} chapterTitle={(id) => chapters.find((chapter) => chapter.id === id)?.fullTitle ?? `Chương ${id}`} />
        </TabsContent>
        <TabsContent value="activity">
          <ActivityView book={book} />
        </TabsContent>
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
}
