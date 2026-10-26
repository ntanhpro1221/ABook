import { Locate } from "lucide-react";
import { feedback } from "@/shared/feedback";
import { memo, useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode, type RefObject, type TouchEvent } from "react";
import { cn } from "@/shared/cn";
import { excerpt } from "@/shared/format";
import { useClock } from "./clock";
import { SpeakerLabel } from "./SpeakerLabel";
import { followScrollTop, needsFollowScroll, placementOf, SCROLL_KEYS, SETTLE_MS, shouldResumeFollowing, showJumpToPlaying, type Placement } from "./follow";
import { usePlayListenBook } from "./LibraryScreen";
import type { ListenBook, ListenChapter, Script, ScriptSegment } from "./model";
import { usePlayer } from "./player";
import { estimatedStarts } from "./readAloud";
import { scrollMotion } from "@/shared/motion";
import { wordAtPoint } from "./wordTap";
import { sentenceIndexAt, splitPieces, usableWords, wordIndexAt, type WordSpan } from "./words";

// Văn bản chương đi cùng giọng đọc - MỘT chỗ cho màn đọc (ReaderScreen) và tab "Đọc theo" của trình phát (PlayerViews): câu đang nghe sáng lên,
// chữ đang đọc sáng đậm hơn, bấm một chữ là nghe từ đúng chữ ấy, khung tự cuộn theo giọng (luật ở follow.ts), bàn phím đi qua các câu bằng mũi
// tên (một điểm dừng Tab cho cả văn bản, không phải mỗi chữ một điểm) và Enter là nghe từ câu ấy. Câu là chữ thường trong đoạn <p>, không phải
// "nút": chương 22.000 câu từng là 22.000 nút, trình đọc màn hình đọc "nút" trước mỗi câu và mất cấu trúc đoạn (soát a31 A5). Câu nhận Tab
// mang lời chỉ cách dùng phím (aria-describedby).

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
  // Giây bắt đầu để hiện mốc; chương chữ gửi thêm segment/word để giữ đúng câu khi giọng hoặc độ dài clip thay đổi.
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
    const target = canSpeak ? { segment: sentence, word: Math.max(0, word) } : undefined;
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
    box.scrollTo({ top: followScrollTop(place.rect, place.view, box.scrollTop), behavior: scrollMotion(animate) });
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
      className={cn("pointer-events-auto inline-flex min-h-[48px] items-center gap-2 rounded-full bg-fg px-4 py-2 text-sm font-semibold text-bg shadow-float", className)}
    >
      <Locate className="size-4" /> Tới câu đang nghe
    </button>
  );
}

/** Giữ ngón tay trên một chữ chừng này (ms) là mở menu của chữ ấy ("Đọc từ này là…"), như bấm chuột phải trên máy tính. */
export const LONG_PRESS_MS = 500;
/** Ngón tay trượt quá chừng này (px) thì là cuộn, không phải giữ. */
const PRESS_SLOP = 10;

/** Câu đang nghe, chữ đang đọc sáng lên. Một component riêng: đồng hồ khung hình chỉ làm render lại MỘT câu, và chỉ khi sang chữ khác.
 *  Mọi chữ của câu đều có sẵn span (chỉ câu đang nghe): sang chữ kế chỉ đổi lớp `is-lit`, nền mờ dần sang chữ mới (styles.css) - span dựng
 *  đúng lúc tới lượt thì không có gì để chuyển tiếp, chữ bật sáng cứng. Chữ nhớ (memo): mỗi nhịp chỉ hai chữ vẽ lại. */
function LitWords({ text, words }: { text: string; words: WordSpan[] }) {
  const wordIndex = useClock((time) => wordIndexAt(words, time * 1000));
  const pieces = useMemo(() => splitPieces(text), [text]);
  return (
    <>
      {pieces.map((piece, at) => (piece.word >= 0 ? <Word key={at} text={piece.text} lit={piece.word === wordIndex} /> : piece.text))}
    </>
  );
}

