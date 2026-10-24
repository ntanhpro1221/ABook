import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence } from "@/shared/MotionPresence";
import { Collapse } from "@/shared/Collapse";
import { Capacitor } from "@capacitor/core";
import * as Popover from "@radix-ui/react-popover";
import { coverColor, coverStyle } from "@/shared/cover";
import * as Slider from "@radix-ui/react-slider";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AudioLines,
  Bookmark as BookmarkIcon,
  BookmarkPlus,
  Check,
  ChevronDown,
  Gauge,
  Keyboard,
  ListOrdered,
  Loader2,
  Maximize2,
  Moon,
  MoreHorizontal,
  Music2,
  Pause,
  Pencil,
  Play,
  Plus,
  SkipBack,
  SkipForward,
  Square,
  Text,
  Trash2,
  TriangleAlert,
  Undo2,
  Volume1,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ButtonHTMLAttributes, type ComponentProps, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import { BookCover } from "@/shared/BookCover";
import { Windowed } from "@/shared/Windowed";
import { reveal } from "@/shared/scrollMemory";
import { cn } from "@/shared/cn";
import { APP_TITLE } from "@/shared/title";
import { useMediaQuery } from "@/shared/media";
import { MUSIC_MODIFIED_NOTE, excerpt, formatClock, formatLength, formatWhen, licenseLabel, musicCreditText, musicNeedsModifiedNote, spokenClock } from "@/shared/format";
import { announce, busyClick, heardBarProps, IconButton, menuArrowKeys, Tooltip, useFocusFollows, Vu } from "@/shared/ui";
import { Switch } from "@/desktop/PhoneSync";
import { LEVEL_NOTES, levelOptions } from "@/shared/musicLevels";
import { useClock, useClockReader, useDuration, usePlaybackSecond } from "./clock";
import { usePlayListenBook, useNextVolume } from "./LibraryScreen";
import { COARSE, EXTEND_GESTURE } from "./extendGesture";
import { openShortcuts } from "./Shortcuts";
import { useBookMusic } from "./EditBook";
import { bookmarkReadPath, canPlay, continuingPart, newerElsewhere, otherBooksToHear, partToContinue, seriesOf, type Bookmark, type ListenChapter, type Script } from "./model";
import { EDIT_BOOKMARK_EVENT, SKIP_SECONDS, SPEEDS, useNowPlaying, usePlayer } from "./player";
import { SLEEP_CHOICES, sleepButtonLabel, sleepExtended, sleepLabel, sleepLeftMs, sleepSpoken, type SleepMode, type SleepRequest } from "./sleep";
import { useVoiceSample } from "./VoiceSettings";
import { genderLabel, groupedVoices, voiceSections } from "./voiceGroups";
import { revealVoiceSettings } from "./voiceSettingsLink";
import { VieneuDownload } from "./VieneuDownload";
import { chooseVoice, chosenVoice, isNoOfflineVoice, isVoiceStuck, localVoiceFor, noOfflineMessage, onlineNotice, resolveVoice, unusableVoiceMessage, voiceCaption } from "./readAloudVoice";
import { bookProgressText, caughtUpDetail, nextChapterLabel, SHORTCUTS, withShortcut, otherBookLine, PREPARING_VOICE, PREPARING_VOICE_AFTER_MS, textChapterLine, toggleLabel, unquoted } from "./labels";
import { useAfter } from "@/shared/useAfter";
import { useBackLayer } from "@/shared/backStack";
import { MOTION, usePresence, useListPresence, withViewTransition } from "@/shared/motion";
import { useRetryWhenOnline } from "./onlineRetry";
import { askOnlineConsent, onlineConsentGiven, pickVoiceWithConsent, spokenVoiceName } from "./onlineConsent";
import { PlaylistOptionLabel, playlistNote, usePlaylistChoice } from "./PlaylistChoice";
import { ADD_MUSIC_LABEL, shortPlaylistLabel } from "./playlistBed";
import { openExternal } from "@/shared/openExternal";
import { ACTION_BUTTON, ACTION_GLYPH, ACTION_LABEL, ActionButton, actionTone } from "./ActionButton";
import { JumpToPlaying, ReadAlongText, useFollowVoice, useListenFrom, usePlayingSentence } from "./ReadAlongText";
import { SuggestionsButton } from "./ReadingSuggestions";
import { useSentenceMenu, type SentenceEditing } from "./SentenceMenu";
import { sentenceIndexAt } from "./words";
import { cacheLabel, canPrepare, clearCacheQuestion, planLabel, PREPARE_STATUS_KEY, prepareIntro, prepareLabel, readyChapterIds, upcomingTextChapters, type PrepareStatus } from "./prepareAhead";
import { READINGS_CHANGED_EVENT, type ReadAloudVoice, type ReadingsChanged } from "./readAloud";
import { chapterScriptQuery, useBookVoice, useWarmVoice, useChapterScript, useListenBook, useListenLibrary, useLastNight, useListenMutations, useReadAloudVoices, useSource, useChosenVoice } from "./source";
import { isRecordGone, RECORD_GONE_MESSAGE, reportWriteFailure } from "./recordWrites";
import { crossedSeekMark, feedback, withFeedback } from "@/shared/feedback";

export function speedLabel(rate: number): string {
  return `${rate.toLocaleString("vi-VN", { maximumFractionDigits: 2 })}×`;
}

/** Tên nút Tốc độ / Giọng đọc kèm giá trị đang dùng: tên nút (aria-label) đè chữ thấy trên nút, nên phải tự mang giá trị - trước đây trình đọc màn
 *  hình chỉ nghe "Tốc độ đọc", "Giọng đọc" (soát a67). */
export function speedButtonLabel(rate: number): string {
  return `Tốc độ đọc: ${speedLabel(rate)}`;
}
export function voiceButtonLabel(name: string | undefined): string {
  return name ? `Giọng đọc: ${spokenVoiceName(name)}` : "Giọng đọc";
}

/** Nút điều khiển không giữ focus sau cú bấm chuột: Space sau đó vẫn là phát/tạm dừng, không lặp lại nút vừa bấm. */
const keepFocus = { onMouseDown: (event: { preventDefault: () => void }) => event.preventDefault() };

function useTicker(active: boolean, every = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    setNow(Date.now());
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), every);
    return () => window.clearInterval(timer);
  }, [active, every]);
  return now;
}

export function sentenceAt(script: Script | undefined, seconds: number): string | null {
  if (!script?.timed) return null;
  const starts = script.segments.map((segment) => segment.start ?? 0);
  const index = sentenceIndexAt(starts, seconds);
  return index >= 0 ? script.segments[index].text : null;
}

// ---- Thanh tua -------------------------------------------------------------------------------------------

// Thanh tua / âm lượng nhỏ chỉ cao 14 px: vùng bấm nới (::after của chính thanh - bấm vào đó là bấm vào thanh) thành 24 px, phần lớn
// dồn xuống dưới để không lấn nút phát ngay bên trên (soát a31, 2.5.8).
const SLIDER_REACH = "after:absolute after:inset-x-0 after:top-[-3px] after:bottom-[-7px] after:content-['']";

function SeekBar({ large = false }: { large?: boolean }) {
  const { seek, skip, track, rate } = usePlayer();
  const second = usePlaybackSecond();
  const duration = useDuration();
  const [dragging, setDragging] = useState<number | null>(null);
  const pointer = useRef(false);
  useEffect(() => setDragging(null), [track?.chapterId, track?.bookId]);
  const shown = dragging ?? second;
  const max = duration > 0 ? duration : 1;
  // Vị trí không bao giờ vượt độ dài (soát UX a9: "1:00" trên thanh dài "0:59" - giờ phát đã làm tròn lên trước khi độ dài kịp cập nhật).
  const clamped = duration > 0 ? Math.min(shown, duration) : shown;
  const onKeyDown = (event: ReactKeyboardEvent) => {
    // Bàn phím trên thanh tua đi theo đúng bước của trình phát (15 giây), không qua trạng thái "đang kéo".
    const steps: Record<string, () => void> = {
      ArrowLeft: () => skip(-SKIP_SECONDS),
      ArrowDown: () => skip(-SKIP_SECONDS),
      ArrowRight: () => skip(SKIP_SECONDS),
      ArrowUp: () => skip(SKIP_SECONDS),
      PageDown: () => skip(-60),
      PageUp: () => skip(60),
      Home: () => seek(0),
      End: () => seek(Math.max(0, duration - 2)),
    };
    const action = steps[event.key];
    if (!action) return;
    event.preventDefault();
    event.stopPropagation();
    action();
  };
  return (
    <div className={cn("w-full", large ? "space-y-1.5" : "flex items-center gap-3")}>
      {!large && <span className="tabular w-12 shrink-0 text-right text-xs text-fg-2">{formatClock(clamped)}</span>}
      <Slider.Root
        className={cn("group relative flex touch-none select-none items-center", large ? "h-5 w-full" : cn("h-4 flex-1", SLIDER_REACH))}
        min={0}
        max={max}
        step={1}
        value={[Math.min(shown, max)]}
        onPointerDown={() => (pointer.current = true)}
        onValueChange={([value]) => {
          if (!pointer.current) return;
          if (crossedSeekMark(dragging ?? second, value, duration, SKIP_SECONDS)) feedback("tick");
          setDragging(value);
        }}
        onValueCommit={([value]) => {
          pointer.current = false;
          seek(value);
          window.setTimeout(() => setDragging(null), 0);
        }}
        onKeyDown={onKeyDown}
        disabled={!duration}
      >
        <Slider.Track className={cn("relative grow overflow-hidden rounded-full bg-line-strong", large ? "h-1.5" : "h-1")}>
          <Slider.Range className={cn("absolute h-full rounded-full", large ? "bg-accent" : "bg-fg group-hover:bg-accent")} />
        </Slider.Track>
        <Slider.Thumb
          aria-label="Vị trí trong chương"
          aria-valuetext={`${spokenClock(clamped)} trên ${spokenClock(duration)}`}
          className={cn(
            "block rounded-full shadow transition-opacity focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
            large ? "size-4 bg-accent opacity-100" : "size-3 bg-fg opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
          )}
        />
      </Slider.Root>
      {large ? (
        <div className="tabular flex justify-between text-xs text-fg-2">
          <span>{formatClock(clamped)}</span>
          <span>-{formatClock(Math.max(0, duration - shown) / (rate || 1))}</span>
        </div>
      ) : (
        // Thời gian còn lại THẬT ở tốc độ đang nghe (như màn "Đang nghe" ghi "6 phút ở 1,5×") - soát UX 29-09.
        <span className="tabular w-12 shrink-0 text-xs text-fg-2">-{formatClock(Math.max(0, duration - shown) / (rate || 1))}</span>
      )}
    </div>
  );
}

// ---- Nút điều khiển ------------------------------------------------------------------------------------

// Vẽ riêng, không đè chữ lên RotateCcw/RotateCw: vòng mũi tên chừa khe ở đầu, mũi tên nằm ngoài vòng, số nằm gọn trong
// lòng vòng bằng <text> cùng hệ toạ độ - chữ co giãn theo biểu tượng, không bao giờ chạm nét (chủ sách 24-10: số 15 đè lên vòng).
function skipIcon(forward: boolean) {
  return function SkipGlyph({ className, strokeWidth = 1.9 }: { className?: string; strokeWidth?: number }) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden className={cn("size-6 shrink-0", className)}>
        <g transform={forward ? "matrix(-1 0 0 1 24 0)" : undefined}>
          <path d="M12 3.5A8.5 8.5 0 1 1 5.04 7.12" />
          <path d="M13.4 1.3 11 3.5l2.4 2.2" />
        </g>
        <text
          x="12"
          y="12.6"
          textAnchor="middle"
          dominantBaseline="central"
          fill="currentColor"
          stroke="none"
          fontSize="8.5"
          fontWeight="600"
          letterSpacing="-0.2"
          style={{ fontFamily: "inherit", fontVariantNumeric: "tabular-nums" }}
        >
          {SKIP_SECONDS}
        </text>
      </svg>
    );
  };
}
export const Back15 = skipIcon(false);
export const Forward15 = skipIcon(true);
// Thanh phát nhỏ: ô biểu tượng 18 px làm số "15" chỉ cao ~6 px, nhoè không đọc được (soát độc lập 24-10) - ở đây vẽ 24 px, gần kín nút 28 px.
const Back15Mini = ({ strokeWidth }: { className?: string; strokeWidth?: number }) => <Back15 className="size-6" strokeWidth={strokeWidth} />;
const Forward15Mini = ({ strokeWidth }: { className?: string; strokeWidth?: number }) => <Forward15 className="size-6" strokeWidth={strokeWidth} />;

/** Chương đang phát là chương chỉ có chữ (giọng máy đọc). */
function useSpeaking(): boolean {
  const { track, queue } = usePlayer();
  return queue.find((chapter) => chapter.id === track?.chapterId)?.state === "text";
}

/** `chapters`: kèm hai nút chương trước / sau (màn Đang nghe: 5 nút); thanh phát máy tính chỉ giữ lùi · phát · tới (docs/DESIGN.md mục 6). */
function Transport({ large = false, chapters = true }: { large?: boolean; chapters?: boolean }) {
  const { playing, buffering, toggle, skip, next, previous, queue, track } = usePlayer();
  const speaking = useSpeaking();
  const [hasNext, hasLater] = useMemo(() => {
    const index = queue.findIndex((chapter) => chapter.id === track?.chapterId);
    const later = queue.slice(index + 1);
    return [later.some(canPlay), later.length > 0];
  }, [queue, track?.chapterId]);
  const size = large ? "lg" : "sm";
  const waiting = buffering && playing;
  return (
    <MotionRegion as="div" data-player-transport className={cn(large ? "slot-row w-full max-w-sm [--slot:clamp(1.25rem,0.8333rlh,2.40625rem)]" : "flex items-center gap-1")}>
      {chapters && <IconButton label={withShortcut("Chương trước", "Shift+←")} icon={SkipBack} size={size} className="touch-box" onClick={previous} {...keepFocus} />}
      <IconButton label={withShortcut(`Lùi ${SKIP_SECONDS} giây`, "←")} icon={large ? Back15 : Back15Mini} size={size} className="touch-box" onClick={() => skip(-SKIP_SECONDS)} {...keepFocus} />
      <button
        type="button"
        onClick={withFeedback("playPause", toggle)}
        {...keepFocus}
        // Đang chờ đoạn đầu: nói đang chờ gì, không nói "Tạm dừng" khi chưa có tiếng nào (bấm vẫn là thôi chờ).
        aria-label={toggleLabel(playing, buffering, speaking)}
        aria-busy={waiting || undefined}
        aria-keyshortcuts={SHORTCUTS ? "Space" : undefined}
        data-player-toggle
        className={cn(
          // Nhấn = thu 0,97 (docs/DESIGN.md 5.2), không nảy. Màn Đang nghe: nút tròn 72 px màu nhấn - nút chính duy nhất của màn.
          "grid shrink-0 place-items-center rounded-full shadow-card transition-[transform,background-color] press",
          large ? "size-[72px] bg-accent text-accent-ink hover:bg-accent-hover" : "size-10 bg-fg text-bg",
        )}
      >
        {waiting ? (
          <Loader2 className={cn("animate-spin", large ? "size-8" : "size-5")} />
        ) : playing ? (
          <span key="pause" className="icon-pop">
            <Pause className={large ? "size-8" : "size-5"} fill="currentColor" strokeWidth={0} />
          </span>
        ) : (
          <span key="play" className="icon-pop">
            <Play className={cn(large ? "size-8" : "size-5", "translate-x-[1px]")} fill="currentColor" strokeWidth={0} />
          </span>
        )}
      </button>
      <IconButton label={withShortcut(`Tới ${SKIP_SECONDS} giây`, "→")} icon={large ? Forward15 : Forward15Mini} size={size} className="touch-box" onClick={() => skip(SKIP_SECONDS)} {...keepFocus} />
      {/* Còn chương sau mà chưa có audio: nút vẫn bấm được và nói vì sao (player.step báo + đường đọc chữ); chỉ chương cuối mới mờ. */}
      {chapters && <IconButton
        label={nextChapterLabel(hasNext, hasLater)}
        icon={SkipForward}
        size={size}
        className="touch-box"
        onClick={next}
        disabled={!hasLater}
        {...keepFocus}
      />}
    </MotionRegion>
  );
}

