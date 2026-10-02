import * as Popover from "@radix-ui/react-popover";
import { ArrowLeft, ArrowRight, BookOpenText, ChevronLeft, ChevronRight, Headphones, Locate, Play, Type } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { cn } from "@/shared/cn";
import { excerpt } from "@/shared/format";
import { usePageTitle } from "@/shared/title";
import { Button, EmptyState, IconButton, Skeleton } from "@/shared/ui";
import { useClock } from "./clock";
import { usePlayListenBook } from "./LibraryScreen";
import { usePlayer } from "./player";
import { sentenceIndexAt } from "./PlayerViews";
import { useListenBook, useScript, useSource } from "./source";

// Chế độ ĐỌC: văn bản chương như một cuốn ebook, đi cùng chỗ đang nghe.
//
// Học từ Whispersync của Audible + Kindle (docs/PLAYER_RESEARCH.md): chuyển qua lại đọc ⇄ nghe đúng chỗ. Ta có sẵn thứ
// họ phải ghép hai sản phẩm mới có: văn bản kèm mốc thời gian từng câu. Đọc được cả chương CHƯA thu âm (văn bản có từ
// lúc tạo sách), nhớ chỗ đọc dở, "Nghe từ đây" bắt đầu nghe đúng câu đang đọc, và câu đang phát sáng lên nếu đang nghe.

interface ReaderPrefs {
  size: number;
  leading: number;
  /** Đã nghe từ một câu chọn trong trang ít nhất một lần - thôi nhắc "chạm vào câu". */
  tapped?: boolean;
}

const PREFS_KEY = "abook-reader";
const SIZES = [16, 18, 20, 22, 24];
const LEADINGS = [1.6, 1.8, 2];

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

