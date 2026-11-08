import { S } from "../shared/strings.generated";
import { TickingValue } from "@/shared/TickingValue";
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
import { DialogActions, Button, Dialog, EmptyState, failedEmpty, IconButton, LoadError, Progress, Skeleton, StatusPill } from "@/shared/ui";
import { ScreenHeader } from "@/shared/ScreenHeader";
import { DotJoin } from "@/shared/DotJoin";
import { MissingLibrary } from "@/shared/MissingLibrary";
import { api, type BookSummary } from "./api";
import { pickFolder, projectStatus, useAppInfo, useLibrary, useOpenBook, useReveal } from "./data";
import { MenuItem, ProjectMenu } from "./ProjectScreen";
import { StudioSetupCard } from "./StudioSetup";
import { groupParts, splitLive, type Entry } from "./projectGroups";
import { PICK_SOURCE } from "./pickSource";

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
          <span className="font-medium">{book.title}</span> <span className="text-xs text-danger">{S.s_chua_doc_duoc_du_an_nay_0125b947}</span>
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
      toast.success(S.s_da_khoi_phuc_0_tu_ban_sao_ca4e9d3a(book.title));
    },
    onError: (error: Error) => toast.error(S.s_chua_khoi_phuc_duoc_4cd0f749, { description: error.message }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["library"] }),
  });
  return (
    <div className={cn("grid items-center gap-x-4 px-3 py-3 text-sm", COLUMNS)}>
      <span aria-hidden className="size-10 rounded-control bg-hover" />
      <div className="min-w-0 md:col-span-2 xl:col-span-3">
        <div className="truncate font-medium">{book.title}</div>
        <div className={cn("truncate text-xs", busy ? "text-warning" : "text-danger")}>
          {busy ? S.s_chua_mo_duoc_ffa5657d : S.s_chua_doc_duoc_2213ed66}
          {book.broken}
        </div>
      </div>
      <div className="col-span-full flex items-center justify-end gap-1 md:col-span-1">
        {busy ? (
          <>
            <IconButton label={S.s_thu_lai_c58d068c} icon={RotateCw} onClick={() => void client.invalidateQueries({ queryKey: ["library"] })} />
            {local && <IconButton label={S.s_mo_thu_muc_4bf5b127} icon={FolderOpen} onClick={() => reveal.mutate(book.id)} />}
          </>
        ) : local ? (
          <ProjectMenu book={book} rename={false}>
            {book.backup && <MenuItem icon={History} onSelect={() => setAsking(true)}>{S.s_khoi_phuc_ban_sao_6b7c7c6e}</MenuItem>}
            <MenuItem icon={FolderOpen} onSelect={() => reveal.mutate(book.id)}>{S.s_mo_thu_muc_4bf5b127}</MenuItem>
          </ProjectMenu>
        ) : (
          // Studio từ xa: khôi phục bản sao, mở thư mục, xoá đều là việc ngay trên máy tính - nói thẳng thay vì để chỗ trống.
          <OnComputerOnly verb={S.s_khoi_phuc_hoac_xoa_9cc4c06f} />
        )}
      </div>
      <Dialog footer={<DialogActions>
          <Button variant="ghost" onClick={() => setAsking(false)}>{S.s_de_sau_9be0a7ab}</Button>
          <Button variant="primary" icon={History} loading={restore.isPending} onClick={() => restore.mutate()}>{S.s_khoi_phuc_c652d9c0}</Button>
        </DialogActions>}
        open={asking}
        onOpenChange={setAsking}
        title={S.s_khoi_phuc_0_tu_ban_sao_cu_a4f1f8c9(book.title)}
        description={S.s_viec_lam_sau_lan_nang_cap_phai_lam_lai_chu_7773cc03}
      >

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
    book.phase !== "done" && book.eta && live ? etaOf(book, true) : S.s_0_1_chuong_8d58e1df(book.chapters.completed, book.chapters.total);
  const needs = [
    book.pendingChanges ? S.s_0_thay_doi_cho_ap_e465c566(book.pendingChanges) : book.phase === "done" && book.chapters.redo ? S.s_0_chuong_cho_thu_lai_043b38de(book.chapters.redo) : "",
    book.chapters.missingAudio ? S.s_0_chuong_mat_audio_865ee6e4(book.chapters.missingAudio) : "",
  ].filter(Boolean);
  return (
    // Nút "…" nằm NGOÀI nút của dòng (nút lồng nút không hợp lệ), đè lên cột cuối mà dòng chừa sẵn.
    <MotionRegion motionKey="row" className="project-row group relative">
      <button
        type="button"
        onClick={() => navigate(`/studio/${book.id}`)}
        className={cn("grid w-full items-center gap-x-4 gap-y-1 rounded-control px-3 py-2.5 text-left transition-colors hover:bg-hover", COLUMNS)}
      >
        <BookCover title={book.title} part={book.series?.part} size="sm" image={book.cover} className="row-span-3 size-10 self-start md:row-span-1 md:self-center" />
        <div className="min-w-0">
          <div className="truncate font-medium">{book.title}</div>
          <div className="truncate text-[0.8125rem] text-fg-2">
            {/* Chất lượng "Cân bằng" là mặc định của gần mọi dự án: chữ giống nhau trên mọi hàng thì chỉ ghi ở hàng KHÁC (soát 25-10). */}
            <DotJoin parts={[book.settings.narrator && S.s_giong_ke_0_958dd853(book.settings.narrator), book.settings.profile !== "balanced" && book.settings.profileLabel]} />
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
                <Progress value={book.progress.overall} running={live} tone={live ? "accent" : "muted"} size="sm" label={S.s_tien_do_0_bebc77d0(book.title)} />
                <span className="tabular w-9 text-right text-xs font-medium"><TickingValue>{formatPercent(book.progress.overall)}</TickingValue></span>
              </div>
              <div className="mt-1 line-clamp-2 text-xs text-fg-2"><TickingValue>{detail}</TickingValue></div>
            </>
          )}
        </MotionRegion>
        <div
          className={cn("project-updated tabular hidden text-right text-xs transition-opacity duration-motion-fast group-focus-within:opacity-0 group-hover:opacity-0 xl:block text-fg-2")}
        >
          {/* Trạng thái đã ở cột Trạng thái - cột này chỉ nói lúc nào (soát 24-10: "đang chạy" lặp lại "Đang thu âm"). */}
          {live ? S.s_vua_xong_b46f7a2b : formatRelative(book.updatedAt)}
        </div>
      </button>
      <div className="absolute right-[3.75px] top-2.5 pointer-coarse:right-[-4.5px] max-sm:right-[-4.5px] md:top-1/2 md:-translate-y-1/2">
        <ProjectMenu
          book={book}
          className="opacity-0 transition-opacity duration-motion-fast focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100"
        >
          {local && <MenuItem icon={FolderOpen} onSelect={() => reveal.mutate(book.id)}>{S.s_mo_thu_muc_4bf5b127}</MenuItem>}
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
      <h2 className="px-3 pb-0.5 pt-3 text-xs font-medium text-fg-2">
        {entry.name} <span className="font-normal">· {entry.books.length} {entry.unit}</span>
      </h2>
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
      <span>{S.s_du_an_4f139d43}</span>
      <span>{S.s_trang_thai_cb31de81}</span>
      <span>{S.s_tien_do_e5947845}</span>
      <span className="hidden text-right xl:block">{S.s_cap_nhat_5293d03c}</span>
    </div>
  );
}

