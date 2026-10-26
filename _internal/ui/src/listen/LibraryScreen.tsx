import { MotionPresence } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { ScreenHeader } from "@/shared/ScreenHeader";
import { useRowFade } from "@/shared/scrollFade";
import { SlidingIndicator } from "@/shared/SlidingIndicator";
import { ArrivalScope, Collapse } from "@/shared/Collapse";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useBackLayer } from "@/shared/backStack";
import { useMediaQuery } from "@/shared/media";
import { LoadingCrossfade } from "@/shared/MotionPresence";
import { useListPresence } from "@/shared/motion";
import { ArrowDownWideNarrow, BookOpen, Headphones, Laptop, Pause, Play, Search, X } from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode, type CSSProperties } from "react";
import { useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import { BookCover } from "@/shared/BookCover";
import { Windowed } from "@/shared/Windowed";
import { useScrollMemory } from "@/shared/scrollMemory";
import { cn } from "@/shared/cn";
import { formatLength, formatLengthUp, formatWhen } from "@/shared/format";
import { Dialog, EmptyState, failedEmpty, heardBarProps, LoadError, Progress, RowGap, SelectionMark, Sheet, Skeleton } from "@/shared/ui";
import { caughtUpLine, displayTitle, resumeWhere } from "./labels";
import { loadLibrarySort, saveLibrarySort, SORT_OPTIONS, sortBooks, type LibrarySort } from "./librarySort";
import { bookMatchesQuery, foldVietnamese, listeningBook, resumePoint, resumeTarget, seriesIndex, twinBookIds, twinKind, volumeBadge, type ListenBook, type ListenChapter } from "./model";
import { usePlayer, type WordTarget } from "./player";
import { useClock } from "./clock";
import { useListenBook, useListenLibrary, useReadAloudVoices, useSource } from "./source";
import { feedback, withFeedback } from "@/shared/feedback";

type Filter = "all" | "listening" | "new" | "finished";
const LIBRARY_FILTER_OPTIONS = [{ value: "all", label: "Tất cả" }, { value: "listening", label: "Nghe dở" }, { value: "new", label: "Chưa nghe" }, { value: "finished", label: "Xong" }] as const;
const LIBRARY_FILTERS: Filter[] = LIBRARY_FILTER_OPTIONS.map(option => option.value);

/** Hành động riêng của nền tảng đi cùng bìa, kể cả khi mở bộ sách. */
type BookExtras = { actions?: (book: ListenBook) => ReactNode; cover?: (book: ListenBook) => ReactNode; seriesCover?: (books: ListenBook[]) => ReactNode };
const BookExtrasContext = createContext<BookExtras>({});

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
  return `Trên ${remoteName(book)}`;
}

/** Tên máy đang giữ cuốn nghe thẳng: tên máy tính đã ghép, "máy khác" khi chưa biết tên, "máy tính" khi điện thoại nghe máy tính. */
export function remoteName(book: ListenBook): string {
  return typeof book.remote === "object" && book.remote ? book.remote.computer || "máy khác" : "máy tính";
}

/** Cuốn nghe thẳng chưa xong: chương còn lại đang ở máy kia và tự hiện khi xong - không phải "file cũ, mở bản mới hơn" (soát a27 lỗi 7). */
export function remoteUnfinishedLine(book: ListenBook): string {
  const name = remoteName(book);
  return `${name.charAt(0).toUpperCase()}${name.slice(1)} còn đang làm, chương mới hiện ở đây khi xong`;
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
    return book.producing ? `${chapters} · đang thu` : chapters;
  }
  const left = Math.max(0, book.duration - book.progress.heardSeconds);
  if (book.progress.heardSeconds <= 0) return formatLength(book.duration);
  // Ở tốc độ của cuốn, làm tròn lên - như số giờ còn lại ở thanh phát (soát a26 L10: "Còn 1 phút" cạnh "-2:09").
  return `Còn ${formatLengthUp(left / (book.state.rate ?? 1))}`;
}

