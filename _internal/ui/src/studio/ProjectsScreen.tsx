import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, FolderOpen, History, MoreHorizontal, Plus, RotateCw } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { RowBoundary } from "@/shared/RowBoundary";
import { etaOf, formatPercent, formatRelative } from "@/shared/format";
import { Button, Dialog, EmptyState, failedEmpty, IconButton, LoadError, Progress, Skeleton, StatusPill } from "@/shared/ui";
import { ScreenHeader } from "@/shared/ScreenHeader";
import { DotJoin } from "@/shared/DotJoin";
import { MissingLibrary } from "@/shared/MissingLibrary";
import { api, type BookSummary } from "./api";
import { pickFolder, projectStatus, useAppInfo, useLibrary, useOpenBook, useReveal } from "./data";
import { MenuItem, ProjectMenu } from "./ProjectScreen";
import { StudioSetupCard } from "./StudioSetup";
import { groupParts, splitLive, type Entry } from "./projectGroups";

// Studio: nơi làm sách. Danh sách là bảng công việc gọn - tên · trạng thái · tiến độ · cập nhật (DESIGN.md mục 7) - chứ không
// phải kệ sách (kệ sách là của phía Nghe). Bảng phẳng: vạch mảnh giữa các hàng, không khung; việc hiếm của một hàng ở "…".

/** Cột của bảng: màn hẹp (Studio từ xa trên điện thoại) trạng thái và tiến độ xếp dưới tên, không chia cột. */
const COLUMNS = "grid-cols-[40px_minmax(0,1fr)_36px] md:grid-cols-[40px_minmax(0,1fr)_190px_170px_36px] xl:grid-cols-[40px_minmax(0,1fr)_230px_190px_100px]";
// Máy tính rộng: không chừa cột riêng cho "…" (cột trống làm lề phải 61 px so với lề trái 11 px, soát 24-10) - "…" hiện đúng chỗ cột Cập nhật khi rê / mở menu, chữ cập nhật mờ đi.

/** Một hàng lỗi khi vẽ (dữ liệu thiếu) chỉ làm hàng ấy báo "Không đọc được", không trắng cả danh sách. */
function ProjectRow({ book }: { book: BookSummary }) {
  return (
    <RowBoundary
      fallback={
        <div className="px-3 py-3 text-sm">
          <span className="font-medium">{book.title}</span> <span className="text-xs text-danger">Không đọc được dự án này</span>
        </div>
      }
    >
      <ProjectRowBody book={book} />
    </RowBoundary>
  );
}

/** Dự án không mở được. Đang bị chương trình khác giữ (diệt virus, sao lưu) thì KHÔNG phải hỏng - chỉ Thử lại / Mở thư mục, không mời xoá
 *  (soát a28 lỗi 5). Hỏng thật: mở thư mục, khôi phục từ bản sao cũ cạnh nó nếu có (lỗi 13), hay xoá (vào Thùng rác) - ở "…". */
