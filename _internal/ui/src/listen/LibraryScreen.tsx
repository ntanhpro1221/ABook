import { BookOpen, Headphones, Laptop, Pause, Play, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode, type CSSProperties } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { BookCover } from "@/shared/BookCover";
import { ShortName } from "@/shared/ShortName";
import { cn } from "@/shared/cn";
import { formatLength, formatWhen } from "@/shared/format";
import { EmptyState, Progress, Segmented, Skeleton } from "@/shared/ui";
import { caughtUpDetail, resumeWhere } from "./labels";
import { loadLibrarySort, saveLibrarySort, SORT_OPTIONS, sortBooks, isLibrarySort, type LibrarySort } from "./librarySort";
import { bookMatchesQuery, foldVietnamese, listeningBook, resumePoint, seriesIndex, twinBookIds, twinKind, volumeBadge, type ListenBook } from "./model";
import { usePlayer, type WordTarget } from "./player";
import { useListenLibrary, useReadAloudVoices, useSource } from "./source";

type Filter = "all" | "listening" | "new" | "finished";

function stateOf(book: ListenBook): Filter {
  if (book.progress.finished) return "finished";
  if (book.progress.heardSeconds > 0 || book.state.last) return "listening";
  return "new";
}

/** Dòng trạng thái của một cuốn, cùng một bộ từ ở Thư viện, trang sách và thẻ nghe dở. `speaks`: máy này có giọng đọc (sách chỉ có chữ). */
export function bookStatusText(book: ListenBook, speaks = false): string {
  const status = progressText(book, speaks);
  // Cuốn nằm ở máy khác, nghe thẳng qua mạng - người nghe cần biết mất mạng hay máy kia tắt thì chương chưa tải không nghe được.
  return book.remote ? `${remotePlace(book)} · ${status}` : status;
}

/** "Trên máy tính" (điện thoại nghe máy tính đã ghép) hay "Trên <tên máy>" (máy tính nghe máy tính khác). */
export function remotePlace(book: ListenBook): string {
  return typeof book.remote === "object" && book.remote ? `Trên ${book.remote.computer || "máy khác"}` : "Trên máy tính";
}

function progressText(book: ListenBook, speaks: boolean): string {
  // Sách mới nhập từ EPUB / DOCX / PDF / TXT: có chữ, máy có giọng thì giọng máy đọc (docs/LISTEN_ANYTHING.md mục 1) - cùng lời với trang
  // sách (labels.textBookLine), không ghi "Chỉ có chữ" ngay dưới nút "Nghe ngay".
  // Dòng phụ là NGƯỜI VIẾT sách (tìm sách theo tác giả được, thẻ cũng phải nói). Không có tác giả thì chỉ số chương: tên giọng không phải thông tin về cuốn sách
  // (cuốn nào cũng cùng một giọng), và "Hoài My (Edge)" còn là chuyện kỹ thuật (soát UX a10, a15). Máy chưa có giọng đọc thì nói "Chỉ có chữ".
  if (book.stage === "text") {
    const lead = book.author?.trim() || (speaks ? "" : "Chỉ có chữ");
    return `${lead ? lead + " · " : ""}${book.chaptersTotal} chương`;
  }
  const chapters = `${book.chaptersAvailable}/${book.chaptersTotal} chương`;
  if (book.progress.finished) return "Đã nghe xong";
  if (book.progress.caughtUp) return `Đã nghe hết phần đã có · ${chapters}`;
  if (!book.complete) {
    const lead = book.producing ? "Đang thu âm" : "Chưa hoàn thành";
    return `${lead} · ${chapters}`;
  }
  const left = Math.max(0, book.duration - book.progress.heardSeconds);
  if (book.progress.heardSeconds <= 0) return formatLength(book.duration);
  return `Còn ${formatLength(left)}`;
}

