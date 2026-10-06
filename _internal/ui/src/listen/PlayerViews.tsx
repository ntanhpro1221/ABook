import * as Popover from "@radix-ui/react-popover";
import { coverStyle } from "@/shared/cover";
import * as Slider from "@radix-ui/react-slider";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AudioLines,
  Bookmark as BookmarkIcon,
  BookmarkPlus,
  Check,
  ChevronDown,
  Gauge,
  ListOrdered,
  Loader2,
  Maximize2,
  Moon,
  Music2,
  Pause,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  RotateCw,
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
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { useMediaQuery } from "@/shared/media";
import { excerpt, formatClock, formatLength, formatWhen, licenseLabel, spokenClock } from "@/shared/format";
import { IconButton, Tooltip, Vu } from "@/shared/ui";
import { Switch } from "@/desktop/PhoneSync";
import { levelOptions } from "@/shared/musicLevels";
import { useClock, useClockReader, useDuration, usePlaybackSecond } from "./clock";
import { usePlayListenBook, useNextVolume } from "./LibraryScreen";
import { COARSE, EXTEND_GESTURE } from "./extendGesture";
import { useBookMusic } from "./EditBook";
import { canPlay, otherBooksToHear, seriesOf, type Bookmark, type ListenChapter, type Script } from "./model";
import { EDIT_BOOKMARK_EVENT, SKIP_SECONDS, SPEEDS, useNowPlaying, usePlayer } from "./player";
import { SLEEP_CHOICES, sleepExtended, sleepLabel, sleepLeftMs, sleepSpoken, type SleepMode, type SleepRequest } from "./sleep";
import { useVoiceSample } from "./VoiceSettings";
import { genderLabel, groupedVoices, voiceSections } from "./voiceGroups";
import { chooseVoice, chosenVoice, isNoOfflineVoice, localVoiceFor, noOfflineMessage, onlineNotice, resolveVoice, voiceCaption } from "./readAloudVoice";
import { bookProgressText, nextChapterLabel, otherBookLine, PREPARING_VOICE, textChapterLine, toggleLabel } from "./labels";
import { spokenVoiceName } from "./onlineConsent";
import { PlaylistOptionLabel, playlistNote, usePlaylistChoice } from "./PlaylistChoice";
import { ADD_MUSIC_LABEL } from "./playlistBed";
import { JumpToPlaying, ReadAlongText, sentenceIndexAt, useFollowVoice, useListenFrom, usePlayingSentence } from "./ReadAlongText";
import { canPrepare, planLabel, PREPARE_STATUS_KEY, prepareIntro, prepareLabel, readyChapterIds, upcomingTextChapters, type PrepareStatus } from "./prepareAhead";
import type { ReadAloudVoice } from "./readAloud";
import { chapterScriptQuery, useChapterScript, useListenBook, useListenLibrary, useLastNight, useListenMutations, useReadAloudVoices, useSource } from "./source";

