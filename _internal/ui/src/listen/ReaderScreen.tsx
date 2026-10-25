import { MotionRegion } from "@/shared/MotionRegion";
import { SlidingIndicator } from "@/shared/SlidingIndicator";
import { LoadingCrossfade, MotionPresence } from "@/shared/MotionPresence";
import * as Popover from "@radix-ui/react-popover";
import { ArrowLeft, ArrowRight, BookOpenText, ChevronLeft, ChevronRight, Headphones, Search, Type } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type TouchEvent as ReactTouchEvent, type WheelEvent as ReactWheelEvent } from "react";
import { toast } from "@/shared/toast";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import { cn } from "@/shared/cn";
import { useMediaQuery } from "@/shared/media";
import { usePageTitle } from "@/shared/title";
import { useLayoutChangeFade } from "@/shared/motion";
import { Button, EmptyState, IconButton, Skeleton } from "@/shared/ui";
import { FindInBook } from "./FindInBook";
import { chapterToFollow, firstVisibleIndex, SCROLL_KEYS } from "./follow";
import { chapterOpenProblem, readerHint } from "./labels";
import { usePlayer } from "./player";
import { JumpToPlaying, ReadAlongText, useFollowVoice, useListenFrom, usePlayingSentence } from "./ReadAlongText";
import { useSentenceMenu, type SentenceEditing } from "./SentenceMenu";
import { useChapterScript, useListenBook, useSource } from "./source";
import { makeAnchor, textFingerprint } from "./readingAnchor";
import { latestReading, localReading, nextReadingRevision, validReadingRevision, readingIndex, readingKey, readingRecord, type ReadingPosition } from "./readingPosition";

// Chế độ ĐỌC: văn bản chương như một cuốn ebook, đi cùng chỗ đang nghe.
//
// Học từ Whispersync của Audible + Kindle (docs/PLAYER_RESEARCH.md): chuyển qua lại đọc ⇄ nghe đúng chỗ. Ta có sẵn thứ
// họ phải ghép hai sản phẩm mới có: văn bản kèm mốc thời gian từng câu. Đọc được cả chương CHƯA thu âm (văn bản có từ
// lúc tạo sách), nhớ chỗ đọc dở, "Nghe từ đây" bắt đầu nghe đúng câu đang đọc, và câu đang phát sáng lên nếu đang nghe.
// Văn bản, chữ sáng, bấm chữ để nghe và tự cuộn theo giọng dùng chung với tab "Đọc theo" của trình phát (ReadAlongText.tsx).

interface ReaderPrefs {
  size: number;
  leading: number;
  /** Đã nghe từ một câu chọn trong trang ít nhất một lần - thôi nhắc "chạm vào câu". */
  tapped?: boolean;
}

const PREFS_KEY = "abook-reader";
const SIZES = [16, 18, 20, 22, 24];
const LEADINGS = [1.5, 1.7, 1.9];
/** Chữ đọc theo mặc định: 20 px / 1,7 (docs/DESIGN.md 5.5). */
const DEFAULT_PREFS: ReaderPrefs = { size: 20, leading: 1.7 };
/** Điện thoại: nút của thanh điều khiển đủ 48 px để chạm. */
const TOUCH = "max-sm:size-[48px]";
/** Thanh nổi dưới đáy màn đọc: không chiếm chỗ (cao 0, nội dung neo lên từ mép dưới) - nổi trong khoảng đáy để trống của bài (pb-40)
 *  thay vì đẩy bài dài thêm lúc hiện ra. Hiện ra khi đang ở cuối chương thì thẻ "Chương tiếp theo" vẫn nằm trên nó (soát a26 L9). */
const FLOATING = "pointer-events-none sticky bottom-6 h-0";
const FLOATING_BODY = "absolute inset-x-0 bottom-0 flex";

function loadPrefs(): ReaderPrefs {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREFS_KEY) ?? "{}") };
  } catch {
    return DEFAULT_PREFS;
  }
}

/** Câu đầu tiên còn thấy trong khung đọc (follow.firstVisibleIndex trên các câu đang hiện). */
function visibleSentence(box: HTMLElement | null): number {
  if (!box) return 0;
  const view = box.getBoundingClientRect();
  const items = [...box.querySelectorAll<HTMLElement>("[data-sentence]")].map((span) => {
    const rect = span.getBoundingClientRect();
    return { index: Number(span.dataset.index), top: rect.top, bottom: rect.bottom };
  });
  return firstVisibleIndex(items, view);
}

