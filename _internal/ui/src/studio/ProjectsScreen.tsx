import { FolderOpen, Plus, Wand2 } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { etaOf, formatPercent, formatRelative } from "@/shared/format";
import { Button, EmptyState, Progress, Skeleton, StatusPill } from "@/shared/ui";
import type { BookSummary } from "./api";
import { phaseTone, pickFolder, useAppInfo, useLibrary, useOpenBook } from "./data";
import { ProjectMenu } from "./ProjectScreen";
import { StudioSetupCard } from "./StudioSetup";
import { groupParts, splitLive, type Entry } from "./projectGroups";

// Studio: nơi làm sách. Danh sách là bảng công việc - trạng thái sản xuất, tiến độ, thời gian còn lại - chứ không
// phải kệ sách (kệ sách là của phía Nghe).

function ProjectRow({ book }: { book: BookSummary }) {
  const navigate = useNavigate();
  // Đổi tên / xoá chỉ trên máy này (remote_studio.ALLOWED không có hai đường ấy).
  const local = !useAppInfo().data?.remote;
  const live = book.running || book.starting;
  if (book.broken) {
    // Dự án hỏng không mở được - trước đây cũng không bỏ được khỏi danh sách; giờ xoá được (vào Thùng rác).
    return (
      <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-4 rounded-xl border border-dashed border-line px-4 py-2 text-sm">
        <span className="truncate font-medium">{book.title}</span>
        <span className="text-xs text-danger">Không đọc được: {book.broken}</span>
        {local ? <ProjectMenu book={book} rename={false} /> : <span />}
      </div>
    );
  }
  const detail =
    book.phase === "done"
      ? `${book.chapters.completed}/${book.chapters.total} chương xong`
      : book.eta && live
        ? etaOf(book)
        : `${book.chapters.completed}/${book.chapters.total} chương xong`;
  const needs = [
    book.pendingChanges ? `${book.pendingChanges} thay đổi chờ áp` : "",
    book.chapters.missingAudio ? `${book.chapters.missingAudio} chương mất audio` : "",
  ].filter(Boolean);
  return (
    // Nút "…" nằm NGOÀI nút của dòng (nút lồng nút không hợp lệ), đè lên lề phải mà dòng chừa sẵn (pr-12).
    <div className="group relative">
      <button
        type="button"
        onClick={() => navigate(`/studio/${book.id}`)}
        className={cn(
          "grid w-full grid-cols-[48px_minmax(0,1fr)] items-center gap-x-4 gap-y-1.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-hover md:grid-cols-[48px_minmax(0,1fr)_160px_170px] md:gap-y-4 xl:grid-cols-[48px_minmax(0,1fr)_170px_200px_110px]",
          local && "pr-12",
        )}
      >
        {/* Màn hẹp (Studio từ xa trên điện thoại): trạng thái và tiến độ xếp dưới tên, không chia cột. */}
        <BookCover title={book.title} part={book.series?.part} size="sm" image={book.cover} className="row-span-3 size-12 self-start md:row-span-1 md:self-center" />
        <div className="min-w-0">
          <div className="truncate font-semibold">{book.title}</div>
          <div className="truncate text-xs text-fg-2">
            {book.settings.narrator ? `Giọng kể ${book.settings.narrator} · ` : ""}
            {book.settings.profileLabel}
          </div>
        </div>
        <div className="col-start-2 md:col-start-auto">
          <StatusPill
            label={book.queuePosition ? `Xếp hàng · thứ ${book.queuePosition}` : book.starting ? "Đang khởi động" : book.precast?.held ? "Chờ bạn duyệt" : book.statusLabel}
            // Cùng trạng thái = cùng màu với chip ở trang dự án (soát UX a8 05-10); việc còn lại của sách xong nói ở dòng tiến độ.
            tone={book.queuePosition || book.paused ? "warning" : phaseTone(book.phase, live)}
            live={live && !book.paused}
          />
        </div>
        <div className="col-start-2 min-w-0 md:col-start-auto">
          {book.phase === "done" ? (
            <span className="text-xs text-fg-2">
              {detail}
              {/* Sách "Hoàn tất" mà còn việc của mình: nói ngay trên dòng (soát UX a6 01-10 - lo18 xanh "Hoàn tất" trong khi còn
                  15 thay đổi chờ áp và 40 chương mất audio, nhìn danh sách không biết cuốn nào cần mình). */}
              {needs.length > 0 && <span className="font-medium text-warning"> · {needs.join(" · ")}</span>}
            </span>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <Progress value={book.progress.overall} running={live} tone={live ? "accent" : "muted"} size="sm" />
                <span className="tabular w-9 text-right text-xs font-semibold">{formatPercent(book.progress.overall)}</span>
              </div>
              <div className="mt-1 truncate text-xs text-fg-2">{detail}</div>
            </>
          )}
        </div>
        <div
          className={cn("tabular hidden text-right text-xs xl:block", live ? (book.paused ? "text-warning" : "text-accent-text") : "text-fg-2")}
        >
          {live ? (book.paused ? "tạm dừng" : "đang chạy") : formatRelative(book.updatedAt)}
        </div>
      </button>
      {local && (
        <div className="absolute right-2 top-2.5 md:top-1/2 md:-translate-y-1/2">
          <ProjectMenu
            book={book}
            className="opacity-0 focus-visible:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100"
          />
        </div>
      )}
    </div>
  );
}