/** Khung chờ đúng hình một hàng của bảng (DESIGN.md mục 2: không vòng xoay giữa màn): hai vạch đứng trong hai hộp dòng của tên và dòng phụ. */
function RowSkeleton() {
  return (
    <div className={cn("grid items-center gap-x-4 px-3 py-2.5", COLUMNS)}>
      <Skeleton className="size-10 rounded-control" />
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
          aria-label={S.s_tuy_chon_studio_16c07366}
          className="touch-box inline-flex size-9 shrink-0 items-center justify-center rounded-control text-fg-2 transition-colors hover:bg-hover hover:text-fg data-[state=open]:bg-hover"
        >
          <MoreHorizontal className="glyph ink-end" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] min-w-52 overflow-y-auto overscroll-contain rounded-cover border border-line bg-panel p-1.5 shadow-float">
          <MenuItem icon={FolderOpen} onSelect={onOpenExisting}>{S.s_mo_du_an_f990c9d8}</MenuItem>
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
      const path = await pickFolder(S.s_chon_thu_muc_mot_cuon_sach_da_tao_9b48464a);
      if (!path) return;
      const result = await open.mutateAsync(path);
      navigate(`/studio/${result.id}`);
    } catch (error) {
      toast.error(S.s_chua_mo_duoc_sach_86cc68d3, { description: (error as Error).message });
    }
  };

  return (
    <MotionRegion as="div" className="page-x mx-auto max-w-[1180px] pb-16">
      {/* Nút đầu trang cùng hàng (căn giữa) với tiêu đề, biểu tượng cuối thẳng mép phải bảng - như đầu trang Thư viện (soát 24-10). */}
      <ScreenHeader
        title={S.s_studio_0aa91af2}
        actions={
          <div className={cn("-my-1 flex items-center gap-1", info?.dialogs ? "-mr-[6.75px] pointer-coarse:-mr-[15px] max-sm:-mr-[15px]" : "-mr-3.5")}>
            <MotionPresence open={!empty}>
              <Button variant="ghost" icon={Plus} onClick={() => navigate("/studio/new", PICK_SOURCE)}>{S.s_du_an_moi_992d22b2}</Button>
            </MotionPresence>
            {info?.dialogs && <StudioMenu onOpenExisting={() => void openExisting()} />}
          </div>
        }
        // Rỗng: lời giữa trang đã nói "Chưa có dự án" - dòng phụ giữ một dòng trống như Thư viện, không lặp lại (soát 25-10).
        subtitle={books.length ? S.s_0_du_an_b2ada839(books.length) : "\u00a0"}
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
        <LoadError what={S.s_danh_sach_du_an_0b93bfdf} error={libraryQuery.error} onRetry={() => void libraryQuery.refetch()} className="mt-12" />
      ) : data?.rootMissing ? (
        <MissingLibrary root={data.root} className="mt-12" />
      ) : !books.length ? (
        // Rỗng: một câu + một nút dẫn tới việc tạo (DESIGN.md mục 2), không khung.
        // Cùng EmptyState và cùng khoảng cách dưới đầu màn với Thư viện trống (soát 25-10: hai màn trống hai kiểu, hai độ cao).
        <EmptyState icon={Clapperboard} title={S.s_chua_co_du_an_dd6cd3d2} className="mt-12"
          action={<Button variant="primary" size="lg" icon={Plus} onClick={() => navigate("/studio/new", PICK_SOURCE)}>{S.s_du_an_moi_992d22b2}</Button>}>{S.s_bien_mot_truyen_thanh_sach_noi_nhieu_giong_3e0bcdc1}</EmptyState>
      ) : (
        // Lề âm bù đệm của dòng: bìa thẳng mép tiêu đề, cột cuối thẳng mép phải; nền rê chuột và vạch kẻ tràn ra lề.
        <section data-list-edges="studio-projects" className="mt-8" aria-label={S.s_du_an_4f139d43}><div className="-mx-3">
          <TableHead />
          <AnimatedRows items={entries} keyOf={entryKey} className="rows-inset [--rows-inset:calc(var(--spacing)*3)]">
            {(entry) => <EntryView entry={entry} />}
          </AnimatedRows>
        </div></section>
      )}
    </MotionRegion>
  );
}
