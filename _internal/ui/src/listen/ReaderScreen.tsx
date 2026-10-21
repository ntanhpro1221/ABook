import * as Popover from "@radix-ui/react-popover";
import { ArrowLeft, ArrowRight, BookOpenText, ChevronLeft, ChevronRight, Headphones, Search, Type } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import { BOOK_STORAGE } from "@/shared/bookStorage";
import { cn } from "@/shared/cn";
import { useMediaQuery } from "@/shared/media";
import { usePageTitle } from "@/shared/title";
import { Button, EmptyState, IconButton, Skeleton } from "@/shared/ui";
import { FindInBook } from "./FindInBook";
import { chapterToFollow, firstVisibleIndex } from "./follow";
import { chapterOpenProblem, readerHint } from "./labels";
import { usePlayer } from "./player";
import { JumpToPlaying, ReadAlongText, useFollowVoice, useListenFrom, usePlayingSentence } from "./ReadAlongText";
import { useSentenceMenu, type SentenceEditing } from "./SentenceMenu";
import { useChapterScript, useListenBook, useSource } from "./source";

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
const LEADINGS = [1.6, 1.8, 2];
/** Điện thoại: nút trên thanh đầu đủ 48 px để chạm. */
const TOUCH = "max-sm:size-[48px]";
/** Thanh nổi dưới đáy màn đọc: không chiếm chỗ (cao 0, nội dung neo lên từ mép dưới) - nổi trong khoảng đáy để trống của bài (pb-40)
 *  thay vì đẩy bài dài thêm lúc hiện ra. Hiện ra khi đang ở cuối chương thì thẻ "Chương tiếp theo" vẫn nằm trên nó (soát a26 L9). */
const FLOATING = "pointer-events-none sticky bottom-6 h-0";
const FLOATING_BODY = "absolute inset-x-0 bottom-0 flex";

function loadPrefs(): ReaderPrefs {
  try {
    return { size: 19, leading: 1.8, ...JSON.parse(localStorage.getItem(PREFS_KEY) ?? "{}") };
  } catch {
    return { size: 19, leading: 1.8 };
  }
}