/** Một dòng dự án, hay khung các phần của một cuốn ("lo18 · 2 phần"). `inset`: khung nằm trong hộp "Đang chạy" (đã có lề
 *  trong) - không kéo ra lề như trong bảng chính. */
function EntryView({ entry, inset = false }: { entry: Entry; inset?: boolean }) {
  if (entry.kind === "book") return <ProjectRow book={entry.book} />;
  return (
    <section aria-label={entry.name} className={cn("rounded-xl border border-line/70 p-1", !inset && "-mx-[5px]")}>
      <h3 className="px-3 pb-1 pt-1.5 text-xs font-semibold text-fg-2">
        {entry.name} <span className="font-normal text-fg-3">· {entry.books.length} {entry.unit}</span>
      </h3>
      <div className="space-y-0.5">
        {entry.books.map((book) => (
          <ProjectRow key={book.id} book={book} />
        ))}
      </div>
    </section>
  );
}

const entryKey = (entry: Entry) => (entry.kind === "book" ? entry.book.id : `series:${entry.name}`);

export function ProjectsScreen() {
  const { data, isLoading } = useLibrary();
  const { data: info } = useAppInfo();
  const navigate = useNavigate();
  const open = useOpenBook();
  const books = useMemo(() => data?.books ?? [], [data]);
  // Nhóm phần trước, rồi mới tách mục "Đang chạy": một phần đang chạy kéo cả nhóm của nó lên, không để phần 2 ở trên và
  // phần 1 đứng lẻ bên dưới (soát UX 30-09).
  const { live: liveEntries, rest: otherEntries, books: live } = useMemo(() => splitLive(groupParts(books)), [books]);

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
    <div className="mx-auto max-w-[1180px] px-4 pb-16 pt-9 md:px-10">
      <header className="flex flex-wrap items-end justify-between gap-4 md:gap-6">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wider text-accent-text">Studio</div>
          <h1 className="mt-1 text-[28px] font-bold tracking-tight">Dự án sách nói</h1>
          <p className="mt-1 text-sm text-fg-2">
            {books.length ? `${books.length} dự án` : "Chưa có dự án"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {info?.dialogs && (
            <Button variant="ghost" icon={FolderOpen} onClick={() => void openExisting()}>
              Mở dự án có sẵn
            </Button>
          )}
          <Button variant="primary" icon={Plus} onClick={() => navigate("/studio/new")}>
            Tạo sách nói
          </Button>
        </div>
      </header>

      <StudioSetupCard className="mt-8" />

      {isLoading ? (
        <div className="mt-8 space-y-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : !books.length ? (
        <EmptyState
          icon={Wand2}
          title="Biến truyện chữ thành sách nói"
          className="mt-12 rounded-2xl border border-dashed border-line"
          action={
            <Button variant="primary" size="lg" icon={Plus} onClick={() => navigate("/studio/new")}>
              Tạo dự án đầu tiên
            </Button>
          }
        >
          Chọn thư mục chứa các chương TXT. ABook đọc cả truyện, nhận ra từng nhân vật, trao cho mỗi người một
          giọng riêng rồi thu thành MP3 theo chương.
        </EmptyState>
      ) : (
        <>
          {live.length > 0 && (
            <section className="mt-8">
              <h2 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-fg-3">{live.every((book) => book.paused) ? "Đang tạm dừng" : "Đang chạy"}</h2>
              <div className="space-y-0.5 rounded-2xl border border-accent/30 bg-panel p-1.5">
                {liveEntries.map((entry) => (
                  <EntryView key={entryKey(entry)} entry={entry} inset />
                ))}
              </div>
            </section>
          )}
          <section className={cn("mt-8", !otherEntries.length && "hidden")}>
            <div
              className={cn(
                "hidden grid-cols-[48px_minmax(0,1fr)_160px_170px] gap-4 border-b border-line px-3 pb-2 text-xs font-semibold uppercase tracking-[0.06em] text-fg-2 md:grid xl:grid-cols-[48px_minmax(0,1fr)_170px_200px_110px]",
                !info?.remote && "pr-12",
              )}
            >
              <span />
              <span>Dự án</span>
              <span>Trạng thái</span>
              <span>Tiến độ</span>
              <span className="hidden text-right xl:block">Cập nhật</span>
            </div>
            <div className="mt-1.5 space-y-0.5">
              {otherEntries.map((entry) => (
                <EntryView key={entryKey(entry)} entry={entry} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
