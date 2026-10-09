import * as Popover from "@radix-ui/react-popover";
import { ArrowLeft, ArrowRight, BookmarkPlus, BookOpenText, ChevronLeft, ChevronRight, Headphones, Pencil, Play, Search, Type } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { lineEditing } from "@/shared/capabilities";
import { useMediaQuery } from "@/shared/media";
import { excerpt } from "@/shared/format";
import { usePageTitle } from "@/shared/title";
import { Button, EmptyState, IconButton, Skeleton } from "@/shared/ui";
import { canEditBook } from "./EditBook";
import { FindInBook } from "./FindInBook";
import { chapterToFollow, firstVisibleIndex } from "./follow";
import { readerHint } from "./labels";
import { LineWishDialog, useWishes, WaitingMark } from "./LineWishes";
import { usePlayer } from "./player";
import { JumpToPlaying, ReadAlongText, useFollowVoice, useListenFrom, usePlayingSentence } from "./ReadAlongText";
import { wordOf } from "./readings";
import { useChapterScript, useListenBook, useListenMutations, useSource } from "./source";
import { WordReadingDialog } from "./WordReadings";

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
/** Điện thoại: nút trên thanh đầu đủ 44 px để chạm. */
const TOUCH = "max-sm:size-[44px]";

function loadPrefs(): ReaderPrefs {
  try {
    return { size: 19, leading: 1.8, ...JSON.parse(localStorage.getItem(PREFS_KEY) ?? "{}") };
  } catch {
    return { size: 19, leading: 1.8 };
  }
}