export function usePlayListenBook() {
  const source = useSource();
  const player = usePlayer();
  return async (book: ListenBook, chapterId?: number, at?: number, extra?: { word?: WordTarget; rate?: number }) => {
    // Cuốn đang ở trình phát: tiếp tục đúng chỗ đang phát, không nạp lại (nạp lại là lùi về điểm lưu gần nhất). player.resume hỏi lại chỗ nghe
    // trước: thiết bị khác nghe xa hơn thì tới chỗ ấy (soát a27 lỗi 2).
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
      toast(caughtUpLine(full.producing));
      return;
    }
    const point = resumePoint(full, chapters);
    if (point) player.play(full, chapters, point.chapter.id, point.at, extra);
  };
}

/** Chỗ nghe tiếp của một cuốn (model.resumeTarget) - thẻ "Đang nghe dở", nút chính của trang sách nói cùng một chỗ, và đúng chỗ bấm sẽ phát.
 *  Cuốn đang trong trình phát mà đang dừng: chỗ trình phát đứng (giây đổi thì vẽ lại; đang phát thì không theo từng giây). */
export function useResumeTarget(book: ListenBook | undefined, chapters: ListenChapter[]): ReturnType<typeof resumeTarget> {
  const { track, playing, positionStamp } = usePlayer();
  const here = Boolean(book && track?.bookId === book.id);
  const second = useClock((time) => (here && !playing ? Math.floor(time) : -1));
  if (!book) return null;
  // Thiết bị khác nghe xa hơn sau lần cuối máy này lưu: nút nói chỗ của máy kia (resumeTarget), và bấm thì trình phát tới đúng chỗ ấy (player.resume).
  return resumeTarget(book, chapters, here && track ? { chapterId: track.chapterId, seconds: Math.max(0, second) } : null, positionStamp());
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
  const extras = useContext(BookExtrasContext);
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
    <MotionRegion as="div" data-book-tile="" className="group">
      <div className="relative">
        {/* Bìa và nút tên bên dưới cùng mở trang sách: bàn phím chỉ dừng ở nút tên (có chữ), bìa vẫn bấm được bằng chuột (soát UX a17: ba điểm Tab mỗi thẻ). */}
        <button type="button" tabIndex={-1} onClick={() => navigate(`/book/${book.id}`)} className="block w-full rounded-control" aria-label={`Mở ${book.title}`} title={book.remote ? `${book.title} · ${remotePlace(book)}` : undefined}>
          <BookCover title={book.title} part={book.series?.part} badge={badge} size="md" image={book.cover} playing={playingHere} className="w-full !aspect-[2/3] !rounded-cover" />
        </button>
        <button
          type="button"
          aria-label={textOnly ? `Đọc ${book.title}` : playingHere ? `Tạm dừng ${book.title}` : book.stage === "text" ? `Nghe ngay ${book.title}` : `Nghe ${book.title}`}
          onClick={() => (textOnly ? navigate(`/book/${book.id}/read`) : (feedback("playPause"), current ? player.toggle() : void playBook(book)))}
          className={cn(
            "touch-hit touch-box absolute bottom-2.5 right-2.5 grid size-[44px] place-items-center rounded-full bg-panel text-fg shadow-card transition-opacity duration-motion-fast focus-visible:pointer-events-auto focus-visible:opacity-100",
            // Điện thoại không có rê chuột: nút chỉ hiện cho cuốn đang ở trình phát, tranh bìa không bị che (soát 24-10).
            current ? "opacity-100" : "pointer-events-none opacity-0 md:group-hover:pointer-events-auto md:group-hover:opacity-100",
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
          // Thanh cắt theo ĐÚNG khung bo của bìa (lớp phủ cùng rounded-control): tự bo góc thì thanh cao 4 px chỉ bo được 4 px, lệch với góc 8 px
          // của bìa thành khe hở ở mép dưới (chủ sách 25-10).
          <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-control">
            <div {...heardBarProps(book.progress.fraction)} className="absolute inset-x-0 bottom-0 h-1 bg-cover-overlay">
              <div className="motion-progress h-full bg-accent" style={{ transform: `scaleX(${book.progress.fraction * 100 / 100})` }} />
            </div>
          </div>
        )}
        {extras.cover?.(book)}
      </div>
      <button type="button" onClick={() => navigate(`/book/${book.id}`)} className="touch-row mt-2.5 block w-full text-left">
        <div className={cn("line-clamp-2 text-sm font-medium leading-snug", current && "text-accent-text")}>{displayTitle(book.title)}</div>
        {/* Cuốn ở máy khác: dấu máy tính đầu dòng trạng thái, không đè lên bìa - nhãn góc trên từng che tên sách của bìa vẽ (audit140 V8). */}
        <div className="mt-1 flex items-center gap-1 text-xs text-fg-2">
          {book.remote && <Laptop role="img" aria-label={typeof book.remote === "object" && book.remote.downloaded ? `${remotePlace(book)}, đã tải về máy này` : remotePlace(book)} className="size-3 shrink-0" />}
          <span className="min-w-0 truncate">{progressText(book, speaks)}</span>
        </div>
        {/* Hai cuốn cùng tên: nhãn "Dự án" (làm trên máy này) / "Đã nhập" (mở từ file) và ngày vào thư viện để biết cuốn nào là cuốn nào
            (tác giả, nếu có, đã nằm ở dòng trên). */}
        {twin && (twinKind(book) || book.addedAt) ? (
          <div className="mt-0.5 text-xs text-fg-3">
            {[twinKind(book), book.addedAt ? `Thêm ${formatWhen(book.addedAt)}` : ""].filter(Boolean).join(" · ")}
          </div>
        ) : null}
      </button>
      {extras.actions?.(book)}
    </MotionRegion>
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
  // Cùng chỗ với nút chính của trang sách ("Nghe tiếp · Chương 3 · 12:04") và đúng chỗ bấm sẽ phát (useResumeTarget). Đang phát thì chỉ
  // nói chương - giờ chạy liên tục.
  const full = useListenBook(book.id, false).data;
  const point = useResumeTarget(full ?? book, full?.chapters ?? book.chapters ?? []);
  const where = !point ? "" : playingHere ? point.chapter.title : resumeWhere(point.chapter.title, point.at);
  return (
    <section className="flex items-center gap-4 sm:gap-6" aria-label="Đang nghe">
      <button type="button" onClick={() => navigate(`/book/${book.id}`)} aria-label={`Mở ${book.title}`}>
        <BookCover title={book.title} part={book.series?.part} size="md" image={book.cover} playing={playingHere} className="w-20 !aspect-[2/3] !rounded-cover sm:w-28" />
      </button>
      {/* Cột chữ giãn theo lưới: mép nút phát trùng mép nội dung và nút tìm bên dưới. */}
      <div className="min-w-0 flex-1">
        <div className="label-section text-fg-2">Đang nghe</div>
        <h2 className="mt-2 line-clamp-2 text-lg font-bold sm:text-2xl">{displayTitle(book.title)}</h2>
        {/* Thẻ giữ khoá theo cuốn (LibraryScreen): đổi phát / tạm dừng, chương, "nghe lần cuối" ở đây tự mờ chéo; giờ chạy không tính. */}
        <MotionRegion as="p" className="tabular mt-1 truncate text-sm text-fg-2">
          {where}
          {current ? (playingHere ? " · đang phát" : " · tạm dừng") : last ? ` · nghe lần cuối ${formatWhen(last.at)}` : ""}
        </MotionRegion>
        <MotionRegion as="p" className="mt-0.5 text-sm text-fg-2">{bookStatusText(book, speaks)}</MotionRegion>
        <Progress value={book.progress.fraction} size="xs" className="mt-3" label="Đã nghe" />
      </div>
      <MotionRegion className="shrink-0" motionKey={book.progress.caughtUp && !current}>
      {book.progress.caughtUp && !current ? (
        // Đã nghe hết phần đã có: nút phát lớn chỉ phát 0 giây rồi báo hết - nói thẳng đang chờ chương mới (soát UX 29-09).
        <span className="block rounded-full bg-hover px-3 py-1.5 text-xs font-medium text-fg-2">Chờ chương mới</span>
      ) : (
      <button
        type="button"
        onClick={withFeedback("playPause", () => (current ? player.toggle() : void playBook(book)))}
        aria-label={playingHere ? `Tạm dừng ${book.title}` : `Nghe tiếp ${book.title}${where ? `, ${where}` : ""}`}
        className="grid size-14 shrink-0 place-items-center rounded-full bg-accent text-accent-ink transition-transform duration-motion-fast active:scale-[0.97]"
      >
        <MotionRegion as="span" motionKey={playingHere} className="inline-grid size-6 place-items-center">
          {playingHere ? (
            <Pause className="size-6" fill="currentColor" strokeWidth={0} />
          ) : (
            <Play className="size-6 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
          )}
        </MotionRegion>
      </button>
      )}
      </MotionRegion>
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

/** Dòng dưới tên một cuốn "sắp có". Chưa có chương nghe được không có nghĩa là đang làm: sách dừng trước chương đầu, hay audio bị dời chỗ
 *  (soát UX 29-09). Cuốn của máy khác thì việc làm nằm ở máy ấy: nói tên máy, không mời "bấm để làm tiếp" - Studio ở đây không có dự án ấy
 *  (soát a27 lỗi 6). */
export function upcomingStatus(book: ListenBook, canOpen: boolean): string {
  if (book.remote) {
    const where = `trên ${remoteName(book)}`;
    if (book.producing && book.pauseReason) return `Đang tạm dừng ${where}`;
    return book.producing ? `Đang làm ${where}` : `Chưa có chương nghe được · làm ${where}`;
  }
  const eta = book.eta && (book.eta.phase === "analysis" || book.eta.phase === "speaker") ? `chương đầu nghe được sau khoảng ${formatLength(book.eta.seconds + 600)}` : "đang chuẩn bị";
  if (book.producing && book.pauseReason) {
    return book.pauseReason === "battery" ? "Đang tạm dừng · máy đang chạy pin" : `Đang tạm dừng${canOpen ? " · bấm để làm tiếp" : ""}`;
  }
  return book.producing ? `Đang làm · ${eta}` : `Chưa có chương nghe được${canOpen ? " · bấm để làm tiếp" : ""}`;
}

function UpcomingCard({ book, onOpen: open }: { book: ListenBook; onOpen?: (book: ListenBook) => void }) {
  const onOpen = book.remote ? undefined : open;
  const status = upcomingStatus(book, Boolean(onOpen));
  return (
    <button
      type="button"
      onClick={() => onOpen?.(book)}
      disabled={!onOpen}
      className="flex items-center gap-3 py-3 text-left"
    >
      <BookCover title={book.title} part={book.series?.part} size="sm" image={book.cover} className="size-12 opacity-80" />
      <MotionRegion as="span" className="min-w-0" motionKey={[book.title, status]}>
        <span className="block truncate text-sm font-semibold">{book.title}</span>
        <span className="block truncate text-xs text-fg-2">{status}</span>
      </MotionRegion>
    </button>
  );
}

const SHELF_GRID = "grid grid-cols-2 gap-x-[16px] gap-y-[32px] sm:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] sm:gap-x-[24px]";
/** Thư viện vài trăm cuốn: dựng từng khối 60 cuốn gần màn hình (shared/Windowed). 60 chia hết cho 2-6 cột: mỗi khối là một lưới
 *  cùng cột, hàng cuối của khối không hụt giữa chừng. */
const SHELF_BLOCK = 60;

function Shelf({ books, badges, twins, memory }: { books: ListenBook[]; badges?: Map<string, string>; twins?: Set<string>; memory?: string }) {
  const rows = useListPresence(books, (book) => book.id);
  const tile = (book: ListenBook, index: number) => (
    // Hiện dần chỉ cho khối đầu: khối sau dựng khi cuộn tới, không nhún lại mỗi lần.
    <div key={book.id} className={index < SHELF_BLOCK ? "rise-in" : undefined} style={{ "--i": index } as CSSProperties}>
      <BookTile book={book} badge={badges?.get(book.id)} twin={twins?.has(book.id)} />
    </div>
  );
  return (
    <MotionRegion as="div" role="list" aria-label="Sách" className="space-y-7" motionKey={books.map((book) => book.id)}>
      <Windowed
        memory={memory} items={rows} block={SHELF_BLOCK} estimate={90} className={SHELF_GRID} alwaysBlocks
        row={({ key, item, state, ref }, index) => (
          <div key={key} ref={ref} role="listitem" aria-posinset={books.findIndex((book) => book.id === key) + 1 || undefined} aria-setsize={books.length} className="motion-row" data-state={state} inert={state === "exit"}>
            {tile(item, index)}
          </div>
        )}
      />
    </MotionRegion>
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

/** Gom theo bộ nhưng giữ vị trí của cuốn đầu tiên trong thứ tự đang chọn. */
function librarySections(books: ListenBook[], grouped: boolean) {
  const places = seriesIndex(books);
  const groups = new Map<string, ListenBook[]>();
  for (const book of books) {
    const place = places.get(book.id)!;
    const key = grouped && place.volume !== null ? place.key : `book:${book.id}`;
    groups.set(key, [...(groups.get(key) ?? []), book]);
  }
  return [...groups.entries()].map(([key, members]) => {
    const items = [...members].sort((a, b) => (places.get(a.id)!.volume ?? 0) - (places.get(b.id)!.volume ?? 0));
    return { key, label: places.get(items[0].id)!.series, items,
      badges: badgesOf(items.map(book => ({ book, ...places.get(book.id)! }))) };
  });
}

/** Một bìa cho cả bộ; điện thoại mở bảng đáy, máy tính mở hộp giữa màn. */
function SeriesTile({ item, twins, phone }: { item: ReturnType<typeof librarySections>[number]; twins: Set<string>; phone: boolean }) {
  const extras = useContext(BookExtrasContext);
  const [open, setOpen] = useState(false);
  const trigger = <button type="button" aria-label={`Mở bộ ${item.label}`} aria-haspopup="dialog" onClick={() => setOpen(true)} className="group block w-full text-left">
    {/* Số tập dưới bìa đã phân biệt bộ sách; bỏ hai tờ trống nhô lên từng trông như dải báo mạng bị mất chữ. */}
    <div className="relative">
      <BookCover title={item.label} image={item.items[0].cover} size="md" className="w-full !aspect-[2/3] !rounded-cover" />
      {extras.seriesCover?.(item.items)}
    </div>
    <span className="mt-2.5 block line-clamp-2 text-sm font-medium leading-snug">{item.label}</span>
    <span className="mt-1 flex items-center gap-1 text-xs text-fg-2">
      {item.items.some(book => book.remote) && <Laptop role="img" aria-label="Có sách trên máy khác" className="size-3 shrink-0" />}
      {item.items.length} tập
    </span>
  </button>;
  const content = open && <Shelf books={item.items} badges={item.badges} twins={twins} />;
  return <MotionRegion data-book-tile="" motionKey={[item.label, item.items.map(book => book.id), item.items[0].cover?.url, item.items.some(book => book.remote)]}>
    {phone ? <Sheet open={open} onOpenChange={setOpen} title={item.label} trigger={trigger}>
      <div className="pb-4 pt-4">{content}</div>
    </Sheet> : <>{trigger}<Dialog open={open} onOpenChange={setOpen} title={item.label}>{content}</Dialog></>}
  </MotionRegion>;
}

/** Lưới luôn mở; presence giữ các ô và Windowed giữ thư viện dài. */
export function SeriesShelves({ books, twins, memory, grouped = true }: { books: ListenBook[]; twins: Set<string>; memory?: string; grouped?: boolean }) {
  const narrow = useMediaQuery("(max-width: 767px)");
  const coarse = useMediaQuery("(pointer: coarse)");
  const sections = librarySections(books, grouped);
  const rows = useListPresence(sections, section => section.key);
  return <div role="list" aria-label="Sách" className="mt-8">
    <Windowed memory={memory} items={rows} block={SHELF_BLOCK} estimate={130} className={SHELF_GRID} alwaysBlocks
      row={({ key, item, state, ref }, index) => <div key={key} ref={ref} role="listitem" className="motion-row" data-state={state} inert={state === "exit"}>
        <div className={index < SHELF_BLOCK ? "rise-in" : undefined} style={{ "--i": index } as CSSProperties}>
          {item.items.length > 1 ? <SeriesTile item={item} twins={twins} phone={narrow || coarse} /> :
            <BookTile book={item.items[0]} badge={item.badges.get(item.items[0].id)} twin={twins.has(item.items[0].id)} />}
        </div>
      </div>} />
  </div>;
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
  bookExtras = {},
  additionalBooks = [],
}: {
  bookExtras?: BookExtras;
  /** Danh mục máy ghép có thể về trước gói nghe trực tiếp; vẫn cho tải cuốn ấy. */
  additionalBooks?: ListenBook[];
  empty?: ReactNode;
  header?: ReactNode;
  recap?: ReactNode;
  /** Máy tính: sách đang làm dở mà chưa có chương nào - mở Studio để xem tiến trình. */
  onOpenUpcoming?: (book: ListenBook) => void;
}) {
  const libraryQuery = useListenLibrary();
  const { isLoading } = libraryQuery;
  const allBooks = useMemo(() => {
    if (!additionalBooks.length) return libraryQuery.data;
    const known = new Set((libraryQuery.data ?? []).map(book => book.id));
    return [...(libraryQuery.data ?? []), ...additionalBooks.filter(book => !known.has(book.id))];
  }, [libraryQuery.data, additionalBooks]);
  // Sách chỉ có chữ chưa có chương nghe được nhưng đã ở trong thư viện (đọc được ngay): không phải sách "sắp có".
  const books = useMemo(() => allBooks?.filter((book) => book.chaptersAvailable > 0 || book.stage === "text"), [allBooks]);
  const upcoming = useMemo(() => allBooks?.filter((book) => book.chaptersAvailable === 0 && book.stage !== "text") ?? [], [allBooks]);
  const [filter, setFilter] = useState<Filter>("all");
  const [filterRow, setFilterRow] = useState<HTMLDivElement | null>(null);
  const filterFade = useRowFade(filterRow);
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);
  useBackLayer(searchOpen, () => { setSearchOpen(false); setQuery(""); });
  const [sort, setSort] = useState<LibrarySort>(loadLibrarySort);
  const container = useRef<HTMLDivElement | null>(null);
  const memory = query.trim() ? undefined : `library.${filter}.${sort}`;
  useScrollMemory(!isLoading && memory ? memory : null, container);
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
  // Cuốn đang làm ở máy khác cũng theo ô tìm và bộ lọc (chưa nghe được nên chỉ thuộc "Tất cả" / "Chưa nghe") - từng hiện mãi dưới kết quả tìm.
  const upcomingShown = useMemo(
    () => upcoming.filter((book) => (filter === "all" || filter === "new") && bookMatchesQuery(book, folded)),
    [upcoming, filter, folded],
  );
  const libraryRows = useListPresence(books ?? [], (book) => book.id);
  const upcomingRows = useListPresence(upcomingShown, (book) => book.id);
  const noResultsTitle = query ? `Không tìm thấy sách nào khớp “${query}”` : "Không có sách ở đây";
  const grouped = true;

  return (
    <BookExtrasContext.Provider value={bookExtras}>
    {/* Cả trang biết lượt sách đầu về: nút "Thêm sách" ở đầu trang hiện tại chỗ cùng lưới, không mọc ra đẩy lưới xuống. */}
    <ArrivalScope loading={isLoading}>
    <div ref={container} className="library-screen page-x mx-auto max-w-[1180px] pb-16">
      {/* Nút nằm trên CÙNG dòng tiêu đề, căn giữa theo dòng ấy (không lơ lửng giữa tiêu đề và số cuốn). */}
      <ScreenHeader
        title="Thư viện"
        // Thư viện trống: nút giữa màn (`empty`) là lời mời chính - nút thứ hai cùng tên ở đầu trang chỉ lặp lại (soát UX a9).
        // -mr bù đệm ngang của nút ghost (px-3.5, trừ phần thừa bên phải của nét chữ) + p-1 giữ chỗ vòng tiêu điểm: chữ "Thêm sách" thẳng mép phải với nút phát và kính lúp bên dưới.
        // Giữ chỗ từ đầu, chỉ mờ vào khi có sách: dòng tiêu đề không cao thêm lúc sách về (đo 25-10: lưới trôi 8 px khi mở app).
        actions={header && <div className="motion-hold -my-1 -ml-1 -mr-[16px] p-1" data-state={books?.length || upcoming.length ? "open" : "closed"} inert={!(books?.length || upcoming.length)}>{header}</div>}
        subtitleKey={folded ? `${shown.length + upcomingShown.length}/${allBooks?.length ?? 0}` : allBooks?.length ?? 0}
        // Đang tìm: nói số cuốn khớp, không phải cả thư viện (soát 24-10 T08 - từng ghi "11 cuốn" trên một kết quả).
        // Chưa có số: giữ một dòng trống, số tới không làm đầu trang cao thêm đẩy lưới xuống.
        subtitle={!allBooks?.length ? "\u00a0" : folded ? `${shown.length + upcomingShown.length} trong ${allBooks.length} cuốn` : `${allBooks.length} cuốn`}
      />
      {recap}
      <LoadingCrossfade loading={isLoading} placeholder={
        <div className="mt-8 grid grid-cols-2 gap-x-[16px] gap-y-[32px] sm:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] sm:gap-x-[24px]">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index}>
              <Skeleton className="aspect-[2/3] w-full rounded-cover" />
              <Skeleton className="mt-3 h-4 w-3/4" />
            </div>
          ))}
        </div>
      }>
      {/* Lỗi / trống / có sách thay nhau (mạng về, sách đầu tiên vào thư viện): mờ hẳn qua, không thay cả trang tức thì. */}
      <MotionRegion fadeThrough motionKey={failedEmpty(libraryQuery) ? "error" : !libraryRows.length ? (upcoming.length ? "upcoming" : "empty") : "books"}>
      {failedEmpty(libraryQuery) ? (
        <LoadError what="thư viện" error={libraryQuery.error} onRetry={() => void libraryQuery.refetch()} className="mt-12" />
      ) : !libraryRows.length ? (
        upcoming.length ? null : empty ?? (
          <EmptyState icon={Headphones} title="Chưa có sách nào" className="mt-12">
            Sách nghe được sẽ hiện ở đây.
          </EmptyState>
        )
      ) : (
        <>
          <MotionPresence open={Boolean(listening)}>{listening && (
            <MotionRegion motionKey={listening.id} className="mt-[32px] sm:mt-[48px]">
              <ContinueCard book={listening} />
            </MotionRegion>
          )}</MotionPresence>
          {/* Khe lọc 14 px trên điện thoại: vừa cả bốn mục ở cỡ chữ hệ thống 115 % ("Xong" từng cụt ở mép); to hơn nữa thì hàng cuộn, mép mờ. */}
          <div className="mt-8 flex items-center gap-2 sm:mt-12 sm:gap-4">
            <div ref={setFilterRow} style={filterFade} role="group" aria-label="Lọc sách" className="relative flex min-w-0 flex-1 overflow-x-auto [scrollbar-width:none]">
              <SlidingIndicator variant="line" />
              {LIBRARY_FILTER_OPTIONS.map((option, index) => [index > 0 && <RowGap key={`gap-${option.value}`} className="w-4" />, <button
                key={option.value} type="button" aria-label={option.value === "finished" ? "Nghe xong" : option.label} aria-pressed={filter === option.value} onClick={() => setFilter(option.value)}
                className={cn("touch-hit min-h-[44px] shrink-0 border-b-2 border-transparent text-xs font-medium transition-colors duration-motion-medium sm:text-sm", filter === option.value ? "text-fg" : "text-fg-2 hover:text-fg")}>
                {option.label}
              </button>])}
            </div>
            {/* Xếp sách không khoá trang: modal đổi pointer-events/biến cuộn trên body, tính lại style mọi bìa. */}
            <DropdownMenu.Root modal={false}>
              <DropdownMenu.Trigger asChild><button type="button" aria-label="Xếp theo" title={`Xếp theo: ${SORT_OPTIONS.find(option => option.value === sort)?.label}`} className="flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center gap-1 text-xs text-fg-2 sm:text-sm">
                <ArrowDownWideNarrow className="size-5 sm:size-4" /><span className="max-sm:sr-only">Xếp theo</span>
              </button></DropdownMenu.Trigger>
              <DropdownMenu.Portal><DropdownMenu.Content align="end" sideOffset={4} collisionPadding={12} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-44 rounded-cover border border-line bg-panel p-1.5 shadow-float">
                <DropdownMenu.RadioGroup value={sort} onValueChange={value => { const next = value as LibrarySort; setSort(next); saveLibrarySort(next); }}>
                  {SORT_OPTIONS.map(option => <DropdownMenu.RadioItem key={option.value} value={option.value} className="flex min-h-[44px] cursor-default items-center gap-3 rounded-control px-3 text-sm outline-none data-[highlighted]:bg-hover data-[state=checked]:text-accent-text"><SelectionMark selected={sort === option.value} />{option.label}</DropdownMenu.RadioItem>)}
                </DropdownMenu.RadioGroup>
              </DropdownMenu.Content></DropdownMenu.Portal>
            </DropdownMenu.Root>
            <button type="button" aria-label="Tìm sách" aria-expanded={searchOpen} onClick={() => { setSearchOpen(value => !value); if (searchOpen) setQuery(""); else requestAnimationFrame(() => searchInput.current?.focus()); }} className="-mr-[14.71px] grid size-[44px] shrink-0 place-items-center rounded-control text-fg-2">
              {/* Vùng chạm 44 px giữ nguyên, mực kính lúp (lề phải 2/24 của ô 17,5 px) chạm đúng mép phải nội dung: (44 - 17,5) / 2 + 17,5 x 2 / 24 = 14,71 px. */}
              <Search className="size-5" />
            </button>
          </div>
          <Collapse open={searchOpen}>
            <label className="relative mt-3 block">
              <span className="sr-only">Tìm sách</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-2" />
              <input ref={searchInput} aria-label="Tìm sách" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Tên sách, tác giả, giọng" title="Gõ không dấu cũng được" className="h-[44px] w-full rounded-control bg-sunken pl-10 pr-11 text-sm outline-none placeholder:text-fg-2 focus:ring-2 focus:ring-focus [&::-webkit-search-cancel-button]:hidden" />
              <button type="button" onClick={() => { if (query) setQuery(""); else setSearchOpen(false); }} aria-label={query ? "Xoá ô tìm" : "Đóng tìm kiếm"} className="absolute right-0 top-0 grid size-[44px] place-items-center text-fg-2"><X className="size-4" /></button>
            </label>
          </Collapse>
          {/* Chỉ fade kết quả: header/tiếp tục nghe/controls giữ một cây. Ảnh theo scrollMemory trước paint. */}
          <MotionRegion followScroll fadeThrough slideIndex={LIBRARY_FILTERS.indexOf(filter)} motionKey={[filter, sort, folded, shown.map(book => book.id), !shown.length && noResultsTitle]}>
            {/* Kết quả rỗng không giữ lại bìa exit dưới ảnh cũ. Còn sách thì giữ node, focus và Windowed. */}
            <SeriesShelves key={shown.length ? "books" : "empty"} books={shown} twins={twins} memory={memory} grouped={grouped} />
            <MotionPresence open={!shown.length}>
              <EmptyState icon={Search} title={noResultsTitle} className="mt-4">
                {query ? "Thử tên sách hoặc tác giả khác." : EMPTY_TEXT[filter]}
              </EmptyState>
            </MotionPresence>
          </MotionRegion>
        </>
      )}
      </MotionRegion>
      </LoadingCrossfade>
      {/* Khung (cả lề 24 px) khép cùng hàng cuối (cả khối thu lại một lần), mở cùng hàng đầu - không gắn / gỡ cứng quanh các hàng. */}
      <MotionPresence open={upcomingRows.some((row) => row.state !== "exit")}>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {upcomingRows.map(({ key, item, state, ref }) => (
            <div key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}><div><UpcomingCard book={item} onOpen={onOpenUpcoming} /></div></div>
          ))}
        </div>
      </MotionPresence>
    </div>
    </ArrivalScope>
    </BookExtrasContext.Provider>
  );
}