export function speedLabel(rate: number): string {
  return `${rate.toLocaleString("vi-VN", { maximumFractionDigits: 2 })}×`;
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

function SeekBar({ large = false }: { large?: boolean }) {
  const { seek, skip, track, rate } = usePlayer();
  const second = usePlaybackSecond();
  const duration = useDuration();
  const [dragging, setDragging] = useState<number | null>(null);
  const pointer = useRef(false);
  useEffect(() => setDragging(null), [track?.chapterId, track?.bookId]);
  const shown = dragging ?? second;
  const max = duration > 0 ? duration : 1;
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
      {!large && <span className="tabular w-12 shrink-0 text-right text-xs text-fg-2">{formatClock(shown)}</span>}
      <Slider.Root
        className={cn("group relative flex touch-none select-none items-center", large ? "h-5 w-full" : "h-4 flex-1")}
        min={0}
        max={max}
        step={1}
        value={[Math.min(shown, max)]}
        onPointerDown={() => (pointer.current = true)}
        onValueChange={([value]) => {
          if (pointer.current) setDragging(value);
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
          <Slider.Range className="absolute h-full rounded-full bg-fg group-hover:bg-accent" />
        </Slider.Track>
        <Slider.Thumb
          aria-label="Vị trí trong chương"
          aria-valuetext={`${spokenClock(shown)} trên ${spokenClock(duration)}`}
          className={cn(
            "block rounded-full bg-fg shadow transition-opacity focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            large ? "size-4 opacity-100" : "size-3 opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
          )}
        />
      </Slider.Root>
      {large ? (
        <div className="tabular flex justify-between text-xs text-fg-2">
          <span>{formatClock(shown)}</span>
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

function skipIcon(Base: typeof RotateCcw) {
  return function SkipGlyph({ className }: { className?: string; strokeWidth?: number }) {
    return (
      <span className={cn("relative inline-grid place-items-center", className)}>
        <Base className="size-full" strokeWidth={1.75} />
        <span className="tabular absolute inset-0 grid place-items-center pt-[1px] text-[0.42em] font-bold leading-none">
          {SKIP_SECONDS}
        </span>
      </span>
    );
  };
}
export const Back15 = skipIcon(RotateCcw);
export const Forward15 = skipIcon(RotateCw);

/** Chương đang phát là chương chỉ có chữ (giọng máy đọc). */
function useSpeaking(): boolean {
  const { track, queue } = usePlayer();
  return queue.find((chapter) => chapter.id === track?.chapterId)?.state === "text";
}

function Transport({ large = false }: { large?: boolean }) {
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
    <div className={cn("flex items-center", large ? "gap-4 sm:gap-6" : "gap-1")}>
      <IconButton label="Chương trước (Shift+←)" icon={SkipBack} size={size} onClick={previous} {...keepFocus} />
      <IconButton label={`Lùi ${SKIP_SECONDS} giây (←)`} icon={Back15} size={size} onClick={() => skip(-SKIP_SECONDS)} {...keepFocus} />
      <button
        type="button"
        onClick={toggle}
        {...keepFocus}
        // Đang chờ đoạn đầu: nói đang chờ gì, không nói "Tạm dừng" khi chưa có tiếng nào (bấm vẫn là thôi chờ).
        aria-label={toggleLabel(playing, buffering, speaking)}
        aria-busy={waiting || undefined}
        aria-keyshortcuts="Space"
        data-player-toggle
        className={cn(
          "grid place-items-center rounded-full bg-fg text-bg shadow-card transition-transform hover:scale-105 active:scale-95",
          large ? "size-16" : "size-10",
        )}
      >
        {waiting ? (
          <Loader2 className={cn("animate-spin", large ? "size-7" : "size-5")} />
        ) : playing ? (
          <span key="pause" className="icon-pop">
            <Pause className={large ? "size-7" : "size-5"} fill="currentColor" strokeWidth={0} />
          </span>
        ) : (
          <span key="play" className="icon-pop">
            <Play className={cn(large ? "size-7" : "size-5", "translate-x-[1px]")} fill="currentColor" strokeWidth={0} />
          </span>
        )}
      </button>
      <IconButton label={`Tới ${SKIP_SECONDS} giây (→)`} icon={Forward15} size={size} onClick={() => skip(SKIP_SECONDS)} {...keepFocus} />
      {/* Còn chương sau mà chưa có audio: nút vẫn bấm được và nói vì sao (player.step báo + đường đọc chữ); chỉ chương cuối mới mờ. */}
      <IconButton
        label={nextChapterLabel(hasNext, hasLater)}
        icon={SkipForward}
        size={size}
        onClick={next}
        disabled={!hasLater}
        {...keepFocus}
      />
    </div>
  );
}

function MenuShell({
  trigger,
  label,
  children,
  active,
  width = "w-56",
  focusSelector,
}: {
  trigger: ReactNode;
  label: string;
  children: ReactNode;
  active?: boolean;
  width?: string;
  /** Khi mở, đưa tiêu điểm tới phần tử khớp (lựa chọn đang áp dụng) thay vì phần tử đầu tiên - viền tiêu điểm ở nút đầu trông như "đang chọn". */
  focusSelector?: string;
}) {
  return (
    <Popover.Root>
      <Tooltip label={label}>
        <Popover.Trigger asChild>
          <button
            type="button"
            aria-label={label}
            {...keepFocus}
            className={cn(
              // Điện thoại (màn "Đang nghe"): đủ 44 px để chạm.
              "tabular inline-flex h-9 min-w-9 shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-lg px-2 text-[13px] font-semibold transition-colors hover:bg-hover max-sm:h-[44px] max-sm:min-w-[44px]",
              active ? "text-accent-text" : "text-fg-2",
            )}
          >
            {trigger}
          </button>
        </Popover.Trigger>
      </Tooltip>
      <Popover.Portal>
        <Popover.Content
          sideOffset={8}
          collisionPadding={12}
          onCloseAutoFocus={(event) => event.preventDefault()}
          onOpenAutoFocus={(event) => {
            const current = focusSelector ? (event.currentTarget as HTMLElement).querySelector<HTMLElement>(focusSelector) : null;
            if (!current) return;
            event.preventDefault();
            current.focus();
          }}
          className={cn("z-50 rounded-xl border border-line bg-panel p-1.5 shadow-float", width)}
        >
          {children}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function SpeedMenu() {
  const { rate, setRate } = usePlayer();
  return (
    <MenuShell label="Tốc độ đọc" active={rate !== 1} trigger={<><Gauge className="size-4" />{speedLabel(rate)}</>}>
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Tốc độ đọc · nhớ riêng cho cuốn này</div>
      <div className="grid grid-cols-3 gap-1 p-1">
        {SPEEDS.map((speed) => (
          <Popover.Close asChild key={speed}>
            <button
              type="button"
              onClick={() => setRate(speed)}
              aria-pressed={speed === rate}
              className={cn(
                "tabular h-9 rounded-lg text-sm hover:bg-hover",
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
export function MusicMenu() {
  const { track, queue } = usePlayer();
  if (!track) return null;
  const speaking = queue.find((chapter) => chapter.id === track.chapterId)?.state === "text";
  return speaking ? <MusicMenuFor bookId={track.bookId} /> : <PackagedMusicMenu bookId={track.bookId} />;
}

function PackagedMusicMenu({ bookId }: { bookId: string }) {
  const { view, change } = useBookMusic(bookId);
  const music = view.data;
  if (!music?.hasMusic) return null;
  const id = `player-music-${bookId}`;
  return (
    <MenuShell
      label="Nhạc nền"
      active={music.enabled}
      width="w-64"
      trigger={
        // Tắt: gạch chéo trên nốt nhạc (lucide không có biểu tượng "nhạc tắt").
        <span className="relative">
          <Music2 className="size-4" />
          {!music.enabled && <span aria-hidden="true" className="absolute left-1/2 top-1/2 h-0.5 w-5 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-full bg-current" />}
        </span>
      }
    >
      <div className="flex items-center justify-between gap-3 px-2 py-2">
        <label htmlFor={id} className="text-sm font-medium">
          Nhạc nền: <span className="font-semibold">{music.enabled ? "Bật" : "Tắt"}</span>
        </label>
        <Switch id={id} label="Nhạc nền" checked={music.enabled} disabled={change.isPending} onCheckedChange={(enabled) => change.mutate({ enabled })} />
      </div>
      <div className={cn("transition-opacity", !music.enabled && "opacity-50")}>
        <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Mức nhạc dưới giọng đọc</div>
        <div className="flex flex-col gap-0.5 p-1">
          {levelOptions(music.levelDb).map(([value, name]) => (
            <button
              key={value}
              type="button"
              disabled={!music.enabled || change.isPending}
              aria-pressed={value === music.levelDb}
              onClick={() => change.mutate({ levelDb: value })}
              className={cn(
                "flex h-9 items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-hover disabled:hover:bg-transparent",
                value === music.levelDb ? "bg-accent-soft font-semibold text-accent-text" : "text-fg",
              )}
            >
              <Check className={cn("size-4 shrink-0", value === music.levelDb ? "text-accent-text" : "invisible")} />
              {name}
            </button>
          ))}
        </div>
      </div>
      <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">Nhạc do người làm sách chọn. Đổi ở đây chỉ trên máy này.</p>
    </MenuShell>
  );
}

function MusicMenuFor({ bookId }: { bookId: string }) {
  const { options, chosen, label, playing, error, loading, choose, canImport, addMusic } = usePlaylistChoice(bookId);
  return (
    <MenuShell
      label="Nhạc nền"
      active={playing}
      trigger={<><Music2 className="size-4" /><span className="max-w-32 truncate max-sm:hidden">{playing ? label : ""}</span></>}
      width="w-72"
    >
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Nhạc nền · nhớ riêng cho cuốn này</div>
      <div className="flex max-h-[60vh] flex-col gap-0.5 overflow-y-auto p-1">
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
      <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{playlistNote(error)}</p>
    </MenuShell>
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
    navigate("/settings");
    let tries = 0;
    const reveal = () => {
      const target = document.getElementById(anchor);
      if (target) {
        target.scrollIntoView({ block: "start" });
        // Danh sách giọng phía trên hiện ra SAU (hỏi máy xong mới dựng): chỗ cần tới bị đẩy xuống - cuộn lại vài lần cho tới khi trang yên.
        for (const wait of [250, 600, 1200]) setTimeout(() => target.scrollIntoView({ block: "start" }), wait);
      } else if (tries++ < 20) setTimeout(reveal, 50);
    };
    setTimeout(reveal, 0);
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
    <div className="relative">
      <div ref={box} onScroll={measure} className={className}>
        {children}
      </div>
      {more && (
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 flex h-12 items-end justify-center bg-gradient-to-t from-panel via-panel/80 to-transparent pb-1">
          <span className="rounded-full bg-panel px-2.5 py-0.5 text-[11px] font-medium text-fg-2 ring-1 ring-line">Kéo xuống còn giọng khác</span>
        </div>
      )}
    </div>
  );
}

export function VoiceMenu() {
  const { track, queue } = usePlayer();
  const source = useSource();
  const { data: voices } = useReadAloudVoices();
  const [chosen, setChosen] = useState("");
  const speaking = queue.find((chapter) => chapter.id === track?.chapterId)?.state === "text";
  const sample = useVoiceSample((voiceId, text) => source.readAloudSample!(voiceId, text));
  const openVoiceSettings = useOpenVoiceSettings();
  useEffect(() => setChosen(track ? chosenVoice(track.bookId) : ""), [track]);
  if (!track || !speaking || !voices?.length) return null;
  const current = resolveVoice(voices, chosen);
  return (
    <MenuShell
      label="Giọng đọc"
      // Tên giọng hiện cả trên điện thoại: người nghe thấy ngay giọng nào đang đọc, không chỉ một biểu tượng.
      trigger={<><AudioLines className="size-4" /><span className="max-w-24 truncate">{current ? spokenVoiceName(current.name) : ""}</span></>}
      width="w-80 max-w-[calc(100vw-1.5rem)]"
    >
      <div className="px-2 pb-1 pt-1 text-xs font-medium text-fg-2">Giọng đọc · nhớ riêng cho cuốn này</div>
      {/* Cùng nhóm, cùng tên giọng với Cài đặt › Giọng đọc; "Thử" dùng cùng cách nghe thử. */}
      <ScrollHint className="max-h-[50vh] overflow-y-auto p-1">
        {groupedVoices(voices).map((group) => (
          <div key={group.provider} role="group" aria-label={group.title} className="mb-1.5">
            <div className="px-2 pb-0.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-fg-3">{group.title}</div>
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
                          onClick={() => {
                            chooseVoice(track.bookId, voice.id);
                            setChosen(voice.id);
                          }}
                          className={cn(
                            "flex min-h-9 min-w-0 flex-1 items-center gap-2 rounded-lg px-2 text-left text-sm hover:bg-hover max-sm:min-h-[44px]",
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
                          onClick={() => (playing ? sample.stop() : void sample.play(voice.id))}
                          aria-label={`${playing ? "Dừng" : "Thử"} giọng ${voice.name}`}
                          className="inline-flex h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-xs font-medium text-fg-2 hover:bg-hover hover:text-fg max-sm:h-[44px]"
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
        className="flex min-h-9 w-full items-center rounded-lg px-3 text-left text-sm text-accent-text hover:bg-hover max-sm:min-h-[44px]"
      >
        Thêm giọng…
      </button>
      {current?.online && <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{onlineNotice(current)}</p>}
      {current && canPrepare(current, Boolean(source.readAloudPrepareOnline)) && (
        <PrepareAhead voice={current} bookId={track.bookId} chapterId={track.chapterId} />
      )}
    </MenuShell>
  );
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
  // Chỉ nguồn báo từng chương (điện thoại); máy tính làm theo đoạn, không có dấu - khỏi hỏi máy chủ.
  const source = useSource();
  const { data } = usePrepareStatus(enabled && Boolean(source.readAloudPreparePlan));
  return useMemo(() => readyChapterIds(data, bookId, chosenVoice(bookId)), [data, bookId]);
}

/** "Làm trước": máy đọc sẵn các chương tới ở nền - giọng chậm hơn tốc độ nghe (VieNeu) vẫn nghe liền mạch; trên điện thoại cả giọng trực tuyến,
 *  để nghe khi không có mạng. Nói rõ còn bao lâu; người nghe bấm mới làm, bấm "Dừng" là thôi. */
function PrepareAhead({ voice, bookId, chapterId }: { voice: ReadAloudVoice; bookId: string; chapterId: number }) {
  const source = useSource();
  const client = useQueryClient();
  const { queue } = usePlayer();
  const { data: status } = usePrepareStatus();
  const [busy, setBusy] = useState(false);
  const upcoming = upcomingTextChapters(queue, chapterId);
  const request = {
    voice: voice.id,
    bookId,
    chapters: upcoming.map(({ id, title }) => ({ id, title })),
    label: upcoming.length === 1 ? upcoming[0].title : `${upcoming.length} chương tới`,
  };
  const mine = Boolean(status && status.voice === voice.id && (!status.bookId || status.bookId === bookId));
  const running = status?.state === "running";
  const { data: plan } = useQuery({
    queryKey: ["readaloud", "prepare-plan", request.voice, request.bookId, request.chapters.map((chapter) => chapter.id)],
    queryFn: () => source.readAloudPreparePlan!(request),
    enabled: Boolean(source.readAloudPreparePlan) && request.chapters.length > 0 && !(mine && running),
  });
  if (!source.readAloudPrepare) return null;
  const chargingOnly = status?.chargingOnly ?? true;
  const settle = (next: PrepareStatus) => client.setQueryData(PREPARE_STATUS_KEY, next);
  const start = async () => {
    setBusy(true);
    try {
      settle(await source.readAloudPrepare!({ ...request, chargingOnly }));
    } catch (error) {
      toast.error("Chưa làm trước được", { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  const label = mine && status ? prepareLabel(status) : running ? "Đang làm trước cho một cuốn hay giọng khác - làm ở đây thì việc ấy dừng." : "";
  return (
    <div className="border-t border-line px-2 pb-1 pt-2 text-xs text-fg-2">
      <p className="text-pretty">{label || prepareIntro(voice)}</p>
      {!(mine && running) && plan && <p className="mt-1 text-pretty">{planLabel(plan)}</p>}
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        {mine && running ? (
          <button type="button" className="rounded-lg px-2 py-1 font-medium text-fg hover:bg-hover" onClick={() => void source.readAloudPrepareCancel?.().then(settle)}>
            Dừng làm trước
          </button>
        ) : (
          upcoming.length > 0 && (
            <button type="button" disabled={busy} className="rounded-lg px-2 py-1 font-medium text-accent-text hover:bg-hover disabled:opacity-45" onClick={() => void start()}>
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
    </div>
  );
}

export function SleepMenu() {
  const { sleep, setSleep, extendSleep, options, sleepStoppedAt, lastSleepMinutes, track } = usePlayer();
  // Thẻ "Tối qua" chỉ đáng nhắc khi người nghe đã từng có đêm nào được ghi lại (chưa có thì nhắc là nhắc một thứ họ chưa thấy bao giờ).
  const hadNight = Boolean(useLastNight().data);
  const now = useTicker(sleep.kind === "minutes" && sleep.since !== null);
  const recentlyStopped = sleep.kind === "off" && sleepStoppedAt !== null && now - sleepStoppedAt < 30 * 60_000;
  return (
    <SleepPicker
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
                onClick={() => setSleep({ kind: "minutes", minutes: lastSleepMinutes })}
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
    />
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
  onExtend,
  onSet,
  idle = null,
  note,
}: {
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
  const [custom, setCustom] = useState(customStart);
  const active = sleep.kind !== "off";
  const left = sleepLeftMs(sleep, now);
  const spoken = active ? sleepSpoken(sleep, now) : "Hẹn giờ tắt";
  return (
    <MenuShell
      label={name ? `${spoken} trên ${name}` : spoken}
      active={active}
      width="w-64"
      focusSelector="[data-current-choice]"
      trigger={
        <>
          <SleepRing fraction={sleep.kind === "minutes" && sleep.minutes > 0 && left !== null ? left / (sleep.minutes * 60_000) : null}>
            <Moon className="size-4" />
          </SleepRing>
          {active && <span className="tabular">{sleepLabel(sleep, now)}</span>}
        </>
      }
    >
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
              aria-pressed={sleep.kind === "minutes" && sleep.minutes === minutes}
              data-current-choice={sleep.kind === "minutes" && sleep.minutes === minutes ? "" : undefined}
              className={cn(
                "tabular h-9 rounded-lg text-sm hover:bg-hover disabled:opacity-40",
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
          className="grid size-9 place-items-center rounded-lg text-lg hover:bg-hover"
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
          className="grid size-9 place-items-center rounded-lg text-lg hover:bg-hover"
        >
          +
        </button>
        <Popover.Close asChild>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSet({ kind: "minutes", minutes: custom })}
            className="h-9 rounded-lg bg-hover px-3 text-sm font-medium hover:bg-line disabled:opacity-40"
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
    </MenuShell>
  );
}

function VolumeControl() {
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
      className={cn("group relative h-4 touch-none select-none items-center", className)}
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
        className="block size-3 rounded-full bg-fg opacity-0 shadow group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-accent"
      />
    </Slider.Root>
  );
  if (!wide) {
    return (
      <Popover.Root>
        <Popover.Trigger asChild>
          <button
            type="button"
            aria-label={`Âm lượng ${Math.round(volume * 100)}%`}
            className="grid size-8 place-items-center rounded-lg text-fg-2 hover:bg-hover hover:text-fg data-[state=open]:bg-hover max-sm:size-[44px]"
          >
            <Icon className="size-[18px]" />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content side="top" sideOffset={8} className="z-50 flex items-center gap-2 rounded-xl border border-line bg-panel p-2 shadow-float">
            <IconButton label={volume === 0 ? "Bật tiếng (M)" : "Tắt tiếng (M)"} icon={Icon} size="sm" onClick={toggleMute} />
            {slider("flex w-32")}
            <span className="tabular w-9 text-right text-xs text-fg-2">{Math.round(volume * 100)}%</span>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <IconButton label={volume === 0 ? "Bật tiếng (M)" : "Tắt tiếng (M)"} icon={Icon} size="sm" {...keepFocus} onClick={toggleMute} />
      {slider("flex w-20")}
    </div>
  );
}

/** Thêm dấu trang kèm thông báo có "Ghi chú" và "Hoàn tác". Dấu trùng chỗ (±5 giây) không tạo thêm. */
export function useAddBookmark() {
  const { addBookmark, track } = usePlayer();
  const { setExpanded } = useNowPlaying();
  const source = useSource();
  const client = useQueryClient();
  return useCallback(async () => {
    if (!track) return;
    const mark = await addBookmark().catch(() => null);
    if (!mark) {
      toast.error("Chưa thêm được dấu trang");
      return;
    }
    if (mark.existing) {
      toast.dismiss("bookmark");
      toast("Đã có dấu trang ở chỗ này", { id: "bookmark-existing", description: formatClock(mark.seconds) });
      return;
    }
    toast.success("Đã thêm dấu trang", {
      id: "bookmark",
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
          void source.deleteBookmark(track.bookId, mark.id).then(() => {
            void client.invalidateQueries({ queryKey: ["listen", "book", track.bookId] });
          });
        },
      },
    });
  }, [addBookmark, client, setExpanded, source, track]);
}

function BookmarkButton() {
  const add = useAddBookmark();
  return <IconButton label="Thêm dấu trang (B)" icon={BookmarkPlus} size="sm" className="max-sm:size-[44px]" {...keepFocus} onClick={() => void add()} />;
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
  if (!fading) return null;
  return (
    <div className={cn("flex items-center gap-3 rounded-xl bg-accent-soft px-3 py-2 text-sm text-accent-text", className)} role="status">
      <Moon className="size-4 shrink-0" />
      <span className="min-w-0 flex-1">Sắp tắt · {EXTEND_GESTURE} để nghe thêm {options.extendMinutes} phút</span>
      <button type="button" onClick={() => extendSleep()} className="shrink-0 rounded-lg bg-accent px-2.5 py-1 text-xs font-semibold text-accent-ink">
        +{options.extendMinutes} phút
      </button>
    </div>
  );
}

/** Ghi công nhạc nền đang nghe (CC BY đòi nêu tác giả ở nơi nhạc phát): một dòng nhỏ, mờ, chỉ hiện khi đang phát; không
 *  có bài thì không hiện gì. Chạm (hay Enter) vào dòng để xem đủ ghi công: tên bài, tác giả, giấy phép (có liên kết) -
 *  màn cảm ứng không có chỗ "giữ chuột" để xem chú thích. */
function MusicCreditLine() {
  const { musicCredit, playing } = usePlayer();
  const [open, setOpen] = useState(false);
  const label = [musicCredit?.title, musicCredit?.creator].filter(Boolean).join(" · ");
  useEffect(() => setOpen(false), [musicCredit]);
  if (!playing || !musicCredit || !label) return null;
  return (
    <div className="mt-0.5 text-xs text-fg-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title={musicCredit.attribution || label}
        className="max-w-full truncate rounded outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        Nhạc nền: {label}
      </button>
      {open && (
        <div className="mx-auto mt-1 max-w-sm break-words text-left">
          {musicCredit.attribution && <p>{musicCredit.attribution}</p>}
          {!musicCredit.attribution && (
            <p>
              {musicCredit.title}
              {musicCredit.creator ? ` - ${musicCredit.creator}` : ""}
            </p>
          )}
          {musicCredit.license && (
            <p>
              Giấy phép:{" "}
              {musicCredit.licenseUrl ? (
                <a href={musicCredit.licenseUrl} target="_blank" rel="noreferrer" className="underline">
                  {licenseLabel(musicCredit.license, musicCredit.licenseUrl)}
                </a>
              ) : (
                licenseLabel(musicCredit.license)
              )}
            </p>
          )}
          {musicCredit.landing && (
            <p>
              <a href={musicCredit.landing} target="_blank" rel="noreferrer" className="underline">
                Trang của bài nhạc
              </a>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Dòng dưới tên chương: tên sách - hay đang chờ giọng máy đọc đoạn đầu. Lỗi KHÔNG nằm ở đây (PlayerAlert). */
function TrackSubtitle() {
  const { track, purpose, atEnd, playing, buffering } = usePlayer();
  const speaking = useSpeaking();
  if (!track) return null;
  return (
    <>
      {purpose === "review" && (
        <span className="mr-1.5 inline-block rounded bg-info-soft px-1.5 text-[11px] font-semibold uppercase tracking-wide text-info">Nghe kiểm</span>
      )}
      {speaking && playing && buffering ? PREPARING_VOICE : atEnd === "caughtUp" ? "Đã nghe hết phần đã có" : track.bookTitle}
    </>
  );
}

/** Không phát được (mất mạng, giọng đọc không phản hồi, file hỏng): một khối riêng đọc màn hình đọc ngay (role="alert") kèm "Thử lại" - không
 *  thay tên sách bằng chữ đỏ. Lời nhắn đã rơi sang giọng của máy (vẫn đang đọc) là một dòng trạng thái, tự ẩn.
 *  Mất mạng mà máy không có giọng đọc không cần mạng: một câu ngắn nói tên giọng, nút chính theo tình huống - đã có giọng chạy trên máy (VieNeu…) thì
 *  "Đọc bằng …" (đổi giọng cuốn này rồi phát tiếp), chưa thì "Tải giọng VieNeu" (tới thẻ tải giọng trong Cài đặt). Mạng về thì khối tự ẩn.
 *  `overlay`: trong màn "Đang nghe"; ở thanh phát thì không đè lên màn Cài đặt (nơi người nghe đang đi tải giọng). */
function PlayerAlert({ className, overlay = false }: { className?: string; overlay?: boolean }) {
  const { error, notice, resume, dismissError, track } = usePlayer();
  const openVoiceSettings = useOpenVoiceSettings();
  const { pathname } = useLocation();
  const voices = useReadAloudVoices().data;
  const offline = Boolean(error) && isNoOfflineVoice(error);
  useEffect(() => {
    if (!offline) return;
    window.addEventListener("online", dismissError);
    return () => window.removeEventListener("online", dismissError);
  }, [offline, dismissError]);
  if (error) {
    if (!overlay && pathname.startsWith("/settings")) return null;
    const current = voices && track ? resolveVoice(voices, chosenVoice(track.bookId)) : undefined;
    const local = offline && voices ? localVoiceFor(voices, current) : undefined;
    const button = "min-h-9 shrink-0 rounded-lg bg-panel px-3 text-xs font-semibold ring-1 ring-line hover:bg-hover max-sm:min-h-[44px]";
    return (
      <div role="alert" className={cn("flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl bg-danger-soft px-3 py-2 text-sm text-fg", className)}>
        <TriangleAlert className="size-4 shrink-0 text-danger" />
        <span className="min-w-[14rem] flex-1">{offline && current ? noOfflineMessage(spokenVoiceName(current.name)) : error}</span>
        {offline && local && track && (
          <button
            type="button"
            onClick={() => {
              chooseVoice(track.bookId, local.id);
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
        {offline && !local && (
          <button type="button" onClick={() => openVoiceSettings("vieneu-module")} {...keepFocus} className={button}>
            Tải giọng VieNeu
          </button>
        )}
        <button type="button" onClick={resume} {...keepFocus} className={button}>
          Thử lại
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
}

function CompactProgress() {
  const fraction = useClock((time, duration) => (duration > 0 ? Math.round((time / duration) * 400) / 400 : 0));
  return (
    <div className="absolute inset-x-0 top-0 h-[2px] bg-line">
      <div className="h-full bg-accent" style={{ width: `${fraction * 100}%` }} />
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
    if (!track || !last || playing || purpose !== "listen") return;
    // chỗ nghe trên máy chủ là của hồ sơ khác (máy khác vừa đổi hồ sơ): FollowRecord lo, đây không phải "nghe xa hơn"
    if (track.recordId && active && track.recordId !== active) return;
    const key = `${track.bookId}:${last.at}`;
    if (asked.current === key || last.at * 1000 <= positionStamp() + 1000) return;
    const here = readClock().time;
    if (last.chapterId === track.chapterId && Math.abs(last.seconds - here) < 30) return;
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
  const { track, close, playing, buffering, toggle } = usePlayer();
  const { expanded, setExpanded } = useNowPlaying();
  const speaking = useSpeaking();
  useContinueIntoNextPart();
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
        <PlayerAlert className="mx-3 mt-2" />
        <div className="flex h-16 items-center gap-3 px-3">
          <button type="button" onClick={() => setExpanded(true)} className="flex min-w-0 flex-1 items-center gap-3 text-left" aria-label="Mở màn hình đang nghe">
            <BookCover title={track.bookTitle} image={track.bookCover} size="sm" className={cn("size-11", !expanded && "cover-morph")} />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{track.chapterTitle}</div>
              <div className="truncate text-xs text-fg-2">
                <TrackSubtitle />
              </div>
            </div>
          </button>
          <button
            type="button"
            onClick={toggle}
            aria-label={toggleLabel(playing, buffering, speaking)}
            aria-busy={(playing && buffering) || undefined}
            className="grid size-11 shrink-0 place-items-center rounded-full bg-fg text-bg"
          >
            {playing && buffering ? (
              <Loader2 className="size-5 animate-spin" />
            ) : playing ? (
              <Pause className="size-5" fill="currentColor" strokeWidth={0} />
            ) : (
              <Play className="size-5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
            )}
          </button>
        </div>
      </section>
    );
  }
  return (
    <section aria-label="Trình phát" className="relative z-20 shrink-0 border-t border-line bg-panel">
      <BookmarkShortcut />
      <FurtherElsewhere />
      <FollowRecord />
      <FadingNotice className="mx-4 mt-2" />
      <PlayerAlert className="mx-4 mt-2" />
      {/* Cột giữa theo bề rộng CỦA THANH (min(40%, 480px)), không theo cửa sổ (40vw): thanh không gồm thanh bên, 40vw từng
          chiếm 512/1044 px ở cửa sổ 1280 - tên chương bị cắt, cụm nút phải (266 px) bị ép vào 238 px (soát UX 29-09). */}
      <div className="grid h-[76px] grid-cols-[minmax(0,1fr)_min(40%,480px)_minmax(0,1fr)] items-center gap-4 px-4">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="flex min-w-0 items-center gap-3 rounded-lg p-1 text-left hover:bg-hover"
          aria-label="Mở màn hình đang nghe"
        >
          <BookCover title={track.bookTitle} image={track.bookCover} size="sm" className={cn("size-12", !expanded && "cover-morph")} />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{track.chapterTitle}</div>
            <div className="truncate text-xs text-fg-2">
              <TrackSubtitle />
            </div>
          </div>
        </button>
        <div className="flex w-full flex-col items-center gap-0.5">
          <Transport />
          <SeekBar />
        </div>
        <div className="flex min-w-0 items-center justify-end gap-0.5">
          {extra}
          <MusicMenu />
          <VoiceMenu />
          <SpeedMenu />
          <SleepMenu />
          <BookmarkButton />
          <VolumeControl />
          <IconButton label="Mở màn hình đang nghe" icon={Maximize2} size="sm" onClick={() => setExpanded(true)} {...keepFocus} />
          <IconButton label="Đóng trình phát" icon={X} size="sm" onClick={close} {...keepFocus} />
        </div>
      </div>
    </section>
  );
}

// ---- Bảng bên của màn hình đang nghe ---------------------------------------------------------------------

/** Tab "Đọc theo" của trình phát: cùng văn bản với màn đọc (ReadAlongText) - câu và chữ đang đọc sáng lên, bấm một chữ là nghe từ chữ ấy, tự cuộn
 *  theo giọng; thêm nhãn người nói và câu đã nghe nhạt đi. */
function ReadAlong() {
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
  const nearEnd = useClock((time, duration) => duration > 0 && duration - time < 30);

  // Sắp hết chương: nạp sẵn văn bản chương kế để sang chương không bị chớp "đang mở".
  useEffect(() => {
    if (!nearEnd || !track) return;
    const index = queue.findIndex((chapter) => chapter.id === track.chapterId);
    const upcoming = queue.slice(index + 1).find(canPlay);
    if (upcoming) void client.prefetchQuery(chapterScriptQuery(source, track.bookId, upcoming));
  }, [client, nearEnd, queue, source, track]);

  if (isLoading) return <div className="animate-[fade-in_0.2s_0.3s_both] p-10 text-fg-2">Đang mở văn bản chương…</div>;
  if (!script) return null;
  return (
    <div className="relative h-full">
      <div ref={container} onScroll={follow.onScroll} {...follow.input} className="h-full overflow-y-auto px-6 py-8 sm:px-10">
        <div className="mx-auto max-w-[62ch] text-[17px] leading-[1.75]">
          {/* Chương giọng máy đọc chưa có mốc chỉ trong lúc chờ đoạn đầu - không phải "chưa có audio". */}
          {!script.timed && current?.state !== "text" && (
            <p className="mb-5 rounded-lg bg-hover px-4 py-3 text-sm text-fg-2">Chương này chưa có audio hoàn chỉnh - đang hiện văn bản, chưa đọc theo được.</p>
          )}
          <ReadAlongText
            script={script}
            playingIndex={active}
            onTap={canListen ? (index, word) => listenFrom(index, word) && follow.follow() : undefined}
            focusIndex={Math.max(0, active)}
            speakers
            dimHeard
            headingClassName="pb-2 text-2xl font-bold leading-snug tracking-tight"
            className="space-y-5"
          />
        </div>
      </div>
      {follow.showJump && (
        <div className="pointer-events-none absolute inset-x-0 bottom-5 flex justify-center">
          <JumpToPlaying onClick={follow.jump} />
        </div>
      )}
    </div>
  );
}

export function chapterStatusLabel(producing: boolean): string {
  return producing ? "Đang thu âm…" : "Chưa có audio";
}

function ChapterPanel() {
  const { track, queue, jumpTo, playing } = usePlayer();
  const { data: book } = useListenBook(track?.bookId);
  const container = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    container.current?.querySelector<HTMLElement>("[data-current=true]")?.scrollIntoView({ block: "center" });
  }, []);
  return (
    <div ref={container} className="h-full overflow-y-auto px-3 py-4 sm:px-6">
      {queue.map((chapter) => {
        const current = chapter.id === track?.chapterId;
        const done = book?.state.chapters[String(chapter.id)]?.done;
        return (
          <button
            key={chapter.id}
            type="button"
            data-current={current}
            disabled={!canPlay(chapter)}
            aria-current={current ? "true" : undefined}
            onClick={() => jumpTo(chapter.id)}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left",
              current ? "bg-accent-soft" : canPlay(chapter) && "hover:bg-hover",
            )}
          >
            <span className="grid w-5 shrink-0 place-items-center">
              {current && playing ? (
                <Vu className="h-3 text-accent" />
              ) : done ? (
                <Check className="size-4 text-success" aria-label="Đã nghe" />
              ) : null}
            </span>
            <span className="min-w-0 flex-1">
              <span className={cn("block truncate text-sm font-medium", current && "text-accent-text", !canPlay(chapter) && "text-fg-2")}>
                {chapter.subtitle || chapter.title}
              </span>
              <span className="tabular block truncate text-xs text-fg-2">
                {chapter.subtitle ? `${chapter.title} · ` : ""}
                {chapter.available
                  ? formatLength(chapter.duration)
                  : chapter.state === "text"
                    ? textChapterLine(Boolean(chapter.speech))
                    : chapterStatusLabel(Boolean(book?.producing))}
              </span>
            </span>
          </button>
        );
      })}
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
    <li className="group rounded-lg px-3 py-2.5 hover:bg-hover">
      <div className="flex items-start gap-2">
        <button type="button" onClick={() => onJump(mark)} className="min-w-0 flex-1 text-left">
          <span className="block truncate text-sm font-medium">{chapter ? chapter.subtitle || chapter.title : "Chương đã bị gỡ"}</span>
          <span className="tabular block text-xs text-fg-2">
            {chapter?.subtitle ? `${chapter.title} · ` : ""}
            {formatClock(mark.seconds)} · {formatWhen(mark.at)}
          </span>
          {quote && <span className="mt-1 line-clamp-2 block text-sm italic leading-snug text-fg">“{quote}”</span>}
        </button>
        <IconButton label="Sửa ghi chú" icon={Pencil} size="sm" onClick={() => onEdit(!editing)} />
        <IconButton label="Xoá dấu trang" icon={Trash2} size="sm" onClick={remove} />
      </div>
      {editing ? (
        <form
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
                  setNote(mark.note);
                  onEdit(false);
                }
              }}
              placeholder="Ghi chú cho dấu trang này"
              aria-label="Ghi chú"
              className="h-9 min-w-0 flex-1 rounded-md border border-line bg-bg px-2 text-sm outline-none focus:border-accent"
            />
            <button type="submit" className="rounded-md bg-accent px-3 text-sm font-medium text-accent-ink">
              Lưu
            </button>
          </div>
          <div className="tabular text-right text-[11px] text-fg-2">{note.length}/500</div>
        </form>
      ) : mark.note ? (
        <p className="mt-1.5 whitespace-pre-wrap rounded-md bg-sunken px-2.5 py-1.5 text-sm text-fg-2">{mark.note}</p>
      ) : null}
    </li>
  );
}

/** Danh sách dấu trang - mới nhất lên đầu, mỗi dấu kèm câu văn ở chỗ đó để nhận ra mà không cần nhớ giây. */
export function BookmarkList({
  bookId,
  chapters,
  marks,
  onJump,
  editingId,
  setEditingId,
}: {
  bookId: string;
  chapters: ListenChapter[];
  marks: Bookmark[];
  onJump: (mark: Bookmark) => void;
  editingId?: string | null;
  setEditingId?: (id: string | null) => void;
}) {
  const source = useSource();
  const [localEditing, setLocalEditing] = useState<string | null>(null);
  const editing = editingId !== undefined ? editingId : localEditing;
  const setEditing = setEditingId ?? setLocalEditing;
  const sorted = useMemo(() => [...marks].sort((a, b) => b.at - a.at), [marks]);
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
  return (
    <ul className="space-y-1">
      {sorted.map((mark) => (
        <BookmarkRow
          key={mark.id}
          bookId={bookId}
          mark={mark}
          chapter={chapters.find((chapter) => chapter.id === mark.chapterId)}
          quote={sentenceAt(scriptOf(mark.chapterId), mark.seconds)}
          editing={editing === mark.id}
          onEdit={(value) => setEditing(value ? mark.id : null)}
          onJump={onJump}
        />
      ))}
    </ul>
  );
}

function BookmarkPanel({ editingId, setEditingId }: { editingId: string | null; setEditingId: (id: string | null) => void }) {
  const { track, queue, jumpTo } = usePlayer();
  const { data: book } = useListenBook(track?.bookId);
  const marks = book?.state.bookmarks ?? [];
  if (!track || !marks.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-8 text-center">
        <BookmarkIcon className="size-8 text-fg-3" />
        <p className="mt-3 font-medium">Chưa có dấu trang</p>
        <p className="mt-1 text-sm text-fg-2">Bấm biểu tượng dấu trang (hoặc phím B) khi nghe tới đoạn muốn quay lại.</p>
      </div>
    );
  }
  return (
    <div className="h-full overflow-y-auto px-3 py-4 sm:px-6">
      <BookmarkList
        bookId={track.bookId}
        chapters={queue}
        marks={marks}
        onJump={(mark) => jumpTo(mark.chapterId, mark.seconds, mark.note.trim() ? `Đã tới dấu trang “${excerpt(mark.note)}”` : undefined)}
        editingId={editingId}
        setEditingId={setEditingId}
      />
    </div>
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
function BookProgressLine() {
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
  if (!track || total <= 0) return null;
  const heard = Math.min(total, before + tens * 10);
  // Sách chưa thu xong: "Cả cuốn 99%" đọc như sắp hết truyện (soát UX 29-09) - đó là phần đã có.
  const whole = queue.every((chapter) => chapter.available);
  return (
    <p className="tabular mt-1 text-xs text-fg-2">
      {bookProgressText({ whole, heard, total, rate, speed: speedLabel(rate), finished: atEnd === "finished" })}
    </p>
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
  const { atEnd, track } = usePlayer();
  const next = useNextVolume(track?.bookId, track?.bookTitle);
  const playBook = usePlayListenBook();
  const continued = useRef("");
  useEffect(() => {
    if (atEnd !== "finished" || !track || !next || seriesOf(next.title).unit !== "phần") return;
    if (continued.current === track.bookId) return;
    continued.current = track.bookId;
    toast(`Nghe tiếp ${nextLabel(next.title)}`, { description: "Hết phần trước - phần sau nối liền như một cuốn." });
    void playBook(next);
  }, [atEnd, track, next, playBook]);
}

/** Cuối màn "Đã nghe hết sách": mời nghe cuốn khác (tối đa 3, mỗi cuốn một nút nghe tiếp từ chỗ đã dừng) và đường về thư viện.
 *  `skipId`: tập kế đã có nút "Nghe tiếp" riêng ngay trên - không mời lần nữa. */
function AfterTheEnd({ skipId }: { skipId?: string }) {
  const { track } = usePlayer();
  const { data: books } = useListenLibrary();
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
        className="mt-1 min-h-[44px] w-full text-center font-semibold text-accent-text underline underline-offset-2"
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
  if (atEnd === "finished" && next) {
    return (
      <div className="mt-3 rounded-xl bg-accent-soft px-3 py-2.5 text-center text-sm">
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
      <div className="mt-3 rounded-xl bg-accent-soft px-3 py-2.5 text-center text-sm">
        <div className="text-fg">Đã nghe hết sách.</div>
        <button type="button" onClick={restart} className="mt-1.5 min-h-[44px] font-semibold text-accent-text underline underline-offset-2">
          Nghe lại từ đầu
        </button>
        <AfterTheEnd />
      </div>
    );
  }
  if (atEnd !== "caughtUp") return null;
  return (
    <p className="mt-3 rounded-xl bg-hover px-3 py-2 text-center text-sm text-fg-2">
      Đã nghe hết phần đã có. Chương tiếp theo nghe được khi Studio làm xong.
    </p>
  );
}

// ---- Màn hình đang nghe ------------------------------------------------------------------------------------

/** `actions`: nút riêng của từng nền ở hàng nút dưới thanh tua (điện thoại: "Phát trên <máy tính>"). */
export function NowPlaying({ mobile = false, actions }: { mobile?: boolean; actions?: ReactNode }) {
  const { track, sleep, fading, canGoBack, goBack, playing, buffering, toggle } = usePlayer();
  const speaking = useSpeaking();
  const { expanded, setExpanded } = useNowPlaying();
  const [panel, setPanelState] = useState<Panel>(initialPanel);
  const [showPanel, setShowPanel] = useState(!mobile);
  const [editingId, setEditingId] = useState<string | null>(null);
  const section = useRef<HTMLElement | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const open = expanded && Boolean(track);

  const setPanel = (value: Panel) => {
    setPanelState(value);
    try {
      localStorage.setItem(PANEL_KEY, value);
    } catch {
      /* không lưu được thì thôi */
    }
  };

  // Mở: đưa focus vào nút Phát; đóng: trả focus về chỗ đã mở.
  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement as HTMLElement | null;
    const timer = window.setTimeout(() => section.current?.querySelector<HTMLElement>("[data-player-toggle]")?.focus(), 30);
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

  const panelTabs = (
    <div role="tablist" aria-label="Bảng" className="flex gap-1">
      {PANELS.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={panel === item.value && showPanel}
          onClick={() => {
            if (mobile && panel === item.value && showPanel) setShowPanel(false);
            else {
              setPanel(item.value);
              setShowPanel(true);
            }
          }}
          className={cn(
            "inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 text-sm font-medium transition-colors",
            panel === item.value && showPanel ? "bg-hover text-fg" : "text-fg-2 hover:text-fg",
          )}
        >
          <item.icon className="size-4" />
          {item.label}
        </button>
      ))}
    </div>
  );

  const panelBody =
    panel === "text" ? <ReadAlong /> : panel === "chapters" ? <ChapterPanel /> : <BookmarkPanel editingId={editingId} setEditingId={setEditingId} />;

  if (!open || !track) return null;
  return (
    <section
      ref={section}
      className={cn("now-playing absolute inset-0 z-30 flex bg-bg", mobile && "flex-col")}
      aria-label="Đang nghe"
    >
      <aside
        // Cửa sổ vừa (~900px): cột trái 400px chỉ chừa ~270px cho đọc theo - co về 320px dưới lg (soát UX 29-09).
        className={cn(
          "flex shrink-0 flex-col bg-panel",
          mobile ? "min-h-0 flex-1 px-6 pb-6 pt-3" : "w-[320px] border-r border-line px-6 pb-8 pt-5 lg:w-[400px] lg:px-8",
        )}
        // Mỗi cuốn một sắc: màu chủ đạo của ảnh bìa thật (máy chủ tính sẵn), không có thì màu của bìa vẽ từ tên.
        // Nhạt dần trước khi tới chữ và nút, nên không đụng tới độ tương phản của chúng.
        style={{
          backgroundImage: `linear-gradient(180deg, color-mix(in oklab, ${track.bookCover?.color || coverStyle(track.bookTitle).from} 42%, transparent) 0%, transparent 58%)`,
        }}
      >
        <div className="flex items-center justify-between">
          <IconButton label="Thu nhỏ (Esc)" icon={ChevronDown} onClick={() => setExpanded(false)} />
          <span className="text-xs font-semibold uppercase tracking-[0.08em] text-fg-2">Đang nghe</span>
          {canGoBack ? <IconButton label="Quay lại chỗ vừa nghe" icon={Undo2} onClick={goBack} /> : <span className="size-9" />}
        </div>
        {mobile && showPanel ? (
          <div className="-mx-6 mt-2 min-h-0 flex-1 border-y border-line">{panelBody}</div>
        ) : (
          // Bìa vuông, to nhất 300px nhưng co theo chỗ còn lại của khung (cả chiều cao): cqw/cqh là cỡ của chính khung này (container-type:size) - nút bìa
          // w-full max-w-[300px] cũ không co theo chiều cao nên đè lên "ĐANG NGHE" khi cửa sổ thấp (soát UX 05-10).
          <div className="mt-4 flex min-h-16 min-w-0 flex-1 items-center justify-center [container-type:size]">
            {/* Chạm bìa để phát/dừng (SABP): mục tiêu lớn nhất màn hình, dễ trúng khi đang nằm và mắt nhắm mắt mở. */}
            <button
              type="button"
              onClick={toggle}
              aria-label={`${toggleLabel(playing, buffering, speaking)} (chạm bìa)`}
              className="size-[min(300px,100cqw,100cqh)] shrink-0 rounded-lg transition-transform active:scale-[0.98]"
            >
              <BookCover title={track.bookTitle} image={track.bookCover} size="xl" className="cover-morph w-full" />
            </button>
          </div>
        )}
        <div className="mt-5 w-full text-center">
          <h2 className="truncate text-lg font-semibold">{track.chapterTitle}</h2>
          <p className="mt-0.5 truncate text-sm text-fg-2">
            <TrackSubtitle />
          </p>
          <BookProgressLine />
          <MusicCreditLine />
        </div>
        <div className="mt-5 w-full">
          <SeekBar large />
        </div>
        <div className="mt-3 flex justify-center">
          <Transport large />
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-1">
          <MusicMenu />
          <VoiceMenu />
          <SpeedMenu />
          <SleepMenu />
          <BookmarkButton />
          <VolumeControl />
          {actions}
        </div>
        {/* Đang nhỏ dần thì "Sắp tắt…" đã nói thay - hai dòng cùng lúc ở chương rất ngắn đọc như mâu thuẫn. */}
        {sleep.kind === "chapter" && !fading && <p className="mt-2 text-center text-xs text-fg-2">Sẽ dừng khi hết chương này.</p>}
        <FadingNotice className="mt-3" />
        <PlayerAlert className="mt-3" overlay />
        <CaughtUpNotice />
        {mobile && <div className="mt-4 flex justify-center">{panelTabs}</div>}
      </aside>
      {!mobile && (
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex h-14 shrink-0 items-center border-b border-line px-6">{panelTabs}</div>
          <div className="min-h-0 flex-1">{panelBody}</div>
        </div>
      )}
    </section>
  );
}