export function usePlayListenBook() {
  const source = useSource();
  const player = usePlayer();
  return async (book: ListenBook, chapterId?: number, at?: number, extra?: { word?: WordTarget }) => {
    // Cuốn đang ở trình phát: tiếp tục đúng chỗ đang phát, không nạp lại (nạp lại là lùi về điểm lưu gần nhất).
    if (chapterId === undefined && player.track?.bookId === book.id) {
      player.resume();
      return;
    }
    const full = book.chapters ? book : await source.book(book.id);
    const chapters = full.chapters ?? [];
    if (chapterId !== undefined) {
      player.play(full, chapters, chapterId, at ?? 0, extra);
      return;
    }
    if (full.progress.caughtUp) {
      toast("Đã nghe hết phần đã có", { description: caughtUpDetail(full.producing) });
      return;
    }
    const point = resumePoint(full, chapters);
    if (point) player.play(full, chapters, point.chapter.id, point.at);
  };
}

/** Mở lại app: thanh phát có sẵn cuốn đang nghe dở (đang dừng) - bấm Space là nghe tiếp, khỏi đi tìm. */
export function useRestoreLastListening() {
  const { data: books } = useListenLibrary(false);
  const player = usePlayer();
  const source = useSource();
  const tried = useRef(false);
  useEffect(() => {
    if (tried.current || !books || player.track) return;
    tried.current = true;
    const recent = listeningBook(books, null);
    if (!recent?.state.last || Date.now() / 1000 - recent.state.last.at > 30 * 86_400) return;
    void source
      .book(recent.id)
      .then((book) => {
        const point = resumePoint(book, book.chapters ?? []);
        if (point) player.prepare(book, book.chapters ?? [], point.chapter.id, point.at);
      })
      .catch(() => undefined);
  }, [books, player, source]);
}

function BookTile({ book, badge, twin }: { book: ListenBook; badge?: string; twin?: boolean }) {
  const navigate = useNavigate();
  const playBook = usePlayListenBook();
  const player = usePlayer();
  const current = player.track?.bookId === book.id;
  const playingHere = current && player.playing;
  // Sách chỉ có chữ: có giọng đọc trên máy thì nút trên bìa là "Nghe ngay" (giọng máy đọc), không thì vẫn là "Đọc".
  const voices = useReadAloudVoices();
  const speaks = (voices.data?.length ?? 0) > 0;
  const textOnly = book.stage === "text" && !speaks;
  return (
    <div className="group">
      <div className="relative">
        {/* Bìa và nút tên bên dưới cùng mở trang sách: bàn phím chỉ dừng ở nút tên (có chữ), bìa vẫn bấm được bằng chuột (soát UX a17: ba điểm Tab mỗi thẻ). */}
        <button type="button" tabIndex={-1} onClick={() => navigate(`/book/${book.id}`)} className="block w-full rounded-lg" aria-label={`Mở ${book.title}`} title={book.remote ? `${book.title} · ${remotePlace(book)}` : undefined}>
          <BookCover title={book.title} part={book.series?.part} badge={badge} size="md" image={book.cover} playing={playingHere} className="w-full" />
        </button>
        <button
          type="button"
          aria-label={textOnly ? `Đọc ${book.title}` : playingHere ? `Tạm dừng ${book.title}` : book.stage === "text" ? `Nghe ngay ${book.title}` : `Nghe ${book.title}`}
          onClick={() => (textOnly ? navigate(`/book/${book.id}/read`) : current ? player.toggle() : void playBook(book))}
          className={cn(
            "touch-hit touch-box absolute bottom-2.5 right-2.5 grid size-10 place-items-center rounded-full bg-accent text-accent-ink shadow-float transition-opacity duration-150 group-hover:opacity-100 focus-visible:opacity-100 max-md:opacity-100",
            current ? "opacity-100" : "opacity-0",
          )}
        >
          {textOnly ? (
            <BookOpen className="size-4" />
          ) : playingHere ? (
            <Pause className="size-4" fill="currentColor" strokeWidth={0} />
          ) : (
            <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
          )}
        </button>
        {book.progress.fraction > 0 && !book.progress.finished && (
          <div className="absolute inset-x-0 bottom-0 h-1 overflow-hidden rounded-b-lg bg-black/40">
            <div className="h-full bg-accent" style={{ width: `${book.progress.fraction * 100}%` }} />
          </div>
        )}
        {book.remote && (
          // Dải dưới bìa, chừa chỗ nút phát bên phải: tên sách vẽ ở ĐẦU bìa, huy hiệu ở góc trên từng đè lên chữ ấy (soát UX a10). Bìa vẽ có nhãn
          // "TẬP n" ở góc dưới trái thì huy hiệu nhích lên trên nhãn.
          <span
            className={cn(
              "pointer-events-none absolute left-2.5 inline-flex max-w-[calc(100%-4.5rem)] items-center gap-1 rounded-full bg-black/60 px-1.5 py-0.5 text-[10px] font-medium text-white",
              book.series?.part || badge ? "bottom-9" : "bottom-2.5",
            )}
          >
            <Laptop className="size-3 shrink-0" />
            <ShortName name={typeof book.remote === "object" && book.remote?.computer ? book.remote.computer : "Máy tính"} short={11} className="truncate" />
          </span>
        )}
      </div>
      <button type="button" onClick={() => navigate(`/book/${book.id}`)} className="touch-row mt-2.5 block w-full text-left">
        <div className={cn("line-clamp-2 text-sm font-semibold leading-snug", current && "text-accent-text")}>{book.title}</div>
        <div className="mt-1 text-xs text-fg-2">{bookStatusText(book, speaks)}</div>
        {/* Hai cuốn cùng tên: nhãn "Dự án" (làm trên máy này) / "Đã nhập" (mở từ file) và ngày vào thư viện để biết cuốn nào là cuốn nào
            (tác giả, nếu có, đã nằm ở dòng trên). */}
        {twin && (twinKind(book) || book.addedAt) ? (
          <div className="mt-0.5 text-xs text-fg-3">
            {[twinKind(book), book.addedAt ? `Thêm ${formatWhen(book.addedAt)}` : ""].filter(Boolean).join(" · ")}
          </div>
        ) : null}
      </button>
    </div>
  );
}