function BrokenRow({ book, local }: { book: BookSummary; local: boolean }) {
  const client = useQueryClient();
  const reveal = useReveal();
  const [asking, setAsking] = useState(false);
  const busy = book.brokenKind === "busy";
  const restore = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/restore-backup`, { method: "POST" }),
    onSuccess: () => {
      setAsking(false);
      toast.success(`Đã khôi phục “${book.title}” từ bản sao`);
    },
    onError: (error: Error) => toast.error("Chưa khôi phục được", { description: error.message }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["library"] }),
  });
  return (
    <div className={cn("grid items-center gap-x-4 px-3 py-3 text-sm", COLUMNS)}>
      <span aria-hidden className="size-10 rounded-lg bg-hover" />
      <div className="min-w-0 md:col-span-2 xl:col-span-3">
        <div className="truncate font-medium">{book.title}</div>
        <div className={cn("truncate text-xs", busy ? "text-warning" : "text-danger")}>
          {busy ? "Chưa mở được: " : "Không đọc được: "}
          {book.broken}
        </div>
      </div>
      <div className="col-span-full flex items-center justify-end gap-1 md:col-span-1">
        {busy ? (
          <>
            <IconButton label="Thử lại" icon={RotateCw} onClick={() => void client.invalidateQueries({ queryKey: ["library"] })} />
            {local && <IconButton label="Mở thư mục" icon={FolderOpen} onClick={() => reveal.mutate(book.id)} />}
          </>
        ) : local ? (
          <ProjectMenu book={book} rename={false}>
            {book.backup && <MenuItem icon={History} onSelect={() => setAsking(true)}>Khôi phục bản sao…</MenuItem>}
            <MenuItem icon={FolderOpen} onSelect={() => reveal.mutate(book.id)}>Mở thư mục</MenuItem>
          </ProjectMenu>
        ) : (
          // Studio từ xa: khôi phục bản sao, mở thư mục, xoá đều là việc ngay trên máy tính - nói thẳng thay vì để chỗ trống.
          <OnComputerOnly verb="Khôi phục hoặc xoá" />
        )}
      </div>
      <Dialog
        open={asking}
        onOpenChange={setAsking}
        title={`Khôi phục “${book.title}” từ bản sao cũ?`}
        description="Việc làm sau lần nâng cấp phải làm lại; chương đã thu và bản hỏng vẫn được giữ."
      >
        <div className="mt-5 dialog-actions">
          <Button variant="ghost" onClick={() => setAsking(false)}>
            Để sau
          </Button>
          <Button variant="primary" icon={History} loading={restore.isPending} onClick={() => restore.mutate()}>
            Khôi phục
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

function ProjectRowBody({ book }: { book: BookSummary }) {
  const navigate = useNavigate();
  const reveal = useReveal();
  // Dự án hỏng: khôi phục / mở thư mục / xoá chỉ trên máy này. Dự án bình thường: menu nào cũng hiện, Studio từ xa chỉ thay dòng Xoá bằng lý do.
  const local = !useAppInfo().data?.remote;
  const live = book.running || book.starting;
  // Hàng hỏng <-> thường (sau "Thử lại"): cùng một vùng ở cả hai nhánh, khoá theo loại hàng - mờ qua, không thay cứng.
  if (book.broken) return <MotionRegion motionKey="broken"><BrokenRow book={book} local={local} /></MotionRegion>;
  const status = projectStatus(book);
  const detail =
    book.phase !== "done" && book.eta && live ? etaOf(book, true) : `${book.chapters.completed}/${book.chapters.total} chương`;
  const needs = [
    book.pendingChanges ? `${book.pendingChanges} thay đổi chờ áp` : book.phase === "done" && book.chapters.redo ? `${book.chapters.redo} chương chờ thu lại` : "",
    book.chapters.missingAudio ? `${book.chapters.missingAudio} chương mất audio` : "",
  ].filter(Boolean);
  return (
    // Nút "…" nằm NGOÀI nút của dòng (nút lồng nút không hợp lệ), đè lên cột cuối mà dòng chừa sẵn.
    <MotionRegion motionKey="row" className="group relative">
      <button
        type="button"
        onClick={() => navigate(`/studio/${book.id}`)}
        className={cn("grid w-full items-center gap-x-4 gap-y-1 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-hover", COLUMNS)}
      >
        <BookCover title={book.title} part={book.series?.part} size="sm" image={book.cover} className="row-span-3 size-10 self-start md:row-span-1 md:self-center" />
        <div className="min-w-0">
          <div className="truncate font-medium">{book.title}</div>
          <div className="truncate text-[0.8125rem] text-fg-2">
            {/* Chất lượng "Cân bằng" là mặc định của gần mọi dự án: chữ giống nhau trên mọi hàng thì chỉ ghi ở hàng KHÁC (soát 25-10). */}
            <DotJoin parts={[book.settings.narrator && `Giọng kể ${book.settings.narrator}`, book.settings.profile !== "balanced" && book.settings.profileLabel]} />
          </div>
        </div>
        <div className="col-start-2 md:col-start-auto">
          {/* Xong là mặc định, không đeo nhãn trên mọi hàng; chỉ dự án chưa xong mới có viên trạng thái (cùng chữ, cùng màu với đầu trang dự án). */}
          {book.phase === "done" && !book.queuePosition ? <span className="sr-only">{status.label}</span> : <StatusPill label={status.label} tone={status.tone} live={status.live} />}
        </div>
        {/* Ô tiến độ: số (chữ số) đổi không mờ; xong <-> đang làm, nhãn việc còn lại hiện / mất (0 -> N) thì mờ qua tại chỗ. */}
        <MotionRegion motionKey={[book.phase === "done", Boolean(book.pendingChanges), Boolean(book.chapters.redo), Boolean(book.chapters.missingAudio)]} className="col-start-2 min-w-0 md:col-start-auto">
          {book.phase === "done" ? (
            <span className="text-xs text-fg-2">
              {detail}
              {/* Sách "Hoàn tất" mà còn việc của mình: nói ngay trên dòng (soát UX a6 01-10 - nhìn danh sách không biết cuốn nào cần mình). */}
              {needs.length > 0 && <span className="font-medium text-warning"> · {needs.join(" · ")}</span>}
            </span>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <Progress value={book.progress.overall} running={live} tone={live ? "accent" : "muted"} size="sm" label={`Tiến độ: ${book.title}`} />
                <span className="tabular w-9 text-right text-xs font-medium">{formatPercent(book.progress.overall)}</span>
              </div>
              <div className="mt-1 line-clamp-2 text-xs text-fg-2">{detail}</div>
            </>
          )}
        </MotionRegion>
        <div
          className={cn("tabular hidden text-right text-xs transition-opacity duration-motion-fast group-focus-within:opacity-0 group-hover:opacity-0 group-has-[[data-state=open]]:opacity-0 xl:block text-fg-2")}
        >
          {/* Trạng thái đã ở cột Trạng thái - cột này chỉ nói lúc nào (soát 24-10: "đang chạy" lặp lại "Đang thu âm"). */}
          {live ? "vừa xong" : formatRelative(book.updatedAt)}
        </div>
      </button>
      <div className="absolute right-[3.75px] top-2.5 pointer-coarse:right-[-4.5px] max-sm:right-[-4.5px] md:top-1/2 md:-translate-y-1/2">
        <ProjectMenu
          book={book}
          className="opacity-0 transition-opacity duration-motion-fast focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100"
        >
          {local && <MenuItem icon={FolderOpen} onSelect={() => reveal.mutate(book.id)}>Mở thư mục</MenuItem>}
        </ProjectMenu>
      </div>
    </MotionRegion>
  );
}

/** Một dòng dự án, hay các phần của một cuốn ("lo18 · 2 phần") dưới một dòng tên nhóm - thụt vào, không khung. */
function EntryView({ entry }: { entry: Entry }) {
  if (entry.kind === "book") return <ProjectRow book={entry.book} />;
  return (
    <section aria-label={entry.name}>
      <h3 className="px-3 pb-0.5 pt-3 text-xs font-medium text-fg-2">
        {entry.name} <span className="font-normal">· {entry.books.length} {entry.unit}</span>
      </h3>
      {entry.books.map((book) => (
        <ProjectRow key={book.id} book={book} />
      ))}
    </section>
  );
}

const entryKey = (entry: Entry) => (entry.kind === "book" ? entry.book.id : `series:${entry.name}`);

/** Đầu bảng: cùng một hàng khi đang tải và khi đã có dự án - khung chờ đứng đúng chỗ các hàng thật, tải xong không nhảy. */
function TableHead() {
  return (
    <div className={cn("mx-3 hidden gap-x-4 border-b border-line pb-2 label-section text-fg-2 md:grid", COLUMNS)}>
      <span />
      <span>Dự án</span>
      <span>Trạng thái</span>
      <span>Tiến độ</span>
      <span className="hidden text-right xl:block">Cập nhật</span>
    </div>
  );
}

/** Khung chờ đúng hình một hàng của bảng (DESIGN.md mục 2: không vòng xoay giữa màn): hai vạch đứng trong hai hộp dòng của tên và dòng phụ. */
function RowSkeleton() {
  return (
    <div className={cn("grid items-center gap-x-4 px-3 py-2.5", COLUMNS)}>
      <Skeleton className="size-10 rounded-lg" />
      <div>
        <div className="flex h-6 items-center"><Skeleton className="h-4 w-1/2" /></div>
        <div className="flex h-[1.21875rem] items-center"><Skeleton className="h-3 w-1/3" /></div>
      </div>
      <Skeleton className="hidden h-6 w-28 rounded-full md:block" />
      <Skeleton className="hidden h-1.5 w-full md:block" />
      <Skeleton className="hidden h-3 w-16 justify-self-end xl:block" />
    </div>
  );
}

/** "…" của đầu trang: việc hiếm của cả Studio. */
function StudioMenu({ onOpenExisting }: { onOpenExisting: () => void }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Tuỳ chọn Studio"
          className="touch-box inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-fg-2 transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover"
        >
          <MoreHorizontal className="glyph ink-end" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] min-w-52 overflow-y-auto overscroll-contain rounded-xl border border-line bg-panel p-1.5 shadow-float">
          <MenuItem icon={FolderOpen} onSelect={onOpenExisting}>Mở dự án có sẵn…</MenuItem>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function ProjectsScreen() {
  const libraryQuery = useLibrary();
  const { data, isLoading } = libraryQuery;
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  const open = useOpenBook();
  const books = useMemo(() => data?.books ?? [], [data]);
  // Nhóm phần trước, rồi mới đưa nhóm đang chạy lên đầu: một phần đang chạy kéo cả nhóm của nó lên, không để phần 2 ở trên và
  // phần 1 đứng lẻ bên dưới (soát UX 30-09).
  const entries = useMemo(() => {
    const { live, rest } = splitLive(groupParts(books));
    return [...live, ...rest];
  }, [books]);
  // Rỗng thì lời mời giữa trang là nút duy nhất; đầu trang không lặp lại nó.
  const empty = !isLoading && !libraryQuery.isError && !data?.rootMissing && !books.length;

  const openExisting = async () => {
    try {
      const path = await pickFolder("Chọn thư mục một cuốn sách đã tạo");
      if (!path) return;
      const result = await open.mutateAsync(path);
      navigate(`/studio/${result.id}`);
    } catch (error) {
      toast.error("Không mở được sách", { description: (error as Error).message });
    }
  };

  return (
    <MotionRegion as="div" className="page-x mx-auto max-w-[1180px] pb-16">
      {/* Nút đầu trang cùng hàng (căn giữa) với tiêu đề, biểu tượng cuối thẳng mép phải bảng - như đầu trang Thư viện (soát 24-10). */}
      <ScreenHeader
        title="Studio"
        actions={
          <div className={cn("-my-1 flex items-center gap-1", info?.dialogs ? "-mr-[6.75px] pointer-coarse:-mr-[15px] max-sm:-mr-[15px]" : "-mr-3.5")}>
            <MotionPresence open={!empty}>
              <Button variant="ghost" icon={Plus} onClick={() => navigate("/studio/new")}>
                Dự án mới
              </Button>
            </MotionPresence>
            {info?.dialogs && <StudioMenu onOpenExisting={() => void openExisting()} />}
          </div>
        }
        // Rỗng: lời giữa trang đã nói "Chưa có dự án" - dòng phụ giữ một dòng trống như Thư viện, không lặp lại (soát 25-10).
        subtitle={books.length ? `${books.length} dự án` : "\u00a0"}
      />

      <StudioSetupCard className="mt-8" />

      {isLoading ? (
        <div className="-mx-3 mt-8" aria-hidden>
          <TableHead />
          <div className="rows-inset [--rows-inset:calc(var(--spacing)*3)]">
            {Array.from({ length: 5 }, (_, index) => (
              <RowSkeleton key={index} />
            ))}
          </div>
        </div>
      ) : failedEmpty({ isError: libraryQuery.isError, data: data?.books }) ? (
        <LoadError what="danh sách dự án" error={libraryQuery.error} onRetry={() => void libraryQuery.refetch()} className="mt-12" />
      ) : data?.rootMissing ? (
        <MissingLibrary root={data.root} className="mt-12" />
      ) : !books.length ? (
        // Rỗng: một câu + một nút dẫn tới việc tạo (DESIGN.md mục 2), không khung.
        // Cùng EmptyState và cùng khoảng cách dưới đầu màn với Thư viện trống (soát 25-10: hai màn trống hai kiểu, hai độ cao).
        <EmptyState icon={Clapperboard} title="Chưa có dự án" className="mt-12"
          action={<Button variant="primary" size="lg" icon={Plus} onClick={() => navigate("/studio/new")}>Dự án mới</Button>}>
          Biến một truyện thành sách nói nhiều giọng.
        </EmptyState>
      ) : (
        // Lề âm bù đệm của dòng: bìa thẳng mép tiêu đề, cột cuối thẳng mép phải; nền rê chuột và vạch kẻ tràn ra lề.
        <section className="-mx-3 mt-8" aria-label="Dự án">
          <TableHead />
          <AnimatedRows items={entries} keyOf={entryKey} className="rows-inset [--rows-inset:calc(var(--spacing)*3)]">
            {(entry) => <EntryView entry={entry} />}
          </AnimatedRows>
        </section>
      )}
    </MotionRegion>
  );
}
