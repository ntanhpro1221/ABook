import {
  AlertTriangle,
  ArrowLeft,
  BookOpenText,
  BookPlus,
  Headphones,
  Check,
  CircleAlert,
  FolderOpen,
  Mic2,
  MoreHorizontal,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Square,
  Trash2,
  Users,
  Wand2,
} from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
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
  useStop,
} from "@/studio/data";
import {
  formatClock,
  formatDate,
  formatEta,
  formatLength,
  formatNumber,
  formatPercent,
  formatRelative,
  formatTime,
} from "@/shared/format";
import { CastList } from "@/listen/BookScreen";
import { CoverEditor } from "./CoverEditor";
import { ReviewQueue, useReviewCount } from "./ReviewQueue";
import { WorkInbox, useWorkCount } from "./WorkInbox";
import { ScriptTab } from "./ScriptTab";
import { NameReadings } from "./NameReadings";
import { VoicePicker } from "./VoicePicker";
import { usePlayer } from "@/listen/player";
import { useSource } from "@/listen/source";

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

function ProductionPanel({ book }: { book: BookSummary }) {
  const [analysis, casting, synthesis] = stepStates(book);
  const live = book.running || book.starting;
  const eta = book.paused ? "đang tạm dừng" : book.eta ? formatEta(book.eta.seconds) : live ? "đang ước tính thời gian…" : "";
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
      {book.startError && (
        <div className="mt-3 flex gap-2 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span>Không khởi động được: {book.startError}</span>
        </div>
      )}
      {book.lastError && book.phase === "error" && (
        <div className="mt-3 flex gap-2 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span>{book.lastError}</span>
        </div>
      )}
    </section>
  );
}

// ---- Nút hành động ---------------------------------------------------------------------------------------

