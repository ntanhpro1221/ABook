import { Locate } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode, type RefObject } from "react";
import { cn } from "@/shared/cn";
import { excerpt } from "@/shared/format";
import { useClock } from "./clock";
import { followScrollTop, needsFollowScroll, placementOf, SCROLL_KEYS, SETTLE_MS, shouldResumeFollowing, showJumpToPlaying, type Placement } from "./follow";
import { usePlayListenBook } from "./LibraryScreen";
import type { ListenBook, ListenChapter, Script, ScriptSegment } from "./model";
import { usePlayer } from "./player";
import { estimatedStarts } from "./readAloud";
import { wordAtPoint } from "./wordTap";
import { splitPieces, usableWords, wordIndexAt, type WordSpan } from "./words";

// Văn bản chương đi cùng giọng đọc - MỘT chỗ cho màn đọc (ReaderScreen) và tab "Đọc theo" của trình phát (PlayerViews): câu đang nghe sáng lên,
// chữ đang đọc sáng đậm hơn, bấm một chữ là nghe từ đúng chữ ấy, khung tự cuộn theo giọng (luật ở follow.ts), bàn phím đi qua các câu bằng mũi
// tên (một điểm dừng Tab cho cả văn bản, không phải mỗi chữ một điểm) và Enter là nghe từ câu ấy.

/** Câu đang đọc ở giây `seconds` (tìm nhị phân trên mốc bắt đầu). */
export function sentenceIndexAt(starts: number[], seconds: number): number {
  let low = 0;
  let high = starts.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (starts[middle] <= seconds + 0.05) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found;
}

/** Câu đang nghe của kịch bản này (-1: không nghe chương này, hay kịch bản chưa có mốc). Chỉ render lại khi sang câu khác. */
export function usePlayingSentence(script: Script | undefined, listening: boolean): number {
  const starts = useMemo(() => (script?.timed ? script.segments.map((segment) => segment.start ?? 0) : []), [script]);
  return useClock((time) => (listening && starts.length ? sentenceIndexAt(starts, time) : -1));
}

/** Nghe từ một câu, hay từ đúng một chữ của câu (`word` >= 0). Sách nói đã căn chữ thì tới mốc của chữ, chưa căn thì đầu câu; chương đọc to báo cho
 *  bộ máy chữ nào (nó tự vào mốc chữ trong clip, hay đọc đoạn ấy trước rồi vào). Cuốn đang ở trình phát thì nhảy trong trình phát, không thì nạp. */
export function useListenFrom(bookId: string, book: ListenBook | undefined, chapter: ListenChapter | undefined, script: Script | undefined) {
  const player = usePlayer();
  const playBook = usePlayListenBook();
  // Chương chỉ có chữ mà máy có giọng đọc: giọng máy đọc (listen/readAloud.ts).
  const canSpeak = chapter?.state === "text" && chapter.speech === true;
  const canListen = Boolean(script && (script.timed || canSpeak));
  // Giây bắt đầu của một câu: mốc đã có; chương đọc to chưa chạy thì ước (cùng cách ước với bộ máy đọc nên "Nghe từ đây" rơi đúng câu).
  const startOf = useCallback(
    (sentence: number): number | null => {
      const start = script?.segments[sentence]?.start;
      if (start !== null && start !== undefined) return start;
      return canSpeak && script?.segments[sentence] ? estimatedStarts(script.segments)[sentence] : null;
    },
    [canSpeak, script],
  );
  const listenFrom = (sentence: number, word = -1): boolean => {
    const segment = script?.segments[sentence];
    const start = startOf(sentence);
    if (!chapter || !segment || start === null || !canListen) return false;
    const spans = word >= 0 ? usableWords(segment.text, segment.words) : null;
    const at = spans ? spans[word][0] / 1000 : start;
    const target = canSpeak && word >= 0 ? { segment: sentence, word } : undefined;
    let offset = 0;
    if (word >= 0) for (const piece of splitPieces(segment.text)) { if (piece.word === word) break; offset += piece.text.length; }
    const note = `Nghe từ “${excerpt(segment.text.slice(offset))}”`;
    if (player.track?.bookId === bookId) player.jumpTo(chapter.id, at, note, target);
    else if (book) void playBook(book, chapter.id, at, { word: target });
    else return false;
    return true;
  };
  return { canSpeak, canListen, listenFrom };
}

/** Khung cuộn đi theo câu đang nghe (luật ở follow.ts). `initial`: mở ra đã theo chưa (màn đọc mở đúng một câu được yêu cầu thì chưa);
 *  `resetKey` đổi (sang chương khác) thì về lại `initial`. Gắn `input` vào khung cuộn, `onScroll` vào sự kiện cuộn của nó. */