function ContinueCard({ book }: { book: ListenBook }) {
  const navigate = useNavigate();
  const playBook = usePlayListenBook();
  const player = usePlayer();
  const current = player.track?.bookId === book.id;
  const playingHere = current && player.playing;
  const voices = useReadAloudVoices().data;
  const speaks = (voices?.length ?? 0) > 0;
  const last = book.state.last;
  const chapter = (current ? player.track?.chapterTitle : undefined) || book.lastChapterTitle;
  // Cùng dạng với nút chính của trang sách ("Nghe tiếp · Chương 3 · 12:04").
  // Cuốn đang nằm trong trình phát: chỗ nghe đã lưu có thể cũ (chỉ làm mới khi dừng) - nói chương đang phát, không nói giờ cũ.
  const where = current ? (chapter ?? "") : last ? resumeWhere(chapter ?? "", last.seconds) : "";
  return (
    <section className="flex items-center gap-4 rounded-2xl border border-line bg-panel p-4 shadow-card sm:gap-5 sm:p-5">
      <button type="button" onClick={() => navigate(`/book/${book.id}`)} aria-label={`Mở ${book.title}`}>
        <BookCover title={book.title} part={book.series?.part} size="md" image={book.cover} playing={playingHere} className="w-20 sm:w-28" />
      </button>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-semibold uppercase tracking-[0.08em] text-accent-text">Đang nghe dở</div>
        <h2 className="mt-1 line-clamp-2 text-base font-semibold sm:text-lg">{book.title}</h2>
        <p className="tabular mt-0.5 text-sm text-fg-2">
          {where}
          {current ? (playingHere ? " · đang phát" : " · đang tạm dừng") : last ? ` · nghe lần cuối ${formatWhen(last.at)}` : ""}
        </p>
        <p className="mt-0.5 text-sm text-fg-2">{bookStatusText(book, speaks)}</p>
        <Progress value={book.progress.fraction} size="xs" className="mt-3 max-w-md" label="Đã nghe" />
      </div>
      {book.progress.caughtUp && !current ? (
        // Đã nghe hết phần đã có: nút phát lớn chỉ phát 0 giây rồi báo hết - nói thẳng đang chờ chương mới (soát UX 29-09).
        <span className="shrink-0 rounded-full bg-hover px-3 py-1.5 text-xs font-medium text-fg-2">Chờ chương mới</span>
      ) : (
      <button
        type="button"
        onClick={() => (current ? player.toggle() : void playBook(book))}
        aria-label={playingHere ? `Tạm dừng ${book.title}` : `Nghe tiếp ${book.title}${where ? `, ${where}` : ""}`}
        className="grid size-14 shrink-0 place-items-center rounded-full bg-accent text-accent-ink shadow-card transition-transform hover:scale-105"
      >
        {playingHere ? (
          <Pause className="size-6" fill="currentColor" strokeWidth={0} />
        ) : (
          <Play className="size-6 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
        )}
      </button>
      )}
    </section>
  );
}