const Word = memo(function Word({ text, lit }: { text: string; lit: boolean }) {
  return <span className={lit ? "read-along-word is-lit" : "read-along-word"}>{text}</span>;
});

export function ReadAlongText({
  script,
  playingIndex,
  onTap,
  onWordMenu,
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
  /** Giữ ngón tay (điện thoại) hay bấm chuột phải (máy tính) vào chữ thứ `word` của câu `index`. Không có: giữ / chuột phải như thường. */
  onWordMenu?: (index: number, word: number) => void;
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
  const paragraphs = useMemo(() => paragraphsOf(script), [script]);

  // Giữ ngón tay: hẹn giờ; trượt / nhấc tay sớm thì huỷ. Menu vừa mở thì cú chạm (click) và menu của hệ thống ngay sau đó không tính.
  const press = useRef<{ timer: number; x: number; y: number } | null>(null);
  const menuAt = useRef(0);
  const release = () => {
    if (press.current) window.clearTimeout(press.current.timer);
    press.current = null;
  };
  useEffect(() => release, []);
  const justOpened = () => Date.now() - menuAt.current < LONG_PRESS_MS + 300;
  const openMenu = (element: HTMLElement, index: number, x: number, y: number): boolean => {
    const word = onWordMenu ? wordAtPoint(element, script.segments[index].text, x, y) : -1;
    if (word < 0) return false;
    menuAt.current = Date.now();
    feedback("longPress");
    onWordMenu!(index, word);
    return true;
  };
  const wordMenu = (index: number) =>
    onWordMenu
      ? {
          onContextMenu: (event: MouseEvent<HTMLElement>) => {
            if (justOpened() || openMenu(event.currentTarget, index, event.clientX, event.clientY)) event.preventDefault();
          },
          onTouchStart: (event: TouchEvent<HTMLElement>) => {
            release();
            if (event.touches.length !== 1) return;
            const { clientX: x, clientY: y } = event.touches[0];
            const element = event.currentTarget;
            const timer = window.setTimeout(() => {
              press.current = null;
              openMenu(element, index, x, y);
            }, LONG_PRESS_MS);
            press.current = { x, y, timer };
          },
          onTouchMove: (event: TouchEvent<HTMLElement>) => {
            const touch = event.touches[0];
            if (press.current && touch && Math.hypot(touch.clientX - press.current.x, touch.clientY - press.current.y) > PRESS_SLOP) release();
          },
          onTouchEnd: release,
          onTouchCancel: release,
        }
      : {};

  const click = (event: MouseEvent<HTMLElement>, index: number) => {
    if (!onTap || justOpened()) return;
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
  // Từng đoạn là một component nhớ (memo): mở ô tìm, chọn một câu, cuộn (câu đầu màn đổi) chỉ vẽ lại đoạn có câu đổi - chương 1,5 triệu
  // chữ từng vẽ lại cả chục nghìn câu mỗi lần (soát uxfix30). Hàm xử lý đi qua `live` để đoạn nhận cùng một đối tượng mọi lần vẽ.
  const live = useRef({ click, wordMenu, focus: setFocused });
  live.current = { click, wordMenu, focus: setFocused };
  const actions = useMemo<SentenceActions>(
    () => ({
      click: (event, index) => live.current.click(event, index),
      focus: (index) => live.current.focus(index),
      menu: (index) => live.current.wordMenu(index),
    }),
    [],
  );
  const marks: Marks = { playing: playingIndex, litWords, heard: dimHeard && playingIndex >= 0 ? playingIndex : -1, selected, tabStop };
  const hintId = useId();
  const hint = onTap ? hintId : undefined;
  const shared = { tappable: Boolean(onTap), menu: Boolean(onWordMenu), speakers, Heading, headingClassName, after, actions, hint };
  const chunks = useMemo(() => chunksOf(paragraphs), [paragraphs]);

  return (
    <div className={className} onKeyDown={keys}>
      {hint && (
        <p id={hint} className="sr-only">
          Mũi tên lên, xuống: sang câu trước, câu sau. Enter: nghe từ câu này.
        </p>
      )}
      {chunks.map((chunk) => (
        <Chunk key={chunk.first} chunk={chunk} {...narrow(marks, chunk.first, chunk.last)} {...shared} />
      ))}
    </div>
  );
}

/** Câu đang nghe / đang chọn / nhận Tab... của cả chương. */
interface Marks {
  playing: number;
  litWords: WordSpan[] | null;
  /** Câu đầu tiên chưa nghe (-1: không làm nhạt câu nào). */
  heard: number;
  selected: number | null;
  tabStop: number;
}

/** Phần của `marks` thuộc khoảng câu [first, last]; ngoài khoảng thì về giá trị trống - phần không đổi thì memo bỏ qua. */
function narrow(marks: Marks, first: number, last: number): Marks {
  const inside = (index: number | null) => index !== null && index >= first && index <= last;
  const playing = inside(marks.playing) ? marks.playing : -1;
  return {
    playing,
    litWords: playing >= 0 ? marks.litWords : null,
    heard: marks.heard >= 0 ? Math.min(Math.max(marks.heard, first), last + 1) : -1,
    selected: inside(marks.selected) ? marks.selected : null,
    tabStop: inside(marks.tabStop) ? marks.tabStop : -1,
  };
}

interface Shared {
  tappable: boolean;
  menu: boolean;
  speakers: boolean;
  Heading: "h1" | "h2";
  headingClassName: string;
  after?: (segment: ScriptSegment) => ReactNode;
  actions: SentenceActions;
  /** Mã lời chỉ cách dùng phím (chỉ khi câu bấm được): gắn vào câu đang nhận Tab. */
  hint?: string;
}

/** Dòng chỉ gồm dấu ngăn cảnh: "***", "* * *", "~~~", "---"... */
const SCENE_BREAK = /^\s*(?:[*·•~#=—–-]\s*){3,}$/;

type ChunkItems = { first: number; last: number; paragraphs: ParagraphItems[] };
/** Số đoạn mỗi nhóm: lần vẽ lại chỉ so ~1/50 số đoạn (chương 11.000 đoạn: 220 nhóm). */
const CHUNK = 50;

function chunksOf(paragraphs: ParagraphItems[]): ChunkItems[] {
  const chunks: ChunkItems[] = [];
  for (let at = 0; at < paragraphs.length; at += CHUNK) {
    const part = paragraphs.slice(at, at + CHUNK);
    chunks.push({ first: part[0].first, last: part[part.length - 1].last, paragraphs: part });
  }
  return chunks;
}

const Chunk = memo(function Chunk({ chunk, ...props }: { chunk: ChunkItems } & Marks & Shared) {
  const marks: Marks = props;
  return (
    <>
      {chunk.paragraphs.map((paragraph) => (
        <Paragraph key={paragraph.key} paragraph={paragraph} {...props} {...narrow(marks, paragraph.first, paragraph.last)} />
      ))}
    </>
  );
});

type ParagraphItems = { key: number; first: number; last: number; items: { index: number; segment: ScriptSegment; showSpeaker: boolean }[] };

/** Câu của chương gom theo đoạn (số `paragraph` liền nhau), kèm chỉ số câu đầu / cuối của đoạn. */
function paragraphsOf(script: Script): ParagraphItems[] {
  const paragraphs: ParagraphItems[] = [];
  script.segments.forEach((segment, index) => {
    const previous = script.segments[index - 1];
    const isSpeech = (item: ScriptSegment | undefined) => item?.kind === "dialogue" || item?.kind === "thought";
    const showSpeaker = isSpeech(segment) && (!isSpeech(previous) || previous?.speaker !== segment.speaker);
    const last = paragraphs[paragraphs.length - 1];
    if (last && last.key === segment.paragraph) {
      last.items.push({ index, segment, showSpeaker });
      last.last = index;
    } else paragraphs.push({ key: segment.paragraph, first: index, last: index, items: [{ index, segment, showSpeaker }] });
  });
  return paragraphs;
}

interface SentenceActions {
  click: (event: MouseEvent<HTMLElement>, index: number) => void;
  focus: (index: number) => void;
  menu: (index: number) => Record<string, unknown>;
}

/** Một đoạn của màn đọc. Chỉ nhận những gì của RIÊNG đoạn này (câu đang nghe / đang chọn / nhận Tab nếu nằm trong đoạn, -1 / null nếu
 *  không) nên React bỏ qua mọi đoạn không đổi. `heard`: câu đầu chưa nghe trong đoạn (-1: không làm nhạt câu nào). */
const Paragraph = memo(function Paragraph({
  paragraph,
  playing,
  litWords,
  heard,
  selected,
  tabStop,
  tappable,
  menu,
  speakers,
  Heading,
  headingClassName,
  after,
  actions,
  hint,
}: { paragraph: ParagraphItems } & Marks & Shared) {
  const sentence = (index: number, segment: ScriptSegment) => ({
    "data-index": index,
    "data-sentence": "",
    tabIndex: index === tabStop ? 0 : -1,
    "aria-describedby": index === tabStop ? hint : undefined,
    "aria-current": index === playing ? ("true" as const) : undefined,
    onFocus: () => actions.focus(index),
    onClick: (event: MouseEvent<HTMLElement>) => actions.click(event, index),
    ...(menu ? actions.menu(index) : {}),
    className: cn(
      // scroll-mt: câu được cuộn tới không nằm khuất dưới thanh đầu dính (soát UX 29-09).
      // Nền / màu / gạch chân của câu luôn có (trong suốt khi không dùng) và chuyển tiếp (styles.css [data-sentence]): sang câu kế, câu đã
      // nghe nhạt đi, chọn / bỏ chọn câu đều mờ dần, không bật tắt cứng.
      "scroll-mt-20 rounded-control outline-none [box-decoration-break:clone] focus-visible:ring-2 focus-visible:ring-focus underline decoration-transparent decoration-2 underline-offset-[0.22em]",
      tappable && "cursor-pointer",
      segment.kind === "thought" && "italic",
      index === playing && "read-along-active",
      heard >= 0 && index < heard && segment.kind !== "heading" && "text-fg-2",
      // Câu đang chọn: gạch chân màu nhấn - khung bao từng dòng của câu dài thành nhiều ô rời, và gạch chân không lẫn với nền của câu đang phát.
      index === selected && "decoration-accent",
    ),
  });
  const first = paragraph.items[0];
  if (first.segment.kind === "heading") {
    const props = sentence(first.index, first.segment);
    return (
      <Heading {...props} className={cn(props.className, headingClassName)}>
        {first.segment.text}
      </Heading>
    );
  }
  // Dòng ngăn cảnh ("***", "* * *") đứng giữa trang như sách in - chỉ cách bày, chữ giữ nguyên.
  const sceneBreak = paragraph.items.length === 1 && (first.segment.sceneBreak || SCENE_BREAK.test(first.segment.text));
  return (
    <p className={sceneBreak ? "pl-[0.3em] text-center tracking-[0.3em] text-fg-2" : "text-pretty"}>
      {paragraph.items.map(({ index, segment, showSpeaker }) => (
        <span key={index}>
          {speakers && segment.speaker && showSpeaker && (
            <SpeakerLabel speaker={segment.speaker} sentence={segment.text} />
          )}
          <span {...sentence(index, segment)}>
            {index === playing && litWords ? <LitWords text={segment.text} words={litWords} /> : segment.text}
            {after?.(segment)}
          </span>{" "}
        </span>
      ))}
    </p>
  );
});
