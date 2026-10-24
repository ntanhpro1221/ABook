import { MotionPresence } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { LoadingCrossfade } from "@/shared/MotionPresence";
import { useListPresence } from "@/shared/motion";
import { BookOpen, Headphones, Laptop, Pause, Play, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode, type CSSProperties } from "react";
import { useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import { BookCover } from "@/shared/BookCover";
import { ShortName } from "@/shared/ShortName";
import { Windowed } from "@/shared/Windowed";
import { useScrollMemory } from "@/shared/scrollMemory";
import { cn } from "@/shared/cn";
import { formatLength, formatLengthUp, formatWhen } from "@/shared/format";
import { EmptyState, failedEmpty, heardBarProps, LoadError, Progress, Segmented, Skeleton } from "@/shared/ui";
import { caughtUpDetail, resumeWhere } from "./labels";
import { loadLibrarySort, saveLibrarySort, SORT_OPTIONS, sortBooks, isLibrarySort, type LibrarySort } from "./librarySort";
import { bookMatchesQuery, foldVietnamese, listeningBook, resumePoint, resumeTarget, seriesIndex, twinBookIds, twinKind, volumeBadge, type ListenBook, type ListenChapter } from "./model";
import { usePlayer, type WordTarget } from "./player";
import { useClock } from "./clock";
import { useListenBook, useListenLibrary, useReadAloudVoices, useSource } from "./source";

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
    const lead = book.producing ? "Đang thu âm" : "Chưa hoàn thành";
    return `${lead} · ${chapters}`;
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
      toast("Đã nghe hết phần đã có", { description: caughtUpDetail(full.producing) });
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
    <MotionRegion as="div" className="group">
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
          <div {...heardBarProps(book.progress.fraction)} className="absolute inset-x-0 bottom-0 h-1 overflow-hidden rounded-b-lg bg-black/40">
            <div className="motion-progress h-full bg-accent" style={{ transform: `scaleX(${book.progress.fraction * 100 / 100})` }} />
          </div>
        )}
        {book.remote && (
          // Dải dưới bìa, chừa chỗ nút phát bên phải: tên sách vẽ ở ĐẦU bìa, huy hiệu ở góc trên từng đè lên chữ ấy (soát UX a10). Bìa vẽ có nhãn
          // "TẬP n" ở góc dưới trái thì huy hiệu nhích lên trên nhãn.
          <span
            className={cn(
              "pointer-events-none absolute left-2.5 inline-flex max-w-[calc(100%-4.5rem)] items-center gap-1 rounded-full bg-black/60 px-1.5 py-0.5 text-[0.625rem] font-medium text-white",
              book.series?.part || badge ? "bottom-9" : "bottom-2.5",
            )}
          >
            <Laptop className="size-3 shrink-0" />
            <ShortName name={typeof book.remote === "object" && book.remote?.computer ? book.remote.computer : "Máy tính"} short={11} className="truncate" />
            {/* Đã tải đủ về máy này: nghe được cả khi máy kia tắt (soát a27 lỗi 8). */}
            {typeof book.remote === "object" && book.remote.downloaded && <span className="shrink-0">· Đã tải</span>}
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
      className="flex items-center gap-3 rounded-xl border border-dashed border-line-strong bg-panel p-3 text-left hover:border-accent disabled:hover:border-line-strong"
    >
      <BookCover title={book.title} part={book.series?.part} size="sm" image={book.cover} className="size-12 opacity-80" />
      <MotionRegion as="span" className="min-w-0" motionKey={[book.title, status]}>
        <span className="block truncate text-sm font-semibold">{book.title}</span>
        <span className="block text-xs text-fg-2">{status}</span>
      </MotionRegion>
    </button>
  );
}

const SHELF_GRID = "grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] sm:gap-x-6";
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

/** Một nguồn cấu trúc cho cả rendering và identity; thay IDs trong cùng kệ để presence lo. */
function librarySections(books: ListenBook[], grouped: boolean) {
  const places = seriesIndex(books);
  const groups = new Map<string, { book: ListenBook; volume: number | null; unit: string; name: string }[]>();
  for (const book of books) {
    const { key: series, series: name, volume, unit } = places.get(book.id)!;
    const key = volume === null ? `\u0000${book.id}` : series;
    groups.set(key, [...(groups.get(key) ?? []), { book, volume, unit, name }]);
  }
  const series = [...groups.entries()]
    .filter(([key, items]) => grouped && !key.startsWith("\u0000") && items.length > 1)
    .map(([key, items]) => [key, [...items].sort((a, b) => (a.volume ?? 0) - (b.volume ?? 0))] as const);
  const singles = books.filter((book) => !series.some(([, items]) => items.some((item) => item.book.id === book.id)));
  return [
    ...series.map(([key, items]) => ({ key, label: items[0].name, items: items.map((item) => item.book), badges: badgesOf(items) })),
    ...(singles.length ? [{ key: "singles", label: series.length ? "Sách khác" : "", items: singles, badges: undefined }] : []),
  ];
}