function localReadingKey(bookId: string) {
  return BOOK_STORAGE.reading + bookId;
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
  const chapters = book?.chapters ?? [];
  const chapterId = Number(chapterParam ?? book?.state.reading?.chapterId ?? chapters[0]?.id ?? 0);
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
  const container = useRef<HTMLDivElement | null>(null);
  const saveTimer = useRef<number | undefined>(undefined);
  const restored = useRef("");

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
    const key = `${id}:${chapterId}:${location.key}`;
    if (restored.current === key) return;
    restored.current = key;
    const requested = params.get("at");
    const reading = book.state.reading?.chapterId === chapterId ? book.state.reading.index : null;
    let local: number | null = null;
    try {
      const saved = JSON.parse(localStorage.getItem(localReadingKey(id)) ?? "null");
      if (saved?.chapterId === chapterId) local = saved.index;
    } catch {
      /* bỏ qua */
    }
    const target = requested !== null ? Number(requested) : playingIndex >= 0 ? playingIndex : reading ?? local ?? 0;
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
  }, [book, canListen, chapterId, follow, id, lineEdit, listenFrom, location.key, params, playingIndex, script, select]);

  // Chỗ đọc = câu đầu tiên còn thấy trong khung; lưu thưa (2 giây sau lần cuộn cuối).
  const onScroll = useCallback(() => {
    follow.onScroll();
    if (!script) return;
    const found = visibleSentence(container.current);
    setCurrent(found);
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      try {
        localStorage.setItem(localReadingKey(id), JSON.stringify({ chapterId, index: found, at: Date.now() / 1000 }));
      } catch {
        /* bỏ qua */
      }
      void source.saveReading?.(id, chapterId, found).catch(() => undefined);
    }, 2000);
  }, [chapterId, follow, id, script, source]);

  useEffect(() => () => window.clearTimeout(saveTimer.current), []);

  // Thông báo (Hoàn tác, dấu trang...) nằm dưới thanh đầu của màn đọc, không che nút "Nghe từ đây" ở góc trên (soát a70): vị trí trên của vùng
  // thông báo theo mép dưới thanh đầu (App đọc --toast-top).
  const header = useRef<HTMLElement | null>(null);
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

  if (!book || isLoading) {
    return (
      <div className="mx-auto max-w-[68ch] space-y-4 px-6 pt-10">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
      </div>
    );
  }
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
  const hint = readerHint({ textOnly, canSpeak, timed: script.timed, tapped: Boolean(prefs.tapped), coarse, wish: lineEdit?.mode === "wish", readings: readingEdit || lineEdit?.mode === "wish" });
  const name = chapter.subtitle || chapter.title;

  return (
    <div className="flex h-full flex-col">
      <header ref={header} className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-bg/95 px-3 backdrop-blur max-sm:h-auto max-sm:flex-wrap max-sm:gap-y-0 sm:px-6">
        <IconButton label="Về trang sách" icon={ArrowLeft} onClick={() => navigate(`/book/${id}`)} className={TOUCH} />
        {/* Điện thoại: sáu nút đã chiếm gần hết bề ngang, tên chương bị cụt còn vài chữ - tên xuống hàng riêng dưới các nút (soát UX a11). */}
        <div className="min-w-0 flex-1 max-sm:order-last max-sm:basis-full max-sm:px-1 max-sm:pb-2">
          <div className="truncate text-sm font-semibold">{name}</div>
          {/* Tên chương đã ở dòng trên: dòng dưới chỉ thêm "Chương 3" khi dòng trên là tên riêng của chương. */}
          <div className="truncate text-xs text-fg-2">{chapter.subtitle ? `${book.title} · ${chapter.title}` : book.title}</div>
        </div>
        <IconButton label="Chương trước" icon={ChevronLeft} disabled={index <= 0} onClick={() => go(-1)} className={cn(TOUCH, "max-sm:ml-auto")} />
        <IconButton label="Chương sau" icon={ChevronRight} disabled={index >= chapters.length - 1} onClick={() => go(1)} className={TOUCH} />
        <IconButton label="Tìm trong sách" icon={Search} onClick={() => setFinding(true)} className={TOUCH} />
        <Popover.Root>
          <Popover.Trigger asChild>
            <button type="button" aria-label="Cỡ chữ và giãn dòng" className={cn("grid size-9 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg", TOUCH)}>
              <Type className="glyph" />
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content align="end" sideOffset={8} className="z-50 w-64 rounded-xl border border-line bg-panel p-3 shadow-float">
              <div className="text-xs font-medium text-fg-2">Cỡ chữ</div>
              <div className="mt-1.5 grid grid-cols-5 gap-1">
                {SIZES.map((size) => (
                  <button
                    key={size}
                    type="button"
                    aria-pressed={prefs.size === size}
                    onClick={() => setPrefs({ ...prefs, size })}
                    className={cn("h-9 rounded-lg max-sm:h-[48px]", prefs.size === size ? "bg-accent-soft font-semibold text-accent-text" : "hover:bg-hover")}
                    style={{ fontSize: Math.round(size * 0.75) }}
                  >
                    A
                  </button>
                ))}
              </div>
              <div className="mt-3 text-xs font-medium text-fg-2">Giãn dòng</div>
              <div className="mt-1.5 grid grid-cols-3 gap-1">
                {LEADINGS.map((leading) => (
                  <button
                    key={leading}
                    type="button"
                    aria-pressed={prefs.leading === leading}
                    onClick={() => setPrefs({ ...prefs, leading })}
                    className={cn("tabular h-9 rounded-lg text-sm max-sm:h-[48px]", prefs.leading === leading ? "bg-accent-soft font-semibold text-accent-text" : "hover:bg-hover")}
                  >
                    {leading.toLocaleString("vi-VN")}
                  </button>
                ))}
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
        {canListen && (
          <>
            {/* Một nhãn cố định: nút luôn nghe từ chỗ đang thấy trên màn (hay nghe tiếp câu đang nghe dở nếu nó còn trên màn). */}
            <Button size="sm" variant="primary" icon={Headphones} onMouseDown={(event) => event.preventDefault()} onClick={listenHere} className="max-sm:hidden">
              Nghe từ đây
            </Button>
            {/* Điện thoại: cùng việc, chỉ còn biểu tượng - trước đây nút ẩn hẳn và chỉ còn cách đoán là chạm vào câu. */}
            <IconButton label="Nghe từ đây" icon={Headphones} tone="solid" onClick={listenHere} className={cn("sm:hidden", TOUCH)} />
          </>
        )}
      </header>

      <div ref={container} onScroll={onScroll} {...follow.input} className="relative min-h-0 flex-1 overflow-y-auto">
        {/* Hộp (Radix) mở / đóng thì đặt lên body pointer-events:none và biến --removed-body-scroll-bar-size (khoá cuộn) - cả hai đều
            kế thừa, chương 1,5 triệu chữ phải tính lại kiểu chữ của mọi câu: ~400 ms mỗi lần mở / đóng ô "Tìm trong sách" (soát uxfix30).
            Giá trị riêng ở đây chặn thay đổi lan xuống; lớp phủ của hộp vẫn che trang nên bấm ra ngoài vẫn không tới chữ. */}
        <article
          className="pointer-events-auto mx-auto max-w-[68ch] px-6 pb-40 pt-8 [--removed-body-scroll-bar-size:0px]"
          style={{ fontSize: prefs.size, lineHeight: prefs.leading }}
        >
          {hint && (
            <p className={cn("mb-6 text-sm leading-relaxed text-fg-2", (textOnly || !script.timed) && "rounded-lg bg-hover px-4 py-3")}>{hint}</p>
          )}
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
              className="mt-12 flex w-full items-center justify-between rounded-2xl border border-line bg-panel px-5 py-4 text-left text-base hover:border-accent"
            >
              <span>
                <span className="block text-xs text-fg-2">Chương tiếp theo</span>
                <span className="block font-semibold">{chapters[index + 1].subtitle || chapters[index + 1].title}</span>
              </span>
              <ArrowRight className="size-5 text-fg-2" />
            </button>
          )}
        </article>
        {menu.bar && (
          <div className={FLOATING}>
            <div className={FLOATING_BODY}>
              <div className="w-full">{menu.bar}</div>
            </div>
          </div>
        )}
        {selected === null && follow.showJump && (
          <div className={FLOATING}>
            <div className={cn(FLOATING_BODY, "justify-center")}>
              <JumpToPlaying onClick={follow.jump} />
            </div>
          </div>
        )}
      </div>
      <FindInBook book={book} open={finding} onOpenChange={setFinding} />
      {menu.dialogs}
    </div>
  );
}