function localReadingKey(bookId: string) {
  return `abook-reading-${bookId}`;
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

/** `editing`: false ở thiết bị điều khiển từ xa (không sửa sách ở đó). `onOpenStudioScript`: máy tính, cuốn có xưởng - mở đúng câu ở
 *  tab Kịch bản của Studio, nơi sửa thật. */
export function ReaderScreen({
  editing = true,
  onOpenStudioScript,
}: {
  editing?: boolean;
  onOpenStudioScript?: (bookId: string, chapterId: number, stableId: string) => void;
}) {
  const { id = "", chapterId: chapterParam } = useParams();
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const source = useSource();
  const player = usePlayer();
  const { data: book } = useListenBook(id);
  const mutations = useListenMutations(id);
  const chapters = book?.chapters ?? [];
  const chapterId = Number(chapterParam ?? book?.state.reading?.chapterId ?? chapters[0]?.id ?? 0);
  const chapter = chapters.find((item) => item.id === chapterId);
  const index = chapters.findIndex((item) => item.id === chapterId);
  usePageTitle(book && chapter ? `${chapter.subtitle || chapter.title} · ${book.title}` : book?.title);
  const { data: script, isLoading } = useChapterScript(id, chapter);
  // Chương chỉ có chữ (sách nhập từ EPUB / DOCX / PDF / TXT, chưa có audio): đọc được, không sửa từng câu; máy có giọng thì giọng máy đọc.
  const textOnly = chapter?.state === "text";
  const { canSpeak, canListen, listenFrom } = useListenFrom(id, book, chapter, script);
  // Sửa một câu (docs/EDITING.md, P2a): cuốn không có xưởng ghi ý muốn chờ Studio ngay tại đây; cuốn có xưởng sửa ở Studio; cuốn
  // nghe thẳng từ máy khác hay chưa cài Studio: nút vẫn hiện, mờ đi, kèm lý do.
  const lineEdit = editing && !textOnly ? lineEditing(book?.capabilities) : null;
  const wishes = useWishes(id, lineEdit?.mode === "wish");
  // "Đọc từ này là…": cuốn chỉ có chữ của máy này - giữ (hay bấm chuột phải) một chữ để dạy giọng đọc cách đọc nó cho cả cuốn.
  const readingEdit = editing && textOnly && canEditBook(book);
  const [readingWord, setReadingWord] = useState<string | null>(null);
  // Câu của hộp "Đọc từ này là…" mở từ nút “Sửa cách đọc” (cho chọn từ trong câu); giữ một chữ thì cũng kèm câu để đổi sang từ khác.
  const [readingSentence, setReadingSentence] = useState("");
  // Cuốn có audio: giữ một chữ mở hộp “Sửa câu này” thẳng ở bước sửa cách đọc từ ấy (cùng việc với cuốn chỉ có chữ).
  const [wishWord, setWishWord] = useState<string | null>(null);
  const [selectedWord, setSelectedWord] = useState(-1);
  const coarse = useMediaQuery("(pointer: coarse)");
  const [prefs, setPrefs] = useState<ReaderPrefs>(loadPrefs);
  const [selected, setSelected] = useState<number | null>(null);
  const [editingLine, setEditingLine] = useState<number | null>(null);
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
      setSelected(null);
    } else if (canListen || lineEdit) setSelected(target);
  }, [book, canListen, chapterId, follow, id, lineEdit, listenFrom, location.key, params, playingIndex, script]);

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
        Chương có thể không còn trong sách.
      </EmptyState>
    );
  }

  /** Nghe từ một câu / một chữ, rồi để trang đi theo giọng. */
  const listen = (sentence: number, word = -1) => {
    if (!listenFrom(sentence, word)) return;
    follow.follow();
    setSelected(null);
    if (!prefs.tapped) setPrefs({ ...prefs, tapped: true });
  };
  // Bấm vào câu: có nghe được thì nghe từ đúng chữ vừa bấm (như Đọc to của Edge); sửa được câu thì câu còn được chọn để hiện "Sửa câu này".
  // Bàn phím: mũi tên đi qua các câu, Enter là nghe từ câu ấy.
  const tapSentence = (sentence: number, word: number) => {
    if (canListen) {
      listen(sentence, word);
      if (lineEdit || readingEdit) {
        setSelected(sentence);
        setSelectedWord(word);
      }
      return;
    }
    setSelected(sentence === selected ? null : sentence);
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
  // Dấu trang theo câu: giữ vị trí câu + ~60 chữ đầu câu; chương có audio thì thêm giờ bắt đầu câu để trình phát cũng tới được.
  const bookmarkSentence = (sentence: number) => {
    const segment = script.segments[sentence];
    if (!segment) return;
    mutations.addBookmark.mutate(
      { chapterId, seconds: segment.start ?? 0, note: "", sentence: { index: sentence, quote: segment.text } },
      {
        onSuccess: (mark) => {
          setSelected(null);
          if (mark.existing) {
            toast("Đã có dấu trang ở câu này", { id: "bookmark-existing", description: excerpt(segment.text) });
            return;
          }
          toast.success("Đã đặt dấu trang", {
            id: "bookmark",
            duration: 8000,
            description: excerpt(segment.text),
            cancel: { label: "Hoàn tác", onClick: () => mutations.deleteBookmark.mutate(mark.id) },
          });
        },
        onError: () => toast.error("Chưa đặt được dấu trang"),
      },
    );
  };
  const go = (step: 1 | -1) => {
    const next = chapters[index + step];
    if (next) navigate(`/book/${id}/read/${next.id}`, { replace: true });
  };
  const hint = readerHint({ textOnly, canSpeak, timed: script.timed, tapped: Boolean(prefs.tapped), coarse, wish: lineEdit?.mode === "wish", readings: readingEdit || lineEdit?.mode === "wish" });
  // Giữ một chữ (điện thoại) / bấm chuột phải (máy tính): sửa cách đọc chữ ấy - cuốn chỉ có chữ lưu thẳng, cuốn có audio ghi thành việc chờ máy làm sách.
  const wordMenu = readingEdit
    ? (sentence: number, word: number) => {
        setReadingSentence(script.segments[sentence].text);
        setReadingWord(wordOf(script.segments[sentence].text, word) || null);
      }
    : lineEdit?.mode === "wish"
      ? (sentence: number, word: number) => {
          const held = wordOf(script.segments[sentence].text, word);
          if (!held) return;
          setWishWord(held);
          setEditingLine(sentence);
        }
      : undefined;
  const name = chapter.subtitle || chapter.title;

  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-bg/95 px-3 backdrop-blur sm:px-6">
        <IconButton label="Về trang sách" icon={ArrowLeft} onClick={() => navigate(`/book/${id}`)} className={TOUCH} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{name}</div>
          {/* Tên chương đã ở dòng trên: dòng dưới chỉ thêm "Chương 3" khi dòng trên là tên riêng của chương. */}
          <div className="truncate text-xs text-fg-2">{chapter.subtitle ? `${book.title} · ${chapter.title}` : book.title}</div>
        </div>
        <IconButton label="Chương trước" icon={ChevronLeft} disabled={index <= 0} onClick={() => go(-1)} className={TOUCH} />
        <IconButton label="Chương sau" icon={ChevronRight} disabled={index >= chapters.length - 1} onClick={() => go(1)} className={TOUCH} />
        <IconButton label="Tìm trong sách" icon={Search} onClick={() => setFinding(true)} className={TOUCH} />
        <Popover.Root>
          <Popover.Trigger asChild>
            <button type="button" aria-label="Cỡ chữ và giãn dòng" className={cn("grid size-9 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg", TOUCH)}>
              <Type className="size-[18px]" />
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
                    className={cn("h-9 rounded-lg max-sm:h-[44px]", prefs.size === size ? "bg-accent-soft font-semibold text-accent-text" : "hover:bg-hover")}
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
                    className={cn("tabular h-9 rounded-lg text-sm max-sm:h-[44px]", prefs.leading === leading ? "bg-accent-soft font-semibold text-accent-text" : "hover:bg-hover")}
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
        <article className="mx-auto max-w-[68ch] px-6 pb-40 pt-8" style={{ fontSize: prefs.size, lineHeight: prefs.leading }}>
          {hint && (
            <p className={cn("mb-6 text-sm leading-relaxed text-fg-2", (textOnly || !script.timed) && "rounded-lg bg-hover px-4 py-3")}>{hint}</p>
          )}
          <ReadAlongText
            script={script}
            playingIndex={playingIndex}
            onTap={selectable ? tapSentence : undefined}
            onWordMenu={wordMenu}
            focusIndex={playingIndex >= 0 ? playingIndex : current}
            selected={selected}
            heading="h1"
            headingClassName="pb-2 text-[1.5em] font-bold leading-snug tracking-tight"
            className="space-y-[0.9em]"
            after={(segment) => (segment.stableId && wishes.data?.lines[segment.stableId] ? <WaitingMark /> : null)}
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
        {selected !== null && (
          <div className="pointer-events-none sticky bottom-6 flex flex-col items-center gap-2">
            <div className="pointer-events-auto flex flex-wrap items-center justify-center gap-2">
              {canListen && (
                <button
                  type="button"
                  onClick={() => listen(selected)}
                  onMouseDown={(event) => event.preventDefault()}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-fg px-5 py-2.5 text-sm font-semibold text-bg shadow-float"
                >
                  <Play className="size-4" fill="currentColor" strokeWidth={0} /> Nghe từ câu này
                </button>
              )}
              <button
                type="button"
                onClick={() => bookmarkSentence(selected)}
                onMouseDown={(event) => event.preventDefault()}
                className="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-panel px-4 py-2.5 text-sm font-semibold shadow-float ring-1 ring-line"
              >
                <BookmarkPlus className="size-4" /> Đặt dấu trang ở câu này
              </button>
              {readingEdit && (
                <button
                  type="button"
                  onClick={() => {
                    const text = script.segments[selected]?.text ?? "";
                    setReadingSentence(text);
                    setReadingWord(selectedWord >= 0 ? wordOf(text, selectedWord) : "");
                  }}
                  onMouseDown={(event) => event.preventDefault()}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-panel px-4 py-2.5 text-sm font-semibold shadow-float ring-1 ring-line"
                >
                  <Pencil className="size-4" /> Sửa cách đọc
                </button>
              )}
              {lineEdit && (
                <button
                  type="button"
                  disabled={lineEdit.mode === "blocked"}
                  onClick={() => {
                    const stableId = script.segments[selected]?.stableId;
                    if (lineEdit.mode === "wish") setEditingLine(selected);
                    else if (lineEdit.mode === "studio" && stableId) onOpenStudioScript?.(id, chapterId, stableId);
                  }}
                  onMouseDown={(event) => event.preventDefault()}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-panel px-4 py-2.5 text-sm font-semibold shadow-float ring-1 ring-line disabled:opacity-60"
                >
                  <Pencil className="size-4" /> {lineEdit.mode === "studio" ? "Sửa trong Studio" : "Sửa câu này"}
                </button>
              )}
            </div>
            {lineEdit?.mode === "blocked" && (
              <p className="pointer-events-auto max-w-sm rounded-xl bg-panel px-3 py-1.5 text-center text-xs text-fg-2 shadow-float ring-1 ring-line">
                Sửa câu này: {lineEdit.note}
              </p>
            )}
          </div>
        )}
        {selected === null && follow.showJump && (
          <div className="pointer-events-none sticky bottom-6 flex justify-center">
            <JumpToPlaying onClick={follow.jump} />
          </div>
        )}
      </div>
      <FindInBook book={book} open={finding} onOpenChange={setFinding} />
      {readingEdit && <WordReadingDialog bookId={id} word={readingWord} sentence={readingSentence} onClose={() => setReadingWord(null)} />}
      {lineEdit?.mode === "wish" && (
        <LineWishDialog
          book={book}
          script={script}
          segmentIndex={editingLine}
          wishes={wishes.data}
          word={wishWord}
          onClose={() => {
            setEditingLine(null);
            setWishWord(null);
          }}
        />
      )}
    </div>
  );
}