/** Sửa được gì ở thiết bị này: SentenceMenu.SentenceEditing (cùng với tab "Đọc theo" của màn "Đang nghe"). */
export function ReaderScreen(edit: SentenceEditing) {
  const { id = "", chapterId: chapterParam } = useParams();
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const source = useSource();
  const player = usePlayer();
  const { data: book } = useListenBook(id);
  const revisionBook = useRef(book);
  revisionBook.current = book;
  const chapters = book?.chapters ?? [];
  const reading = latestReading(book);
  const record = readingRecord(book);
  const chapterId = Number(chapterParam ?? reading?.chapterId ?? chapters[0]?.id ?? 0);
  const chapter = chapters.find((item) => item.id === chapterId);
  const index = chapters.findIndex((item) => item.id === chapterId);
  usePageTitle(book && chapter ? `${chapter.subtitle || chapter.title} · ${book.title}` : book?.title);
  const { data: script, isLoading, error: scriptError } = useChapterScript(id, chapter);
  // Chương chỉ có chữ (sách nhập từ EPUB / DOCX / PDF / TXT, chưa có audio): đọc được; máy có giọng thì giọng máy đọc.
  const textOnly = chapter?.state === "text";
  const { canSpeak, canListen, listenFrom } = useListenFrom(id, book, chapter, script);
  // "Nghe từ câu này" của thanh việc: hàm nghe khai báo sau (cần kịch bản đã nạp) - đi qua ref.
  const listenRef = useRef<(sentence: number) => void>(() => undefined);
  const menu = useSentenceMenu({ ...edit, bookId: id, book, chapter, script, canListen, onListen: (sentence) => listenRef.current(sentence) });
  const { lineEdit, readingEdit, selected, select } = menu;
  const coarse = useMediaQuery("(pointer: coarse)");
  const [prefs, setPrefs] = useState<ReaderPrefs>(loadPrefs);
  const [current, setCurrent] = useState(0);
  const [finding, setFinding] = useState(false);
  // Thanh điều khiển dưới đáy mờ đi khi người đọc tự cuộn (L7), chạm vào trang là hiện lại.
  const [controls, setControls] = useState(true);
  const container = useRef<HTMLDivElement | null>(null);
  const saveTimer = useRef<number | undefined>(undefined);
  const restored = useRef("");
  const touched = useRef("");
  const { pending, saving } = useMemo(() => ({ pending: { current: undefined as ReadingPosition | undefined }, saving: { current: false } }), [id, record]);
  const owner = `${id}:${record}:${chapterId}`;
  const paragraphs = useMemo(() => script?.segments.map((segment) => segment.text) ?? [], [script]);
  const textHash = useMemo(() => textFingerprint(paragraphs), [paragraphs]);

  const listeningHere = player.track?.bookId === id && player.track.chapterId === chapterId;
  const playingIndex = usePlayingSentence(script, listeningHere);
  // Mở đúng một câu được yêu cầu (?at=, từ dấu trang / tìm kiếm): đứng yên ở đó, chưa theo giọng; còn lại thì đi theo giọng ngay.
  const follow = useFollowVoice(container, playingIndex, { initial: params.get("at") === null, resetKey: `${id}:${chapterId}`, smooth: player.playing });

  // Giọng tự sang chương kế (hay người bấm "Chương sau" ở trình phát) khi màn đọc đang mở đúng chương đang nghe: màn đọc đi theo sang
  // chương mới, như đã tự cuộn theo câu. Người đã tự mở một chương khác chương đang nghe thì để yên, không kéo đi (soát máy thật 03-10).
  const playingChapter = player.track?.bookId === id ? player.track.chapterId : null;
  const lastPlayingChapter = useRef(playingChapter);
  useEffect(() => {
    const before = lastPlayingChapter.current;
    lastPlayingChapter.current = playingChapter;
    const next = chapterToFollow(before, playingChapter, chapterId);
    if (next !== null) navigate(`/book/${id}/read/${next}`, { replace: true });
  }, [chapterId, id, navigate, playingChapter]);

  useEffect(() => {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    } catch {
      /* không lưu được thì thôi */
    }
  }, [prefs]);

  // Ctrl+F (Cmd+F) mở ô "Tìm trong sách" thay cho ô tìm của trình duyệt: tìm cả cuốn, không chỉ chữ đang hiện trên trang.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "f") {
        event.preventDefault();
        setFinding(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Mở chương: tới câu được yêu cầu (?at=), câu đang nghe, hay chỗ đọc dở - theo thứ tự ấy. Mỗi lần được yêu cầu một chỗ (kể cả cùng chương, kể cả
  // cùng chỗ lần nữa - location.key đổi) thì tới đó; `&play=1` (chọn từ ô tìm lúc đang nghe cuốn này): nghe tiếp từ chính câu ấy.
  useEffect(() => {
    if (!script || !book) return;
    const key = `${owner}:${location.key}:${textHash}:${reading?.at ?? 0}`;
    if (restored.current === key) return;
    if (restored.current.startsWith(`${owner}:${location.key}:${textHash}:`) && touched.current === owner) return;
    restored.current = key;
    const requested = params.get("at");
    let anchor: ReadingPosition["anchor"];
    try { anchor = JSON.parse(params.get("anchor") ?? "null") ?? undefined; } catch { /* Liên kết cũ: dùng câu trích và chỉ số. */ }
    const saved = reading?.chapterId === chapterId ? reading : undefined;
    const target = readingIndex(script, requested !== null ? { index: Number(requested), quote: params.get("quote") ?? undefined, anchor }
      : playingIndex >= 0 ? { index: playingIndex } : saved ?? { index: 0 });
    window.requestAnimationFrame(() => {
      // Đầu chương: về đầu trang, không cuộn tới câu đầu - dòng nhắc đứng TRƯỚC câu ấy và từng bị cuộn khuất ngay lúc mở (soát UX 29-09).
      if (target <= 0) container.current?.scrollTo({ top: 0 });
      else container.current?.querySelector<HTMLElement>(`[data-index="${target}"]`)?.scrollIntoView({ block: "start" });
      setCurrent(target);
    });
    if (requested === null) return;
    // Chỗ vừa tìm thấy: chọn câu ấy để thấy nó sáng lên và có nút "Nghe từ câu này"; chọn nghe ngay thì nghe, không cần chọn.
    if (params.get("play") === "1" && canListen && listenFrom(target)) {
      follow.follow();
      select(null);
    } else if (canListen || lineEdit) select(target);
  }, [book, canListen, chapterId, follow, id, lineEdit, listenFrom, location.key, params, playingIndex, script, select, owner, reading, textHash]);

  // Bản local ghi ngay; ACK chỉ xác nhận đúng phiên bản, không xoá chỗ mới vừa cuộn tới.
  const flushReading = useCallback(async () => {
    const place = pending.current;
    if (!place || saving.current || !source.saveReading) return;
    if (!validReadingRevision(place.rev)) {
      place.rev = nextReadingRevision(revisionBook.current, place);
      try { localStorage.setItem(readingKey(id, record), JSON.stringify(place)); }
      catch { toast.error("Chưa lưu được bản dự phòng chỗ đọc", { id: "reading-local" }); }
    }
    saving.current = true;
    try {
      await source.saveReading(id, place.chapterId, place.index, place, record === "default" ? undefined : record);
      if (pending.current === place) pending.current = undefined;
      const local = localReading(id, record);
      if (local && (place.rev ? local.rev?.counter === place.rev.counter && local.rev.node === place.rev.node
        && (local.rev.epoch ?? "") === (place.rev.epoch ?? "") : local.at === place.at)) {
        try { localStorage.setItem(readingKey(id, record), JSON.stringify({ ...place, pending: false })); } catch { /* nguồn đã lưu */ }
      }
    } catch (error) {
      const backup = Boolean(localReading(id, record));
      toast.error("Chưa lưu được chỗ đọc vào hồ sơ", { id: "reading-save", description: `${backup ? "Bạn vẫn có bản lưu trên máy này." : "App sẽ thử lưu lại chỗ đọc của bạn."} ${(error as Error).message}` });
    } finally {
      saving.current = false;
    }
  }, [id, record, source, pending, saving]);

  // Chỗ đọc = câu đầu tiên còn thấy trong khung; lưu thưa (2 giây sau lần cuộn cuối).
  const onScroll = useCallback(() => {
    follow.onScroll();
    if (!script) return;
    const found = visibleSentence(container.current);
    touched.current = owner;
    setCurrent(found);
    const place: ReadingPosition = { chapterId, index: found, at: Date.now() / 1000, rev: nextReadingRevision(book, pending.current ?? localReading(id, record)), anchor: makeAnchor(paragraphs, found, 0, textHash), quote: paragraphs[found]?.slice(0, 200), pending: true };
    pending.current = place;
    try { localStorage.setItem(readingKey(id, record), JSON.stringify(place)); }
    catch { toast.error("Chưa lưu được bản dự phòng chỗ đọc", { id: "reading-local" }); }
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => void flushReading(), 2000);
  }, [book, chapterId, follow, id, script, record, owner, paragraphs, textHash, flushReading, pending]);

  useEffect(() => {
    const saved = localReading(id, record);
    if (saved?.pending) pending.current = saved;
    const flush = () => { void flushReading(); };
    const hidden = () => { if (document.visibilityState === "hidden") flush(); };
    window.addEventListener("pagehide", flush);
    document.addEventListener("visibilitychange", hidden);
    const retry = window.setInterval(flush, 5000);
    return () => {
      window.clearTimeout(saveTimer.current);
      window.clearInterval(retry);
      window.removeEventListener("pagehide", flush);
      document.removeEventListener("visibilitychange", hidden);
      flush();
    };
  }, [id, record, chapterId, flushReading]);

  // Thông báo (Hoàn tác, dấu trang...) nằm dưới thanh đầu của màn đọc, không che nút "Nghe từ đây" ở góc trên (soát a70): vị trí trên của vùng
  // thông báo theo mép dưới thanh đầu (App đọc --toast-top).
  const header = useRef<HTMLElement | null>(null);
  // Đổi cỡ chữ / giãn dòng: cả chương dàn lại - khung chữ hiện dần từ 55 % thay vì nhảy (không chụp ảnh cả chương dài như MotionRegion).
  const article = useRef<HTMLElement | null>(null);
  useLayoutChangeFade(article, `${prefs.size}:${prefs.leading}`);
  useEffect(() => {
    const root = document.documentElement;
    const place = () => {
      const bottom = header.current?.getBoundingClientRect().bottom;
      if (bottom) root.style.setProperty("--toast-top", `${Math.round(bottom + 8)}px`);
    };
    place();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(place);
    if (header.current) observer?.observe(header.current);
    return () => {
      observer?.disconnect();
      root.style.removeProperty("--toast-top");
    };
  }, [book, isLoading]);

  const placeholder = (
      <div className="mx-auto max-w-[68ch] space-y-4 px-[20px] pt-10">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
      </div>
  );
  const content = () => {
    if (!book) return null;

  if (!chapter || !script) {
    return (
      <EmptyState icon={BookOpenText} title="Không mở được chương này" className="mt-20" action={<Button onClick={() => navigate(`/book/${id}`)}>Về trang sách</Button>}>
        {chapterOpenProblem(scriptError)}
      </EmptyState>
    );
  }

  /** Nghe từ một câu / một chữ, rồi để trang đi theo giọng. */
  const listen = (sentence: number, word = -1) => {
    if (!listenFrom(sentence, word)) return;
    follow.follow();
    select(null);
    if (!prefs.tapped) setPrefs({ ...prefs, tapped: true });
  };
  listenRef.current = listen;
  // Bấm vào câu: có nghe được thì nghe từ đúng chữ vừa bấm (như Đọc to của Edge); sửa được câu thì câu còn được chọn để hiện "Sửa câu này".
  // Bàn phím: mũi tên đi qua các câu, Enter là nghe từ câu ấy.
  const tapSentence = (sentence: number, word: number) => {
    if (canListen) {
      listen(sentence, word);
      if (menu.editable) select(sentence, word);
      return;
    }
    select(sentence === selected ? null : sentence, word);
  };
  // "Nghe từ đây" trên thanh đầu: câu đang nghe dở (dừng) vẫn nằm trong màn thì nghe tiếp từ đúng chỗ ấy - trước đây nút luôn nhảy về câu đầu
  // màn hình (1:11 lùi về 0:41, soát UX 29-09). Không thì nghe từ câu đầu tiên còn thấy trên màn.
  const listenHere = () => {
    if (listeningHere && playingIndex >= 0) {
      const box = container.current?.getBoundingClientRect();
      const rect = container.current?.querySelector<HTMLElement>(`[data-index="${playingIndex}"]`)?.getBoundingClientRect();
      if (box && rect && rect.bottom > box.top && rect.top < box.bottom) {
        follow.follow();
        if (!player.playing) player.resume();
        return;
      }
    }
    listen(visibleSentence(container.current));
  };
  // Câu nào cũng chọn được: ít nhất có "Đặt dấu trang ở câu này" (sách chỉ có chữ, máy không có giọng cũng đặt được).
  const selectable = true;
  const go = (step: 1 | -1) => {
    const next = chapters[index + step];
    if (next) navigate(`/book/${id}/read/${next.id}`, { replace: true });
  };
  // Chỉ THAO TÁC cuộn của người (lăn, vuốt, phím cuộn) làm thanh mờ đi - trang tự cuộn theo giọng thì thanh vẫn đứng yên.
  // Sự kiện nổi từ hộp cỡ chữ (portal) không chạm trang; từ chính thanh thì trang vẫn cuộn (thanh nằm trong khung cuộn) nên vẫn tắt
  // theo giọng như mọi lần cuộn tay, chỉ không gỡ thanh đang giữ con trỏ. Tab gọi thanh lại.
  const origin = (target: EventTarget) => {
    const el = target as HTMLElement;
    return el.closest?.("[data-radix-popper-content-wrapper]") ? "popover" : el.closest?.("[data-reader-controls]") ? "bar" : "page";
  };
  const scrollInput = {
    ...follow.input,
    onWheel: (event: ReactWheelEvent<HTMLDivElement>) => {
      const from = origin(event.target);
      if (from === "popover") return;
      follow.input.onWheel();
      if (from === "page") setControls(false);
    },
    onTouchMove: (event: ReactTouchEvent<HTMLDivElement>) => {
      const from = origin(event.target);
      if (from === "popover") return;
      follow.input.onTouchMove();
      if (from === "page") setControls(false);
    },
    onKeyDown: (event: ReactKeyboardEvent<HTMLDivElement>) => {
      const from = origin(event.target);
      if (from === "popover") return;
      if (event.key === "Tab") { setControls(true); return; }
      follow.input.onKeyDown(event);
      if (from === "page" && SCROLL_KEYS.has(event.key)) setControls(false);
    },
    onClick: () => setControls(true),
  };
  const hint = readerHint({ textOnly, canSpeak, timed: script.timed, tapped: Boolean(prefs.tapped), coarse, wish: lineEdit?.mode === "wish", readings: readingEdit || lineEdit?.mode === "wish" });
  const name = chapter.subtitle || chapter.title;
  const bar = (
    <div role="toolbar" aria-label="Điều khiển đọc" data-reader-controls className="pointer-events-auto mx-auto flex max-w-[calc(100vw-16px)] items-center gap-1 rounded-2xl bg-panel px-2 py-1.5 shadow-float">
      <IconButton label="Chương trước" icon={ChevronLeft} disabled={index <= 0} onClick={() => go(-1)} className={TOUCH} />
      <IconButton label="Tìm trong sách" icon={Search} onClick={() => setFinding(true)} className={TOUCH} />
      {/* Một nhãn cố định: nút luôn nghe từ chỗ đang thấy trên màn (hay nghe tiếp câu đang nghe dở nếu nó còn trên màn). */}
      {canListen && (
        // Thanh rộng ~345 px với nhãn: màn dưới 380 px (hay chữ hệ thống 130 % trên máy 360 px) chỉ còn icon - nhãn vẫn đọc cho trình đọc màn hình.
        // Chữ hệ thống phóng to (textZoom Android không đổi bề rộng màn) thì nút này co, nhãn cắt "…" - các nút khác đứng yên trong thanh.
        <Button size="sm" variant="primary" icon={Headphones} onMouseDown={(event) => event.preventDefault()} onClick={listenHere} className="mx-1 min-w-0 max-sm:h-11 max-[379px]:px-3">
          <span className="min-w-0 truncate max-[379px]:sr-only">Nghe từ đây</span>
        </Button>
      )}
      <Popover.Root>
        <Popover.Trigger asChild>
          <button type="button" aria-label="Cỡ chữ và giãn dòng" className={cn("grid size-9 shrink-0 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg", TOUCH)}>
            <Type className="glyph" />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content side="top" align="end" sideOffset={8} collisionPadding={12} className="z-50 w-64 rounded-xl border border-line bg-panel p-3 shadow-float">
            <div className="text-xs font-medium text-fg-2">Cỡ chữ</div>
            <div role="group" aria-label="Cỡ chữ" className="relative mt-1.5 grid grid-cols-5 gap-1">
              <SlidingIndicator variant="pill" className="rounded-lg bg-accent-soft" />
              {SIZES.map((size) => (
                <button
                  key={size}
                  type="button"
                  aria-pressed={prefs.size === size}
                  aria-label={`Cỡ chữ ${size}`}
                  onClick={() => setPrefs({ ...prefs, size })}
                  className={cn("relative h-9 rounded-lg transition-colors duration-motion-medium max-sm:h-[48px]", prefs.size === size ? "font-semibold text-accent-text" : "hover:bg-hover")}
                  style={{ fontSize: Math.round(size * 0.75) }}
                >
                  A
                </button>
              ))}
            </div>
            <div className="mt-3 text-xs font-medium text-fg-2">Giãn dòng</div>
            <div className="relative mt-1.5 grid grid-cols-3 gap-1">
              <SlidingIndicator variant="pill" className="rounded-lg bg-accent-soft" />
              {LEADINGS.map((leading) => (
                <button
                  key={leading}
                  type="button"
                  aria-pressed={prefs.leading === leading}
                  onClick={() => setPrefs({ ...prefs, leading })}
                  className={cn("tabular relative h-9 rounded-lg text-sm transition-colors duration-motion-medium max-sm:h-[48px]", prefs.leading === leading ? "font-semibold text-accent-text" : "hover:bg-hover")}
                >
                  {leading.toLocaleString("vi-VN")}
                </button>
              ))}
            </div>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
      <IconButton label="Chương sau" icon={ChevronRight} disabled={index >= chapters.length - 1} onClick={() => go(1)} className={TOUCH} />
    </div>
  );

  return (
    <div className="motion-reveal flex h-full flex-col">
      {/* Thanh đầu chỉ có nút về + tên chương, nền đặc, đứng NGOÀI khung cuộn: không bao giờ đè lên chữ. Mọi điều khiển khác ở thanh dưới. */}
      <header ref={header} data-reader-header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-bg page-x">
        {/* Nét mũi tên (không phải hộp nút) đứng trên lề màn như mép chữ bên dưới: bù phần đệm của nút 36 / 48 px (soát 25-10: lệch 7,5 px). */}
        <IconButton label="Về trang sách" icon={ArrowLeft} onClick={() => navigate(`/book/${id}`)} className={cn(TOUCH, "-ml-[10px] max-sm:-ml-[18px]")} />
        <h2 className="min-w-0 flex-1 truncate text-base font-semibold" title={chapter.subtitle ? `${chapter.title} · ${name}` : name}>
          <MotionRegion as="span" motionKey={chapterId} className="block truncate">{name}</MotionRegion>
        </h2>
      </header>

      <div ref={container} onScroll={onScroll} {...scrollInput} data-reader-scroll className="reading-surface relative min-h-0 flex-1 overflow-y-auto">
        {/* Mép trên mờ dần như mép dưới (soát 25-10 V6): chữ cuộn lên không bị cắt ngang dưới thanh đầu. Dính mép trên, cao bằng lề pt-8 của bài và
            lùi lại bằng đúng chừng ấy (-mb-8) nên không chiếm chỗ; chưa cuộn thì chỉ phủ lên phần lề trống nên chẳng thấy. */}
        <div aria-hidden data-reader-fade-top className="pointer-events-none sticky top-0 z-[1] -mb-8 h-8 bg-gradient-to-b from-[var(--read-bg)] from-40% to-transparent" />
        {/* Hộp (Radix) mở / đóng thì đặt lên body pointer-events:none và biến --removed-body-scroll-bar-size (khoá cuộn) - cả hai đều
            kế thừa, chương 1,5 triệu chữ phải tính lại kiểu chữ của mọi câu: ~400 ms mỗi lần mở / đóng ô "Tìm trong sách" (soát uxfix30).
            Giá trị riêng ở đây chặn thay đổi lan xuống; lớp phủ của hộp vẫn che trang nên bấm ra ngoài vẫn không tới chữ. */}
        <article
          ref={article}
          className="pointer-events-auto mx-auto max-w-[68ch] px-[20px] pb-40 pt-8 [--removed-body-scroll-bar-size:0px]"
          style={{ fontSize: prefs.size, lineHeight: prefs.leading }}
        >
          <MotionPresence open={Boolean(hint)}>
            <p className={cn("mb-6 text-sm leading-relaxed text-fg-2", (textOnly || !script.timed) && "rounded-lg bg-hover px-4 py-3")}>{hint}</p>
          </MotionPresence>
          <ReadAlongText
            script={script}
            playingIndex={playingIndex}
            onTap={selectable ? tapSentence : undefined}
            onWordMenu={menu.wordMenu}
            focusIndex={playingIndex >= 0 ? playingIndex : current}
            selected={selected}
            heading="h1"
            headingClassName="pb-2 text-[1.5em] font-bold leading-snug tracking-tight"
            className="space-y-[0.9em]"
            after={menu.waitingMark}
          />
          {index < chapters.length - 1 && (
            <button
              type="button"
              onClick={() => go(1)}
              className="mt-12 flex w-full items-center justify-between gap-4 border-t border-line py-5 text-left text-base transition-colors duration-motion-fast hover:text-accent-text"
            >
              <span>
                <span className="block text-xs text-fg-2">Chương tiếp theo</span>
                <span className="block font-semibold">{chapters[index + 1].subtitle || chapters[index + 1].title}</span>
              </span>
              <ArrowRight className="ink-end size-5 text-fg-2 [--icon-w:17.5px]" />
            </button>
          )}
        </article>
        {/* Chữ mờ dần dưới thanh nổi thay vì lộ nửa dòng giữa thanh và trình phát nhỏ (soát T11); ẩn thanh thì cũng tắt dần. */}
        <div
          aria-hidden
          data-reader-fade
          className={cn(
            "pointer-events-none sticky bottom-0 -mt-28 h-28 bg-gradient-to-t from-[var(--read-bg)] from-40% to-transparent transition-opacity duration-motion-slow",
            controls || menu.bar ? "opacity-100" : "opacity-0",
          )}
        />
        {/* Thanh chọn câu / "Tới câu đang nghe" hiện / ẩn dần. Vùng con có khoá cố định: chúng không làm vùng của cả màn (MotionRegion dưới cùng)
            thấy "nội dung đổi" mà mờ chéo cả chương mỗi lần chọn câu (W2). */}
        <MotionRegion motionKey="floating" className={FLOATING}>
          <div className={cn(FLOATING_BODY, "flex-col items-center")}>
            <MotionPresence open={Boolean(menu.bar)} className="w-full">{menu.bar}</MotionPresence>
            <MotionPresence open={selected === null && follow.showJump}><JumpToPlaying onClick={follow.jump} className="mb-2" /></MotionPresence>
            {/* Đang chọn câu thì thanh việc của câu thay chỗ thanh này. */}
            {/* Vùng có khoá riêng: "Nghe từ đây" tới / đi (giọng máy sẵn sàng muộn) mờ qua cả thanh, không bật vào đẩy các nút khác. */}
            <MotionPresence open={controls && !menu.bar}><MotionRegion motionKey={canListen}>{bar}</MotionRegion></MotionPresence>
          </div>
        </MotionRegion>
      </div>
      <FindInBook book={book} open={finding} onOpenChange={setFinding} />
      {menu.dialogs}
    </div>
  );
  };
  // Cả chuỗi khung cao đúng bằng màn: chỉ khung chữ cuộn, thanh đầu và thanh dưới đứng yên (trước đây cả trang cuộn, thanh đầu trong suốt đè lên chữ).
  return <LoadingCrossfade loading={!book || isLoading} placeholder={placeholder} className="h-full grid-rows-[minmax(0,1fr)] [&>.motion-loading-content]:h-full"><MotionRegion className="h-full">{content()}</MotionRegion></LoadingCrossfade>;
}