function StopDialog({ book, open, onOpenChange }: { book: BookSummary; open: boolean; onOpenChange: (open: boolean) => void }) {
  const stop = useStop();
  const pause = usePause();
  const inAnalysis = book.phase === "analysis";
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={inAnalysis ? "Dừng giữa lúc phân tích truyện?" : "Dừng tạo sách nói?"}
      description={
        inAnalysis
          ? undefined
          : "Mọi chương và câu đã xong được giữ nguyên. Bấm “Tiếp tục tạo” để làm tiếp từ chỗ dừng."
      }
    >
      {inAnalysis && (
        <div className="mb-5 flex gap-3 rounded-xl bg-warning-soft p-4 text-sm leading-relaxed text-fg">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" />
          <div className="text-pretty">
            <p>
              Phân tích là bước duy nhất không nên ngắt. Chạy tiếp sau khi dừng sẽ ra <span className="font-semibold">một cuốn
              sách khác</span> so với chạy liền một mạch: đoạn sau chỗ dừng có thể đổi người nói, kéo theo đổi giọng.
            </p>
            <p className="mt-2 text-fg-2">
              Nên để chạy hết bước này{book.eta ? ` (${formatEta(book.eta.seconds)})` : ""}.
              {book.canPause && (
                <>
                  {" "}
                  Muốn nghỉ giữa chừng thì bấm <span className="font-medium text-fg">Tạm dừng</span>: sách đứng yên (sau phần
                  đang làm dở) và làm tiếp đúng chỗ, không đổi gì - nhưng vẫn giữ bộ nhớ card đồ hoạ.
                </>
              )}{" "}
              Nếu buộc phải dừng hẳn (tắt máy), hãy tạo lại sách từ đầu thay vì bấm “Tiếp tục tạo”.
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
          onClick={() => stop.mutate(book.id, { onSettled: () => onOpenChange(false) })}
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
          autoFocus
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
  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={`Tuỳ chọn dự án ${book.title}`}
            className={cn(
              "inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-fg-2 transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover",
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
            <DropdownMenu.Item
              disabled={book.segments.analyzed === 0}
              onSelect={() => navigate(`/studio/new?continue=${book.id}`)}
              className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
            >
              <BookPlus className="size-4" /> Làm tiếp cuốn này…
              {book.segments.analyzed === 0 && <span className="ml-auto pl-3 text-xs text-fg-3">chạy phần này trước</span>}
            </DropdownMenu.Item>
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
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
  const [confirmStop, setConfirmStop] = useState(false);
  const live = book.running;
  const stop = useStop();
  const pause = usePause();
  // Phân tích xong thì sổ nhân vật đã đủ để làm tiếp; nút chỉ hiện khi thư mục truyện có chương mới sau chương cuối.
  const analyzed = book.segments.total > 0 && book.segments.analyzed === book.segments.total;
  const next = useContinuation(book.id, analyzed).data?.paths.length ?? 0;
  return (
    <div className="mt-5 flex flex-wrap items-center gap-2">
      {book.chapters.completed > 0 && (
        // Một nút chính mỗi lúc: sách xong mà còn thay đổi chờ áp thì "Áp dụng" là việc chính, không phải hai nút cam cạnh nhau
        // (soát UX 29-09).
        <Button
          variant={book.phase === "done" && !book.pendingChanges ? "primary" : "secondary"}
          size="lg"
          icon={Headphones}
          onClick={() => navigate(`/book/${book.id}`)}
        >
          Nghe trong Thư viện
        </Button>
      )}
      {book.queuePosition ? (
        <>
          <span className="inline-flex h-11 items-center gap-2 rounded-xl bg-warning-soft px-4 text-sm font-medium text-warning">
            Đang xếp hàng · thứ {book.queuePosition} - tự bắt đầu khi cuốn đang chạy xong
          </span>
          <Button variant="ghost" size="lg" onClick={() => stop.mutate(book.id)}>
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
            <Button variant="primary" size="lg" icon={Play} loading={pause.isPending} onClick={() => pause.mutate({ id: book.id, paused: false })}>
              Tiếp tục
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
        <Button variant="primary" size="lg" icon={Wand2} loading={start.isPending} onClick={() => start.mutate(book.id)}>
          Bắt đầu tạo sách nói
        </Button>
      ) : book.phase !== "done" ? (
        <Button variant="primary" size="lg" icon={Play} loading={start.isPending} onClick={() => start.mutate(book.id)}>
          Tiếp tục tạo
        </Button>
      ) : book.pendingChanges ? (
        // Sách đã xong không tự chạy lại: sửa của người nghe chờ ở đây. Chạy lại áp chúng trước rồi chỉ thu lại câu bị ảnh
        // hưởng (Pipeline._recover) - không làm lại cả cuốn.
        <Button variant="primary" size="lg" icon={RefreshCw} loading={start.isPending} onClick={() => start.mutate(book.id)}>
          Áp dụng {book.pendingChanges} thay đổi
        </Button>
      ) : null}
      {next > 0 && (
        <Button variant="secondary" size="lg" icon={BookPlus} onClick={() => navigate(`/studio/new?continue=${book.id}`)}>
          Làm tiếp cuốn này · {next} chương mới
        </Button>
      )}
      {!remote && <IconButton label="Mở thư mục sách" icon={FolderOpen} onClick={() => reveal.mutate(book.id)} />}
      {/* Đổi tên / xoá chỉ trên máy này - Studio từ xa không có hai đường ấy (remote_studio.ALLOWED). */}
      {!remote && <ProjectMenu book={book} />}
      <StopDialog book={book} open={confirmStop} onOpenChange={setConfirmStop} />
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
  if (chapter.status === "completed") return "success" as const;
  if (chapter.status === "failed") return "danger" as const;
  if (chapter.status === "synthesizing" || chapter.status === "verifying") return "accent" as const;
  return "muted" as const;
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
        "group grid h-14 grid-cols-[40px_minmax(0,1fr)_auto] md:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px] items-center gap-3 rounded-lg px-2 text-sm",
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
          <div className="truncate text-xs text-danger">{chapter.lastError}</div>
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
      <div className="tabular hidden text-right text-xs text-fg-2 md:block">
        {chapter.status === "completed" ? formatLength(chapter.seconds) : chapter.segments.total ? `${formatNumber(chapter.segments.total)} câu` : ""}
      </div>
      <div className="tabular hidden whitespace-nowrap text-right text-xs text-fg-3 md:block">
        {chapter.completedAt ? formatRelative(chapter.completedAt) : ""}
      </div>
    </div>
  );
}

function ChapterList({ book, chapters }: { book: BookSummary; chapters: Chapter[] }) {
  return (
    <div role="table" aria-label="Danh sách chương" className="mt-2">
      <div className="grid h-9 grid-cols-[40px_minmax(0,1fr)_auto] md:grid-cols-[48px_minmax(0,1fr)_150px_110px_96px] items-center gap-3 border-b border-line px-2 text-[11px] font-semibold uppercase tracking-wider text-fg-3">
        <span className="text-center">#</span>
        <span>Chương</span>
        <span>Trạng thái</span>
        {/* Màn hẹp (điện thoại, Studio từ xa) chỉ còn #, chương, trạng thái - soát UX 29-09: 5 cột cố định vỡ ở 375px. */}
        <span className="hidden text-right md:block">Độ dài</span>
        <span className="hidden text-right md:block">Xong lúc</span>
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

export function ProjectScreen() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = ["chapters", "work", "script", "review", "cast", "activity"].includes(params.get("tab") ?? "") ? params.get("tab")! : "chapters";
  const reviewCount = useReviewCount(id ?? "");
  const workCount = useWorkCount(id ?? "");
  const { data, isLoading, error } = useBook(id);
  const [picking, setPicking] = useState<{ name: string; displayName: string } | null>(null);
  usePageTitle(data ? `${data.book.title} · Studio` : undefined);

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
    book.createdAt && `Tạo ${formatDate(book.createdAt)}`,
  ].filter(Boolean);

  return (
    <div className="mx-auto max-w-[1180px] px-4 pb-16 pt-7 sm:px-10">
      <button type="button" onClick={() => navigate("/studio")} className="inline-flex items-center gap-1.5 text-sm text-fg-2 hover:text-fg">
        <ArrowLeft className="size-4" /> Studio
      </button>
      {/* Màn hẹp (Studio từ xa trên điện thoại): bìa trên, tên và nút dưới - cạnh nhau thì nút tràn mép. */}
      <header className="mt-5 flex flex-col gap-5 sm:flex-row sm:gap-7">
        <CoverEditor book={book} />
        <div className="min-w-0 flex-1 pt-1">
          <StatusPill
            label={book.starting ? "Đang khởi động" : book.statusLabel}
            tone={book.paused ? "warning" : phaseTone(book.phase, live)}
            live={live && !book.paused}
          />
          <h1 className="mt-3 text-2xl font-bold leading-tight tracking-tight sm:text-[30px]">{book.title}</h1>
          <p className="mt-2 text-sm text-fg-2">{meta.join(" · ")}</p>
          <PartLinks id={book.id} />
          {book.phase === "done" || book.audioSeconds > 0 ? (
            <p className="tabular mt-1 text-sm text-fg-2">
              {formatLength(book.audioSeconds)} audio · {book.chapters.completed - (book.chapters.missingAudio ?? 0)}/{book.chapters.total} chương nghe được
              {book.chapters.missingAudio ? (
                <span className="font-medium text-warning"> · {book.chapters.missingAudio} chương mất file audio</span>
              ) : null}
              {book.position && (
                <span className="text-fg-3"> · lần nghe cuối {formatRelative(book.position.at)} ở {formatClock(book.position.seconds)}</span>
              )}
            </p>
          ) : null}
          <Actions book={book} />
        </div>
      </header>

      {book.phase !== "done" && <ProductionPanel book={book} />}

      <Tabs value={tab} onValueChange={(value) => setParams({ tab: value }, { replace: true })} className="mt-9">
        <TabsList>
          <TabsTrigger value="chapters" count={chapters.length}>
            Chương
          </TabsTrigger>
          <TabsTrigger value="work" count={workCount || undefined}>
            Việc cần duyệt
          </TabsTrigger>
          <TabsTrigger value="script">Kịch bản</TabsTrigger>
          <TabsTrigger value="review" count={reviewCount || undefined}>
            Cần nghe lại
          </TabsTrigger>
          <TabsTrigger value="cast">Nhân vật</TabsTrigger>
          <TabsTrigger value="activity">Nhật ký</TabsTrigger>
        </TabsList>
        <TabsContent value="chapters">
          <ChapterList book={book} chapters={chapters} />
        </TabsContent>
        <TabsContent value="work">
          <WorkInbox
            book={book}
            onOpenReview={() => setParams({ tab: "review" }, { replace: true })}
            onOpenScript={(chapterId, stableId, pick = true) =>
              setParams({ tab: "script", chapter: String(chapterId), line: stableId, ...(pick ? {} : { pick: "0" }) }, { replace: true })
            }
            onOpenNames={(name) => setParams({ tab: "cast", focus: "names", ...(name ? { name } : {}) }, { replace: true })}
          />
        </TabsContent>
        <TabsContent value="script">
          <ScriptTab bookId={book.id} />
        </TabsContent>
        <TabsContent value="review">
          <ReviewQueue
            bookId={book.id}
            onOpenScript={(chapterId, stableId) =>
              setParams({ tab: "script", chapter: String(chapterId), line: stableId }, { replace: true })
            }
          />
        </TabsContent>
        <TabsContent value="cast">
          <CastList bookId={book.id} onPickVoice={(person) => setPicking({ name: person.name, displayName: person.displayName })} />
          <VoicePicker bookId={book.id} person={picking} onClose={() => setPicking(null)} />
          <NameReadings bookId={book.id} focus={params.get("focus") === "names"} name={params.get("name") ?? ""} />
        </TabsContent>
        <TabsContent value="activity">
          <ActivityView book={book} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