export function ReaderScreen() {
  const { id = "", chapterId: chapterParam } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const source = useSource();
  const player = usePlayer();
  const playBook = usePlayListenBook();
  const { data: book } = useListenBook(id);
  const chapters = book?.chapters ?? [];
  const chapterId = Number(chapterParam ?? book?.state.reading?.chapterId ?? chapters[0]?.id ?? 0);
  const chapter = chapters.find((item) => item.id === chapterId);
  const index = chapters.findIndex((item) => item.id === chapterId);
  usePageTitle(book && chapter ? `${chapter.subtitle || chapter.title} · ${book.title}` : book?.title);
  const { data: script, isLoading } = useScript(id, chapterId || undefined);
  const [prefs, setPrefs] = useState<ReaderPrefs>(loadPrefs);
  const [selected, setSelected] = useState<number | null>(null);
  const [current, setCurrent] = useState(0);
  const container = useRef<HTMLDivElement | null>(null);
  const saveTimer = useRef<number | undefined>(undefined);
  const restored = useRef("");

  const listeningHere = player.track?.bookId === id && player.track.chapterId === chapterId;
  const starts = useMemo(() => (script?.timed ? script.segments.map((segment) => segment.start ?? 0) : []), [script]);
  const playingIndex = useClock((time) => (listeningHere && starts.length ? sentenceIndexAt(starts, time) : -1));

  useEffect(() => {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    } catch {
      /* không lưu được thì thôi */
    }
  }, [prefs]);

  // Mở chương: tới câu được yêu cầu (?at=), chỗ đọc dở, hoặc câu đang phát - theo thứ tự ấy.
  useEffect(() => {
    if (!script || !book) return;
    const key = `${id}:${chapterId}`;
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
    const target = requested !== null ? Number(requested) : reading ?? local ?? (playingIndex >= 0 ? playingIndex : 0);
    window.requestAnimationFrame(() => {
      // Đầu chương: về đầu trang, không cuộn tới câu đầu - dòng "Chương này chưa có audio" đứng TRƯỚC câu ấy và từng bị
      // cuộn khuất ngay lúc mở (soát UX 29-09).
      if (target <= 0) container.current?.scrollTo({ top: 0 });
      else container.current?.querySelector<HTMLElement>(`[data-index="${target}"]`)?.scrollIntoView({ block: "start" });
      setCurrent(target);
    });
  }, [book, chapterId, id, params, playingIndex, script]);

  // Chỗ đọc = câu đầu tiên còn thấy ở đỉnh khung; lưu thưa (2 giây sau lần cuộn cuối).
  const onScroll = useCallback(() => {
    const box = container.current;
    if (!box || !script) return;
    const top = box.getBoundingClientRect().top + 72;
    const spans = box.querySelectorAll<HTMLElement>("[data-index]");
    let found = 0;
    for (const span of spans) {
      if (span.getBoundingClientRect().bottom >= top) {
        found = Number(span.dataset.index);
        break;
      }
    }
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
  }, [chapterId, id, script, source]);

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

  const listenFrom = (sentence: number) => {
    const start = script.segments[sentence]?.start;
    if (!script.timed || start === null || start === undefined) return;
    if (player.track?.bookId === id) player.jumpTo(chapterId, start, `Nghe từ “${excerpt(script.segments[sentence].text)}”`);
    else void playBook(book, chapterId, start);
    setSelected(null);
    if (!prefs.tapped) setPrefs({ ...prefs, tapped: true });
  };
  // "Nghe từ đây" trên thanh đầu: câu đang nghe dở (dừng) vẫn nằm trong màn thì nghe tiếp từ đúng chỗ ấy - trước đây nút
  // luôn nhảy về câu đầu màn hình (1:11 lùi về 0:41, soát UX 29-09). Câu ấy đã trôi khỏi màn thì nghe từ câu đang đọc.
  const listenHere = () => {
    if (listeningHere && playingIndex >= 0) {
      const rect = container.current?.querySelector<HTMLElement>(`[data-index="${playingIndex}"]`)?.getBoundingClientRect();
      if (rect && rect.bottom > 0 && rect.top < window.innerHeight) {
        if (!player.playing) player.resume();
        return;
      }
    }
    listenFrom(current);
  };
  const go = (step: 1 | -1) => {
    const next = chapters[index + step];
    if (next) navigate(`/book/${id}/read/${next.id}`, { replace: true });
  };
  const paragraphs: { key: number; items: { index: number; text: string; kind: string; speaker: string }[] }[] = [];
  script.segments.forEach((segment, position) => {
    const last = paragraphs[paragraphs.length - 1];
    const item = { index: position, text: segment.text, kind: segment.kind, speaker: segment.speaker };
    if (last && last.key === segment.paragraph) last.items.push(item);
    else paragraphs.push({ key: segment.paragraph, items: [item] });
  });

  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-bg/95 px-3 backdrop-blur sm:px-6">
        <IconButton label="Về trang sách" icon={ArrowLeft} onClick={() => navigate(`/book/${id}`)} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{chapter.subtitle || chapter.title}</div>
          <div className="truncate text-xs text-fg-2">
            {book.title} · {chapter.title}
          </div>
        </div>
        <IconButton label="Chương trước" icon={ChevronLeft} disabled={index <= 0} onClick={() => go(-1)} />
        <IconButton label="Chương sau" icon={ChevronRight} disabled={index >= chapters.length - 1} onClick={() => go(1)} />
        <Popover.Root>
          <Popover.Trigger asChild>
            <button type="button" aria-label="Cỡ chữ và giãn dòng" className="grid size-9 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg">
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
                    className={cn("h-9 rounded-lg", prefs.size === size ? "bg-accent-soft font-semibold text-accent-text" : "hover:bg-hover")}
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
                    className={cn("tabular h-9 rounded-lg text-sm", prefs.leading === leading ? "bg-accent-soft font-semibold text-accent-text" : "hover:bg-hover")}
                  >
                    {leading.toLocaleString("vi-VN")}
                  </button>
                ))}
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
        {script.timed && (
          <>
            <Button size="sm" variant="primary" icon={Headphones} onMouseDown={(event) => event.preventDefault()} onClick={listenHere} className="max-sm:hidden">
              Nghe từ đây
            </Button>
            {/* Điện thoại: cùng việc, chỉ còn biểu tượng - trước đây nút ẩn hẳn và chỉ còn cách đoán là chạm vào câu. */}
            <IconButton label="Nghe từ đây" icon={Headphones} tone="solid" onClick={listenHere} className="sm:hidden" />
          </>
        )}
      </header>

      <div ref={container} onScroll={onScroll} className="relative min-h-0 flex-1 overflow-y-auto">
        <article className="mx-auto max-w-[68ch] px-6 pb-40 pt-8" style={{ fontSize: prefs.size, lineHeight: prefs.leading }}>
          {!script.timed && (
            <p className="mb-6 rounded-lg bg-hover px-4 py-3 text-sm leading-relaxed text-fg-2">
              Chương này chưa có audio - vẫn đọc được. Khi Studio thu xong, “Nghe từ đây” sẽ hiện ra.
            </p>
          )}
          {script.timed && !prefs.tapped && <p className="mb-6 text-sm text-fg-2">Chạm vào một câu rồi bấm “Nghe từ câu này” để nghe từ câu ấy.</p>}
          <div className="space-y-[0.9em]">
            {paragraphs.map((paragraph) => {
              const first = paragraph.items[0];
              if (first.kind === "heading") {
                return (
                  <h1 key={paragraph.key} data-index={first.index} className="pb-2 text-[1.5em] font-bold leading-snug tracking-tight">
                    {first.text}
                  </h1>
                );
              }
              return (
                <p key={paragraph.key} className="text-pretty">
                  {paragraph.items.map((item) => (
                    <span key={item.index}>
                      <span
                        data-index={item.index}
                        onClick={() => script.timed && setSelected(item.index === selected ? null : item.index)}
                        className={cn(
                          // scroll-mt: câu được cuộn tới không nằm khuất dưới thanh đầu dính (soát UX 29-09).
                          "scroll-mt-20 rounded-[4px] [box-decoration-break:clone]",
                          script.timed && "cursor-pointer",
                          item.kind === "thought" && "italic",
                          item.index === playingIndex && "read-along-active",
                          // Câu đang chọn: gạch chân màu nhấn - khung bao từng dòng của câu dài thành nhiều ô rời, và gạch
                          // chân không lẫn với nền của câu đang phát.
                          item.index === selected && "underline decoration-accent decoration-2 underline-offset-[0.22em]",
                        )}
                      >
                        {item.text}
                      </span>{" "}
                    </span>
                  ))}
                </p>
              );
            })}
          </div>
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
          <div className="pointer-events-none sticky bottom-6 flex justify-center">
            <button
              type="button"
              onClick={() => listenFrom(selected)}
              onMouseDown={(event) => event.preventDefault()}
              className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-fg px-5 py-2.5 text-sm font-semibold text-bg shadow-float"
            >
              <Play className="size-4" fill="currentColor" strokeWidth={0} /> Nghe từ câu này
            </button>
          </div>
        )}
        {selected === null && listeningHere && playingIndex >= 0 && Math.abs(playingIndex - current) > 12 && (
          <div className="pointer-events-none sticky bottom-6 flex justify-center">
            <button
              type="button"
              onClick={() => container.current?.querySelector<HTMLElement>(`[data-index="${playingIndex}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" })}
              className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-panel px-4 py-2 text-sm font-semibold shadow-float ring-1 ring-line"
            >
              <Locate className="size-4" /> Tới câu đang nghe
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