/** Tập kế tiếp của cùng bộ trong thư viện (nghe xong Tập 16 thì mời Tập 17; phần đầu của "Làm tiếp cuốn này" mời Phần 2). */
export function useNextVolume(bookId: string | undefined, title: string | undefined): ListenBook | null {
  const { data: books } = useListenLibrary(false);
  if (!bookId || !title || !books) return null;
  const places = seriesIndex(books);
  const here = places.get(bookId);
  if (!here || here.volume === null) return null;
  const volume = here.volume;
  return (
    books
      .filter((book) => book.id !== bookId && book.chaptersAvailable > 0)
      .map((book) => ({ book, place: places.get(book.id)! }))
      .filter(({ place }) => place.key === here.key && place.volume !== null && place.volume > volume)
      .sort((a, b) => (a.place.volume ?? 0) - (b.place.volume ?? 0))[0]?.book ?? null
  );
}

function UpcomingCard({ book, onOpen }: { book: ListenBook; onOpen?: (book: ListenBook) => void }) {
  const eta = book.eta && book.eta.phase === "analysis" ? `chương đầu nghe được sau khoảng ${formatLength(book.eta.seconds + 600)}` : "đang chuẩn bị";
  return (
    <button
      type="button"
      onClick={() => onOpen?.(book)}
      disabled={!onOpen}
      className="flex items-center gap-3 rounded-xl border border-dashed border-line-strong bg-panel p-3 text-left hover:border-accent disabled:hover:border-line-strong"
    >
      <BookCover title={book.title} part={book.series?.part} size="sm" image={book.cover} className="size-12 opacity-80" />
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold">{book.title}</span>
        {/* Chưa có chương nghe được không có nghĩa là đang làm: sách dừng trước chương đầu, hay audio bị dời chỗ (soát UX 29-09). */}
        <span className="block text-xs text-fg-2">
          {book.producing && book.pauseReason
            ? book.pauseReason === "battery"
              ? "Đang tạm dừng · máy đang chạy pin"
              : `Đang tạm dừng${onOpen ? " · bấm để làm tiếp" : ""}`
            : book.producing
              ? `Đang làm · ${eta}`
              : `Chưa có chương nghe được${onOpen ? " · bấm để làm tiếp" : ""}`}
        </span>
      </span>
    </button>
  );
}

function Shelf({ books, badges, twins }: { books: ListenBook[]; badges?: Map<string, string>; twins?: Set<string> }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] sm:gap-x-6">
      {books.map((book, index) => (
        <div key={book.id} className="rise-in" style={{ "--i": index } as CSSProperties}>
          <BookTile book={book} badge={badges?.get(book.id)} twin={twins?.has(book.id)} />
        </div>
      ))}
    </div>
  );
}

function badgesOf(items: { book: ListenBook; volume: number | null; unit: string }[]): Map<string, string> {
  const badges = new Map<string, string>();
  for (const { book, volume, unit } of items) {
    const badge = volumeBadge(book, volume, unit);
    if (badge) badges.set(book.id, badge);
  }
  return badges;
}