export function useFollowVoice(container: RefObject<HTMLElement | null>, playingIndex: number, { initial = true, resetKey = "", smooth = true } = {}) {
  const [following, setFollowing] = useState(initial);
  const [placement, setPlacement] = useState<Placement | null>(null);
  const followingRef = useRef(following);
  followingRef.current = following;
  const indexRef = useRef(playingIndex);
  indexRef.current = playingIndex;
  const smoothRef = useRef(smooth);
  smoothRef.current = smooth;
  const manualAt = useRef(0);
  const settle = useRef<number | undefined>(undefined);

  const measure = useCallback(() => {
    const box = container.current;
    const element = indexRef.current >= 0 ? box?.querySelector<HTMLElement>(`[data-index="${indexRef.current}"]`) : null;
    if (!box || !element) return null;
    const rect = element.getBoundingClientRect();
    const view = box.getBoundingClientRect();
    return { rect: { top: rect.top, bottom: rect.bottom }, view: { top: view.top, bottom: view.bottom }, placement: placementOf(rect, view) };
  }, [container]);

  const scrollToPlaying = useCallback((animate: boolean) => {
    const box = container.current;
    const place = measure();
    if (!box || !place) return;
    const still = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    box.scrollTo({ top: followScrollTop(place.rect, place.view, box.scrollTop), behavior: animate && !still ? "smooth" : "auto" });
  }, [container, measure]);

  useEffect(() => {
    setFollowing(initial);
    manualAt.current = 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  // Sang câu mới (hay vừa theo lại): đang theo thì cuộn nếu câu sắp khuất; không theo thì cập nhật nút "Tới câu đang nghe", và theo lại nếu người
  // đọc đã tự về đúng chỗ câu đang nghe.
  // Đo ngay sau khi vẽ (không đợi khung hình kế: thẻ ẩn / màn hình tắt không có khung hình, câu đang nghe vẫn phải được theo).
  useEffect(() => {
    if (playingIndex < 0) {
      setPlacement(null);
      return;
    }
    const place = measure();
    if (!place) {
      setPlacement(null);
      return;
    }
    if (following) {
      if (needsFollowScroll(place.rect, place.view)) scrollToPlaying(smoothRef.current);
      setPlacement("inside");
      return;
    }
    setPlacement(place.placement);
    if (shouldResumeFollowing(false, place.placement, manualAt.current, Date.now())) setFollowing(true);
  }, [following, measure, playingIndex, scrollToPlaying]);

  useEffect(() => () => window.clearTimeout(settle.current), []);

  /** Người tự cuộn: thôi theo; thôi cuộn SETTLE_MS mà câu đang nghe nằm trong khung thì theo lại. */
  const manual = useCallback(() => {
    setFollowing(false);
    manualAt.current = Date.now();
    window.clearTimeout(settle.current);
    settle.current = window.setTimeout(() => {
      const place = measure();
      setPlacement(place?.placement ?? null);
      if (place && shouldResumeFollowing(followingRef.current, place.placement, manualAt.current, Date.now())) setFollowing(true);
    }, SETTLE_MS);
  }, [measure]);

  const onScroll = useCallback(() => {
    if (!followingRef.current) setPlacement(measure()?.placement ?? null);
  }, [measure]);

  // Chỉ THAO TÁC của người (lăn chuột, vuốt, phím cuộn, kéo thanh cuộn) mới tắt theo - không suy từ sự kiện cuộn: cuộn mượt do app kéo dài
  // dễ bị tưởng là người cuộn (soát UX 29-09).
  const input = {
    onWheel: manual,
    onTouchMove: manual,
    onPointerDown: (event: { target: EventTarget; currentTarget: EventTarget }) => {
      if (event.target === event.currentTarget) manual();
    },
    onKeyDown: (event: KeyboardEvent) => {
      if (SCROLL_KEYS.has(event.key)) manual();
    },
  };

  return {
    following,
    showJump: playingIndex >= 0 && showJumpToPlaying(following, placement),
    /** "Tới câu đang nghe": theo lại và cuộn tới ngay. */
    jump: () => {
      setFollowing(true);
      scrollToPlaying(true);
    },
    /** Người vừa chọn nghe từ một chỗ: theo lại. */
    follow: () => setFollowing(true),
    input,
    onScroll,
  };
}

/** Nút "Tới câu đang nghe" (một kiểu cho cả màn đọc và trình phát). */
export function JumpToPlaying({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseDown={(event) => event.preventDefault()}
      className={cn("pointer-events-auto inline-flex min-h-[44px] items-center gap-2 rounded-full bg-fg px-4 py-2 text-sm font-semibold text-bg shadow-float", className)}
    >
      <Locate className="size-4" /> Tới câu đang nghe
    </button>
  );
}

/** Câu đang nghe, chữ đang đọc sáng lên. Một component riêng: đồng hồ khung hình chỉ làm render lại MỘT câu, và chỉ khi sang chữ khác. */
function LitWords({ text, words }: { text: string; words: WordSpan[] }) {
  const wordIndex = useClock((time) => wordIndexAt(words, time * 1000));
  return (
    <>
      {splitPieces(text).map((piece, at) =>
        piece.word >= 0 && piece.word === wordIndex ? (
          <span key={at} className="read-along-word">
            {piece.text}
          </span>
        ) : (
          piece.text
        ),
      )}
    </>
  );
}

export function ReadAlongText({
  script,
  playingIndex,
  onTap,
  focusIndex,
  selected = null,
  speakers = false,
  dimHeard = false,
  heading: Heading = "h2",
  headingClassName,
  className,
  after,
}: {
  script: Script;
  playingIndex: number;
  /** Bấm vào câu (chuột / chạm: `word` = chữ dưới chỗ bấm, -1 nếu không biết) hay Enter trên câu (`word` -1). Không có: câu không bấm được. */
  onTap?: (index: number, word: number) => void;
  /** Câu nhận Tab khi người dùng chưa tự đi qua câu nào (thường là câu đang đọc / đang nghe). */
  focusIndex: number;
  selected?: number | null;
  /** Nhãn người nói trước lời thoại. */
  speakers?: boolean;
  /** Câu đã nghe qua nhạt đi. */
  dimHeard?: boolean;
  heading?: "h1" | "h2";
  headingClassName: string;
  className?: string;
  /** Thêm sau câu (dấu "đang chờ Studio" của màn đọc). */
  after?: (segment: ScriptSegment) => ReactNode;
}) {
  const [focused, setFocused] = useState<number | null>(null);
  // Sang chương khác thì quên câu đã đi tới bằng bàn phím (kịch bản cùng chương đổi mỗi khi giọng máy đọc xong một đoạn - không tính).
  useEffect(() => setFocused(null), [script.chapterId]);
  const litWords = useMemo(() => {
    const segment = playingIndex >= 0 ? script.segments[playingIndex] : undefined;
    return segment ? usableWords(segment.text, segment.words) : null;
  }, [playingIndex, script]);
  const tabStop = focused ?? Math.max(0, Math.min(script.segments.length - 1, focusIndex));
  const paragraphs: { key: number; items: { index: number; segment: ScriptSegment }[] }[] = [];
  script.segments.forEach((segment, index) => {
    const last = paragraphs[paragraphs.length - 1];
    if (last && last.key === segment.paragraph) last.items.push({ index, segment });
    else paragraphs.push({ key: segment.paragraph, items: [{ index, segment }] });
  });

  const click = (event: MouseEvent<HTMLElement>, index: number) => {
    if (!onTap) return;
    // Đang bôi chữ để chép: không nghe.
    if (window.getSelection()?.isCollapsed === false) return;
    onTap(index, wordAtPoint(event.currentTarget, script.segments[index].text, event.clientX, event.clientY));
  };
  const keys = (event: KeyboardEvent<HTMLElement>) => {
    const index = Number((event.target as HTMLElement).dataset.index);
    if (!Number.isFinite(index) || (event.target as HTMLElement).dataset.sentence === undefined) return;
    if (event.key === "Enter" && onTap) {
      event.preventDefault();
      event.stopPropagation();
      onTap(index, -1);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      const next = Math.max(0, Math.min(script.segments.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)));
      const element = (event.currentTarget as HTMLElement).querySelector<HTMLElement>(`[data-index="${next}"]`);
      if (!element) return;
      event.preventDefault();
      element.focus();
    }
  };
  const sentence = (index: number, segment: ScriptSegment) => ({
    "data-index": index,
    "data-sentence": "",
    tabIndex: index === tabStop ? 0 : -1,
    role: onTap ? "button" : undefined,
    "aria-current": index === playingIndex ? ("true" as const) : undefined,
    onFocus: () => setFocused(index),
    onClick: (event: MouseEvent<HTMLElement>) => click(event, index),
    className: cn(
      // scroll-mt: câu được cuộn tới không nằm khuất dưới thanh đầu dính (soát UX 29-09).
      "scroll-mt-20 rounded-[4px] outline-none [box-decoration-break:clone] focus-visible:ring-2 focus-visible:ring-accent",
      onTap && "cursor-pointer",
      segment.kind === "thought" && "italic",
      index === playingIndex && "read-along-active",
      dimHeard && playingIndex >= 0 && index < playingIndex && "text-fg-2",
      // Câu đang chọn: gạch chân màu nhấn - khung bao từng dòng của câu dài thành nhiều ô rời, và gạch chân không lẫn với nền của câu đang phát.
      index === selected && "underline decoration-accent decoration-2 underline-offset-[0.22em]",
    ),
  });

  return (
    <div className={className} onKeyDown={keys}>
      {paragraphs.map((paragraph) => {
        const first = paragraph.items[0];
        if (first.segment.kind === "heading") {
          const { role: _role, ...props } = sentence(first.index, first.segment);
          return (
            <Heading key={paragraph.key} {...props} className={cn(props.className, headingClassName)}>
              {first.segment.text}
            </Heading>
          );
        }
        return (
          <p key={paragraph.key} className="text-pretty">
            {paragraph.items.map(({ index, segment }) => (
              <span key={index}>
                {speakers && segment.speaker && (segment.kind === "dialogue" || segment.kind === "thought") && (
                  <span className="mr-1.5 inline-block -translate-y-px rounded bg-accent-soft px-1.5 text-[11px] font-semibold uppercase tracking-wide text-accent-text">
                    {segment.speaker}
                  </span>
                )}
                <span {...sentence(index, segment)}>
                  {index === playingIndex && litWords ? <LitWords text={segment.text} words={litWords} /> : segment.text}
                  {after?.(segment)}
                </span>{" "}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}