/** Sách cùng bộ đứng cạnh nhau theo số tập; sách lẻ ở cuối. Chỉ gom khi không lọc, không tìm. */
export function SeriesShelves({ books, twins, memory, grouped = true }: { books: ListenBook[]; twins: Set<string>; memory?: string; grouped?: boolean }) {
  const sections = librarySections(books, grouped);
  const rows = useListPresence(sections, (section) => section.key);
  return <div className="mt-6 space-y-10">{rows.map(({ key, item, state, ref }) => (
    <section key={key} ref={ref} aria-label={item.label || "Sách lẻ"} className="motion-row" data-state={state} inert={state === "exit"}><div>
      {grouped && (item.label || item.items.length > 4) ? (
        <Fold storageKey={`library.series.${key}`} title={item.label || "Sách lẻ"} summary={`${item.items.length} cuốn`}>
          <Shelf books={item.items} badges={item.badges} twins={twins} memory={memory && `${memory}.${key}`} />
        </Fold>
      ) : <Shelf books={item.items} badges={item.badges} twins={twins} memory={memory && `${memory}.${key}`} />}
    </div></section>
  ))}</div>;
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
  const libraryQuery = useListenLibrary();
  const { data: allBooks, isLoading } = libraryQuery;
  // Sách chỉ có chữ chưa có chương nghe được nhưng đã ở trong thư viện (đọc được ngay): không phải sách "sắp có".
  const books = useMemo(() => allBooks?.filter((book) => book.chaptersAvailable > 0 || book.stage === "text"), [allBooks]);
  const upcoming = useMemo(() => allBooks?.filter((book) => book.chaptersAvailable === 0 && book.stage !== "text") ?? [], [allBooks]);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
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
  const libraryRows = useListPresence(books ?? [], (book) => book.id);
  const upcomingRows = useListPresence(upcoming, (book) => book.id);
  const noResultsTitle = query ? `Không tìm thấy sách nào khớp “${query}”` : "Không có sách ở đây";
  const grouped = filter === "all" && !folded;
  const shelvesKey = JSON.stringify(librarySections(shown, grouped).map(section => [section.key, Boolean(grouped && (section.label || section.items.length > 4))]));
  return (
    <div ref={container} className="mx-auto max-w-[1180px] px-4 pb-16 pt-6 sm:px-10 sm:pt-9">
      {/* Hai nút cạnh tiêu đề không được bóp tiêu đề thành "Thư / viện" ở 390 px (soát UX 05-10): tiêu đề giữ một dòng, nút xuống dưới. */}
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div className="shrink-0">
          <h1 className="whitespace-nowrap text-2xl font-bold tracking-tight sm:text-[1.75rem]">Thư viện</h1>
          <MotionRegion as="p" motionKey={books?.length ?? 0} className="mt-1 text-sm text-fg-2">{books?.length ? `${books.length} cuốn` : ""}</MotionRegion>
        </div>
        {/* Thư viện trống: nút giữa màn (`empty`) là lời mời chính - nút thứ hai cùng tên ở đầu trang chỉ lặp lại (soát UX a9). */}
        <MotionPresence open={Boolean(books?.length || upcoming.length)} className="-m-1" bodyClassName="p-1">{header}</MotionPresence>
      </header>
      {recap}
      {upcomingRows.length > 0 && (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {upcomingRows.map(({ key, item, state, ref }) => (
            <div key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}><div><UpcomingCard book={item} onOpen={onOpenUpcoming} /></div></div>
          ))}
        </div>
      )}
      <LoadingCrossfade loading={isLoading} placeholder={
        <div className="mt-8 grid grid-cols-2 gap-x-4 gap-y-7 sm:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] sm:gap-x-6">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index}>
              <Skeleton className="aspect-square w-full rounded-lg" />
              <Skeleton className="mt-3 h-4 w-3/4" />
            </div>
          ))}
        </div>
      }>
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
            <MotionRegion motionKey={listening.id} className="mt-6">
              <ContinueCard book={listening} />
            </MotionRegion>
          )}</MotionPresence>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
            <Segmented<Filter>
              label="Lọc sách"
              // Điện thoại: mỗi nút lọc đủ 48 px để chạm; cả thanh trải hết bề ngang, các nút chia đều - chữ to (cỡ chữ hệ thống 1,3) không bị cắt "Nghe xong".
              // Chữ to hơn nữa (cỡ chữ trình duyệt 32 px, soát uxfix32) thì nhãn xuống dòng trong nút thay vì đè lên nút bên cạnh.
              className="max-sm:flex max-sm:w-full"
              itemClassName="max-sm:h-auto max-sm:min-h-[48px] max-sm:min-w-0 max-sm:flex-1 max-sm:px-1 max-sm:whitespace-normal"
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
                className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-panel px-2 text-sm text-fg outline-none focus:border-focus max-sm:h-[48px]"
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
                className="touch-row h-9 w-full rounded-lg border border-line bg-panel pl-9 pr-9 text-sm outline-none placeholder:text-fg-3 focus:border-focus sm:w-80 [&::-webkit-search-cancel-button]:hidden"
              />
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  aria-label="Xoá ô tìm"
                  inert={!query}
                  aria-hidden={!query}
                  style={{ opacity: query ? 1 : 0, pointerEvents: query ? undefined : "none" }}
                  className="absolute right-1 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-fg-3 transition-opacity duration-motion-fast hover:bg-hover hover:text-fg"
                >
                  <X className="size-4" />
                </button>
            </label>
          </div>
          {/* Chỉ fade kết quả: header/tiếp tục nghe/controls giữ một cây. Ảnh theo scrollMemory trước paint. */}
          <MotionRegion followScroll fadeThrough motionKey={[filter, sort, folded, shown.map(book => book.id), !shown.length && noResultsTitle]}>
            {/* Chỉ reset khi đổi cấu trúc kệ/Fold: tránh hàng exit đổi bố cục rồi chồng ảnh.
                Cùng cấu trúc giữ node, focus và Windowed; presence lo IDs vào/ra. */}
            <SeriesShelves key={shelvesKey} books={shown} twins={twins} memory={memory} grouped={grouped} />
            <MotionPresence open={!shown.length}>
              {!shown.length && <EmptyState icon={Search} title={noResultsTitle} className="mt-4">
                {query ? "Thử tên sách hoặc tác giả khác." : EMPTY_TEXT[filter]}
              </EmptyState>}
            </MotionPresence>
          </MotionRegion>
        </>
      )}
      </LoadingCrossfade>
    </div>
  );
}