/** Sách cùng bộ đứng cạnh nhau theo số tập; sách lẻ ở cuối. Chỉ gom khi không lọc, không tìm. */
function SeriesShelves({ books, twins }: { books: ListenBook[]; twins: Set<string> }) {
  const places = seriesIndex(books);
  const groups = new Map<string, { book: ListenBook; volume: number | null; unit: string; name: string }[]>();
  for (const book of books) {
    const { key: series, series: name, volume, unit } = places.get(book.id)!;
    const key = volume === null ? `\u0000${book.id}` : series;
    groups.set(key, [...(groups.get(key) ?? []), { book, volume, unit, name }]);
  }
  const series = [...groups.entries()]
    .filter(([key, items]) => !key.startsWith("\u0000") && items.length > 1)
    .map(([key, items]) => [key, [...items].sort((a, b) => (a.volume ?? 0) - (b.volume ?? 0))] as const);
  const singles = books.filter((book) => !series.some(([, items]) => items.some((item) => item.book.id === book.id)));
  return (
    <div className="mt-6 space-y-10">
      {series.map(([key, items]) => (
        <section key={key} aria-label={items[0].name}>
          <h2 className="mb-3 flex items-baseline gap-2 text-base font-semibold">
            {items[0].name} <span className="text-sm font-normal text-fg-2">· {items.length} {items[0].unit}</span>
          </h2>
          <Shelf books={items.map((item) => item.book)} badges={badgesOf(items)} twins={twins} />
        </section>
      ))}
      {singles.length > 0 && (
        <section aria-label="Sách lẻ">
          {series.length > 0 && <h2 className="mb-3 text-base font-semibold">Sách khác</h2>}
          <Shelf books={singles} twins={twins} />
        </section>
      )}
    </div>
  );
}

const EMPTY_TEXT: Record<Filter, string> = {
  all: "Thư viện chưa có sách nào.",
  listening: "Chưa nghe dở cuốn nào - chọn một cuốn để bắt đầu.",
  new: "Cuốn nào cũng đã được nghe ít nhất một đoạn.",
  finished: "Chưa có cuốn nào nghe xong.",
};