function MenuShell({
  trigger,
  triggerKey,
  label,
  tooltip,
  children,
  active,
  width = "w-56",
  focusSelector,
  dialogLabel,
  open,
  onOpenChange,
  look = "chip",
  caption,
  icon: RowIcon,
  side,
}: {
  trigger: ReactNode;
  /** Kiểu nút mở: "chip" (thanh phát máy tính), "action" (nút phụ có nhãn của màn Đang nghe - `caption` là nhãn dưới), "row" (một dòng trong
   *  menu "…" - `caption` là tên dòng, `trigger` là giá trị đứng bên phải). */
  look?: "chip" | "action" | "row";
  caption?: ReactNode;
  /** Biểu tượng đầu dòng của kiểu "row". */
  icon?: typeof Gauge;
  side?: "top" | "bottom";
  /** Nút đổi theo một lựa chọn chỉ có số ("1,5×"): số không vào dấu đổi nội dung của MotionRegion, nên đưa lựa chọn làm khoá chuyển cảnh. */
  triggerKey?: unknown;
  label: string;
  /** Chú thích khi rê chuột / tiêu điểm vào nút, nếu muốn nói nhiều hơn tên nút (mặc định = tên nút). */
  tooltip?: string;
  children: ReactNode;
  active?: boolean;
  width?: string;
  /** Khi mở, đưa tiêu điểm tới phần tử khớp (lựa chọn đang áp dụng) thay vì phần tử đầu tiên - viền tiêu điểm ở nút đầu trông như "đang chọn". */
  focusSelector?: string;
  /** Tên của hộp khi mở (trình đọc màn hình đọc khi tiêu điểm vào hộp); mặc định theo nút. Nút đổi chữ theo trạng thái ("Tắt sau 4 phút") thì hộp giữ tên cố định. */
  dialogLabel?: string;
  /** Hộp do bên ngoài mở được (nút "Chọn giọng khác" ở lời báo lỗi giọng); bỏ trống thì hộp tự quản. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Tooltip label={tooltip ?? label}>
        <Popover.Trigger asChild>
          <button
            type="button"
            aria-label={label}
            {...keepFocus}
            className={cn(
              look === "action"
                ? ACTION_BUTTON
                : look === "row"
                  ? "flex min-h-10 w-full items-center gap-3 rounded-lg px-2 text-left text-sm text-fg hover:bg-hover max-sm:min-h-[48px]"
                  : // Điện thoại (màn "Đang nghe"): đủ 48 px để chạm.
                    "tabular inline-flex h-9 min-w-9 shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-lg px-2 text-[0.8125rem] font-semibold transition-colors hover:bg-hover max-sm:h-[48px] max-sm:min-w-[48px]",
              look !== "row" && actionTone(active),
            )}
          >
            {look === "row" && <span className="flex min-w-0 flex-1 items-center gap-3">{RowIcon && <RowIcon className="size-4 shrink-0 text-fg-2" />}<span className="truncate">{caption}</span></span>}
            {/* Mọi nút menu (tốc độ, nhạc, giọng, hẹn giờ, loa / TV) đổi biểu tượng / chữ theo trạng thái: một chỗ mờ chéo cho cả năm. */}
            <MotionRegion as="span" motionKey={triggerKey} className={cn(look === "action" ? ACTION_GLYPH : "inline-flex items-center gap-1", look === "row" && cn("tabular min-w-0 text-xs font-medium", actionTone(active)))}>{trigger}</MotionRegion>
            {look === "action" && <MotionRegion as="span" className={ACTION_LABEL} motionKey={typeof caption === "string" ? caption.replace(/\d+/g, "#") : undefined}>{caption}</MotionRegion>}
          </button>
        </Popover.Trigger>
      </Tooltip>
      <Popover.Portal>
        <Popover.Content
          side={side}
          sideOffset={8}
          collisionPadding={12}
          // Esc hay chọn xong: Radix tự trả tiêu điểm về nút mở (bấm ra ngoài thì không) - trước đây chặn nên rơi về BODY (soát a31 K1). Mở
          // bằng chuột thì nút không bật chú thích (Tooltip quietFocus).
          onOpenAutoFocus={(event) => {
            const current = focusSelector ? (event.currentTarget as HTMLElement).querySelector<HTMLElement>(focusSelector) : null;
            if (!current) return;
            event.preventDefault();
            current.focus();
          }}
          aria-label={dialogLabel ?? label}
          // Mũi tên đi giữa các nút trong bảng như menu "Tuỳ chọn khác" (soát a67: chỉ Tab).
          onKeyDown={menuArrowKeys}
          // Không bao giờ cao hơn chỗ còn lại của màn (điện thoại 375x812: danh sách nhạc / giọng từng tràn đáy): phần dài cuộn trong hộp.
          className={cn(
            "z-50 flex max-h-[var(--radix-popover-content-available-height)] flex-col overflow-y-auto overscroll-contain rounded-xl border border-line bg-panel p-1.5 shadow-float",
            width,
          )}
        >
          {children}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

type MenuLook = "chip" | "action" | "row";

export function SpeedMenu({ look = "chip" }: { look?: MenuLook }) {
  const { rate, setRate } = usePlayer();
  return (
    <MenuShell
      label={speedButtonLabel(rate)}
      dialogLabel="Tốc độ đọc"
      active={rate !== 1}
      triggerKey={rate}
      focusSelector="[data-current-choice]"
      look={look}
      caption="Tốc độ"
      // Nút có nhãn của màn Đang nghe: chính con số là biểu tượng ("1,15×"), nhãn "Tốc độ" ở dưới.
      trigger={look === "action" ? speedLabel(rate) : <><Gauge className="size-4" />{speedLabel(rate)}</>}
    >
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Tốc độ đọc · nhớ riêng cho cuốn này</div>
      <div className="grid grid-cols-3 gap-1 p-1">
        {SPEEDS.map((speed) => (
          <Popover.Close asChild key={speed}>
            <button
              type="button"
              onClick={() => {
                feedback("toggle");
                setRate(speed);
                announce(`Đã chọn tốc độ đọc ${speedLabel(speed)}`);
              }}
              aria-pressed={speed === rate}
              data-current-choice={speed === rate ? "" : undefined}
              className={cn(
                "tabular touch-row h-9 rounded-lg text-sm hover:bg-hover",
                speed === rate ? "bg-accent-soft font-semibold text-accent-text" : "text-fg",
              )}
            >
              {speedLabel(speed)}
            </button>
          </Popover.Close>
        ))}
      </div>
      {!COARSE && (
        <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">
          Phím <kbd className="font-semibold">[</kbd> và <kbd className="font-semibold">]</kbd> để giảm, tăng.
        </p>
      )}
    </MenuShell>
  );
}

/** Nhạc nền ở trình phát. Chương chỉ-có-chữ ("Nghe ngay"): một danh sách phát cho cả cuốn, "Nhạc của tôi" hay tắt - cùng lựa chọn với
 *  menu của sách (PlaylistChoice.tsx), lưu vào phần sửa của sách. Chương có audio của sách nói có nhạc người làm sách gắn: bật/tắt và mức
 *  (cùng lệnh với hộp "Sửa sách"); sách không gắn nhạc thì không hiện nút. */
export function MusicMenu({ look = "chip" }: { look?: MenuLook }) {
  const { track, queue } = usePlayer();
  const speaking = Boolean(track) && queue.find((chapter) => chapter.id === track?.chapterId)?.state === "text";
  // Một vỏ cho cả hai loại chương (và lúc chưa có gì): đổi component không dựng lại nút trần mà mờ chéo. Vùng con tự lo cùng một cuốn đổi
  // trạng thái, nên vỏ chỉ chuyển cảnh khi đổi cuốn / loại chương.
  return (
    <MotionRegion as="span" motionKey={[track?.bookId ?? null, speaking]} className="inline-flex">
      {track && (speaking ? <MusicMenuFor bookId={track.bookId} look={look} /> : <PackagedMusicMenu bookId={track.bookId} look={look} />)}
    </MotionRegion>
  );
}

/** "Mức nhạc dưới giọng đọc": các mức (shared/musicLevels.ts), mức hiện tại có dấu, lời kèm mức (nếu có) chữ nhỏ cạnh tên. Chung cho nhạc
 *  người làm sách gắn và nhạc nền của sách chữ. */
export function LevelButtons({ level, disabled, onChange }: { level: number; disabled: boolean; onChange: (levelDb: number) => void }) {
  return (
    <>
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Mức nhạc dưới giọng đọc</div>
      <div className="flex flex-col gap-0.5 p-1">
        {levelOptions(level).map(([value, name]) => (
          <button
            key={value}
            type="button"
            disabled={disabled}
            aria-pressed={value === level}
            onClick={() => onChange(value)}
            className={cn(
              "flex h-9 items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-hover disabled:hover:bg-transparent",
              value === level ? "bg-accent-soft font-semibold text-accent-text" : "text-fg",
            )}
          >
            <Check className={cn("size-4 shrink-0", value === level ? "text-accent-text" : "invisible")} />
            {name}
            {LEVEL_NOTES[value] && <span className="text-xs font-normal text-fg-2">{LEVEL_NOTES[value]}</span>}
          </button>
        ))}
      </div>
    </>
  );
}

function PackagedMusicMenu({ bookId, look }: { bookId: string; look: MenuLook }) {
  const { view, change } = useBookMusic(bookId);
  const { musicBroken: broken } = usePlayer();
  const music = view.data;
  const id = `player-music-${bookId}`;
  // Gốc luôn là một MotionRegion: nhạc tải xong / gỡ nhạc thì nút hiện / ẩn dần, không thay gốc MotionRegion <-> MenuShell.
  return (
    <MotionRegion as="span" className={look === "row" ? "flex" : "inline-flex"}>{music?.hasMusic && <MenuShell
      label="Nhạc nền"
      active={music.enabled}
      width="w-64"
      look={look}
      caption="Nhạc nền"
      icon={Music2}
      triggerKey={look === "row" ? music.enabled : undefined}
      trigger={look === "row" ? (music.enabled ? "Bật" : "Tắt") :
        // Tắt: gạch chéo trên nốt nhạc (lucide không có biểu tượng "nhạc tắt").
        <span className="relative">
          <Music2 className="size-4" />
          {!music.enabled && <span aria-hidden="true" className="absolute left-1/2 top-1/2 h-0.5 w-5 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-full bg-current" />}
        </span>
      }
    ><MotionRegion>
      <div className="flex items-center justify-between gap-3 px-2 py-2">
        <label htmlFor={id} className="text-sm font-medium">
          Nhạc nền: <span className="font-semibold">{music.enabled ? "Bật" : "Tắt"}</span>
        </label>
        <Switch id={id} label="Nhạc nền" checked={music.enabled} disabled={change.isPending} onCheckedChange={(enabled) => change.mutate({ enabled })} />
      </div>
      {music.enabled && broken && <p className="px-2 pb-1 text-xs text-warning">Bài nhạc chương này không phát được.</p>}
      {music.error && <p className="px-2 pb-1 text-xs text-warning">{music.error}</p>}
      <div className={cn("transition-opacity", !music.enabled && "opacity-50")}>
        <LevelButtons level={music.levelDb} disabled={!music.enabled || change.isPending} onChange={(levelDb) => change.mutate({ levelDb })} />
      </div>
      <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{music.project ? "Nhạc của cuốn này. Đổi ở đây là đổi luôn trong Studio." : "Nhạc do người làm sách chọn. Đổi ở đây chỉ trên máy này."}</p>
    </MotionRegion></MenuShell>}</MotionRegion>
  );
}

function MusicMenuFor({ bookId, look }: { bookId: string; look: MenuLook }) {
  const { options, chosen, label, playing, scene, error, loading, choose, busy, levelDb, setLevel, levelBusy, canImport, addMusic } = usePlaylistChoice(bookId);
  const { musicOffline, musicBroken, musicLoading } = usePlayer();
  const waiting = busy || musicLoading;
  return (
    <MenuShell
      label="Nhạc nền"
      tooltip={waiting ? "Đang chuẩn bị nhạc nền…" : playing ? `Nhạc nền: ${shortPlaylistLabel(label)} - bấm để chọn nhạc khác` : "Nhạc nền - bấm để chọn nhạc"}
      active={playing || waiting}
      look={look}
      caption="Nhạc nền"
      icon={Music2}
      triggerKey={look === "row" ? [waiting, playing, label] : undefined}
      trigger={look === "row"
        ? (waiting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <span className="block max-w-32 truncate">{playing ? shortPlaylistLabel(label) : "Tắt"}</span>)
        : <>{waiting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Music2 className="size-4" />}<span className="max-w-40 truncate max-sm:hidden @max-[83rem]:hidden" title={playing ? label : undefined}>{playing ? shortPlaylistLabel(label) : ""}</span></>}
      width="w-72"
    ><MotionRegion>
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Nhạc nền · nhớ riêng cho cuốn này</div>
      <div role="group" aria-label="Danh sách nhạc nền" className="flex min-h-0 flex-col gap-0.5 overflow-y-auto p-1">
        {options.map((option) => (
          <Popover.Close asChild key={option.id ?? "off"}>
            <button
              type="button"
              disabled={option.disabled}
              aria-pressed={option.id === chosen}
              onClick={() => choose(option.id)}
              className={cn(
                "flex min-h-9 shrink-0 items-center gap-2 rounded-lg px-2 py-1 text-left text-sm hover:bg-hover disabled:opacity-50",
                option.id === chosen ? "bg-accent-soft font-semibold text-accent-text" : "text-fg",
              )}
            >
              <PlaylistOptionLabel option={option} chosen={option.id === chosen} />
            </button>
          </Popover.Close>
        ))}
        {canImport && (
          <Popover.Close asChild>
            <button type="button" onClick={() => void addMusic()} className="flex min-h-9 shrink-0 items-center gap-2 rounded-lg px-2 py-1 text-left text-sm text-fg hover:bg-hover">
              <Plus className="size-4 shrink-0" />
              {ADD_MUSIC_LABEL}
            </button>
          </Popover.Close>
        )}
        {loading && <p className="px-2 py-1.5 text-xs text-fg-2">Đang tải các danh sách nhạc…</p>}
      </div>
      {/* Chỉ khi cuốn đang có nhạc: tắt nhạc thì chỉnh mức chẳng nghe thấy gì. */}
      {playing && <LevelButtons level={levelDb} disabled={levelBusy} onChange={setLevel} />}
      {playing && scene && musicBroken && <p className="px-2 pb-1 text-xs text-warning">Có bài nhạc chưa phát được, máy sẽ thử lại sau.</p>}
      <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{playlistNote(error || musicOffline, scene)}</p>
    </MotionRegion></MenuShell>
  );
}

/** Giọng đọc của "Nghe ngay" (chương chỉ-có-chữ đang nghe): chọn nhớ riêng cho cuốn này và làm giọng chung cho cuốn khác; đổi giữa chừng
 *  có hiệu lực từ đoạn kế. Không hiện khi đang nghe chương có audio. */
/** Mở Cài đặt › Giọng đọc (nơi tải thêm giọng): đóng màn "Đang nghe" nếu đang mở, rồi cuộn tới mục giọng khi trang đã dựng xong. `anchor`: mã của chỗ cần cuộn
 *  tới (mặc định đầu mục Giọng đọc; "vieneu-module" = thẻ tải giọng VieNeu). */
function useOpenVoiceSettings() {
  const navigate = useNavigate();
  const { setExpanded } = useNowPlaying();
  return useCallback((anchor = "voices") => {
    setExpanded(false);
    navigate("/settings/voice");
    revealVoiceSettings(anchor);
  }, [navigate, setExpanded]);
}

/** Vùng cuộn có dấu hiệu "còn nữa": bóng mờ ở đáy kèm dòng nhắc khi phần dưới chưa cuộn tới - danh sách giọng dài hơn khung của menu mà không
 *  có dấu hiệu nào thì người nghe tưởng chỉ có bấy nhiêu giọng (soát điện thoại 03-10). */
function ScrollHint({ className, children }: { className: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement | null>(null);
  const [more, setMore] = useState(false);
  const measure = useCallback(() => {
    const element = box.current;
    if (element) setMore(element.scrollHeight - element.scrollTop - element.clientHeight > 8);
  }, []);
  useEffect(() => {
    measure();
    const element = box.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const watcher = new ResizeObserver(measure);
    watcher.observe(element);
    return () => watcher.disconnect();
  }, [measure]);
  return (
    <div className="relative flex min-h-0 flex-col">
      <div ref={box} onScroll={measure} className={className}>
        {children}
      </div>
      {/* Luôn dựng, chỉ đổi độ mờ: cuộn tới đáy thì dòng nhắc mờ đi, không bật tắt cứng. */}
      <div aria-hidden="true" className={cn("pointer-events-none absolute inset-x-0 bottom-0 flex h-12 items-end justify-center bg-gradient-to-t from-panel via-panel/80 to-transparent pb-1 transition-opacity duration-motion-fast", more ? "opacity-100" : "opacity-0")}>
        <span className="rounded-full bg-panel px-2.5 py-0.5 text-[0.6875rem] font-medium text-fg-2 ring-1 ring-line">Kéo xuống còn giọng khác</span>
      </div>
    </div>
  );
}

/** Nút "Chọn giọng khác" ở lời báo lỗi giọng mở menu Giọng đọc của cùng chỗ: `scope` = thanh phát hay màn "Đang nghe" (cả hai cùng nằm trong cây khi màn mở). */
const OPEN_VOICE_MENU_EVENT = "abook:open-voice-menu";
type VoiceMenuScope = "bar" | "screen";
/** Thanh gọn không có menu giọng: bấm nút ở đó mở màn "Đang nghe" rồi menu của màn ấy mở ngay khi dựng xong. */
let voiceMenuWaiting: VoiceMenuScope | null = null;

export function VoiceMenu({ scope = "bar", look = "chip" }: { scope?: VoiceMenuScope; look?: MenuLook }) {
  const [menuOpen, setMenuOpen] = useState(false);
  // Mở từ lời báo lỗi giọng ("Chọn giọng khác"): chọn xong là đọc tiếp bằng giọng mới, như nút "Đọc bằng …" (soát a67: lời báo mất mà không phát gì).
  const fromAlert = useRef(false);
  useEffect(() => {
    if (voiceMenuWaiting === scope) {
      voiceMenuWaiting = null;
      fromAlert.current = true;
      setMenuOpen(true);
    }
    const open = (event: Event) => {
      if ((event as CustomEvent<VoiceMenuScope>).detail !== scope) return;
      fromAlert.current = true;
      setMenuOpen(true);
    };
    window.addEventListener(OPEN_VOICE_MENU_EVENT, open);
    return () => window.removeEventListener(OPEN_VOICE_MENU_EVENT, open);
  }, [scope]);
  const { track, queue, resume } = usePlayer();
  const source = useSource();
  const { data: voices } = useReadAloudVoices();
  const chosen = useChosenVoice(track?.bookId); // thanh phát và màn "Đang nghe" đều có menu này: đổi ở một nơi, nơi kia cũng đổi nhãn ngay
  const speaking = queue.find((chapter) => chapter.id === track?.chapterId)?.state === "text";
  const sample = useVoiceSample((voiceId, text) => source.readAloudSample!(voiceId, text));
  const openVoiceSettings = useOpenVoiceSettings();
  // Gốc luôn là một MotionRegion (sang chương có audio / hết giọng thì nút mờ đi), không đổi gốc MotionRegion <-> MenuShell.
  const menu = () => {
  if (!track || !speaking || !voices?.length) return null;
  const current = resolveVoice(voices, chosen);
  return (
    <MenuShell
      label={voiceButtonLabel(current?.name)}
      dialogLabel="Giọng đọc"
      // Mở ở giọng đang đọc, không ở giọng đầu danh sách (soát a67).
      focusSelector="[data-current-choice]"
      open={menuOpen}
      onOpenChange={(open) => {
        if (!open) fromAlert.current = false;
        setMenuOpen(open);
      }}
      look={look}
      caption="Giọng đọc"
      icon={AudioLines}
      triggerKey={look === "row" ? current?.id : undefined}
      // Tên giọng hiện cả trên điện thoại: người nghe thấy ngay giọng nào đang đọc, không chỉ một biểu tượng.
      trigger={look === "row"
        ? <span className="block max-w-32 truncate">{current ? spokenVoiceName(current.name) : ""}</span>
        : <><AudioLines className="size-4" /><span className="max-w-24 truncate @max-[75rem]:hidden">{current ? spokenVoiceName(current.name) : ""}</span></>}
      width="w-80 max-w-[calc(100vw-1.5rem)]"
    ><MotionRegion>
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Giọng đọc · nhớ riêng cho cuốn này</div>
      {/* Cùng nhóm, cùng tên giọng với Cài đặt › Giọng đọc; "Thử" dùng cùng cách nghe thử. */}
      <ScrollHint className="min-h-0 flex-1 overflow-y-auto p-1">
        {groupedVoices(voices).map((group) => (
          <div key={group.provider} role="group" aria-label={group.title} className="mb-1.5">
            <div className="px-2 pb-0.5 pt-1 text-[0.6875rem] font-semibold uppercase tracking-wider text-fg-3">{group.title}</div>
            {voiceSections(group.voices).map((section) => (
              <div key={section.label ?? ""}>
                {section.label && <div className="px-2 pb-0.5 pt-1 text-xs font-medium text-fg-2">{section.label}</div>}
                {section.voices.map(({ voice, shown }) => {
                  const selected = voice.id === current?.id;
                  const playing = sample.playing === voice.id;
                  return (
                    <div key={voice.id} className="flex items-center gap-1">
                      <Popover.Close asChild>
                        <button
                          type="button"
                          aria-pressed={selected}
                          data-current-choice={selected ? "" : undefined}
                          onClick={() => {
                            // Giọng trực tuyến chưa đồng ý: hỏi trước khi đổi - đổi giọng làm đoạn kế gửi đi ngay (không có lệnh phát nào chen vào để hỏi).
                            const resumeAfter = fromAlert.current;
                            void pickVoiceWithConsent(voice, voices).then((id) => {
                              if (!id) return;
                              chooseVoice(track.bookId, id, track.recordId);
                              announce(`Đã chọn giọng ${spokenVoiceName(voices.find((item) => item.id === id)?.name ?? voice.name)}`);
                              // Lõi điện thoại nhận giọng mới qua một lệnh riêng: cho nó kịp tới trước lệnh phát (như "Đọc bằng …").
                              if (resumeAfter) window.setTimeout(resume, 300);
                            });
                          }}
                          className={cn(
                            "flex min-h-9 min-w-0 flex-1 items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-hover max-sm:min-h-[48px]",
                            selected ? "bg-accent-soft font-semibold text-accent-text" : "text-fg",
                          )}
                        >
                          <span className="truncate">{shown}</span>
                          {genderLabel(voice.gender) && <span className="shrink-0 text-xs font-normal text-fg-2">{genderLabel(voice.gender)}</span>}
                        </button>
                      </Popover.Close>
                      {source.readAloudSample && (
                        <button
                          type="button"
                          data-arrow-side
                          onClick={() => (playing ? sample.stop() : void sample.play(voice.id))}
                          aria-label={`${playing ? "Dừng" : "Thử"} giọng ${voice.name}`}
                          className="inline-flex h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-xs font-medium text-fg-2 hover:bg-hover hover:text-fg max-sm:h-[48px]"
                        >
                          {sample.loading === voice.id ? <Loader2 className="size-3.5 animate-spin" /> : playing ? <Square className="size-3.5" /> : <Play className="size-3.5" />}
                          {playing ? "Dừng" : "Thử"}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        ))}
        {sample.failed && <p className="px-2 pb-1 text-xs text-danger text-pretty">{sample.failed.message}</p>}
      </ScrollHint>
      <button
        type="button"
        onClick={() => openVoiceSettings()}
        className="flex min-h-9 w-full items-center rounded-lg px-3 text-left text-sm text-accent-text hover:bg-hover max-sm:min-h-[48px]"
      >
        Thêm giọng…
      </button>
      {current?.online && <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{onlineNotice(current)}</p>}
      {current && canPrepare(current, Boolean(source.readAloudPrepareOnline)) && (
        <PrepareAhead voice={current} bookId={track.bookId} chapterId={track.chapterId} />
      )}
      {source.readAloudCache && <ReadAloudCache bookId={track.bookId} />}
    </MotionRegion></MenuShell>
  );
  };
  return <MotionRegion as="span" className={look === "row" ? "flex" : "inline-flex"}>{menu()}</MotionRegion>;
}

/** Trạng thái "Làm trước" (một việc cho cả máy): hỏi lại thường xuyên khi đang làm. Điện thoại còn đẩy tiến độ vào cùng khoá (android/readAloud.ts). */
function usePrepareStatus(enabled = true) {
  const source = useSource();
  return useQuery({
    queryKey: PREPARE_STATUS_KEY,
    queryFn: () => source.readAloudPrepareStatus!(),
    enabled: enabled && Boolean(source.readAloudPrepareStatus),
    refetchInterval: (query) => (query.state.data?.state === "running" ? 2000 : 15000),
  });
}

/** Các chương của cuốn này đã làm sẵn bằng giọng của cuốn (dấu "Đã làm sẵn" ở danh sách chương). */
export function usePreparedChapters(bookId: string, enabled: boolean): Set<number> {
  // Chỉ nguồn báo từng chương (điện thoại, có "Chỉ khi đang sạc"); máy tính làm theo đoạn, không có dấu - khỏi hỏi máy chủ.
  const source = useSource();
  const { data } = usePrepareStatus(enabled && Boolean(source.readAloudPrepareOptions));
  const voice = useChosenVoice(bookId); // đổi giọng thì dấu "Đã làm sẵn" theo giọng mới, không giữ dấu của giọng cũ
  return useMemo(() => readyChapterIds(data, bookId, voice), [data, bookId, voice]);
}

/** "Làm trước": máy đọc sẵn các chương tới ở nền - giọng chậm hơn tốc độ nghe (VieNeu) vẫn nghe liền mạch; trên điện thoại cả giọng trực tuyến,
 *  để nghe khi không có mạng. Nói rõ còn bao lâu; người nghe bấm mới làm, bấm "Dừng" là thôi. */
function PrepareAhead({ voice, bookId, chapterId }: { voice: ReadAloudVoice; bookId: string; chapterId: number }) {
  const source = useSource();
  const client = useQueryClient();
  const { queue } = usePlayer();
  const { data: status } = usePrepareStatus();
  const { data: voices } = useReadAloudVoices();
  const [busy, setBusy] = useState(false);
  const upcoming = upcomingTextChapters(queue, chapterId);
  const request = {
    voice: voice.id,
    bookId,
    chapters: upcoming.map(({ id, title, skip }) => ({ id, title, skip })),
    label: upcoming.length === 1 ? upcoming[0].title : `${upcoming.length} chương tới`,
  };
  const mine = Boolean(status && status.voice === voice.id && (!status.bookId || status.bookId === bookId));
  const running = status?.state === "running";
  const { data: plan } = useQuery({
    queryKey: ["readaloud", "prepare-plan", request.voice, request.bookId, request.chapters.map((chapter) => chapter.id)],
    queryFn: () => source.readAloudPreparePlan!(request),
    enabled: Boolean(source.readAloudPreparePlan) && request.chapters.length > 0 && !(mine && running),
  });
  // "Làm trước" <-> "Dừng làm trước" thay chỗ nhau: tiêu điểm theo sang nút mới (soát a67).
  const follow = useFocusFollows(mine && running);
  if (!source.readAloudPrepare) return <MotionRegion />;
  const chargingOnly = status?.chargingOnly ?? true;
  const settle = (next: PrepareStatus) => client.setQueryData(PREPARE_STATUS_KEY, next);
  const start = async () => {
    setBusy(true);
    try {
      // Giọng trực tuyến chưa đồng ý: "Làm trước" gửi chữ cả loạt chương đi ở nền - hỏi trước như lúc bấm phát (soát a79 lỗi 6). Chọn giọng khác trong hộp thì đổi giọng, chưa làm trước.
      if (voice.online && !onlineConsentGiven(voice.provider)) {
        const picked = await askOnlineConsent(voice, voices ?? [voice]);
        if (!picked) return;
        if (picked.voice !== voice.id) {
          chooseVoice(bookId, picked.voice);
          return;
        }
      }
      settle(await source.readAloudPrepare!({ ...request, chargingOnly }));
    } catch (error) {
      toast.error("Chưa làm trước được", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const label = mine && status ? prepareLabel(status) : running ? "Đang làm trước cho một cuốn hay giọng khác - làm ở đây thì việc ấy dừng." : "";
  // Chương cuối: không còn chương nào để làm trước thì không mời (câu mời không có nút nào theo sau chỉ làm người nghe tìm nút).
  if (!label && upcoming.length === 0) return <MotionRegion />;
  return (
    <MotionRegion as="div" {...follow} elementRef={follow.ref} ref={undefined} className="border-t border-line px-2 pb-1 pt-2 text-xs text-fg-2">
      <p className="text-pretty">{label || prepareIntro(voice)}</p>
      {!(mine && running) && plan && <p className="mt-1 text-pretty">{planLabel(plan)}</p>}
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        {mine && running ? (
          <button type="button" data-focus-next className="rounded-lg px-2 py-1 font-medium text-fg hover:bg-hover" onClick={() => void source.readAloudPrepareCancel?.().then(settle)}>
            Dừng làm trước
          </button>
        ) : (
          upcoming.length > 0 && (
            <button type="button" data-focus-next aria-disabled={busy || undefined} aria-busy={busy || undefined} className="rounded-lg px-2 py-1 font-medium text-accent-text hover:bg-hover aria-disabled:opacity-45" onClick={busyClick(busy, () => void start())}>
              {upcoming.length === 1 ? "Làm trước chương sau" : `Làm trước ${upcoming.length} chương tới`}
            </button>
          )
        )}
        {source.readAloudPrepareOptions && (
          <label className="flex min-h-8 cursor-pointer items-center gap-1.5 px-1">
            <input
              type="checkbox"
              className="size-4 accent-[var(--accent)]"
              checked={chargingOnly}
              onChange={(event) => void source.readAloudPrepareOptions!({ chargingOnly: event.target.checked }).then(settle)}
            />
            Chỉ khi đang sạc
          </label>
        )}
      </div>
    </MotionRegion>
  );
}

/** Bản đọc đã làm (máy tính): các đoạn đã đọc xong nằm trong bộ đệm của máy - nói rõ chiếm bao nhiêu (cuốn này / cả máy) và cho xoá phần của cuốn,
 *  hỏi lại ngay tại chỗ (không hộp thoại). Xoá xong, các đoạn đã nạp sẵn trong lúc nghe cũng bỏ để lần phát sau đọc lại. */
function ReadAloudCache({ bookId }: { bookId: string }) {
  const source = useSource();
  const client = useQueryClient();
  const [asking, setAsking] = useState(false);
  const askBox = useRef<HTMLDivElement>(null);
  useBackLayer(asking, () => setAsking(false), askBox);
  const [busy, setBusy] = useState(false);
  const key = ["readaloud", "cache", bookId];
  const { data: usage } = useQuery({ queryKey: key, queryFn: () => source.readAloudCache!(bookId), refetchInterval: 15000 });
  // Hỏi lại / xoá xong: nút đang giữ tiêu điểm biến mất - tiêu điểm theo sang nút vừa hiện, xoá xong thì về dòng dung lượng (soát a67).
  const follow = useFocusFollows(`${asking}:${(usage?.book ?? 0) > 0}`);
  if (!usage) return <MotionRegion />;
  const clear = async () => {
    setBusy(true);
    try {
      client.setQueryData(key, await source.readAloudCacheClear!(bookId));
      void client.invalidateQueries({ queryKey: PREPARE_STATUS_KEY }); // máy chủ đã bỏ dòng "Đã làm trước ..." của cuốn này cùng bản đọc
      window.dispatchEvent(new CustomEvent<ReadingsChanged>(READINGS_CHANGED_EVENT, { detail: { bookId, surfaces: [], all: true } }));
    } catch (error) {
      toast.error("Chưa xoá được bản đọc", { description: (error as Error).message });
    } finally {
      setBusy(false);
      setAsking(false);
    }
  };
  return (
    <MotionRegion as="div" {...follow} elementRef={follow.ref} ref={undefined} className="border-t border-line px-2 pb-1 pt-2 text-xs text-fg-2">
      <p tabIndex={-1} data-focus-fallback className="text-pretty">{cacheLabel(usage)}</p>
      {usage.book > 0 &&
        (asking ? (
          <div ref={askBox} role="alertdialog" aria-label="Xoá bản đọc" className="mt-1.5">
            <p className="text-pretty text-fg">{clearCacheQuestion(usage)}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <button type="button" aria-disabled={busy || undefined} aria-busy={busy || undefined} className="rounded-lg px-2 py-1 font-medium text-danger hover:bg-hover aria-disabled:opacity-45" onClick={busyClick(busy, () => void clear())}>
                Xoá
              </button>
              <button type="button" data-focus-next aria-disabled={busy || undefined} className="rounded-lg px-2 py-1 font-medium text-fg hover:bg-hover" onClick={busyClick(busy, () => setAsking(false))}>
                Giữ lại
              </button>
            </div>
          </div>
        ) : (
          <button type="button" data-focus-next className="mt-1.5 rounded-lg px-2 py-1 font-medium text-fg hover:bg-hover" onClick={() => setAsking(true)}>
            Xoá bản đọc
          </button>
        ))}
    </MotionRegion>
  );
}

export function SleepMenu({ look = "chip" }: { look?: MenuLook }) {
  const { sleep, setSleep, extendSleep, options, sleepStoppedAt, lastSleepMinutes, track } = usePlayer();
  // Thẻ "Tối qua" chỉ đáng nhắc khi người nghe đã từng có đêm nào được ghi lại (chưa có thì nhắc là nhắc một thứ họ chưa thấy bao giờ).
  const hadNight = Boolean(useLastNight().data);
  const now = useTicker(sleep.kind === "minutes" && sleep.since !== null);
  const recentlyStopped = sleep.kind === "off" && sleepStoppedAt !== null && now - sleepStoppedAt < 30 * 60_000;
  return (
    <MotionRegion as={look === "chip" ? "div" : "span"} className={look === "row" ? "flex" : look === "action" ? "inline-flex" : undefined}><SleepPicker
      look={look}
      sleep={sleep}
      now={now}
      disabled={!track}
      customStart={lastSleepMinutes || 20}
      extendMinutes={options.extendMinutes}
      onExtend={() => extendSleep()}
      onSet={setSleep}
      idle={
        recentlyStopped ? (
          <div className="px-2 pb-2 pt-1.5">
            <div className="text-sm">
              Hẹn giờ đã tắt tiếng lúc{" "}
              <span className="tabular font-semibold">{new Date(sleepStoppedAt!).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</span>.
            </div>
            <Popover.Close asChild>
              <button
                type="button"
                onClick={withFeedback("toggle", () => setSleep({ kind: "minutes", minutes: lastSleepMinutes }))}
                className="mt-2 h-9 w-full rounded-lg bg-accent-soft text-sm font-semibold text-accent-text"
              >
                Bật lại {lastSleepMinutes} phút
              </button>
            </Popover.Close>
          </div>
        ) : null
      }
      note={
        <>
          Tiếng nhỏ dần {options.fadeSeconds} giây trước khi dừng. Lúc đó {EXTEND_GESTURE} để nghe thêm {options.extendMinutes} phút.
          {hadNight && " Sáng hôm sau, thẻ “Tối qua” giúp tìm lại đoạn còn nhớ."}
        </>
      }
    /></MotionRegion>
  );
}

/**
 * Hẹn giờ tắt cho loa / TV đang phát (thanh "Đang phát trên…" của máy tính và điện thoại): cùng nút, cùng lựa chọn với hẹn
 * giờ của trình phát ở đây, nhưng máy giữ phiên phát mới là bên đếm - nút chỉ đọc lại và gửi lệnh.
 */
export function RemoteSleepMenu({ sleep, name, onSet }: { sleep: SleepMode; name: string; onSet: (request: SleepRequest) => void }) {
  const { options } = usePlayer();
  const now = useTicker(sleep.kind === "minutes" && sleep.since !== null);
  return (
    <SleepPicker
      sleep={sleep}
      now={now}
      name={name}
      customStart={20}
      extendMinutes={options.extendMinutes}
      onExtend={() => {
        const longer = sleepExtended(sleep, options.extendMinutes, sleep.kind === "minutes" && sleep.since !== null, now);
        if (longer.kind === "minutes") onSet({ kind: "minutes", minutes: (sleepLeftMs(longer, now) ?? 0) / 60_000 });
      }}
      onSet={onSet}
      note={`Hết giờ thì ${name} tạm dừng, chỗ đang nghe được lưu.`}
    />
  );
}

/** Nút hẹn giờ và bảng chọn giờ: dùng chung cho trình phát ở đây (SleepMenu) và loa / TV (RemoteSleepMenu). */
function SleepPicker({
  sleep,
  now,
  name,
  disabled = false,
  customStart,
  extendMinutes,
  idle = null,
  note,
  look = "chip",
  ...handlers
}: {
  look?: MenuLook;
  sleep: SleepMode;
  now: number;
  /** Thiết bị đang phát (loa / TV): tên đi vào nhãn đọc màn hình. */
  name?: string;
  disabled?: boolean;
  customStart: number;
  extendMinutes: number;
  onExtend: () => void;
  onSet: (request: SleepRequest) => void;
  /** Hiện thay phần "đang hẹn" khi chưa hẹn gì. */
  idle?: ReactNode;
  note: ReactNode;
}) {
  // Chọn mức / thêm giờ là việc người nghe vừa làm: tiếng chạm + rung (DESIGN 5.3/5.4). Hẹn giờ tự tắt thì không đi qua đây.
  const onExtend = withFeedback("toggle", handlers.onExtend);
  const onSet = withFeedback("toggle", handlers.onSet);
  const [custom, setCustom] = useState(customStart);
  const active = sleep.kind !== "off";
  const left = sleepLeftMs(sleep, now);
  const spoken = active ? sleepSpoken(sleep, now) : "Hẹn giờ tắt";
  return (
    <MenuShell
      label={name ? `${spoken} trên ${name}` : spoken}
      dialogLabel={name ? `Hẹn giờ tắt trên ${name}` : "Hẹn giờ tắt"}
      active={active}
      width="w-64"
      focusSelector="[data-current-choice]"
      look={look}
      icon={Moon}
      // Nút có nhãn: đang hẹn thì nhãn dưới là thời gian còn lại ("12 phút"), mờ chéo khi đổi.
      caption={look === "row" ? "Hẹn giờ tắt" : active ? sleepButtonLabel(sleep, now) : "Hẹn giờ"}
      triggerKey={look === "row" ? active && sleepButtonLabel(sleep, now) : undefined}
      trigger={look === "row" ? (active ? sleepButtonLabel(sleep, now) : "Tắt") :
        <>
          <SleepRing fraction={sleep.kind === "minutes" && sleep.minutes > 0 && left !== null ? left / (sleep.minutes * 60_000) : null}>
            <Moon className={look === "action" ? "size-5" : "size-4"} />
          </SleepRing>
          {active && look === "chip" && <span className="tabular">{sleepButtonLabel(sleep, now)}</span>}
        </>
      }
    ><MotionRegion>
      {active ? (
        <div className="px-2 pb-2 pt-1.5">
          <div className="text-xs font-medium text-fg-2">{sleep.kind === "chapter" ? "Dừng khi" : "Tắt sau"}</div>
          <div className="tabular mt-0.5 text-2xl font-semibold tracking-tight">
            {sleep.kind === "chapter" ? "hết chương này" : sleepLabel(sleep, now)}
          </div>
          {sleep.kind === "minutes" && sleep.since === null && left !== null && (
            <div className="mt-0.5 text-xs text-fg-2">Đang tạm dừng - đồng hồ cũng dừng.</div>
          )}
          <div className="mt-3 flex gap-1.5">
            <Popover.Close asChild>
              <button
                type="button"
                onClick={onExtend}
                className="h-9 flex-1 rounded-lg bg-accent-soft text-sm font-semibold text-accent-text hover:brightness-95"
              >
                +{extendMinutes} phút
              </button>
            </Popover.Close>
            <Popover.Close asChild>
              <button type="button" onClick={() => onSet({ kind: "off" })} className="h-9 flex-1 rounded-lg text-sm font-medium text-danger hover:bg-hover">
                Tắt hẹn giờ
              </button>
            </Popover.Close>
          </div>
        </div>
      ) : (
        idle
      )}
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">{active ? "Đặt lại" : "Dừng phát sau"}</div>
      <div className="grid grid-cols-4 gap-1 p-1">
        {SLEEP_CHOICES.map((minutes) => (
          <Popover.Close asChild key={minutes}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSet({ kind: "minutes", minutes })}
              aria-label={`${minutes} phút`}
              aria-pressed={sleep.kind === "minutes" && sleep.minutes === minutes}
              data-current-choice={sleep.kind === "minutes" && sleep.minutes === minutes ? "" : undefined}
              className={cn(
                "tabular touch-row h-9 rounded-lg text-sm hover:bg-hover disabled:opacity-40",
                sleep.kind === "minutes" && sleep.minutes === minutes && "bg-accent-soft font-semibold text-accent-text",
              )}
            >
              {minutes}′
            </button>
          </Popover.Close>
        ))}
      </div>
      <div className="flex items-center gap-1 px-1 pb-1">
        <button
          type="button"
          aria-label="Bớt 5 phút"
          onClick={() => setCustom((value) => Math.max(5, value - 5))}
          className="touch-box grid size-9 place-items-center rounded-lg text-lg hover:bg-hover"
        >
          −
        </button>
        <span className="tabular flex-1 text-center text-sm font-medium" aria-live="polite">
          {custom} phút
        </span>
        <button
          type="button"
          aria-label="Thêm 5 phút"
          onClick={() => setCustom((value) => Math.min(240, value + 5))}
          className="touch-box grid size-9 place-items-center rounded-lg text-lg hover:bg-hover"
        >
          +
        </button>
        <Popover.Close asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSet({ kind: "minutes", minutes: custom })}
            className="touch-row h-9 rounded-lg bg-hover px-3 text-sm font-medium hover:bg-line disabled:opacity-40 pointer-coarse:min-w-[48px]"
          >
            Đặt
          </button>
        </Popover.Close>
      </div>
      <div className="px-1 pb-1">
        <Popover.Close asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSet({ kind: "chapter" })}
            className="h-9 w-full rounded-lg bg-hover text-sm font-medium hover:bg-line disabled:opacity-40"
          >
            Dừng khi hết chương này
          </button>
        </Popover.Close>
      </div>
      <p className="px-2 pb-1 pt-2 text-xs leading-snug text-fg-2">{note}</p>
    </MotionRegion></MenuShell>
  );
}

function VolumeControl({ look = "chip" }: { look?: "chip" | "row" }) {
  const { volume, setVolume } = usePlayer();
  const Icon = volume === 0 ? VolumeX : volume < 0.5 ? Volume1 : Volume2;
  const remembered = useRef(volume || 0.9);
  // Dưới 1280px thanh phát không còn chỗ cho thanh trượt: bấm loa mở ô chỉnh âm lượng thay vì chỉ có tắt/bật tiếng (soát UX
  // 29-09). Phím M vẫn tắt/bật tiếng ở mọi cỡ.
  const wide = useMediaQuery("(min-width: 1280px)");
  const toggleMute = () => {
    if (volume === 0) setVolume(remembered.current);
    else {
      remembered.current = volume;
      setVolume(0);
    }
  };
  const slider = (className: string) => (
    <Slider.Root
      className={cn("group relative h-4 touch-none select-none items-center", SLIDER_REACH, className)}
      min={0}
      max={1}
      step={0.05}
      value={[volume]}
      onValueChange={([value]) => setVolume(value)}
      onKeyDown={(event) => event.stopPropagation()}
    >
      <Slider.Track className="relative h-1 grow overflow-hidden rounded-full bg-line-strong">
        <Slider.Range className="absolute h-full rounded-full bg-fg-2 group-hover:bg-accent" />
      </Slider.Track>
      <Slider.Thumb
        aria-label="Âm lượng"
        aria-valuetext={`Âm lượng ${Math.round(volume * 100)}%`}
        className="block size-3 rounded-full bg-fg opacity-0 shadow group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-focus"
      />
    </Slider.Root>
  );
  // Một dòng trong menu "…" của màn Đang nghe: tên + nút tắt tiếng + thanh trượt, không thêm bảng nổi nào.
  if (look === "row") {
    return (
      <div className="flex min-h-10 items-center gap-2 px-2 text-sm max-sm:min-h-[48px]">
        <span className="min-w-0 flex-1">Âm lượng</span>
        <IconButton label={withShortcut(volume === 0 ? "Bật tiếng" : "Tắt tiếng", "M")} icon={Icon} size="sm" onClick={toggleMute} />
        {slider("flex w-28")}
      </div>
    );
  }
  if (!wide) {
    return (
      <Popover.Root><MotionRegion>
        <Popover.Trigger asChild>
          <button
            type="button"
            aria-label={`Âm lượng ${Math.round(volume * 100)}%`}
            className="grid size-8 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg data-[state=open]:bg-hover max-sm:size-[48px]"
          >
            <Icon className="glyph" />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content side="top" sideOffset={8} className="z-50 flex items-center gap-2 rounded-xl border border-line bg-panel p-2 shadow-float">
            <IconButton label={withShortcut(volume === 0 ? "Bật tiếng" : "Tắt tiếng", "M")} icon={Icon} size="sm" onClick={toggleMute} />
            {slider("flex w-32")}
            <span className="tabular w-9 text-right text-xs text-fg-2">{Math.round(volume * 100)}%</span>
          </Popover.Content>
        </Popover.Portal>
      </MotionRegion></Popover.Root>
    );
  }
  return (
    <MotionRegion as="div" className="flex items-center gap-1">
      <IconButton label={withShortcut(volume === 0 ? "Bật tiếng" : "Tắt tiếng", "M")} icon={Icon} size="sm" {...keepFocus} onClick={toggleMute} />
      {slider("flex w-20")}
    </MotionRegion>
  );
}

/** Thêm dấu trang kèm thông báo có "Ghi chú" và "Hoàn tác". Dấu trùng chỗ (±5 giây) không tạo thêm. */
export function useAddBookmark() {
  const { addBookmark, track } = usePlayer();
  const { expanded, setExpanded } = useNowPlaying();
  const source = useSource();
  const client = useQueryClient();
  const phoneLayout = useMediaQuery("(max-width: 767px)");
  // Màn "Đang nghe" mở: thông báo ở góc trên phải từng che đúng tab "Dấu trang" (soát UX a16) - xuống đáy, dưới bảng. Bố cục điện thoại (dưới 768 px) thì tab nằm ở đáy: thông báo ở đầu màn. App Android giữ chỗ cũ.
  const position = expanded && !Capacitor.isNativePlatform() ? (phoneLayout ? "top-center" : "bottom-right") : undefined;
  return useCallback(async () => {
    if (!track) return;
    let failure: unknown;
    const mark = await addBookmark().catch((error: unknown) => {
      failure = error;
      return null;
    });
    if (!mark) {
      if (isRecordGone(failure)) toast.error(RECORD_GONE_MESSAGE, { id: "record-gone", position });
      else toast.error("Chưa thêm được dấu trang", { position });
      feedback("reject");
      return;
    }
    if (mark.existing) {
      toast.dismiss("bookmark");
      toast("Đã có dấu trang ở chỗ này", { id: "bookmark-existing", description: formatClock(mark.seconds), position });
      return;
    }
    feedback("confirm");
    toast.success("Đã thêm dấu trang", {
      id: "bookmark",
      position,
      duration: 8000,
      // Giờ ghi trong dấu trang (đã làm tròn ở nơi lưu) - cùng con số danh sách dấu trang hiện, không đọc lại đồng hồ phát.
      description: `${track.chapterTitle} · ${formatClock(mark.seconds)}`,
      action: {
        label: "Ghi chú",
        onClick: () => {
          setExpanded(true);
          window.setTimeout(() => window.dispatchEvent(new CustomEvent(EDIT_BOOKMARK_EVENT, { detail: mark.id })), 50);
        },
      },
      cancel: {
        label: "Hoàn tác",
        onClick: () => {
          // dấu vừa đặt vào hồ sơ của phiên phát: hoàn tác cũng vào đúng hồ sơ ấy
          void source.deleteBookmark(track.bookId, mark.id, track.recordId).then(() => {
            void client.invalidateQueries({ queryKey: ["listen", "book", track.bookId] });
          }).catch((error: unknown) => reportWriteFailure(error, "Chưa hoàn tác được dấu trang"));
        },
      },
    });
  }, [addBookmark, client, position, setExpanded, source, track]);
}

function BookmarkButton() {
  const add = useAddBookmark();
  return <ActionButton label="Dấu trang" aria-label={withShortcut("Thêm dấu trang", "B")} icon={BookmarkPlus} {...keepFocus} onClick={() => void add()} />;
}

/** Phím B: một chỗ lắng nghe duy nhất (thanh phát luôn có mặt khi đang nghe). */
function BookmarkShortcut() {
  const add = useAddBookmark();
  useEffect(() => {
    const onShortcut = () => void add();
    window.addEventListener("abook:bookmark", onShortcut);
    return () => window.removeEventListener("abook:bookmark", onShortcut);
  }, [add]);
  return null;
}

/** Vòng đếm ngược quanh biểu tượng hẹn giờ: phần còn lại của khoảng đã đặt, liếc là biết sắp tắt chưa. */
function SleepRing({ fraction, children }: { fraction: number | null; children: ReactNode }) {
  if (fraction === null) return <>{children}</>;
  const radius = 10;
  const length = 2 * Math.PI * radius;
  const shown = Math.max(0, Math.min(1, fraction));
  return (
    <span className="relative grid size-6 place-items-center">
      <svg className="absolute inset-0 -rotate-90" viewBox="0 0 24 24" aria-hidden>
        <circle cx="12" cy="12" r={radius} fill="none" stroke="currentColor" strokeOpacity={0.22} strokeWidth="2" />
        <circle
          cx="12"
          cy="12"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray={length}
          strokeDashoffset={length * (1 - shown)}
          className="transition-[stroke-dashoffset] duration-500 ease-linear"
        />
      </svg>
      <span className="scale-[0.8]">{children}</span>
    </span>
  );
}

/** Đang nhỏ dần trước khi tắt: nói rõ và cho nghe thêm bằng một chạm. */
function FadingNotice({ className }: { className?: string }) {
  const { fading, extendSleep, options } = usePlayer();
  const content = () => {
  if (!fading) return null;
  return (
    <div className={cn("motion-appear flex items-center gap-3 rounded-xl bg-accent-soft px-3 py-2 text-sm text-accent-text", className)} role="status">
      <Moon className="size-4 shrink-0" />
      <span className="min-w-0 flex-1">Sắp tắt · {EXTEND_GESTURE} để nghe thêm {options.extendMinutes} phút</span>
      <button type="button" onClick={() => extendSleep()} className="shrink-0 rounded-lg bg-accent px-2.5 py-1 text-xs font-semibold text-accent-ink">
        +{options.extendMinutes} phút
      </button>
    </div>
  );
  };
  return <MotionPresence open={Boolean(fading)}><MotionRegion>{content()}</MotionRegion></MotionPresence>;
}

/** Ghi công nhạc nền đang nghe (CC BY đòi nêu tác giả ở nơi nhạc phát): một dòng nhỏ, mờ, chỉ hiện khi đang phát; không
 *  có bài thì không hiện gì. Chạm (hay Enter) vào dòng để xem đủ ghi công: tên bài, tác giả, giấy phép (có liên kết) -
 *  màn cảm ứng không có chỗ "giữ chuột" để xem chú thích. */
function MusicCreditLine() {
  const { musicCredit, playing } = usePlayer();
  const [open, setOpen] = useState(false);
  const label = [musicCredit?.title, musicCredit?.creator].filter(Boolean).join(" · ");
  useEffect(() => setOpen(false), [musicCredit]);
  const content = () => {
  if (!playing || !musicCredit || !label) return null;
  return (
    <div className="motion-appear mt-0.5 text-xs text-fg-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title={musicCreditText(musicCredit) || label}
        className="max-w-full truncate rounded outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Nhạc nền: {label}
      </button>
      <Collapse open={open} className="mx-auto mt-1 max-w-sm break-words text-left">
          <p>{musicCreditText(musicCredit)}</p>
          {musicCredit.license && (
            <p>
              Giấy phép:{" "}
              {musicCredit.licenseUrl ? (
                <a href={musicCredit.licenseUrl} target="_blank" rel="noreferrer" onClick={(event) => openExternal(musicCredit.licenseUrl!, event)} className="underline">
                  {licenseLabel(musicCredit.license, musicCredit.licenseUrl)}
                </a>
              ) : (
                licenseLabel(musicCredit.license)
              )}
            </p>
          )}
          {musicNeedsModifiedNote(musicCredit.license) && <p>{MUSIC_MODIFIED_NOTE}</p>}
          {musicCredit.landing && (
            <p>
              <a href={musicCredit.landing} target="_blank" rel="noreferrer" onClick={(event) => openExternal(musicCredit.landing!, event)} className="underline">
                Trang của bài nhạc
              </a>
            </p>
          )}
        </Collapse>
    </div>
  );
  };
  return <MotionPresence open={Boolean(playing && musicCredit && label)}><MotionRegion>{content()}</MotionRegion></MotionPresence>;
}

/** Dòng dưới tên chương: tên sách - hay đang chờ giọng máy đọc đoạn đầu. Lỗi KHÔNG nằm ở đây (PlayerAlert). */
function TrackSubtitle() {
  const { track, purpose, atEnd, playing, buffering } = usePlayer();
  const speaking = useSpeaking();
  // Đệm một nhịp giữa câu (~1 giây) không được làm dòng này nháy "Đang chuẩn bị giọng đọc…" rồi mất: chỉ nói khi chờ thật sự lâu (soát UX a9).
  const preparing = useAfter(speaking && playing && buffering, PREPARING_VOICE_AFTER_MS);
  if (!track) return <MotionRegion />;
  return (
    <MotionRegion>
      {purpose === "review" && (
        <span className="mr-1.5 inline-block rounded bg-info-soft px-1.5 text-[0.6875rem] font-semibold uppercase tracking-wide text-info">Nghe kiểm</span>
      )}
      {preparing ? PREPARING_VOICE : atEnd === "caughtUp" ? "Đã nghe hết phần đã có" : track.bookTitle}
    </MotionRegion>
  );
}

/** Không phát được (mất mạng, giọng đọc không phản hồi, file hỏng): một khối riêng đọc màn hình đọc ngay (role="alert") kèm "Thử lại" - không
 *  thay tên sách bằng chữ đỏ. Lời nhắn đã rơi sang giọng của máy (vẫn đang đọc) là một dòng trạng thái, tự ẩn.
 *  Mất mạng mà máy không có giọng đọc không cần mạng: một câu ngắn nói tên giọng, nút chính theo tình huống - đã có giọng chạy trên máy (VieNeu…) thì
 *  "Đọc bằng …" (đổi giọng cuốn này rồi phát tiếp), chưa thì "Tải giọng VieNeu" (tới thẻ tải giọng trong Cài đặt). Mạng về thì tự "Thử lại" (onlineRetry.ts).
 *  Hiện ở MỌI màn, kể cả Cài đặt (soát a67: đổi sang giọng cần mạng ở Cài đặt khi mất mạng - trình phát dừng im lặng, bấm Phát không lời nào). Bấm phát
 *  khi lời báo đang hiện: khối dựng lại (`errorRepeat`) để trình đọc màn hình đọc lại.
 *  `overlay`: trong màn "Đang nghe". */
function PlayerAlert({ className, overlay = false, compact = false }: { className?: string; overlay?: boolean; compact?: boolean }) {
  const { error, errorRepeat, notice, resume, retry, dismissError, wantsPlay, track } = usePlayer();
  const { setExpanded } = useNowPlaying();
  const openVoiceSettings = useOpenVoiceSettings();
  const voices = useReadAloudVoices().data;
  const offline = Boolean(error) && isNoOfflineVoice(error);
  // Mất mạng, hay giọng có mạng mà hỏng (dịch vụ từ chối, lỗi, không phản hồi) và máy không có giọng nào khác: cùng một câu ngắn + cùng đường ra.
  const stuck = Boolean(error) && isVoiceStuck(error);
  useRetryWhenOnline(offline, retry, dismissError, wantsPlay);
  const content = () => {
  if (error) {
    const current = voices && track ? resolveVoice(voices, chosenVoice(track.bookId, track.recordId)) : undefined;
    const local = stuck && voices ? localVoiceFor(voices, current) : undefined;
    const button = "min-h-9 shrink-0 rounded-lg bg-panel px-3 text-xs font-semibold ring-1 ring-line hover:bg-hover max-sm:min-h-[48px]";
    return (
      <div key={errorRepeat} role="alert" className={cn("motion-appear flex items-start gap-3 rounded-xl bg-danger-soft px-3 py-2 text-sm text-fg", className)}>
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-danger" />
        {/* Lời báo + cụm nút xuống hàng khi hẹp; nút ✕ đứng riêng ở góc trên phải nên không thêm hàng nào và không bao giờ trôi xuống dưới cụm nút. */}
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-2">
          <span className="min-w-0 flex-1 basis-[14rem]">{stuck && current ? (offline ? noOfflineMessage : unusableVoiceMessage)(spokenVoiceName(current.name)) : error}</span>
          {stuck && local && track && (
            <button
              type="button"
              onClick={() => {
                chooseVoice(track.bookId, local.id, track.recordId);
                dismissError();
                // Lõi điện thoại nhận giọng mới qua một lệnh riêng: cho nó kịp tới trước lệnh phát.
                window.setTimeout(resume, 300);
              }}
              {...keepFocus}
              className={button}
            >
              Đọc bằng {voiceCaption(local)}
            </button>
          )}
          <button type="button" onClick={retry} {...keepFocus} className={button}>
            Thử lại
          </button>
          {stuck && Boolean(voices?.length) && (
            <button
              type="button"
              onClick={() => {
                if (compact) {
                  voiceMenuWaiting = "screen";
                  setExpanded(true);
                } else {
                  window.dispatchEvent(new CustomEvent<VoiceMenuScope>(OPEN_VOICE_MENU_EVENT, { detail: overlay ? "screen" : "bar" }));
                }
              }}
              {...keepFocus}
              className={button}
            >
              Chọn giọng khác
            </button>
          )}
          {stuck && !local && <VieneuDownload button="Tải giọng VieNeu" onOpenSettings={() => openVoiceSettings("vieneu-module")} />}
        </div>
        {/* Gạt đi tới lần lỗi mới: khối này nằm trên mọi màn, người đang làm việc khác (Cài đặt, Thư viện) không bị nó đè mãi. */}
        <button
          type="button"
          aria-label="Đóng lời báo"
          onClick={dismissError}
          {...keepFocus}
          className="-my-1 -mr-1 grid size-9 shrink-0 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg max-sm:size-[48px]"
        >
          <X className="size-4" />
        </button>
      </div>
    );
  }
  if (!notice) return null;
  return (
    <div role="status" className={cn("flex items-center gap-3 rounded-xl bg-hover px-3 py-2 text-sm text-fg-2", className)}>
      <AudioLines className="size-4 shrink-0" />
      <span className="min-w-0 flex-1">{notice}</span>
    </div>
  );
  };
  // Lỗi <-> lời nhắn, hay đổi lời báo khi khối đang hiện: mờ chéo bên trong (MotionPresence chỉ lo hiện / ẩn cả khối).
  return <MotionPresence open={Boolean(error || notice)}><MotionRegion>{content()}</MotionRegion></MotionPresence>;
}

function CompactProgress() {
  const fraction = useClock((time, duration) => (duration > 0 ? Math.min(1, Math.round((time / duration) * 400) / 400) : 0));
  return (
    <div {...heardBarProps(fraction)} aria-label="Đã nghe chương này" aria-valuetext={`đã nghe ${Math.round(fraction * 100)}% chương`} className="absolute inset-x-0 top-0 h-[2px] bg-line">
      <div className="motion-progress h-full bg-accent" style={{ transform: `scaleX(${fraction * 100 / 100})` }} />
    </div>
  );
}

/** Thiết bị khác (điện thoại) đã nghe xa hơn chỗ đang nạp ở đây: hỏi, đừng lặng lẽ nhảy - và đừng để lần lưu kế tiếp
 *  của máy này ghi đè vị trí mới hơn ấy (Audible hỏi "tới vị trí xa nhất?"; Audiobookshelf bị chê vì không hỏi). */
function FurtherElsewhere() {
  const { track, playing, queue, positionStamp, jumpTo, purpose } = usePlayer();
  const { data: book } = useListenBook(track?.bookId);
  const readClock = useClockReader();
  const asked = useRef("");
  const last = book?.state.last;
  const active = book?.records?.find((record) => record.active)?.id;
  useEffect(() => {
    // Cả khi ĐANG PHÁT (soát a27 lỗi 2): máy này đã bấm nghe trước khi chỗ của máy kia về tới - lần lưu kế của nó sẽ đè, nên vẫn phải hỏi.
    if (!track || !last || purpose !== "listen") return;
    // chỗ nghe trên máy chủ là của hồ sơ khác (máy khác vừa đổi hồ sơ): FollowRecord lo, đây không phải "nghe xa hơn"
    if (track.recordId && active && track.recordId !== active) return;
    const key = `${track.bookId}:${last.at}`;
    if (asked.current === key || !newerElsewhere(last, positionStamp(), { chapterId: track.chapterId, seconds: readClock().time })) return;
    asked.current = key;
    const chapter = queue.find((item) => item.id === last.chapterId);
    if (!chapter || !canPlay(chapter)) return;
    toast("Thiết bị khác đã nghe tới chỗ khác", {
      id: "further-elsewhere",
      duration: 20_000,
      description: `${chapter.title} · ${formatClock(last.seconds)} (${formatWhen(last.at)})`,
      action: { label: "Nghe tiếp từ đó", onClick: () => jumpTo(last.chapterId, last.seconds) },
      cancel: { label: "Ở lại đây", onClick: () => undefined },
    });
  }, [active, jumpTo, last, playing, positionStamp, purpose, queue, readClock, track]);
  return null;
}

/** Máy khác (điện thoại) đổi hồ sơ nghe của cuốn đang nạp ở đây: đang dừng thì theo sang - nạp lại đúng chỗ của hồ sơ
 *  mới. Đang phát thì phát tiếp hồ sơ cũ (mọi lần lưu vẫn vào hồ sơ ấy), dừng rồi mới theo. */
function FollowRecord() {
  const source = useSource();
  const { track, playing, purpose, switchRecord } = usePlayer();
  const { data: book } = useListenBook(track?.bookId);
  const active = book?.records?.find((record) => record.active)?.id;
  const following = useRef("");
  useEffect(() => {
    if (!track?.recordId || !active || track.recordId === active || playing || purpose !== "listen") return;
    const key = `${track.bookId}:${track.recordId}>${active}`;
    if (following.current === key) return;
    following.current = key;
    const { bookId, recordId: held } = track;
    // hỏi lại máy chủ: bộ nhớ đệm có thể còn là lúc trước khi chính máy này vừa đổi hồ sơ
    void source
      .book(bookId)
      .then((fresh) => {
        const chosen = fresh.records?.find((record) => record.active);
        if (!chosen || chosen.id === held) return;
        return switchRecord(bookId, async () => undefined).then(() =>
          toast(`Đang dùng hồ sơ nghe “${chosen.name}”`, { description: "Vừa chọn trên thiết bị khác." }),
        );
      })
      .catch(() => undefined);
  }, [active, playing, purpose, source, switchRecord, track]);
  return null;
}

// ---- Menu "…" của trình phát -----------------------------------------------------------------------------

const MENU_ROW = "flex min-h-10 w-full items-center gap-3 rounded-lg px-2 text-left text-sm text-fg hover:bg-hover disabled:opacity-40 disabled:hover:bg-transparent max-sm:min-h-[48px]";

/** Một việc trong menu "…": chọn là làm và đóng menu. */
function MenuRow({ icon: Icon, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: typeof Gauge }) {
  return (
    <Popover.Close asChild>
      <button type="button" className={MENU_ROW} {...keepFocus} {...rest}>
        <Icon className="size-4 shrink-0 text-fg-2" />
        <span className="min-w-0 flex-1 truncate">{children}</span>
      </button>
    </Popover.Close>
  );
}

/** "…" của trình phát: mọi việc ít dùng (nhạc nền, giọng, âm lượng, gợi ý, phát trên máy khác...) nằm trong một bảng, hàng chính chỉ giữ việc
 *  hay dùng (docs/DESIGN.md mục 4.3). Menu Giọng đọc nằm trong bảng này: "Chọn giọng khác" ở lời báo lỗi giọng mở bảng trước, menu giọng mở ngay
 *  khi dựng (voiceMenuWaiting). */
function MoreMenu({ scope, children }: { scope: VoiceMenuScope; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const openRef = useRef(open);
  openRef.current = open;
  useEffect(() => {
    if (voiceMenuWaiting === scope) setOpen(true);
    const onOpen = (event: Event) => {
      // Bảng đang mở thì menu giọng trong đó tự nghe sự kiện này.
      if ((event as CustomEvent<VoiceMenuScope>).detail !== scope || openRef.current) return;
      voiceMenuWaiting = scope;
      setOpen(true);
    };
    window.addEventListener(OPEN_VOICE_MENU_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_VOICE_MENU_EVENT, onOpen);
  }, [scope]);
  return (
    <MenuShell
      label="Thêm tuỳ chọn"
      trigger={<MoreHorizontal className="glyph" />}
      width="w-72 max-w-[calc(100vw-1.5rem)]"
      // Mở ra: tiêu điểm vào chính bảng, không vào nút đầu tiên - nút đầu bật chú thích và trông như "đang chọn".
      focusSelector="[data-player-more]"
      open={open}
      onOpenChange={(value) => {
        if (!value && voiceMenuWaiting === scope) voiceMenuWaiting = null;
        setOpen(value);
      }}
    >
      <div data-player-more tabIndex={-1} className="flex flex-col gap-0.5 outline-none">{children}</div>
    </MenuShell>
  );
}

/** Một dòng có tên cho nút riêng của nền / tính năng (gợi ý đọc, phát trên thiết bị khác): nút đứng bên phải; nút không có thì cả dòng không chiếm chỗ. */
function MenuSlot({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-h-10 items-center gap-3 rounded-lg pl-2 text-sm text-fg max-sm:min-h-[48px] [&:not(:has(button))]:hidden">
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {children}
    </div>
  );
}

// ---- Thanh phát nhỏ ------------------------------------------------------------------------------------

/** `extra`: nút riêng của từng nền, đặt trước nhóm nút phải (máy tính: "Phát trên điện thoại"). */
export function PlayerBar({
  compact = false,
  notices = false,
  extra,
}: {
  compact?: boolean;
  /** Thanh gọn trên máy tính (cửa sổ hẹp): vẫn cần các báo "đang nghe xa hơn ở máy khác" và hồ sơ - app Android có đường riêng. */
  notices?: boolean;
  extra?: ReactNode;
}) {
  const { track, close, playing, buffering, toggle, next, previous } = usePlayer();
  const { expanded, setExpanded } = useNowPlaying();
  const speaking = useSpeaking();
  const addBookmark = useAddBookmark();
  useContinueIntoNextPart();
  useWarmVoice(track?.bookId); // trình phát mở lại với cuốn đang dở: nạp sẵn model giọng trên máy
  const content = () => {
  if (!track) return null;
  if (compact) {
    return (
      <section aria-label="Trình phát" className="relative z-20 shrink-0 border-t border-line bg-panel">
        <CompactProgress />
        {notices && (
          <>
            <BookmarkShortcut />
            <FurtherElsewhere />
            <FollowRecord />
          </>
        )}
        <FadingNotice className="mx-3 mt-2" />
        <PlayerAlert className="mx-3 mt-2" compact />
        <div className="flex h-16 items-center gap-3 px-3">
          {/* title: tên chương / sách bị cắt "Chương 3 · Đ…" khi phóng chữ hay cửa sổ hẹp - rê chuột đọc được đủ (soát a31 Z1). */}
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="touch-row flex min-w-0 flex-1 items-center gap-3 text-left"
            aria-label="Mở màn hình đang nghe"
            title={`${track.chapterTitle} · ${track.bookTitle}`}
          >
            <BookCover title={track.bookTitle} image={track.bookCover} size="sm" label={false} className={cn("size-11", !expanded && "cover-morph")} />
            <div className="min-w-0">
              <MotionRegion motionKey={[track.bookId, track.chapterId, track.chapterTitle]} className="truncate text-sm font-semibold">{track.chapterTitle}</MotionRegion>
              <div className="truncate text-xs text-fg-2">
                <TrackSubtitle />
              </div>
            </div>
          </button>
          <button
            type="button"
            onClick={withFeedback("playPause", toggle)}
            aria-label={toggleLabel(playing, buffering, speaking)}
            aria-busy={(playing && buffering) || undefined}
            className="touch-hit press grid size-11 shrink-0 place-items-center rounded-full bg-fg text-bg transition-transform"
          >
            <MotionRegion as="span" className="inline-grid size-5 place-items-center">{playing && buffering ? (
              <Loader2 className="size-5 animate-spin" />
            ) : playing ? (
              <Pause className="size-5" fill="currentColor" strokeWidth={0} />
            ) : (
              <Play className="size-5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
            )}</MotionRegion>
          </button>
        </div>
      </section>
    );
  }
  return (
    <section aria-label="Trình phát" className="@container relative z-20 shrink-0 border-t border-line bg-panel">
      <BookmarkShortcut />
      <FurtherElsewhere />
      <FollowRecord />
      <FadingNotice className="mx-4 mt-2" />
      <PlayerAlert className="mx-4 mt-2" />
      {/* Cột giữa theo bề rộng CỦA THANH (min(36%, 480px)), không theo cửa sổ (40vw): thanh không gồm thanh bên, 40vw từng
          chiếm 512/1044 px ở cửa sổ 1280 - tên chương bị cắt, cụm nút phải (266 px) bị ép vào 238 px (soát UX 29-09). Cột tên sách có tối thiểu 10rem (soát UX a16: còn ~30 px khi đủ chip nhạc / giọng / hẹn giờ); cột giữa co trước, rồi nhãn chữ của chip ẩn theo bề rộng thanh.
          Thanh hẹp (cửa sổ 1024): cột giữa đứng ở mức tối thiểu 14rem, phần còn lại cho tên chương; cụm nút không bao giờ xuống dòng -
          thiếu chỗ thì tên co trước các nút (soát a26 L11: "Chương…" cạnh thanh tua 260 px, chip "Hết chương" rớt dòng).
          Mốc bề rộng tính bằng rem, không px: người đặt cỡ chữ trình duyệt 150 % / 200 % thì thanh đổi bố cục sớm hơn theo chữ. Thanh dưới 48rem (cỡ chữ to,
          hay cửa sổ hẹp): hai hàng - tên + cụm nút (cụm nút được xuống dòng) ở trên, nút phát + thanh tua cả hàng dưới - không nút nào chồng nút nào (soát a67:
          150 % chồng 9 cặp, 200 % chồng 12 cặp). Cao theo nội dung, tối thiểu 76 px như cũ. */}
      <div className="grid min-h-[4.75rem] grid-cols-[minmax(10rem,1fr)_minmax(14rem,min(36%,480px))_auto] items-center gap-4 px-4 @max-[56.25rem]:grid-cols-[minmax(8rem,1fr)_14rem_auto] @max-[48rem]:grid-cols-[minmax(min(12rem,45%),1fr)_auto] @max-[48rem]:gap-y-1 @max-[48rem]:py-2">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="flex min-w-0 items-center gap-3 rounded-lg p-1 text-left hover:bg-hover"
          aria-label="Mở màn hình đang nghe"
          title={`${track.chapterTitle} · ${track.bookTitle}`}
        >
          <BookCover title={track.bookTitle} image={track.bookCover} size="sm" label={false} className={cn("size-12", !expanded && "cover-morph")} />
          <div className="min-w-0">
            <MotionRegion motionKey={[track.bookId, track.chapterId, track.chapterTitle]} className="truncate text-sm font-semibold">{track.chapterTitle}</MotionRegion>
            <div className="truncate text-xs text-fg-2">
              <TrackSubtitle />
            </div>
          </div>
        </button>
        <div className="flex w-full flex-col items-center gap-0.5 @max-[48rem]:col-span-2 @max-[48rem]:row-start-2">
          <Transport chapters={false} />
          <SeekBar />
        </div>
        {/* Tối đa 6 điều khiển (docs/DESIGN.md mục 6): lùi · phát · tới ở giữa; tốc độ · âm lượng · "…" bên phải - còn lại vào "…". */}
        <div className="flex min-w-0 items-center justify-end gap-0.5 whitespace-nowrap @max-[48rem]:col-start-2 @max-[48rem]:row-start-1">
          <SpeedMenu />
          <VolumeControl />
          <MoreMenu scope="bar">
            <SleepMenu look="row" />
            <MenuRow icon={BookmarkPlus} aria-keyshortcuts={SHORTCUTS ? "B" : undefined} onClick={() => void addBookmark()}>Thêm dấu trang</MenuRow>
            <MenuRow icon={SkipBack} aria-keyshortcuts={SHORTCUTS ? "Shift+ArrowLeft" : undefined} onClick={previous}>Chương trước</MenuRow>
            <MenuRow icon={SkipForward} aria-keyshortcuts={SHORTCUTS ? "Shift+ArrowRight" : undefined} onClick={next}>Chương sau</MenuRow>
            <MusicMenu look="row" />
            <VoiceMenu look="row" />
            <MenuRow icon={Maximize2} onClick={() => setExpanded(true)}>Mở màn hình đang nghe</MenuRow>
            <MenuRow icon={X} onClick={close}>Đóng trình phát</MenuRow>
            <MenuSlot label="Phát trên thiết bị khác">{extra}</MenuSlot>
          </MoreMenu>
        </div>
      </div>
    </section>
  );
  };
  return <MotionPresence open={Boolean(track)} className="shrink-0">{content()}</MotionPresence>;
}

// ---- Bảng bên của màn hình đang nghe ---------------------------------------------------------------------

/** Tab "Đọc theo" của trình phát: cùng văn bản với màn đọc (ReadAlongText) - câu và chữ đang đọc sáng lên, bấm một chữ là nghe từ chữ ấy, tự cuộn
 *  theo giọng; thêm nhãn người nói và câu đã nghe nhạt đi. Cùng thanh việc với màn đọc (SentenceMenu): bấm câu thì câu được chọn, giữ / bấm chuột
 *  phải một chữ thì sửa chữ ấy - sửa câu đang phát không phải rời màn này (soát a70). */
function ReadAlong({ edit }: { edit?: SentenceEditing }) {
  const { track, playing, queue } = usePlayer();
  const source = useSource();
  const client = useQueryClient();
  const current = queue.find((chapter) => chapter.id === track?.chapterId);
  const { data: book } = useListenBook(track?.bookId);
  const { data: script, isLoading } = useChapterScript(track?.bookId, current);
  const container = useRef<HTMLDivElement | null>(null);
  const active = usePlayingSentence(script, true);
  const follow = useFollowVoice(container, active, { resetKey: `${track?.bookId}:${track?.chapterId}`, smooth: playing });
  const { canListen, listenFrom } = useListenFrom(track?.bookId ?? "", book, current, script);
  const listen = (index: number, word = -1) => {
    if (listenFrom(index, word)) follow.follow();
  };
  const menu = useSentenceMenu({ ...edit, bookId: track?.bookId ?? "", book, chapter: current, script, canListen, onListen: (index) => {
    listen(index);
    menu.select(null);
  } });
  const nearEnd = useClock((time, duration) => duration > 0 && duration - time < 30);

  // Sắp hết chương: nạp sẵn văn bản chương kế để sang chương không bị chớp "đang mở".
  useEffect(() => {
    if (!nearEnd || !track) return;
    const index = queue.findIndex((chapter) => chapter.id === track.chapterId);
    const upcoming = queue.slice(index + 1).find(canPlay);
    if (upcoming) void client.prefetchQuery(chapterScriptQuery(source, track.bookId, upcoming));
  }, [client, nearEnd, queue, source, track]);

  if (isLoading) return <MotionRegion as="div" className="animate-[fade-in_0.2s_0.3s_both] p-10 text-fg-2">Đang mở văn bản chương…</MotionRegion>;
  if (!script) return <MotionRegion />;
  return (
    <MotionRegion as="div" className="relative h-full">
      <div ref={container} onScroll={follow.onScroll} {...follow.input} className="reading-surface h-full overflow-y-auto px-6 py-8 sm:px-10">
        <div className="mx-auto max-w-[68ch] text-[1.25rem] leading-[1.7]">
          {/* Chương giọng máy đọc chưa có mốc chỉ trong lúc chờ đoạn đầu - không phải "chưa có audio". */}
          {!script.timed && current?.state !== "text" && (
            <p className="mb-5 rounded-lg bg-hover px-4 py-3 text-sm text-fg-2">Chương này chưa có audio hoàn chỉnh - đang hiện văn bản, chưa đọc theo được.</p>
          )}
          <ReadAlongText
            script={script}
            playingIndex={active}
            onTap={(index, word) => {
              if (canListen) listen(index, word);
              // Sửa được thì câu vừa bấm còn được chọn (thanh việc), như ở màn đọc; không nghe được thì bấm là chọn / bỏ chọn.
              if (canListen ? menu.editable : true) menu.select(!canListen && menu.selected === index ? null : index, word);
            }}
            onWordMenu={menu.wordMenu}
            focusIndex={Math.max(0, active)}
            selected={menu.selected}
            after={menu.waitingMark}
            speakers
            dimHeard
            headingClassName="pb-2 text-2xl font-bold leading-snug tracking-tight"
            className="space-y-5"
          />
        </div>
      </div>
      {/* Thanh việc của câu / nút "Tới câu đang nghe" hiện / ẩn dần (MotionPresence). Vùng con có khoá cố định: chúng không làm vùng của cả bài
          thấy "nội dung đổi" mà mờ chéo cả văn bản mỗi lần chọn câu hay cuộn khỏi câu đang nghe (W2). */}
      <MotionRegion motionKey="floating" className="pointer-events-none absolute inset-x-0 bottom-5 flex flex-col items-center">
        <MotionPresence open={Boolean(menu.bar)} className="w-full px-3">{menu.bar}</MotionPresence>
        <MotionPresence open={!menu.bar && follow.showJump}><JumpToPlaying onClick={follow.jump} /></MotionPresence>
      </MotionRegion>
      {menu.dialogs}
    </MotionRegion>
  );
}

export function chapterStatusLabel(producing: boolean): string {
  return producing ? "Đang thu âm…" : "Chưa có audio";
}

export function ChapterPanel() {
  const { track, queue, jumpTo, playing } = usePlayer();
  const { data: book } = useListenBook(track?.bookId);
  const voice = useBookVoice(track?.bookId);
  const container = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const scroller = container.current;
    const current = scroller?.querySelector<HTMLElement>("[data-current=true]");
    if (scroller && current) reveal(scroller, current);
  }, []);
  // Chương mới thu xong / gỡ khỏi hàng nghe: hàng mở ra hay khép lại tại chỗ (useListPresence), không nhảy cả danh sách.
  const rows = useListPresence(queue, (chapter) => String(chapter.id));
  return (
    <div ref={container} className="h-full overflow-y-auto px-3 py-4 sm:px-6">
      <Windowed items={rows} estimate={60} keep={rows.findIndex((row) => row.item.id === track?.chapterId)} row={({ key, item: chapter, state, ref }) => {
        const current = chapter.id === track?.chapterId;
        const done = book?.state.chapters[String(chapter.id)]?.done;
        return (
          <div key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}>
          <button
            type="button"
            data-current={current}
            disabled={!canPlay(chapter)}
            aria-current={current ? "true" : undefined}
            onClick={() => jumpTo(chapter.id)}
            // Hàng đang phát: chữ màu nhấn, không tô nền cả hàng (docs/DESIGN.md mục 6).
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors duration-motion-fast",
              canPlay(chapter) && "hover:bg-hover",
            )}
          >
            <MotionRegion as="span" className="inline-grid h-4 w-5 shrink-0 place-items-center">
              {current && playing ? (
                <Vu className="h-3 text-accent" />
              ) : done ? (
                <Check className="size-4 text-success" aria-label="Đã nghe" />
              ) : <span aria-hidden />}
            </MotionRegion>
            <span className="min-w-0 flex-1">
              <span className={cn("block truncate text-sm font-medium transition-colors duration-motion-fast", current && "text-accent-text", !canPlay(chapter) && "text-fg-2")}>
                {chapter.subtitle || chapter.title}
              </span>
              {/* Dòng phụ đổi khi chương thu xong ("Đang thu âm…" -> độ dài) hay đổi giọng: mờ chéo, không thay chữ cứng. */}
              <MotionRegion as="span" className="tabular block truncate text-xs text-fg-2">
                {chapter.subtitle ? `${chapter.title} · ` : ""}
                {chapter.available
                  ? formatLength(chapter.duration)
                  : chapter.state === "text"
                    ? textChapterLine(Boolean(chapter.speech), voice)
                    : chapterStatusLabel(Boolean(book?.producing))}
              </MotionRegion>
            </span>
          </button>
          </div>
        );
      }} />
    </div>
  );
}

// ---- Dấu trang (dùng chung cho màn Đang nghe và trang sách) ------------------------------------------------

function BookmarkRow({
  bookId,
  mark,
  chapter,
  quote,
  editing,
  onEdit,
  onJump,
}: {
  bookId: string;
  mark: Bookmark;
  chapter: ListenChapter | undefined;
  quote: string | null;
  editing: boolean;
  onEdit: (editing: boolean) => void;
  onJump: (mark: Bookmark) => void;
}) {
  const mutations = useListenMutations(bookId);
  const [note, setNote] = useState(mark.note);
  useEffect(() => setNote(mark.note), [mark.note]);
  const editBox = useRef<HTMLFormElement>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const cancelEdit = () => { setNote(mark.note); onEdit(false); };
  useBackLayer(editing, cancelEdit, editBox, editButton);
  useEffect(() => { if (!editing) setNote(mark.note); }, [editing, mark.note]);
  const remove = () => {
    mutations.deleteBookmark.mutate(mark.id, {
      onSuccess: () =>
        toast("Đã xoá dấu trang", {
          id: `bookmark-${mark.id}`,
          duration: 8000,
          action: { label: "Hoàn tác", onClick: () => mutations.restoreBookmark.mutate(mark) },
        }),
    });
  };
  return (
    <MotionRegion as="div" className="group rounded-lg px-3 py-2.5 hover:bg-hover">
      <div className="flex items-start gap-2">
        <button type="button" onClick={() => onJump(mark)} className="min-w-0 flex-1 text-left">
          <span className="block truncate text-sm font-medium">{chapter ? chapter.subtitle || chapter.title : "Chương đã bị gỡ"}</span>
          <span className="tabular block text-xs text-fg-2">
            {chapter?.subtitle ? `${chapter.title} · ` : ""}
            {/* Chương chưa có audio (sách chỉ có chữ): giờ phút vô nghĩa với người đọc - chỉ có câu chữ. */}
            {chapter?.available === false && mark.index !== undefined ? "" : `${formatClock(mark.seconds)} · `}
            {formatWhen(mark.createdAt ?? mark.at)}
          </span>
          {quote && <span className="mt-1 line-clamp-2 block text-sm italic leading-snug text-fg">“{unquoted(quote)}”</span>}
        </button>
        {/* Biểu tượng thùng rác thẳng mép phải như "…" của hàng chương (soát 24-10): điện thoại dồn biểu tượng về mép phải nền chạm 48 px
            (bút theo cùng để khoảng hai biểu tượng giữ nguyên), máy tính bù nửa phần nền thừa của nút 28 px. */}
        <IconButton ref={editButton} label="Sửa ghi chú" icon={Pencil} size="sm" className="max-sm:!justify-end" onClick={() => editing ? cancelEdit() : onEdit(true)} />
        <IconButton label="Xoá dấu trang" icon={Trash2} size="sm" className="max-sm:!justify-end sm:-mr-[5px]" onClick={remove} />
      </div>
      {editing ? (
        <form
          ref={editBox}
          className="mt-2 space-y-1"
          onSubmit={(event) => {
            event.preventDefault();
            mutations.updateBookmark.mutate({ id: mark.id, note });
            onEdit(false);
          }}
        >
          <div className="flex gap-2">
            <input
              autoFocus
              value={note}
              maxLength={500}
              onChange={(event) => setNote(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.preventDefault();
                  event.stopPropagation();
                  cancelEdit();
                }
              }}
              placeholder="Ghi chú cho dấu trang này"
              aria-label="Ghi chú"
              className="h-9 min-w-0 flex-1 rounded-md border border-line bg-bg px-2 text-sm outline-none focus:border-focus"
            />
            <button type="submit" className="rounded-md bg-accent px-3 text-sm font-medium text-accent-ink">
              Lưu
            </button>
            <button type="button" className="rounded-md px-3 text-sm text-fg-2 hover:bg-hover" onClick={cancelEdit}>Huỷ</button>
          </div>
          <div className="tabular text-right text-[0.6875rem] text-fg-2">{note.length}/500</div>
        </form>
      ) : mark.note ? (
        <p className="mt-1.5 whitespace-pre-wrap rounded-md bg-sunken px-2.5 py-1.5 text-sm text-fg-2">{mark.note}</p>
      ) : null}
    </MotionRegion>
  );
}

/** Danh sách dấu trang - mới nhất lên đầu, mỗi dấu kèm câu văn ở chỗ đó để nhận ra mà không cần nhớ giây. */
const bookmarkKey = (mark: Bookmark) => mark.id;

export function BookmarkList({
  bookId,
  chapters,
  marks,
  onJump,
  editingId,
  setEditingId,
  empty,
}: {
  bookId: string;
  chapters: ListenChapter[];
  marks: Bookmark[];
  onJump: (mark: Bookmark) => void;
  editingId?: string | null;
  setEditingId?: (id: string | null) => void;
  empty?: ReactNode;
}) {
  const source = useSource();
  const [localEditing, setLocalEditing] = useState<string | null>(null);
  const editing = editingId !== undefined ? editingId : localEditing;
  const setEditing = setEditingId ?? setLocalEditing;
  const sorted = useMemo(() => [...marks].sort((a, b) => (b.createdAt ?? b.at) - (a.createdAt ?? a.at)), [marks]);
  const chapterIds = useMemo(() => [...new Set(sorted.map((mark) => mark.chapterId))], [sorted]);
  const scripts = useQueries({
    queries: chapterIds.map((chapterId) => ({
      queryKey: ["listen", "script", bookId, chapterId],
      queryFn: () => source.script(bookId, chapterId),
      staleTime: Infinity,
      enabled: chapters.some((chapter) => chapter.id === chapterId && chapter.available),
    })),
  });
  const scriptOf = (chapterId: number) => scripts[chapterIds.indexOf(chapterId)]?.data as Script | undefined;
  // Thêm / xoá dấu trang: hàng mở ra hay khép lại tại chỗ (shared/motion.ts useListPresence), không nhảy cả danh sách.
  const rows = useListPresence(sorted, bookmarkKey);
  return (
    <><MotionPresence open={!rows.length && Boolean(empty)}>{empty}</MotionPresence><ul className="space-y-1">
      {rows.map(({ key, item: mark, state, ref }) => (
        <li key={key} ref={ref} className="motion-row" data-state={state} inert={state === "exit"}>
          <BookmarkRow
            bookId={bookId}
            mark={mark}
            chapter={chapters.find((chapter) => chapter.id === mark.chapterId)}
            quote={mark.quote || sentenceAt(scriptOf(mark.chapterId), mark.seconds)}
            editing={state !== "exit" && editing === mark.id}
            onEdit={(value) => setEditing(value ? mark.id : null)}
            onJump={onJump}
          />
        </li>
      ))}
    </ul></>
  );
}

function BookmarkPanel({ editingId, setEditingId }: { editingId: string | null; setEditingId: (id: string | null) => void }) {
  const { track, queue, jumpTo } = usePlayer();
  const { setExpanded } = useNowPlaying();
  const navigate = useNavigate();
  const { data: book } = useListenBook(track?.bookId);
  const marks = book?.state.bookmarks ?? [];
  if (!track) return <MotionRegion />;
  const empty = !marks.length ? (
      <div className="flex h-full flex-col items-center justify-center px-8 text-center">
        <BookmarkIcon className="size-8 text-fg-3" />
        <p className="mt-3 font-medium">Chưa có dấu trang</p>
        <p className="mt-1 text-sm text-fg-2">Bấm biểu tượng dấu trang (hoặc phím B) khi nghe tới đoạn muốn quay lại.</p>
      </div>
  ) : null;
  return (
    <MotionRegion as="div" className="h-full overflow-y-auto px-3 py-4 sm:px-6">
      <BookmarkList
        empty={empty}
        bookId={track.bookId}
        chapters={queue}
        marks={marks}
        onJump={(mark) => {
          const path = bookmarkReadPath(track.bookId, mark);
          if (path) {
            setExpanded(false);
            navigate(path);
          } else jumpTo(mark.chapterId, mark.seconds, mark.note.trim() ? `Đã tới dấu trang “${excerpt(mark.note)}”` : undefined);
        }}
        editingId={editingId}
        setEditingId={setEditingId}
      />
    </MotionRegion>
  );
}

type Panel = "text" | "chapters" | "bookmarks";
const PANELS: { value: Panel; label: string; icon: typeof Text }[] = [
  { value: "text", label: "Đọc theo", icon: Text },
  { value: "chapters", label: "Chương", icon: ListOrdered },
  { value: "bookmarks", label: "Dấu trang", icon: BookmarkIcon },
];
const PANEL_KEY = "abook-now-playing-panel";

function initialPanel(): Panel {
  try {
    const stored = localStorage.getItem(PANEL_KEY);
    if (stored === "text" || stored === "chapters" || stored === "bookmarks") return stored;
  } catch {
    /* không có bộ nhớ trình duyệt */
  }
  return "text";
}

/** Tiến độ cả cuốn (phần đã có audio): "Đã nghe 42% cả cuốn · còn khoảng 2 giờ 32 phút ở tốc độ 1,5×". */
function BookProgressLine({ className }: { className?: string }) {
  const { queue, track, rate, atEnd } = usePlayer();
  const tens = useClock((time) => Math.floor(time / 10));
  const { before, total } = useMemo(() => {
    let heardBefore = 0;
    let sum = 0;
    let reached = false;
    for (const chapter of queue) {
      if (!chapter.available) continue;
      if (chapter.id === track?.chapterId) reached = true;
      else if (!reached) heardBefore += chapter.duration;
      sum += chapter.duration;
    }
    return { before: heardBefore, total: sum };
  }, [queue, track?.chapterId]);
  const shown = Boolean(track) && total > 0;
  const heard = Math.min(total, before + tens * 10);
  // Sách chưa thu xong: "Cả cuốn 99%" đọc như sắp hết truyện (soát UX 29-09) - đó là phần đã có.
  const whole = queue.every((chapter) => chapter.available);
  const finished = atEnd === "finished";
  const text = shown ? bookProgressText({ whole, heard, total, rate, speed: speedLabel(rate), finished }) : "";
  // Số chạy theo đồng hồ không chuyển cảnh; hiện / ẩn dòng, đổi lời (cả cuốn / phần đã có / đã nghe hết, phút -> giờ) và đổi tốc độ thì mờ chéo.
  return (
    <MotionRegion as="p" motionKey={[rate, text.replace(/\d[\d\s.,:%–/\-]*/g, "#")]} className={cn("tabular text-xs text-fg-2", className)}>
      {text}
    </MotionRegion>
  );
}

/** "Tập 17", "Phần 2" - hay cả tên khi cuốn kế không đánh số. */
function nextLabel(title: string): string {
  const { volume, unit } = seriesOf(title);
  return volume === null ? title : `${unit.charAt(0).toUpperCase()}${unit.slice(1)} ${volume}`;
}

/** Các phần của CÙNG một cuốn ("Làm tiếp cuốn này": "Tên", "Tên · Phần 2"...) nối liền như một cuốn - hết phần này tự nghe
 *  phần sau, từ chỗ nghe tiếp của nó. Tập khác của một bộ ("Tập 17") thì chỉ mời (CaughtUpNotice): sang tập mới là việc người
 *  nghe chọn. Hẹn giờ "hết chương" dừng trước khi tới đây (atEnd không thành "finished"). Gọi ở PlayerBar - có mặt ở mọi
 *  màn của máy tính lẫn điện thoại. */
function useContinueIntoNextPart() {
  const { atEnd, track, rate, setContinues } = usePlayer();
  const next = useNextVolume(track?.bookId, track?.bookTitle);
  const playBook = usePlayListenBook();
  const continued = useRef("");
  // Báo trước cho trình phát: hết cuốn này không phải hết sách - nó khỏi nói "Đã nghe hết sách / Nghe lại từ đầu" (soát a26 L1).
  const continues = continuingPart(next) && track ? track.bookId : null;
  useEffect(() => setContinues(continues), [continues, setContinues]);
  useEffect(() => {
    const part = partToContinue(atEnd, next);
    if (!part || !track) return;
    if (continued.current === track.bookId) return;
    continued.current = track.bookId;
    // Phần sau chưa đặt tốc độ riêng thì nghe tiếp đúng tốc độ phần trước (soát a26 L3).
    toast(`Nghe tiếp ${nextLabel(part.title)}`, { description: "Hết phần trước - phần sau nối liền như một cuốn." });
    void playBook(part, undefined, undefined, { rate });
  }, [atEnd, track, next, playBook, rate]);
}

/** Cuối màn "Đã nghe hết sách": mời nghe cuốn khác (tối đa 3, mỗi cuốn một nút nghe tiếp từ chỗ đã dừng) và đường về thư viện.
 *  `skipId`: tập kế đã có nút "Nghe tiếp" riêng ngay trên - không mời lần nữa. */
function AfterTheEnd({ skipId }: { skipId?: string }) {
  const { track } = usePlayer();
  const { data: books } = useListenLibrary(false);
  const speaks = (useReadAloudVoices().data?.length ?? 0) > 0;
  const playBook = usePlayListenBook();
  const navigate = useNavigate();
  const { setExpanded } = useNowPlaying();
  const others = useMemo(
    () => otherBooksToHear((books ?? []).filter((book) => book.id !== skipId), track?.bookId, speaks),
    [books, track?.bookId, speaks, skipId],
  );
  return (
    <div className="mt-3 border-t border-accent/20 pt-2.5 text-left">
      {others.length > 0 && (
        <>
          <div className="px-1 pb-1 text-xs font-medium text-fg-2">Nghe cuốn khác</div>
          <ul className="space-y-1">
            {others.map((book) => (
              <li key={book.id}>
                <button
                  type="button"
                  onClick={() => void playBook(book)}
                  aria-label={`Nghe ${book.title}`}
                  className="flex min-h-[48px] w-full items-center gap-3 rounded-lg px-1 py-1 text-left hover:bg-hover"
                >
                  <BookCover title={book.title} part={book.series?.part} size="xs" image={book.cover} className="size-10" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-fg">{book.title}</span>
                    <span className="tabular block truncate text-xs text-fg-2">{otherBookLine(book)}</span>
                  </span>
                  <Play className="size-4 shrink-0 text-accent-text" fill="currentColor" strokeWidth={0} />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <button
        type="button"
        onClick={() => {
          setExpanded(false);
          navigate("/");
        }}
        className="mt-1 min-h-[48px] w-full text-center font-semibold text-accent-text underline underline-offset-2"
      >
        Về thư viện
      </button>
    </div>
  );
}

function CaughtUpNotice() {
  const { atEnd, track, restart } = usePlayer();
  const next = useNextVolume(track?.bookId, track?.bookTitle);
  const playBook = usePlayListenBook();
  const content = () => {
  if (atEnd === "finished" && next) {
    return (
      <div className="motion-appear mt-3 rounded-xl bg-accent-soft px-3 py-2.5 text-center text-sm">
        <div className="text-fg">Đã nghe hết cuốn này.</div>
        <button type="button" onClick={() => void playBook(next)} className="mt-1.5 font-semibold text-accent-text underline underline-offset-2">
          Nghe tiếp {nextLabel(next.title)}
        </button>
        <AfterTheEnd skipId={next.id} />
      </div>
    );
  }
  if (atEnd === "finished") {
    return (
      <div className="motion-appear mt-3 rounded-xl bg-accent-soft px-3 py-2.5 text-center text-sm">
        <div className="text-fg">Đã nghe hết sách.</div>
        <button type="button" onClick={restart} className="mt-1.5 min-h-[48px] font-semibold text-accent-text underline underline-offset-2">
          Nghe lại từ đầu
        </button>
        <AfterTheEnd />
      </div>
    );
  }
  if (atEnd !== "caughtUp") return null;
  return (
    <p className="mt-3 rounded-xl bg-hover px-3 py-2 text-center text-sm text-fg-2">
      Đã nghe hết phần đã có. {caughtUpDetail()}
    </p>
  );
  };
  return <MotionPresence open={atEnd === "finished" || atEnd === "caughtUp"}>{content()}</MotionPresence>;
}

// ---- Màn hình đang nghe ------------------------------------------------------------------------------------

/** `actions`: nút riêng của từng nền ở hàng nút dưới thanh tua (điện thoại: "Phát trên <máy tính>"). */
/** `edit`: sửa được gì ở tab "Đọc theo" (như màn đọc của cùng thiết bị - SentenceMenu.SentenceEditing). */
/** Bìa to của màn "Đang nghe" là nút phát / dừng. Component riêng: nhãn đổi theo mỗi lần phát / dừng không làm cả màn (một MotionRegion)
 *  thấy "nội dung đổi" và mờ chéo theo (W1). */
function CoverToggle({ title, image }: { title: string; image: ComponentProps<typeof BookCover>["image"] }) {
  const { playing, buffering, toggle } = usePlayer();
  const speaking = useSpeaking();
  return (
    <button
      type="button"
      onClick={withFeedback("playPause", toggle)}
      aria-label={`${toggleLabel(playing, buffering, speaking)} (chạm bìa)`}
      className="size-[min(480px,100cqw,100cqh)] shrink-0 rounded-xl transition-transform press"
    >
      <BookCover title={title} image={image} size="xl" className="cover-morph w-full rounded-xl shadow-float" />
    </button>
  );
}

export function NowPlaying({ mobile = false, actions, edit }: { mobile?: boolean; actions?: ReactNode; edit?: SentenceEditing }) {
  const { track, sleep, fading, canGoBack, goBack } = usePlayer();
  const { expanded, setExpanded } = useNowPlaying();
  const navigate = useNavigate();
  const [panel, setPanelState] = useState<Panel>(initialPanel);
  const [showPanel, setShowPanelNow] = useState(!mobile);
  // Bìa <-> bảng (Đọc theo / Chương / Dấu trang) và đổi bảng: mờ chéo qua một View Transition (a120), không thay chỗ tức thì.
  const setShowPanel = (value: boolean) => withViewTransition(() => setShowPanelNow(value));
  const [editingId, setEditingId] = useState<string | null>(null);
  const section = useRef<HTMLElement | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const open = expanded && Boolean(track);
  const presence = usePresence(open, MOTION.slowOut);
  // Nút Back của điện thoại (android/backLayers.ts): panel (Chương, Dấu trang…) đóng trước, rồi tới màn Đang nghe, rồi mới tới trang.
  useBackLayer(mobile && open, () => setExpanded(false));
  useBackLayer(mobile && open && showPanel, () => setShowPanel(false));

  const setPanel = (value: Panel) => {
    setPanelState(value);
    try {
      localStorage.setItem(PANEL_KEY, value);
    } catch {
      /* không lưu được thì thôi */
    }
  };

  // Tên cửa sổ / thẻ trình duyệt theo chương đang nghe ("Chương 3 · Tên sách · ABook"); đóng màn này thì trả lại tên của trang bên dưới.
  const titleChapter = track?.chapterTitle;
  const titleBook = track?.bookTitle;
  useEffect(() => {
    if (!open || !titleChapter) return;
    const before = document.title;
    document.title = [titleChapter, titleBook, APP_TITLE].filter(Boolean).join(" · ");
    return () => {
      document.title = before;
    };
  }, [open, titleChapter, titleBook]);

  // Mở: đưa focus vào nút Phát; đóng: trả focus về chỗ đã mở. Mở ra kèm một menu (nút "Chọn giọng khác" ở thanh gọn mở luôn menu Giọng đọc):
  // focus đã vào menu ấy thì để yên - kéo focus đi là menu tự đóng (soát a66: phải bấm lần hai).
  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement as HTMLElement | null;
    const timer = window.setTimeout(() => {
      if (document.activeElement?.closest("[data-radix-popper-content-wrapper]")) return;
      section.current?.querySelector<HTMLElement>("[data-player-toggle]")?.focus();
    }, 30);
    return () => {
      window.clearTimeout(timer);
      opener.current?.focus?.();
    };
  }, [open]);

  useEffect(() => {
    const onEdit = (event: Event) => {
      setPanel("bookmarks");
      setShowPanel(true);
      setEditingId(String((event as CustomEvent).detail));
    };
    window.addEventListener(EDIT_BOOKMARK_EVENT, onEdit);
    return () => window.removeEventListener(EDIT_BOOKMARK_EVENT, onEdit);
  }, []);

  // Esc đóng màn này ở MỌI chỗ đang có tiêu điểm (soát UX 29-09: bấm vào chỗ trống, tiêu điểm về trang, Esc không ăn - mà
  // Cài đặt ghi "Dùng được ở mọi màn hình"). Một lần Esc đóng một lớp: menu, popover hay hộp thoại đang mở thì chỉ đóng nó.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (document.querySelector("[role='dialog'], [role='menu'], [role='listbox']")) return;
      event.preventDefault();
      setExpanded(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, setExpanded]);

  // Tab theo mẫu WAI-ARIA: Tab vào đúng MỘT tab (tab đang chọn), ←/→ (Home/End) đổi sang tab bên cạnh; mỗi tab trỏ tới tabpanel của nó.
  const selectPanel = (value: Panel) => {
    if (value === panel && showPanel) return;
    withViewTransition(() => {
      setPanel(value);
      setShowPanelNow(true);
    });
  };
  const onTabKeys = (event: ReactKeyboardEvent<HTMLElement>) => {
    const index = PANELS.findIndex((item) => item.value === panel);
    const step = ({ ArrowRight: 1, ArrowLeft: -1 } as Record<string, number>)[event.key];
    const next = step ? (index + step + PANELS.length) % PANELS.length : event.key === "Home" ? 0 : event.key === "End" ? PANELS.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    selectPanel(PANELS[next].value);
    event.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus();
  };
  const panelTabs = (
    <div role="tablist" aria-label="Bảng" onKeyDown={onTabKeys} className="flex min-w-0 gap-1">
      {PANELS.map((item) => {
        const selected = panel === item.value && showPanel;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            id={`now-tab-${item.value}`}
            title={item.label}
            aria-selected={selected}
            aria-controls={selected ? `now-panel-${item.value}` : undefined}
            tabIndex={panel === item.value ? 0 : -1}
            onClick={() => {
              if (mobile && selected) setShowPanel(false);
              else selectPanel(item.value);
            }}
            className={cn(
              "touch-row inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 text-sm font-medium transition-colors",
              selected ? "bg-hover text-fg" : "text-fg-2 hover:text-fg",
            )}
          >
            <item.icon className="size-4" />
            {/* Cột phải hẹp (cửa sổ ~768 px: hai cột + thanh bên chỉ chừa ~210 px) thì chỉ còn biểu tượng, chữ giữ cho trình đọc màn hình. */}
            <span className="@max-[20rem]:sr-only">{item.label}</span>
          </button>
        );
      })}
    </div>
  );

  const panelBody = (
    <div role="tabpanel" id={`now-panel-${panel}`} aria-labelledby={`now-tab-${panel}`} key={panel} data-motion-content className="motion-reveal h-full">
      {panel === "text" ? <ReadAlong edit={edit} /> : panel === "chapters" ? <ChapterPanel /> : <BookmarkPanel editingId={editingId} setEditingId={setEditingId} />}
    </div>
  );

  // Điện thoại: "Đọc theo" mở màn đọc của chương đang nghe - cả màn cho chữ, thanh điều khiển tự mờ khi cuộn đọc (L7). Máy tính: bảng bên phải.
  const readAlong = () => {
    if (!track) return;
    if (!mobile) return selectPanel("text");
    setExpanded(false);
    navigate(`/book/${track.bookId}/read/${track.chapterId}`);
  };
  // Điện thoại: bảng Chương / Dấu trang thay chỗ bìa; bấm lại nút ấy (hay Back) là về bìa.
  const togglePanel = (value: Panel) => {
    if (mobile && showPanel && panel === value) setShowPanel(false);
    else selectPanel(value);
  };
  const shown = (value: Panel) => showPanel && panel === value;

  if ((!open && !presence.mounted) || !track) return <MotionRegion />;
  // Mỗi cuốn một không khí: màu chủ đạo của bìa (máy chủ tính sẵn, đã lọc), không có thì màu của bìa vẽ từ tên - pha 10 % / 16 % vào nền
  // (styles.css .now-playing-tint, docs/DESIGN.md 5.1); đổi cuốn thì nền mờ chéo sang màu mới.
  const tint = { "--cover-tint": coverColor(track.bookCover?.color) || coverStyle(track.bookTitle).from } as CSSProperties;
  return (
    <MotionRegion as="section"
      elementRef={section}
      data-state={presence.state}
      inert={!open}
      aria-hidden={!open || undefined}
      onAnimationEnd={presence.onAnimationEnd}
      className={cn("now-playing now-playing-vt now-playing-tint absolute inset-0 z-30 flex", mobile && "flex-col")}
      style={tint}
      // Mở ra thì đây là nội dung chính: <main> của trang nằm dưới đã khoá (inert) và ra khỏi cây trợ năng - phím "tới vùng chính" của
      // trình đọc màn hình phải tới đây (soát a31 A3). role thay vì thẻ <main>: tài liệu chỉ được có một thẻ <main>.
      role="main"
      aria-label="Đang nghe"
    >
      <aside
        className={cn(
          "flex shrink-0 flex-col",
          // Điện thoại xoay ngang chỉ cao ~360px: cả cột không vừa - cho cả cột cuộn dọc (soát UX a9). Màn dọc đủ chỗ nên không có gì để cuộn.
          // Cửa sổ vừa (~900px): cột trái co về 320px dưới lg (soát UX 29-09).
          mobile ? "min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-6 pt-2" : "w-[320px] border-r border-line px-6 pb-8 pt-5 lg:w-[400px] lg:px-8",
        )}
      >
        {/* Thanh đầu: thu nhỏ · ĐANG NGHE · "…" - không gì khác. */}
        <div className="slot-row [--slot:clamp(1.125rem,0.75rlh,1.96875rem)]">
          <IconButton label={withShortcut("Thu nhỏ", "Esc")} icon={ChevronDown} className="touch-box" onClick={() => setExpanded(false)} />
          <span className="text-xs font-semibold uppercase tracking-[0.06em] text-fg-2">Đang nghe</span>
          <div>
            <MoreMenu scope="screen">
              <BookProgressLine className="mb-1 border-b border-line px-2 pb-2 pt-1" />
              <MusicMenu look="row" />
              <VoiceMenu scope="screen" look="row" />
              <VolumeControl look="row" />
              <MenuRow icon={BookmarkIcon} onClick={() => selectPanel("bookmarks")}>Danh sách dấu trang</MenuRow>
              {canGoBack && <MenuRow icon={Undo2} onClick={goBack}>Quay lại chỗ vừa nghe</MenuRow>}
              {/* Máy có bàn phím: gợi ý phím tắt (cùng hộp với phím ?). Màn cảm ứng không có phím để gõ. */}
              {!COARSE && <MenuRow icon={Keyboard} aria-keyshortcuts="?" onClick={openShortcuts}>Phím tắt</MenuRow>}
              <MenuSlot label="Gợi ý cho phần đọc"><SuggestionsButton bookId={track.bookId} className="max-sm:size-[48px]" /></MenuSlot>
              <MenuSlot label="Phát trên thiết bị khác">{actions}</MenuSlot>
            </MoreMenu>
          </div>
        </div>
        {mobile && showPanel ? (
          <div key="panel" data-motion-content className="motion-reveal -mx-5 mt-2 flex min-h-56 flex-1 flex-col">
            <div className="flex shrink-0 items-center justify-between px-5 pb-1">
              <span className="text-xs font-semibold uppercase tracking-[0.06em] text-fg-2">{panel === "bookmarks" ? "Dấu trang" : "Chương"}</span>
              <IconButton label="Về bìa sách" icon={X} size="sm" onClick={() => setShowPanel(false)} />
            </div>
            <div className="min-h-0 flex-1 border-y border-line">{panelBody}</div>
          </div>
        ) : (
          // Bìa vuông, to nhất 480px (điện thoại: cả bề ngang) nhưng co theo chỗ còn lại của khung (cả chiều cao): cqw/cqh là cỡ của chính khung này (container-type:size) -
          // nút bìa không co theo chiều cao thì đè lên "ĐANG NGHE" khi cửa sổ thấp (soát UX 05-10).
          <div key="cover" data-motion-content className="motion-reveal mt-4 flex min-h-16 min-w-0 flex-1 items-center justify-center [container-type:size]">
            {/* Chạm bìa để phát/dừng (SABP): mục tiêu lớn nhất màn hình, dễ trúng khi đang nằm và mắt nhắm mắt mở. */}
            <CoverToggle title={track.bookTitle} image={track.bookCover} />
          </div>
        )}
        <div className="mt-6 w-full min-w-0">
          <h2 className="truncate text-xl font-bold leading-snug" title={track.chapterTitle}>
            <MotionRegion as="span" motionKey={[track.bookId, track.chapterId, track.chapterTitle]} className="block truncate">{track.chapterTitle}</MotionRegion>
          </h2>
          <p className="mt-0.5 truncate text-sm text-fg-2">
            <TrackSubtitle />
          </p>
          <MusicCreditLine />
        </div>
        <div className="mt-5 w-full">
          <SeekBar large />
        </div>
        {/* Một hàng 5 nút: chương trước · lùi 15 · phát · tới 15 · chương sau. */}
        <div className="mt-3 flex justify-center">
          <Transport large />
        </div>
        {/* Một hàng 4 nút phụ có nhãn; mọi việc khác ở "…" trên thanh đầu. */}
        <div role="group" aria-label="Điều khiển phụ" data-player-secondary className="slot-row mt-5 items-start [--slot:1.9rlh]">
          <SpeedMenu look="action" />
          <SleepMenu look="action" />
          <BookmarkButton />
          <ActionButton icon={ListOrdered} label="Chương" aria-pressed={shown("chapters")} active={shown("chapters")} {...keepFocus} onClick={() => togglePanel("chapters")} />
        </div>
        {/* Đang nhỏ dần thì "Sắp tắt…" đã nói thay - hai dòng cùng lúc ở chương rất ngắn đọc như mâu thuẫn. */}
        <MotionPresence open={sleep.kind === "chapter" && !fading}><p className="mt-2 text-center text-xs text-fg-2">Sẽ dừng khi hết chương này.</p></MotionPresence>
        <FadingNotice className="mt-3" />
        <PlayerAlert className="mt-3" overlay />
        <CaughtUpNotice />
        <button
          type="button"
          onClick={readAlong}
          aria-pressed={mobile ? undefined : shown("text")}
          {...keepFocus}
          className={cn(
            "mt-5 flex min-h-12 w-full shrink-0 items-center justify-center gap-2 rounded-lg bg-hover text-sm font-medium transition-[transform,color,background-color] duration-motion-fast hover:bg-line active:scale-[0.97]",
            !mobile && shown("text") ? "text-accent-text" : "text-fg",
          )}
        >
          <Text className="size-4" />
          Đọc theo
        </button>
      </aside>
      {!mobile && (
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="@container flex h-14 shrink-0 items-center overflow-hidden border-b border-line px-3 lg:px-6">{panelTabs}</div>
          <div className="min-h-0 flex-1">{panelBody}</div>
        </div>
      )}
    </MotionRegion>
  );
}