export function LibraryScreen({
  empty,
  header,
  recap,
  onOpenUpcoming,
}: {
  empty?: ReactNode;
  header?: ReactNode;
  recap?: ReactNode;
  /** Máy tính: sách đang làm dở mà chưa có chương nào - mở Studio để xem tiến trình. */
  onOpenUpcoming?: (book: ListenBook) => void;
}) {
  const { data: allBooks, isLoading } = useListenLibrary();
  // Sách chỉ có chữ chưa có chương nghe được nhưng đã ở trong thư viện (đọc được ngay): không phải sách "sắp có".
  const books = useMemo(() => allBooks?.filter((book) => book.chaptersAvailable > 0 || book.stage === "text"), [allBooks]);
  const upcoming = useMemo(() => allBooks?.filter((book) => book.chaptersAvailable === 0 && book.stage !== "text") ?? [], [allBooks]);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<LibrarySort>(loadLibrarySort);
  const player = usePlayer();
  // Theo cuốn đang phát (không tính nghe kiểm trong Studio), không chỉ theo chỗ nghe đã lưu - chỗ ấy chỉ được làm mới khi dừng.
  const playingId = player.track && player.purpose !== "review" ? player.track.bookId : null;
  const listening = useMemo(() => listeningBook(books ?? [], playingId), [books, playingId]);
  const folded = foldVietnamese(query.trim());
  const twins = useMemo(() => twinBookIds(books ?? []), [books]);
  const shown = useMemo(
    () =>
      sortBooks(
        (books ?? []).filter(
          // Tên sách, tác giả hoặc giọng kể ("duc tri" tìm ra mọi cuốn Đức Trí đọc - soát UX 29-09).
          (book) => (filter === "all" || stateOf(book) === filter) && bookMatchesQuery(book, folded),
        ),
        sort,
      ),
    [books, filter, folded, sort],
  );
  return (
    <div className="mx-auto max-w-[1180px] px-4 pb-16 pt-6 sm:px-10 sm:pt-9">
      {/* Hai nút cạnh tiêu đề không được bóp tiêu đề thành "Thư / viện" ở 390 px (soát UX 05-10): tiêu đề giữ một dòng, nút xuống dưới. */}
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div className="shrink-0">
          <h1 className="whitespace-nowrap text-2xl font-bold tracking-tight sm:text-[28px]">Thư viện</h1>
          <p className="mt-1 text-sm text-fg-2">{books?.length ? `${books.length} cuốn` : ""}</p>
        </div>
        {/* Thư viện trống: nút giữa màn (`empty`) là lời mời chính - nút thứ hai cùng tên ở đầu trang chỉ lặp lại (soát UX a9). */}
        {(books?.length || upcoming.length > 0) && header}
      </header>
      {recap}
      {upcoming.length > 0 && (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {upcoming.map((book) => (
            <UpcomingCard key={book.id} book={book} onOpen={onOpenUpcoming} />
          ))}
        </div>
      )}
      {isLoading ? (
        <div className="mt-8 grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] sm:gap-x-6">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index}>
              <Skeleton className="aspect-square w-full rounded-lg" />
              <Skeleton className="mt-3 h-4 w-3/4" />
            </div>
          ))}
        </div>
      ) : !books?.length ? (
        upcoming.length ? null : empty ?? (
          <EmptyState icon={Headphones} title="Chưa có sách nào" className="mt-12">
            Sách nghe được sẽ hiện ở đây.
          </EmptyState>
        )
      ) : (
        <>
          {listening && (
            <div className="mt-6">
              <ContinueCard book={listening} />
            </div>
          )}
          <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
            <Segmented<Filter>
              label="Lọc sách"
              // Điện thoại: mỗi nút lọc đủ 44 px để chạm; cả thanh trải hết bề ngang, các nút chia đều - chữ to (cỡ chữ hệ thống 1,3) không bị cắt "Nghe xong".
              className="max-sm:flex max-sm:w-full"
              itemClassName="max-sm:h-[44px] max-sm:min-w-0 max-sm:flex-1 max-sm:px-1"
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: "Tất cả" },
                { value: "listening", label: "Đang nghe" },
                { value: "new", label: "Chưa nghe" },
                { value: "finished", label: "Nghe xong" },
              ]}
            />
            <label className="flex items-center gap-2 text-sm text-fg-2 max-sm:w-full">
              <span className="shrink-0">Xếp theo</span>
              <select
                value={sort}
                onChange={(event) => {
                  if (!isLibrarySort(event.target.value)) return;
                  setSort(event.target.value);
                  saveLibrarySort(event.target.value);
                }}
                className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-panel px-2 text-sm text-fg outline-none focus:border-accent max-sm:h-[44px]"
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="relative max-sm:w-full">
              <span className="sr-only">Tìm sách</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-3" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm sách"
                title="Tên sách hay giọng kể - gõ không dấu cũng được"
                className="touch-row h-9 w-full rounded-lg border border-line bg-panel pl-9 pr-9 text-sm outline-none placeholder:text-fg-3 focus:border-accent sm:w-80 [&::-webkit-search-cancel-button]:hidden"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  aria-label="Xoá ô tìm"
                  className="absolute right-1 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-fg-3 hover:bg-hover hover:text-fg"
                >
                  <X className="size-4" />
                </button>
              )}
            </label>
          </div>
          {shown.length ? (
            filter === "all" && !folded ? (
              <SeriesShelves books={shown} twins={twins} />
            ) : (
              <div className="mt-6">
                <Shelf books={shown} twins={twins} />
              </div>
            )
          ) : (
            <EmptyState icon={Search} title={query ? `Không tìm thấy sách nào khớp “${query}”` : "Không có sách ở đây"} className="mt-4">
              {query ? "Thử gõ một phần tên sách hoặc tên tác giả khác." : EMPTY_TEXT[filter]}
            </EmptyState>
          )}
        </>
      )}
    </div>
  );
}
