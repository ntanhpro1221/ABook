import { S } from "../shared/strings.generated";
import { TickingValue } from "@/shared/TickingValue";
import { ActionMenu } from "@/shared/ActionMenu";
import { MotionRegion } from "@/shared/MotionRegion";
import { Fold } from "@/shared/Collapse";
import { AnimatedRows, LoadingCrossfade, MotionPresence } from "@/shared/MotionPresence";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, AudioLines, BookOpen, BookOpenText, Check, CheckCheck, ChevronDown, CircleDashed, CloudDownload, FileDown, GitMerge, History, Hourglass, Laptop, Loader2, MoreHorizontal, Pause, Pencil, Play, Plus, RotateCcw, Save, Search, Share2, SlidersHorizontal, TextCursorInput, Trash2, UserRound } from "lucide-react";
import { memo, useId, Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState, type ButtonHTMLAttributes, type CSSProperties, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "@/shared/toast";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { SCREEN_TITLE, ScreenHeader } from "@/shared/ScreenHeader";
import { syncsToComputer } from "@/shared/capabilities";
import { usePageTitle } from "@/shared/title";
import { reveal, saveScroll, scrollParent, useScrollMemory } from "@/shared/scrollMemory";
import { chapterAnchor, placeChapterAnchor, type ChapterAnchor } from "./bookAnchor";
import { useElementWidth } from "@/shared/elementWidth";
import { useFadeScroller } from "@/shared/scrollFade";
import { useListPresence } from "@/shared/motion";
import { Windowed } from "@/shared/Windowed";
import { formatClock, formatLength, formatNumber } from "@/shared/format";
import { DialogActions, Select, SelectionMark, Button, Dialog, EmptyState, heardBarProps, IconButton, Progress, Skeleton, Tabs, TabsContent, TabsList, TabsPanels, TabsTrigger, Tooltip, Vu } from "@/shared/ui";
import { GenderDialog, RenamePersonDialog } from "@/studio/CastEdits";
import { MergeDialog } from "@/studio/MergePeople";
import { useClip } from "./clip";
import { FindInBook } from "./FindInBook";
import { canEditBook, EditBlockedItem, EditBookDialog, refreshAfterEdit, RenameChapterDialog, SaveAsDialog, StudioOnlyItem, useSaveBook, useShareBook } from "./EditBook";
import { bookStatusText, remoteUnfinishedLine, usePlayListenBook, useResumeTarget } from "./LibraryScreen";
import { canPlay, chapterHeard, chapterResumeAt, chaptersByPart, type CastMember, type ListenBook, type ListenChapter, voiceName } from "./model";
import { chapterSubline, displayTitle, keepTogether, partialBookLine, primaryListenLabel, textBookLine } from "./labels";
import { useNowPlaying, usePlayer } from "./player";
import { usePreparedChapters } from "./PlayerViews";
import { EditsNoticesBanner, EditsSyncBanner, LocalEditsBanner, SendEditsItem } from "./SendEdits";
import { PlaylistSubmenu } from "./PlaylistChoice";
import { ProjectFileItems, ProjectViewsDialog, TextBookItems } from "./ProjectFileItems";
import { BookSuggestions } from "./ReadingSuggestions";
import { WishesDialog } from "./WishesDialog";
import { isMissing, useCast, useListenBook, useListenLibrary, useListenMutations, useSource, useWarmVoice } from "./source";
import { latestReading } from "./readingPosition";
import { moreMenuHasItems } from "./bookMenu";
import { withFeedback } from "@/shared/feedback";
import { ActionButton } from "./ActionButton";
import { DotJoin } from "@/shared/DotJoin";
import { WIDTH_FROM, widthAtLeast } from "@/shared/widthClass.generated";

/** Trang sách chia hai cột từ khổ expanded của bề rộng NỘI DUNG (sau thanh bên): bìa + thông tin một bên, danh sách chương một bên, cuộn riêng từng bên.
 *  Cùng ngưỡng, cùng tỉ lệ với Qt (BookPage.qml: Theme.widthExpanded, leftWidth, listMeasure). Hẹp hơn: một cột như cũ. */
const BOOK_LIST_MEASURE = 640;
/** Bề rộng cột trái (bìa + thông tin): 320 ở 840, rộng thêm 6 % phần dư, tối đa 380 (Qt BookPage.qml leftWidth). */
export function bookLeftWidth(content: number): number {
  return Math.min(380, 320 + Math.max(0, content - WIDTH_FROM.expanded) * 0.06);
}

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** Việc của một hàng chương. Một đối tượng cố định cho cả danh sách (useChapterActions): hàng nhớ (memo) không vẽ lại chỉ vì hàm mới. */
export interface ChapterActions {
  /** Nghe chương từ giây `at`; chương đang nạp trong trình phát thì phát / tạm dừng. */
  play: (chapter: ListenChapter, at: number) => void;
  toggle: () => void;
  /** Mở trình phát (hàng chương đang nạp). */
  open: () => void;
  read: (chapter: ListenChapter) => void;
  done: (chapterId: number, done: boolean) => void;
  rename: (chapter: ListenChapter) => void;
}

/** Hành động của hàng chương cho cuốn `book`: luôn cùng một đối tượng, gọi tới bản mới nhất của trình phát / cuốn / hàm truyền vào. */
function useChapterActions(book: ListenBook, onDone: (chapterId: number, done: boolean) => void, onRename?: (chapter: ListenChapter) => void): ChapterActions {
  const player = usePlayer();
  const playBook = usePlayListenBook();
  const navigate = useNavigate();
  const { setExpanded } = useNowPlaying();
  const live = useRef({ book, player, playBook, navigate, setExpanded, onDone, onRename });
  live.current = { book, player, playBook, navigate, setExpanded, onDone, onRename };
  return useMemo<ChapterActions>(() => ({
    play: (chapter, at) => void live.current.playBook(live.current.book, chapter.id, at),
    toggle: () => live.current.player.toggle(),
    open: () => live.current.setExpanded(true),
    read: (chapter) => live.current.navigate(`/book/${live.current.book.id}/read/${chapter.id}`),
    done: (chapterId, done) => live.current.onDone(chapterId, done),
    rename: (chapter) => live.current.onRename?.(chapter),
  }), []);
}

/** Một hàng chương với dữ liệu lấy thẳng từ cuốn và trình phát (dùng riêng lẻ). Danh sách dùng ChapterLine: mỗi hàng chỉ nhận phần của nó. */
export function ChapterRow({
  book,
  chapter,
  onDone,
  onRename,
  prepared = false,
}: {
  book: ListenBook;
  chapter: ListenChapter;
  /** "Làm trước" đã đọc sẵn chương này bằng giọng của cuốn: nghe ngay, không cần mạng hay chờ. */
  prepared?: boolean;
  onDone: (chapterId: number, done: boolean) => void;
  /** Sách sửa được trên máy này (shared/capabilities.ts): "Đổi tên chương…" - cái tên hiện trên màn hình, không đổi audio. */
  onRename?: (chapter: ListenChapter) => void;
}) {
  const player = usePlayer();
  const actions = useChapterActions(book, onDone, onRename);
  const current = player.track?.bookId === book.id && player.track.chapterId === chapter.id;
  return (
    <ChapterLine
      chapter={chapter}
      heard={chapterHeard(book.state, chapter)}
      heardSeconds={chapterResumeAt(book.state, chapter)}
      current={current}
      playing={current && player.playing}
      producing={book.producing}
      prepared={prepared}
      renamable={Boolean(onRename)}
      actions={actions}
    />
  );
}

/** Hàng chương nhớ (memo): trình phát đổi trạng thái, cuốn được hỏi lại (tiến độ mới), danh sách cuộn - chỉ hàng có giá trị đổi vẽ lại
 *  (trang sách 2500 chương từng vẽ lại cả 80 hàng đang dựng mỗi lần phát / dừng - docs/PERF_WEB.md). */
const ChapterLine = memo(function ChapterLine({
  chapter,
  heard,
  heardSeconds,
  current,
  playing,
  producing,
  prepared,
  renamable,
  actions,
}: {
  chapter: ListenChapter;
  /** Phần đã nghe (0..1; 1 = đã nghe xong). */
  heard: number;
  /** Giây đã nghe (nghe tiếp từ đây khi chương nghe dở). */
  heardSeconds: number;
  current: boolean;
  playing: boolean;
  producing: boolean;
  prepared: boolean;
  renamable: boolean;
  actions: ChapterActions;
}) {
  const done = heard >= 1;
  const onPlay = () => {
    if (!canPlay(chapter)) return;
    if (current) actions.toggle();
    // Cùng luật với "Nghe tiếp" (model.chapterResumeAt): còn vài giây cuối thì nghe lại từ đầu chương, không phát giây cuối rồi nhảy sang chương kế.
    else actions.play(chapter, heardSeconds);
  };
  const name = chapter.subtitle || chapter.title;
  return (
    <MotionRegion as="div"
      // Hàng đang phát: chữ màu nhấn + vạch tiến độ mảnh, không tô nền cả hàng (docs/DESIGN.md mục 6).
      // Biểu tượng hai đầu thẳng mép nội dung như tab và nút chính (soát 24-10): lề âm bù đệm hàng, nút hai đầu bù nửa phần nền chạm thừa
      // quanh biểu tượng 14 px (nút phát size-9 = 31,5 px, màn chạm 48 px; nút "…" size-8 = 28 px). Điện thoại hết chỗ cho lề âm (nút 48 px sẽ
      // lòi khỏi màn): biểu tượng dồn về mép ngoài của nút. Nền rê chuột tràn ra lề.
      className={cn(
        "group -mx-2 flex items-center gap-3 rounded-control px-2 py-2.5 transition-colors duration-motion-fast sm:-mx-3 sm:px-3",
        canPlay(chapter) && "hover:bg-hover",
      )}
    >
      <button
        type="button"
        onClick={onPlay}
        disabled={!canPlay(chapter)}
        aria-label={playing ? S.s_tam_dung_0_43ccbbf2(chapter.fullTitle) : S.s_nghe_0_42d1e966(chapter.fullTitle)}
        className="touch-hit touch-box -ml-[8.75px] grid size-9 shrink-0 place-items-center rounded-full text-fg-2 max-sm:ml-0 max-sm:!min-w-0 max-sm:!justify-start sm:pointer-coarse:-ml-[17px] hover:bg-panel hover:text-fg disabled:text-fg-3 disabled:hover:bg-transparent"
      >
        {playing ? (
          <Vu className="h-3 text-accent" />
        ) : done ? (
          <Check className="size-4 text-success" strokeWidth={3} aria-label={S.s_da_nghe_1e0f8d88} />
        ) : canPlay(chapter) ? (
          <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
        ) : (
          <CircleDashed className="size-4" />
        )}
      </button>
      {/* Chương chưa có audio vẫn đọc được: bấm vào dòng là mở màn đọc (soát UX 29-09 - trước đây cả dòng bị vô hiệu, chỉ
          nút "…" hiện khi rê chuột mới có "Đọc chương này"). Chương đang nạp: bấm vào dòng mở trình phát, nút bên trái vẫn phát / dừng (DESIGN.md L3b). */}
      <button
        type="button"
        onClick={!canPlay(chapter) ? () => actions.read(chapter) : current ? actions.open : onPlay}
        aria-label={!canPlay(chapter) ? S.s_doc_0_chua_co_audio_baeeb512(chapter.fullTitle) : current ? S.s_mo_man_hinh_dang_nghe_2426b4ad : undefined}
        // Nghe được thì nút tên làm đúng việc của nút phát bên trái: bàn phím dừng ở nút phát (đã có tên đầy đủ), chuột vẫn bấm cả dòng.
        tabIndex={canPlay(chapter) && !current ? -1 : undefined}
        className="touch-hit min-w-0 flex-1 text-left"
      >
        <div className={cn("break-words text-sm font-medium", current && "text-accent-text", (done || !canPlay(chapter)) && !current && "text-fg-2")}>
          {name}
        </div>
        {/* min-h 1rem (= một dòng text-xs): dòng phụ luôn giữ chỗ - chương có audio rồi hàng không cao thêm, và mọi hàng cùng nhịp. */}
        <div className="min-h-[1rem] break-words text-xs text-fg-2">
          {chapterSubline(chapter, producing)}
          {prepared && (
            <span className="ml-1.5 inline-flex items-center gap-0.5 rounded-control bg-accent-soft px-1 align-[1px] text-[0.6875rem] font-medium text-accent-text">
              <CloudDownload className="size-3" aria-hidden />{S.s_da_lam_san_18d7d0da}</span>
          )}
        </div>
        {heard > 0 && heard < 1 && (
          <div {...heardBarProps(heard)} className="mt-1.5 h-[3px] w-24 overflow-hidden rounded-full bg-line-strong">
            <div className="motion-progress h-full bg-accent" style={{ transform: `scaleX(${heard * 100 / 100})` }} />
          </div>
        )}
      </button>
      <div className="-mr-[7px] size-8 shrink-0 max-sm:mr-0 max-sm:size-[48px]">
        <ChapterMenu chapter={chapter} done={done} renamable={renamable} actions={actions} />
      </div>
    </MotionRegion>
  );
});

/** Nút "…" của hàng chương và menu của nó. Menu Radix (~20 component mỗi hàng) chỉ dựng khi cần: trước đó là một nút trơn cùng hình, cùng
 *  thuộc tính (aria-haspopup, data-state) - rê chuột tới hay Tab vào thì dựng menu thật ngay (tiêu điểm giữ ở nút), bấm thẳng (màn cảm ứng)
 *  thì dựng và mở luôn. Danh sách 2500 chương: dựng / cuộn một khối 40 hàng bớt hơn nửa số component (docs/PERF_WEB.md). */
function ChapterMenu({ chapter, done, renamable, actions }: { chapter: ListenChapter; done: boolean; renamable: boolean; actions: ChapterActions }) {
  const [armed, setArmed] = useState(false);
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  // Tiêu điểm vừa vào nút trơn: nút thật thay chỗ nó, đưa tiêu điểm sang (Enter / Space / ↓ của Radix chạy như mọi menu khác).
  useLayoutEffect(() => {
    if (!armed || !refocus.current) return;
    refocus.current = false;
    trigger.current?.focus();
  }, [armed]);
  const button = (extra: ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button
      ref={trigger}
      type="button"
      aria-label={S.s_them_tuy_chon_cho_0_82a2cf4d(chapter.fullTitle)}
      aria-haspopup="menu"
      aria-expanded={open}
      data-state={open ? "open" : "closed"}
      className="grid size-8 place-items-center rounded-control text-fg-2 opacity-0 transition-[opacity,color,background-color] duration-motion-fast hover:bg-panel hover:text-fg group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100 max-sm:size-[48px] max-sm:justify-items-end"
      {...extra}
    >
      <MoreHorizontal className="ink-end size-4" />
    </button>
  );
  if (!armed) {
    return button({
      onPointerEnter: () => setArmed(true),
      onFocus: () => {
        refocus.current = true;
        setArmed(true);
      },
      // Như nút mở của Radix: chuột trái (không Ctrl) mở ngay lúc nhấn, không lấy tiêu điểm.
      onPointerDown: (event) => {
        if (event.button !== 0 || event.ctrlKey) return;
        event.preventDefault();
        setOpen(true);
        setArmed(true);
      },
    });
  }
  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger asChild>{button({})}</DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-52 rounded-cover border border-line bg-panel p-1.5 shadow-float">
          {canPlay(chapter) && (
            <DropdownMenu.Item onSelect={() => actions.play(chapter, 0)} className={MENU_ITEM}>
              <Play className="size-4" />{S.s_nghe_tu_dau_chuong_d35ec3e0}</DropdownMenu.Item>
          )}
          <DropdownMenu.Item onSelect={() => actions.read(chapter)} className={MENU_ITEM}>
            <BookOpen className="size-4" />{S.s_doc_chuong_nay_b70e10a7}</DropdownMenu.Item>
          {canPlay(chapter) && (
            <DropdownMenu.Item onSelect={() => actions.done(chapter.id, !done)} className={MENU_ITEM}>
              {done ? <CircleDashed className="size-4" /> : <CheckCheck className="size-4" />}
              {done ? S.s_chua_nghe_2fbea4c8 : S.s_da_nghe_xong_d276b702}
            </DropdownMenu.Item>
          )}
          {renamable && (
            <DropdownMenu.Item onSelect={() => actions.rename(chapter)} className={MENU_ITEM}>
              <TextCursorInput className="size-4" />{S.s_doi_ten_chuong_9fe7f4f4}</DropdownMenu.Item>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function ChapterGroups({ book, currentChapter, onDone, onRename, prepared, layout }: {
  book: ListenBook; currentChapter?: number; onDone: (chapterId: number, done: boolean) => void;
  onRename?: (chapter: ListenChapter) => void; prepared?: Set<number>;
  /** Bố cục của trang chứa danh sách (đổi thì khung cuộn đổi chỗ): Windowed quan sát lại khung mới. */
  layout?: string;
}) {
  const chapters = book.chapters ?? [];
  const groups = chaptersByPart(chapters, book.parts);
  const actions = useChapterActions(book, onDone, onRename);
  const list = { book, actions, renamable: Boolean(onRename), prepared, currentChapter, layout };
  // Sách không chia phần: một danh sách phẳng ngay dưới tab - không gấp trong một khối "Danh sách chương" lặp lại tên tab.
  if (groups.length === 1 && !groups[0].heading) {
    return <div className="mt-2"><ChapterGroupList {...list} chapters={groups[0].chapters} memory={`book.${book.id}.0`} /></div>;
  }
  return <>{groups.map((group, index) => (
            <Fold key={group.heading ?? index} storageKey={`book.${book.id}.chapters.${index}`} title={group.heading || S.s_danh_sach_chuong_7fa755f9} summary={S.s_0_chuong_1_6fd924b9(group.chapters.length, group.chapters.some(chapter => chapter.id === currentChapter) ? S.s_dang_nghe_a38a21a6 : "")} defaultOpen={group.chapters.length <= 4 || group.chapters.some(chapter => chapter.id === currentChapter)} onOpened={(element) => {
              const row = element.querySelector(`[data-chapter="${CSS.escape(String(currentChapter))}"]`);
              if (row && !row.closest("[inert]")) reveal(scrollParent(row), row);
            }} heading="h3" className="mt-3">
              <ChapterGroupList {...list} chapters={group.chapters} heading={group.heading} memory={`book.${book.id}.${index}`} />
            </Fold>
          ))}</>;
}

/** Sách vài nghìn chương: chỉ dựng các chương gần màn hình (shared/Windowed); chương đang nghe luôn có sẵn. Chương mới về (sách đang
 *  thu) hay bị gỡ: hàng mở ra / khép lại tại chỗ (useListPresence, như kệ sách của thư viện), không nhảy cả danh sách. */
function ChapterGroupList({ book, chapters, heading, memory, currentChapter, actions, renamable, prepared, layout }: {
  book: ListenBook; chapters: ListenChapter[]; heading?: string | null; memory: string; currentChapter?: number;
  actions: ChapterActions; renamable: boolean; prepared?: Set<number>; layout?: string;
}) {
  const player = usePlayer();
  const rows = useListPresence(chapters, (chapter) => String(chapter.id));
  const positions = useMemo(() => new Map(chapters.map((chapter, index) => [chapter.id, index + 1])), [chapters]);
  const playingChapter = player.track?.bookId === book.id ? player.track.chapterId : undefined;
  return (
    <div role="list" aria-label={heading ?? S.s_danh_sach_chuong_7fa755f9}>
      <Windowed
        items={rows}
        estimate={54}
        memory={memory}
        layout={layout}
        keep={rows.findIndex((row) => row.item.id === currentChapter)}
        row={({ key, item: chapter, state, ref }) => (
          <div key={key} ref={ref} role="listitem" aria-posinset={positions.get(chapter.id)} aria-setsize={chapters.length} data-chapter={chapter.id} className="motion-row" data-state={state} inert={state === "exit"}>
            <ChapterLine
              chapter={chapter}
              heard={chapterHeard(book.state, chapter)}
              heardSeconds={chapterResumeAt(book.state, chapter)}
              current={chapter.id === playingChapter}
              playing={chapter.id === playingChapter && player.playing}
              producing={book.producing}
              prepared={chapter.state === "text" && Boolean(prepared?.has(chapter.id))}
              renamable={renamable}
              actions={actions}
            />
          </div>
        )}
      />
    </div>
  );
}

export function SampleButton({ id, url, label }: { id: string; url: string; label: string }) {
  const clip = useClip();
  const active = clip.current === id;
  return (
    <Tooltip label={active ? S.s_dung_11554138 : label}>
      <button
        type="button"
        aria-label={active ? S.s_dung_nghe_thu_41a2925b : label}
        onClick={() => clip.toggle(id, url)}
        className={cn(
          // Cuối hàng: bù nửa phần ô 36 px rộng hơn icon 16 px để mực ▶ chạm mép cột như chữ các hàng khác (máy dò trailing-control-inset).
          "touch-hit -mr-2.5 grid size-9 shrink-0 place-items-center rounded-full transition-colors",
          active ? "text-accent-text" : "text-fg-2 hover:bg-hover hover:text-fg",
        )}
      >
        <MotionRegion as="span" className="grid size-4 place-items-center">{active && clip.loading ? <Loader2 className="size-4 animate-spin" /> : active ? <Vu className="h-3" /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}</MotionRegion>
      </button>
    </Tooltip>
  );
}

export function hueOf(text: string): number {
  let value = 0;
  for (const char of text) value = (value * 31 + char.charCodeAt(0)) % 360;
  return value;
}

/** Tên hiển thị không lộ dữ liệu thô: gạch dưới thành dấu cách. */
export function cleanName(name: string): string {
  return name.replace(/_/g, " ").replace(/\s+/g, " ").trim();
}

export function PersonRow({
  bookId,
  person,
  onPickVoice,
  onMerge,
  onUnmerge,
  onRename,
  onGender,
  waiting,
}: {
  bookId: string;
  person: CastMember;
  top?: number;
  /** Cuốn không có xưởng: thay đổi người nghe ghi chỉ chờ Studio - dòng "Đang chờ Studio" thay cho "Chờ áp dụng". */
  waiting?: boolean;
  /** Chỉ Studio: mở màn "Đổi giọng" cho nhân vật (giọng ấy có từ bước phân vai). Người mang từ phần trước (0 câu) không có
   *  nút này và "Đổi giới tính": dây chuyền chỉ đổi giọng của người đã có câu (NO_VOICE), còn "Đổi tên" thì được. */
  onPickVoice?: (person: CastMember) => void;
  /** Chỉ Studio: "Gộp vào…" - máy tách một người thành hai tên. */
  onMerge?: (person: CastMember) => void;
  /** Chỉ Studio: "Bỏ gộp" - rút lần "Gộp vào…" đang chờ áp dụng của người này. */
  onUnmerge?: (person: CastMember) => void;
  /** Chỉ Studio: "Đổi tên" - tên trên màn hình, không đổi gì trong audio. */
  onRename?: (person: CastMember) => void;
  /** Chỉ Studio: "Đổi giới tính" - một thay đổi chờ "Áp dụng thay đổi" (POST /voice). */
  onGender?: (person: CastMember) => void;
}) {
  const source = useSource();
  const name = cleanName(person.displayName);
  // "Gộp vào người khác…" nằm trong menu "…" của người (chữ hiện sẵn) - nút chỉ-biểu-tượng cạnh các nút khác không ai đoán được.
  const canMerge = Boolean(onMerge) && person.lines > 0;
  const initials = name
    .split(/\s+/)
    .filter((word) => !/^[IVXLCDM]+$/.test(word))
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
  return (
    // min-w-0: ô lưới mặc định không co dưới chiều rộng nội dung - tên dài từng đẩy "Đổi giọng" ra ngoài màn 375px.
    <MotionRegion as="div" className="flex min-w-0 items-center gap-3 py-3">
      <div
        className="avatar grid size-10 shrink-0 place-items-center rounded-full text-sm font-bold"
        style={{ ["--hue" as string]: hueOf(person.voice?.preset ?? person.name) }}
        aria-hidden
      >
        {initials}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          {/* Tên và giọng xuống dòng thay vì cắt: "Thanh Bình · trầm hẳn" cắt giữa chừng là mất đúng chữ người nghe cần (soát UX a8). */}
          <span className="min-w-0 break-words font-semibold">{name}</span>
          {person.gender && <span className="shrink-0 text-xs text-fg-2">{person.gender}</span>}
        </div>
        {person.originalName && <div className="break-words text-xs text-fg-3">{S.s_ten_goc_ece0e59a}{cleanName(person.originalName)})</div>}
        <div className="mt-0.5 break-words text-xs text-fg-2">
          <AudioLines className="mr-1 inline size-3.5 -translate-y-px text-fg-3" />
          {person.voice ? voiceName(person.voice) : S.s_chua_co_giong_7ce5f4b4}
        </div>
        {/* Việc của Studio (giọng người nghe đã chọn, chưa áp) - trang nghe không cần (soát UX 29-09). */}
        {person.pendingVoice && (onPickVoice || waiting) && (
          <div className="mt-0.5 truncate text-xs font-medium text-accent-text">
            {waiting ? S.s_dang_cho_may_lam_sach_bad9fc96 : S.s_cho_ap_dung_77a52853}:{" "}
            {[person.pendingVoice.preset && S.s_giong_0_e048b478(voiceName(person.pendingVoice)), person.pendingVoice.gender.toLowerCase()]
              .filter(Boolean)
              .join(" · ")}
          </div>
        )}
        {person.mergedInto && (onPickVoice || waiting) && (
          <div className="mt-0.5 break-words text-xs font-medium text-accent-text">
            {waiting ? S.s_dang_cho_may_lam_sach_bad9fc96 : S.s_cho_ap_dung_77a52853}{S.s_gop_vao_6f4014d0}{cleanName(person.mergedInto)}
            {onUnmerge && typeof person.mergedAt === "number" && (
              <button
                type="button"
                className="ml-2 rounded-control font-medium underline underline-offset-2 hover:text-fg"
                aria-label={S.s_bo_gop_0_vao_1_46630ca2(name, cleanName(person.mergedInto))}
                onClick={() => onUnmerge(person)}
              >{S.s_bo_gop_d7199137}</button>
            )}
          </div>
        )}
        <div className="mt-1 text-xs text-fg-2">
          {formatNumber(person.lines)}{S.s_cau_b07e1008}{person.seconds > 0 ? ` · ${formatLength(person.seconds)}` : ""}
          {person.firstChapter ? S.s_tu_0_4f683e5d(keepTogether(person.firstChapter)) : ""}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {person.sampleId ? <SampleButton id={`sample-${bookId}-${person.sampleId}`} url={source.sampleUrl(bookId, person.sampleId)} label={S.s_nghe_0_noi_e9307f6f(name)} /> : null}
        {onPickVoice && person.voice && person.lines > 0 ? (
          <IconButton label={S.s_doi_giong_0_0e34c43b(name)} icon={SlidersHorizontal} size="sm" onClick={() => onPickVoice(person)} />
        ) : null}
        {onRename || onGender || canMerge ? (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                aria-label={S.s_them_tuy_chon_cho_0_82a2cf4d(name)}
                className="grid size-8 place-items-center rounded-control text-fg-2 hover:bg-hover hover:text-fg data-[state=open]:bg-hover"
              >
                <MoreHorizontal className="size-4" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content collisionPadding={12} align="end" sideOffset={4} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain min-w-48 rounded-cover border border-line bg-panel p-1.5 shadow-float">
                {canMerge && (
                  <DropdownMenu.Item onSelect={() => onMerge?.(person)} className={MENU_ITEM}>
                    <GitMerge className="size-4" />{S.s_gop_vao_nguoi_khac_2d232c7b}</DropdownMenu.Item>
                )}
                {onRename && (
                  <DropdownMenu.Item onSelect={() => onRename(person)} className={MENU_ITEM}>
                    <TextCursorInput className="size-4" />{S.s_doi_ten_ea9267a1}</DropdownMenu.Item>
                )}
                {onGender && person.voice && person.lines > 0 && (
                  <DropdownMenu.Item onSelect={() => onGender(person)} className={MENU_ITEM}>
                    <UserRound className="size-4" />{S.s_doi_gioi_tinh_b6d7da31}</DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        ) : null}
      </div>
    </MotionRegion>
  );
}

function ahead(people: CastMember[], reached: Set<string>): number {
  return people.filter((person) => person.firstChapter && !reached.has(person.firstChapter)).length;
}

/** Tên (ngắn và đầy đủ) của các chương từ đầu tới chương `until` (chưa nghe gì: tới chương đầu). */
function reachedTitles(chapters: ListenChapter[], until: number | undefined): Set<string> {
  const titles = new Set<string>();
  const last = until ?? chapters[0]?.id;
  for (const chapter of chapters) {
    titles.add(chapter.title);
    titles.add(chapter.fullTitle);
    if (chapter.id === last) break;
  }
  return titles;
}

/** `reached`: tên các chương tới chỗ đang nghe (trang nghe) - người chỉ xuất hiện SAU đó bị ẩn tới khi bấm hiện, để dàn nhân
 *  vật không lộ nội dung ("Douglas · từ Chương 738" khi đang nghe Chương 725 - soát UX 29-09). Studio không truyền: hiện hết. */
export function CastList({ bookId, onPickVoice, onPickNarrator, onMerge, onUnmerge, onRename, onGender, reached, waiting, narratorNote }: {
  bookId: string;
  /** Dưới hàng "Người kể chuyện": đổi giọng kể ở đâu, hay vì sao chưa đổi được. */
  narratorNote?: ReactNode;
  /** Chỉ Studio, sách đã phân vai: mở màn "Đổi giọng" cho người kể (như nhân vật - câu kể đã thu được thu lại). */
  onPickNarrator?: () => void;
  onPickVoice?: (person: CastMember) => void;
  onMerge?: (person: CastMember) => void;
  onUnmerge?: (person: CastMember) => void;
  onRename?: (person: CastMember) => void;
  onGender?: (person: CastMember) => void;
  reached?: Set<string>;
  /** Cuốn không có xưởng: đổi giới tính, gộp người ghi thành ý muốn chờ Studio (docs/EDITING.md, P2a). */
  waiting?: boolean;
}) {
  const source = useSource();
  const { data: cast, isLoading } = useCast(bookId);
  const [later, setLater] = useState(false);
  const carriedPeople = onPickVoice ? (cast?.carried ?? []) : [];
  if (isLoading) return <MotionRegion as="div" className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="h-[84px] rounded-cover" />)}</MotionRegion>;
  if (!cast || (!cast.characters.length && !cast.extras.length && !carriedPeople.length)) {
    return (
      <MotionRegion><EmptyState icon={AudioLines} title={S.s_chua_co_dan_nhan_vat_6f7729cd} className="mt-2">{S.s_dan_nhan_vat_hien_ra_khi_truyen_da_duoc_ph_dacb7364}</EmptyState></MotionRegion>
    );
  }
  return (
    <MotionRegion as="div" className="motion-reveal mt-4">
      <div className="flex items-center gap-3 py-2">
        <div className="grid size-10 place-items-center rounded-full bg-accent-soft text-accent-text">
          <BookOpenText className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="label-section text-fg-2">{S.s_nguoi_ke_chuyen_c0c2c504}</div>
          <div className="mt-0.5 font-semibold">{cast.narrator.voice || S.s_mac_dinh_9a1af367}</div>
          {cast.narrator.chapterVoices?.map(line => <div key={line} className="mt-0.5 text-xs text-fg-2">{line}</div>)}
          {onPickNarrator && cast.narrator.pendingVoice?.preset && (
            <div className="mt-0.5 truncate text-xs font-medium text-accent-text">{S.s_cho_ap_dung_giong_82c96902}{voiceName(cast.narrator.pendingVoice)}</div>
          )}
          <div className="text-xs text-fg-2">{formatNumber(cast.narrator.lines)}{S.s_cau_dan_truyen_f0d4156b}{cast.narrator.seconds > 0 ? ` · ${formatLength(cast.narrator.seconds)}` : ""}
            {/* Sau "Áp dụng" đổi giọng kể: các câu đã thu chờ thu lại bằng giọng mới (soát UX a24). */}
            {cast.narrator.redo ? S.s_0_cau_cho_thu_lai_e42ce3ef(formatNumber(cast.narrator.redo)) : ""}</div>
        </div>
        {cast.narrator.voice && <SampleButton id={`voice-${cast.narrator.voice}`} url={source.voiceUrl(cast.narrator.voice)} label={S.s_nghe_giong_0_1b667018(cast.narrator.voice)} />}
        {onPickNarrator && <IconButton label={S.s_doi_giong_nguoi_ke_c2afb757} icon={SlidersHorizontal} size="sm" onClick={onPickNarrator} />}
      </div>
      {narratorNote && <div className="mt-2 text-xs text-fg-2">{narratorNote}</div>}
      <Fold storageKey={`book.${bookId}.cast`} title={S.s_vai_chinh_b84f4098} summary={S.s_0_nguoi_co_loi_thoai_1e48f89a(cast.characters.length)} defaultOpen={cast.characters.length <= 4} className="mt-4">
      {/* "Hiện / Ẩn chương sau": người của các chương sau mở / khép tại chỗ (hàng tự mờ khi đổi giọng - PersonRow là một vùng), không mờ cả tab. */}
      <div data-motion-live="">
      <AnimatedRows
        className="grid gap-x-8 sm:grid-cols-2 xl:grid-cols-3"
        items={cast.characters.filter((person) => later || !reached || !person.firstChapter || reached.has(person.firstChapter))}
        keyOf={(person) => person.name}
      >
        {(person) => <PersonRow bookId={bookId} person={person} onPickVoice={onPickVoice} onMerge={onMerge} onUnmerge={onUnmerge} onRename={onRename} onGender={onGender} waiting={waiting} />}
      </AnimatedRows>
      </div>
      <MotionPresence open={Boolean(reached && ahead(cast.characters, reached) > 0)}>
        <button type="button" onClick={() => setLater((value) => !value)} className="touch-row mt-3 text-sm font-medium text-fg-2 hover:text-fg">
          <MotionRegion as="span">{later ? S.s_an_chuong_sau_97c9aacb : S.s_hien_chuong_sau_81aa431a} · {reached ? ahead(cast.characters, reached) : 0}{S.s_nguoi_dfc3c5c7}</MotionRegion>
        </button>
      </MotionPresence>
      </Fold>
      {cast.extras.length > 0 && (
        <Fold storageKey={`book.${bookId}.extras`} title={S.s_vai_phu_6e7c6bce} summary={S.s_0_nguoi_trong_mot_canh_bb4fd602(cast.extras.length)} className="mt-4">
          <div className="grid gap-x-8 sm:grid-cols-2 xl:grid-cols-3">{cast.extras.map((person) => <PersonRow key={person.name} bookId={bookId} person={person} onPickVoice={onPickVoice} onMerge={onMerge} onUnmerge={onUnmerge} onRename={onRename} onGender={onGender} waiting={waiting} />)}</div>
        </Fold>
      )}
      {/* Phần nối tiếp: dàn mang sang chưa nói ở phần này (soát UX a6 01-10, B2 - tab từng ghi "Chưa có dàn"). Mở sẵn khi chưa ai
          nói câu nào - lúc ấy đây là cả dàn. */}
      {carriedPeople.length > 0 && (
        <Fold storageKey={`book.${bookId}.carried`} title={S.s_tu_phan_truoc_aaf26cfe} summary={S.s_0_nguoi_chua_xuat_hien_e84c0de4(carriedPeople.length)} defaultOpen={!cast.characters.length && carriedPeople.length <= 4} className="mt-4">
            <div className="mt-3 grid gap-x-8 sm:grid-cols-2 xl:grid-cols-3">
              {carriedPeople.map((person) => <PersonRow key={person.name} bookId={bookId} person={person} onPickVoice={onPickVoice} onRename={onRename} onGender={onGender} />)}
            </div>
        </Fold>
      )}
    </MotionRegion>
  );
}

const TABS = ["chapters", "history", "cast"] as const;

function dayLabel(epoch: number): string {
  const date = new Date(epoch * 1000);
  const today = new Date();
  const days = Math.round(
    (new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() - new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) /
      86_400_000,
  );
  if (days === 0) return S.s_hom_nay_e6747a82;
  if (days === 1) return S.s_hom_qua_89bca9be;
  return date.toLocaleDateString("vi-VN", { weekday: "long", day: "numeric", month: "numeric" });
}

function clockOf(epoch: number): string {
  return new Date(epoch * 1000).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

/** Lịch sử nghe: mỗi phiên một dòng, gom theo ngày; bấm để nghe tiếp từ cuối phiên ấy. */
export function HistoryTab({ book }: { book: ListenBook }) {
  const source = useSource();
  const playBook = usePlayListenBook();
  const { data: sessions, isLoading } = useQuery({
    queryKey: ["listen", "sessions", book.id],
    queryFn: () => source.sessions!(book.id),
    enabled: Boolean(source.sessions),
  });
  const titleOf = (chapterId: number) => {
    const chapter = book.chapters?.find((item) => item.id === chapterId);
    return chapter ? chapter.title : S.s_chuong_da_go_d391d2d1;
  };
  // Đang hỏi lịch sử: khung chờ, không phải "Chưa có lịch sử nghe" (đọc như mất hết lịch sử) rồi mới thay bằng danh sách. Trống <-> có thì mờ hẳn qua.
  const placeholder = (
    <div className="mt-3 space-y-3" aria-hidden>
      <Skeleton className="h-4 w-56" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
  const historyBody = () => {
  if (!sessions?.length) {
    return (
      <EmptyState icon={History} title={S.s_chua_co_lich_su_nghe_5823581d} className="mt-2">{S.s_moi_luot_nghe_luu_lai_cho_ban_dung_4c3bdda1}</EmptyState>
    );
  }
  const week = sessions.filter((item) => Date.now() / 1000 - item.startedAt < 7 * 86_400).reduce((sum, item) => sum + item.listened, 0);
  const groups = new Map<string, typeof sessions>();
  [...sessions].reverse().forEach((item) => {
    const key = dayLabel(item.startedAt);
    groups.set(key, [...(groups.get(key) ?? []), item]);
  });
  return (
    <div className="mt-3">
      <p className="text-sm text-fg-2">{S.s_7_ngay_qua_70c6d33d}<span className="font-semibold text-fg">{formatLength(week)}</span>{S.s_nghe_cuon_nay_8e481d62}</p>
      {/* Nhóm ngày / lượt nghe mới thêm khi đang mở tab: mở ra tại chỗ (vùng ngoài chỉ khoá "có / không có"). */}
      <AnimatedRows items={[...groups.entries()]} keyOf={([day]) => day}>
      {([day, items]) => (
        <div className="pt-3">
        <Fold storageKey={`book.${book.id}.history.${day}`} title={day} summary={S.s_0_luot_nghe_6788e770(items.length)}>
          <AnimatedRows className="mt-2 divide-y divide-line" items={items} keyOf={(item) => String(item.id)}>
            {(item) => (
              <div className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">
                    {/* Cùng phút thì một mốc giờ, không "13:57-13:57" (soát UX 29-09). */}
                    {clockOf(item.startedAt) === clockOf(item.endedAt) ? clockOf(item.startedAt) : `${clockOf(item.startedAt)}-${clockOf(item.endedAt)}`} ·{" "}
                    {formatLength(item.listened)}
                  </div>
                  <div className="break-words text-xs text-fg-2">
                    {titleOf(item.from.chapterId)} {formatClock(item.from.seconds)} → {titleOf(item.to.chapterId)} {formatClock(item.to.seconds)}
                  </div>
                </div>
                {/* Nút nhảy tới CUỐI phiên nghe ấy - nói rõ tới đâu, "Nghe từ đây" mơ hồ (soát UX 29-09). */}
                <Button size="sm" variant="ghost" icon={Play} onClick={() => void playBook(book, item.to.chapterId, item.to.seconds)}>{S.s_nghe_tiep_tu_b61da900}{formatClock(item.to.seconds)}
                </Button>
              </div>
            )}
          </AnimatedRows>
        </Fold>
        </div>
      )}
      </AnimatedRows>
    </div>
  );
  };
  return (
    <LoadingCrossfade loading={isLoading} placeholder={placeholder}>
      <MotionRegion fadeThrough motionKey={sessions?.length ? "list" : "empty"}>{historyBody()}</MotionRegion>
    </LoadingCrossfade>
  );
}

type RecordDialog = { kind: "create" | "rename" | "delete" | "move"; name: string; target?: { id: string; title: string } } | null;

/** Hộp "Nghe lại từ đầu (hồ sơ mới)" mở sẵn tên gợi ý. */
function newRecordDialog(book: ListenBook): RecordDialog {
  return { kind: "create", name: S.s_lan_nghe_0_10ac9e59((book.records?.length ?? 0) + 1) };
}

/** Việc làm với hồ sơ nghe khi cuốn chỉ có MỘT hồ sơ (không có nút "Hồ sơ nghe:"): menu "Thêm" (…) liệt kê các việc này. Nhiều hồ sơ thì RecordPicker lo. */
export function singleRecordActions(book: ListenBook): { key: string; label: string; icon: typeof Plus; dialog: RecordDialog; danger?: boolean }[] {
  if (book.records?.length !== 1) return [];
  const name = book.records[0].name;
  return [
    { key: "create", label: S.s_ho_so_moi_5dfda9aa, icon: Plus, dialog: newRecordDialog(book) },
    { key: "move", label: S.s_chuyen_ho_so_a1c66184, icon: ArrowRightLeft, dialog: { kind: "move", name } },
    { key: "rename", label: S.s_doi_ten_ho_so_92440dab, icon: TextCursorInput, dialog: { kind: "rename", name } },
    { key: "delete", label: S.s_xoa_ho_so_38a06d83, icon: Trash2, dialog: { kind: "delete", name }, danger: true },
  ];
}

/** Chọn cuốn nhận hồ sơ: mọi cuốn trong thư viện trừ cuốn này. Chỉ hỏi thư viện lúc hộp đang mở. */
function MoveTarget({ book, value, onChange }: { book: ListenBook; value: string; onChange: (target: { id: string; title: string }) => void }) {
  const { data, isLoading } = useListenLibrary();
  const others = (data ?? []).filter((item) => item.id !== book.id);
  // Ba trạng thái (đang mở thư viện / chưa có cuốn nào khác / ô chọn) mờ qua tại chỗ trong hộp đang mở.
  return (
    <MotionRegion motionKey={isLoading ? "loading" : others.length ? "list" : "empty"}>
    {isLoading ? <p className="text-sm text-fg-2">{S.s_dang_mo_thu_vien_0faed631}</p> : !others.length ? <p className="text-sm text-fg-2">{S.s_thu_vien_chua_co_cuon_nao_khac_4bff3d9b}</p> : <Select
      aria-label={S.s_chuyen_sang_cuon_ffe90248}
      autoFocus
      value={value}
      onChange={(event) => {
        const chosen = others.find((item) => item.id === event.target.value);
        if (chosen) onChange({ id: chosen.id, title: chosen.title });
      }}

    >
      <option value="" disabled>{S.s_chon_cuon_34833868}</option>
      {others.map((item) => (
        <option key={item.id} value={item.id}>
          {item.title}
        </option>
      ))}
    </Select>}
    </MotionRegion>
  );
}

/**
 * Hồ sơ nghe của cuốn: dữ liệu nghe độc lập với sách, app giữ liên kết - một cuốn nhiều hồ sơ (nghe lại từ đầu mà giữ
 * lần trước, mỗi người trong nhà một hồ sơ). Cuốn đang nạp trong trình phát thì trình phát theo sang hồ sơ mới.
 * Chỉ có một hồ sơ (gần như mọi người): không hiện nút "Hồ sơ nghe: Mặc định"; "Hồ sơ mới" nằm trong menu "Thêm" (…)
 * (soát UX 03-10) - vì thế trang sách giữ `dialog`, menu ấy mở được cùng hộp.
 */
function RecordPicker({ book, dialog, setDialog }: { book: ListenBook; dialog: RecordDialog; setDialog: Dispatch<SetStateAction<RecordDialog>> }) {
  const dialogForm1 = useId();
  const source = useSource();
  const player = usePlayer();
  const navigate = useNavigate();
  const mutations = useListenMutations(book.id);
  const records = book.records ?? [];
  const active = records.find((record) => record.active);
  if (!source.records || !active) return null;
  const done = (message: string) => (promise: Promise<unknown>) =>
    promise.then(() => toast(message)).catch((error: unknown) => toast.error(error instanceof Error ? error.message : String(error)));
  const switchTo = (change: () => Promise<unknown>, message: string, startOver = false) =>
    void done(message)(player.switchRecord(book.id, change, startOver));
  const submit = () => {
    if (!dialog) return;
    const name = dialog.name.trim();
    if (dialog.kind === "create") switchTo(() => mutations.createRecord.mutateAsync(name), S.s_ho_so_moi_0_nghe_tu_chuong_dau_d9c8929e(name || S.s_khong_ten_7a5bff7f), true);
    if (dialog.kind === "rename" && name) void done(S.s_da_doi_ten_ho_so_543ec6a6)(mutations.renameRecord.mutateAsync({ recordId: active.id, name }));
    if (dialog.kind === "delete") switchTo(() => mutations.removeRecord.mutateAsync(active.id), S.s_da_xoa_ho_so_0_54dabd55(active.name));
    // Bản làm lại của cùng truyện, hay lỡ nghe nhầm cuốn: hồ sơ (chỗ nghe, lịch sử) sang cuốn kia, thành hồ sơ đang dùng ở đó.
    const target = dialog.target;
    if (dialog.kind === "move" && target) {
      void player
        .switchRecord(book.id, () => mutations.moveRecord.mutateAsync({ recordId: active.id, toBook: target.id }))
        .then(() =>
          toast(S.s_da_chuyen_ho_so_0_sang_1_607c3506(active.name, target.title), {
            action: { label: S.s_mo_cuon_ay_064ee566, onClick: () => navigate(`/book/${target.id}`) },
          }),
        )
        .catch((error: unknown) => toast.error(error instanceof Error ? error.message : String(error)));
    }
    setDialog(null);
  };
  return (
    <>
      {records.length > 1 && (
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            className="mt-3 inline-flex min-h-8 max-w-full items-center gap-1.5 rounded-full border-line px-3 py-1 text-left text-xs text-fg-2 hover:bg-hover hover:text-fg"
          >
            <UserRound className="size-3.5 shrink-0" />
            <span className="shrink-0">{S.s_ho_so_nghe_a80cbba0}</span>
            <span className="min-w-0 break-words font-medium text-fg">{active.name}</span>
            <ChevronDown className="size-3.5 shrink-0" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={6} collisionPadding={12} className="z-50 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto overscroll-contain w-72 rounded-cover border border-line bg-panel p-1.5 shadow-float">
            <p className="px-2 pb-1.5 pt-1 text-xs text-fg-2">{S.s_moi_ho_so_giu_cho_nghe_lich_su_rieng_c3195597}</p>
            {records.map((record) => (
              <DropdownMenu.Item
                key={record.id}
                onSelect={() => {
                  if (!record.active) switchTo(() => mutations.activateRecord.mutateAsync(record.id), S.s_dang_dung_ho_so_0_59e7b339(record.name));
                }}
                className={cn(MENU_ITEM, "h-auto py-1.5")}
              >
                <SelectionMark selected={record.active} />
                <span className="min-w-0 flex-1">
                  <span className="block text-pretty [overflow-wrap:anywhere]">{record.name}</span>
                  <span className="block text-xs text-fg-3">
                    {record.last
                      ? `${book.chapters?.find((chapter) => chapter.id === record.last!.chapterId)?.title ?? S.s_chuong_2d157977} · ${formatClock(record.last.seconds)} · `
                      : ""}
                    {record.updatedAt ? S.s_nghe_gan_nhat_0_3ef6d860(dayLabel(record.updatedAt).toLowerCase()) : S.s_chua_nghe_2d5b1cbe}
                  </span>
                </span>
              </DropdownMenu.Item>
            ))}
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
            <DropdownMenu.Item onSelect={() => setDialog(newRecordDialog(book))} className={MENU_ITEM}>
              <Plus className="size-4" />{S.s_ho_so_moi_b25fb2e0}</DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setDialog({ kind: "rename", name: active.name })} className={MENU_ITEM}>
              <TextCursorInput className="size-4" />{S.s_doi_ten_ho_so_9e97245a}</DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setDialog({ kind: "move", name: active.name })} className={MENU_ITEM}>
              <ArrowRightLeft className="size-4" />{S.s_chuyen_sang_cuon_khac_4cf6fce5}</DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setDialog({ kind: "delete", name: active.name })} className={cn(MENU_ITEM, "text-danger")}>
              <Trash2 className="size-4" />{S.s_xoa_ho_so_nay_59e25a25}</DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      )}
      <Dialog footer={<DialogActions>
            <Button type="button" variant="ghost" onClick={() => setDialog(null)}>{S.s_huy_96732485}</Button>
            <Button
              type="submit" form={dialogForm1}
              variant={dialog?.kind === "delete" ? "danger" : "primary"}
              disabled={(dialog?.kind === "rename" && !dialog.name.trim()) || (dialog?.kind === "move" && !dialog.target)}
            >
              {dialog?.kind === "create" ? S.s_tao_va_nghe_ee442c79 : dialog?.kind === "delete" ? S.s_xoa_ho_so_38a06d83 : dialog?.kind === "move" ? S.s_chuyen_c35a0ca1 : S.s_luu_e91f26c0}
            </Button>
          </DialogActions>}
        open={dialog !== null}
        onOpenChange={(open) => !open && setDialog(null)}
        title={
          dialog?.kind === "create"
            ? S.s_nghe_lai_tu_dau_e251d632
            : dialog?.kind === "rename"
              ? S.s_doi_ten_ho_so_92440dab
              : dialog?.kind === "move"
                ? S.s_chuyen_ho_so_0_sang_cuon_khac_dcb9ea1a(active.name)
                : S.s_xoa_ho_so_0_14007a36(active.name)
        }
        description={
          dialog?.kind === "create"
            ? S.s_ho_so_moi_nghe_tu_dau_ho_so_cu_van_giu_ngu_38f1a4a4
            : dialog?.kind === "move"
              ? S.s_cho_nghe_lich_su_di_theo_ho_so_sang_cuon_k_b4020c7a(records.length > 1 ? S.s_cuon_nay_chuyen_sang_ho_so_nghe_gan_nhat_c_93f8e93a : S.s_cuon_nay_se_nhu_chua_nghe_lan_nao_bae846d0)
            : dialog?.kind === "delete"
              ? S.s_cho_nghe_lich_su_cua_ho_so_nay_mat_han_tre_90bb23f3(records.length > 1 ? S.s_cuon_chuyen_sang_ho_so_nghe_gan_nhat_con_l_8cdb3e30 : S.s_day_la_ho_so_duy_nhat_nen_cuon_se_nhu_chua_75e8b48a)
              : undefined
        }
        width="max-w-md"
      >
        <form id={dialogForm1}
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
          className="flex flex-col gap-4"
        >
          {dialog?.kind === "move" && (
            <MoveTarget
              book={book}
              value={dialog.target?.id ?? ""}
              onChange={(target) => setDialog((current) => (current ? { ...current, target } : current))}
            />
          )}
          {dialog?.kind !== "delete" && dialog?.kind !== "move" && (
            <input
              id="record-name"
              data-autofocus
              autoFocus
              maxLength={60}
              aria-label={S.s_ten_ho_so_0ea145bd}
              placeholder={S.s_ten_ho_so_0ea145bd}
              value={dialog?.name ?? ""}
              onChange={(event) => setDialog((current) => (current ? { ...current, name: event.target.value } : current))}
              className="touch-box h-10 rounded-control border border-line bg-panel px-3 text-sm outline-none focus:border-focus"
            />
          )}

        </form>
      </Dialog>
    </>
  );
}

/** Sửa sách "áp ngay" trên trang nghe (EditBook.tsx). `false`: không cho sửa ở đây (thiết bị điều khiển từ xa). */
export interface EditingOptions {
  /** Máy tính trong cửa sổ app: chọn thư mục lưu file ("Lưu thành…"). Điện thoại để trống - hệ thống hỏi chỗ lưu. */
  pickFolder?: () => Promise<string | null>;
  /** Máy tính, cuốn có xưởng: mở tab Nhạc nền của Studio. */
  onOpenStudio?: (book: ListenBook) => void;
  /** Studio từ xa (remote_studio.ALLOWED): chỉ những sửa chỉ-là-chữ / ảnh bìa / nhạc nền / tên nhân vật chạy được trên máy tính; lưu thành file,
   *  gửi về, việc chờ Studio, file dự án đều là việc của chính máy tính - không hiện ở đây. */
  remote?: string;
}

type BookScreenProps = {
  extraActions?: (book: ListenBook) => ReactNode;
  dangerActions?: (book: ListenBook) => ReactNode;
  /** Máy tính: lối sang Studio ngay trên dòng trạng thái của sách đang làm. */
  studioLink?: (book: ListenBook) => ReactNode;
  /** Dòng tình trạng riêng của nền tảng dưới tên sách (máy tính: tải sách của máy khác về máy). */
  notice?: (book: ListenBook) => ReactNode;
  editing?: false | EditingOptions;
};

/** Mỗi cuốn một trang riêng: app chuyển thẳng từ /book/A sang /book/B (thông báo "Mở cuốn đó", chọn hồ sơ khác) thì hộp đang mở của A (đổi tên chương,
 *  tìm, sửa sách) không mang sang B - đổi tên chương của A từng gửi lên B theo số chương. */
export function BookScreen(props: BookScreenProps) {
  const { id } = useParams();
  return <BookPage key={id} {...props} />;
}

function BookPage({ extraActions, dangerActions, studioLink, notice, editing = {} }: BookScreenProps) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const requested = params.get("tab");
  const tab = TABS.includes(requested as (typeof TABS)[number]) ? (requested as string) : "chapters";
  const { data: book, isLoading, error } = useListenBook(id);
  const player = usePlayer();
  const { setExpanded } = useNowPlaying();
  const playBook = usePlayListenBook();
  const mutations = useListenMutations(id ?? "");
  const source = useSource();
  const client = useQueryClient();
  usePageTitle(book?.title);
  const [editOpen, setEditOpen] = useState(false);
  const [saveAsOpen, setSaveAsOpen] = useState(false);
  const [renamingChapter, setRenamingChapter] = useState<ListenChapter | null>(null);
  const [renamingPerson, setRenamingPerson] = useState<CastMember | null>(null);
  const [genderPerson, setGenderPerson] = useState<CastMember | null>(null);
  const [mergingPerson, setMergingPerson] = useState<CastMember | null>(null);
  const [wishesOpen, setWishesOpen] = useState(false);
  const [viewsOpen, setViewsOpen] = useState(false);
  const [recordDialog, setRecordDialog] = useState<RecordDialog>(null);
  const [finding, setFinding] = useState(false);
  const { data: castView } = useCast(id);
  // Bề rộng nội dung (không phải cửa sổ): từ khổ expanded thì chia hai cột. Chưa đo xong (null) thì một cột.
  const frame = useRef<HTMLDivElement>(null);
  const contentWidth = useElementWidth(frame);
  const split = contentWidth !== null && widthAtLeast(contentWidth, "expanded");
  // Hai cột: mỗi cột tự cuộn nên mờ mép (DESIGN 4.5); một cột không cuộn riêng nên mặt nạ không bao giờ bật.
  const infoFade = useFadeScroller<HTMLElement>();
  const listFade = useFadeScroller<HTMLDivElement>();
  // Sách của máy khác đã tải về máy: dòng "Đã tải về máy" (desktop/RemoteDownload.tsx, cùng khoá truy vấn) đã nói đủ, bỏ dòng "Nghe thẳng"
  // đi cùng nó - hai dòng ngược nghĩa nhau (soát UX a11). Chỉ đọc bộ nhớ tạm, không tự hỏi máy chủ.
  const downloaded = useQuery<{ state?: string }>({ queryKey: ["listen", "download", id], enabled: false }).data?.state === "done";
  // Hook không được đặt sau `return` sớm: cuốn chưa nạp xong thì dùng một cuốn rỗng (nút lưu chưa hiện lúc ấy).
  const saver = useSaveBook(book ?? ({ id: id ?? "" } as ListenBook));
  const sharer = useShareBook(book ?? ({ id: id ?? "" } as ListenBook));
  // Chương đã "Làm trước" (điện thoại, PrepareAhead.kt): dấu "Đã làm sẵn" ở danh sách chương.
  useWarmVoice(id); // giọng trên máy: nạp sẵn model lúc mở trang sách, bấm phát không phải chờ
  const prepared = usePreparedChapters(id ?? "", Boolean(book?.chapters?.some((chapter) => chapter.state === "text" && chapter.speech)));
  // Điện thoại: mở sách là hỏi máy tính đã ghép bản mới nhất của hồ sơ nghe (chỗ nghe, tên, hồ sơ vừa chọn bên ấy) -
  // không thì chỉ biết khi chính điện thoại phát hay dừng cuốn này.
  useEffect(() => {
    if (!id || !source.refreshListening) return;
    void source.refreshListening(id).then(() => client.invalidateQueries({ queryKey: ["listen", "book", id] })).catch(() => undefined);
  }, [client, id, source]);

  // Cùng chỗ với thẻ "Đang nghe dở" ở Thư viện; cuốn đang nằm trong trình phát thì đúng chỗ trình phát đứng (soát a26 L10).
  // Hook nên đứng trước các `return` sớm.
  const point = useResumeTarget(book, book?.chapters ?? []);
  // Quay lại từ trình phát / màn đọc / Thư viện: về đúng chỗ đang xem trong danh sách chương; mở lần đầu trong phiên thì đưa chương
  // đang nghe vào khung (soát a30 L3 - sách 3000 chương luôn mở ở đầu).
  const chapterList = useRef<HTMLDivElement>(null);
  // Hai bố cục có hai khung cuộn khác nhau (cả trang / cột phải): mỗi bên nhớ chỗ cuộn riêng.
  const memoryKey = book && tab === "chapters" ? `book.${book.id}${split ? ".split" : ""}` : null;
  useScrollMemory(memoryKey, chapterList, (scroller) => {
    const row = point && chapterList.current?.querySelector(`[data-chapter="${CSS.escape(String(point.chapter.id))}"]`);
    if (row && !row.closest("[inert]")) reveal(scroller, row);
  });
  // Đổi khổ qua ngưỡng 840 giữa chừng: chỗ đang xem trong danh sách chương đứng yên (DESIGN.md 5.5), không về chỗ đã nhớ của bố cục kia
  // hay chương đang nghe. Đo ngay lúc dựng (DOM còn là bố cục cũ), đặt lại sau useScrollMemory (microtask xếp sau của nó, trước khi vẽ).
  const measured = contentWidth !== null;
  const laidOut = useRef<boolean | null>(null);
  const anchor = useRef<ChapterAnchor | null>(null);
  if (measured && laidOut.current !== null && laidOut.current !== split && !anchor.current && frame.current && chapterList.current) {
    anchor.current = chapterAnchor(frame.current, chapterList.current, laidOut.current);
  }
  useLayoutEffect(() => {
    const before = anchor.current;
    anchor.current = null;
    laidOut.current = measured ? split : null;
    if (!before || !memoryKey) return;
    queueMicrotask(() => {
      if (!frame.current || !chapterList.current) return;
      saveScroll(memoryKey, placeChapterAnchor(frame.current, chapterList.current, split, before));
    });
  }, [split, measured, memoryKey]);

  const placeholder = (
      <div className="page-x mx-auto max-w-[1180px]">
        {/* Cùng đầu màn với trang đã tải: nút ← bấm được ngay, bìa không nhảy khi dữ liệu về. */}
        <ScreenHeader back={{ label: S.s_ve_thu_vien_992fad7b, onClick: () => navigate("/") }} />
        <div className="mt-5 flex gap-6"><Skeleton className="size-36 rounded-control" /><div className="flex-1 space-y-3 pt-3"><Skeleton className="h-7 w-2/3" /><Skeleton className="h-4 w-1/3" /></div></div>
      </div>
  );
  const content = () => {

  // Chỉ 404 mới là sách không còn: một lần hỏi lại hụt (máy chủ khởi động lại, mạng chớp) giữ nguyên trang đã có - không thì cả trang biến thành
  // "Không tìm thấy" và hộp thoại đang sửa dở mất theo.
  if (!book || isMissing(error)) {
    return (
      <EmptyState icon={BookOpenText} title={S.s_khong_tim_thay_sach_nay_0836038e} className="mt-20" action={<Button onClick={() => navigate("/")}>{S.s_ve_thu_vien_7bb3f8c2}</Button>}>{S.s_sach_co_the_da_bi_chuyen_sang_thu_muc_khac_b74249d0}</EmptyState>
    );
  }
  const chapters = book.chapters ?? [];
  // Sách chỉ có chữ (nhập từ EPUB / DOCX / PDF / TXT): đọc được, chưa có âm thanh - không phát, không nhân vật, không nhạc.
  const textOnly = book.stage === "text";
  const editable = editing !== false && canEditBook(book);
  const workshop = Boolean(book.capabilities?.workshop);
  // Cuốn tải từ máy tính (điện thoại): phần sửa gửi về máy tính thay vì lưu thành file.
  const syncs = syncsToComputer(book.capabilities);
  // Cuốn của máy này không có xưởng (file .abook): việc của Studio (giới tính, gộp người...) ghi lại thành ý muốn chờ Studio.
  const remoteEdit = editing !== false && Boolean(editing.remote);
  const waiting = editable && !workshop && !remoteEdit;
  const extra = extraActions?.(book);
  const danger = dangerActions?.(book);
  // Nút "…" chỉ khi menu có mục (thiết bị chỉ được nghe: sách chỉ có chữ thì menu rỗng).
  const moreMenu = moreMenuHasItems({
    records: Boolean(source.records) && book.records?.length === 1,
    finishedToggle: !textOnly,
    edit: editing !== false && editable,
    platform: editing !== false && !remoteEdit,
    extra: extra || danger,
  });
  const listening = player.track?.bookId === book.id;
  const heard = book.progress.heardSeconds;
  const left = Math.max(0, book.duration - heard);
  // Điện thoại, sách chưa đủ chương mà không máy nào thu ở đây: dòng "Sách này có x/y chương đã thu" thay cho dòng đếm chương ở trên.
  const phonePartial = !book.complete && !textOnly && !book.producing && !book.imported && source.kind === "android";
  const caughtUp = Boolean(book.progress.caughtUp) && !listening;
  // Máy này có giọng đọc cho các chương chỉ có chữ (source.withReadAloud gắn `speech`).
  const speaks = chapters.some((chapter) => chapter.speech === true);
  // Đã nghe tới đâu. Sách chỉ có chữ: máy chủ chưa tính tiến độ cả cuốn (chưa có độ dài thật) - suy từ chỗ nghe và từng chương đã nghe xong.
  const started = heard > 0 || Boolean(book.state.last);
  const playable = chapters.filter(canPlay);
  const heardAll = Boolean(book.progress.finished) || (textOnly && playable.length > 0 && playable.every((chapter) => chapterHeard(book.state, chapter) >= 1));
  // Hết cả cuốn (cuốn đang nạp mà đang phát thì vẫn là "Tạm dừng").
  const finished = heardAll && !(listening && player.playing);
  // Nói rõ nghe tiếp từ ĐÂU, cùng dạng với thẻ "Đang nghe dở" ở Thư viện (soát UX 29-09, 03-10).
  const primaryLabel = primaryListenLabel({
    playingHere: listening && player.playing,
    finished,
    point: point ? { title: point.chapter.title, at: point.at } : null,
    heard: started ? Math.max(heard, 1) : 0,
    textOnly,
  });
  // Nghe được ở máy này: nút chính là nghe, "Đọc" vào hàng phụ; không nghe được (sách chữ, máy không có giọng): nút chính là "Đọc".
  const listenFirst = Boolean(point);
  const readLabel = listening ? S.s_doc_5709880c : latestReading(book) ? S.s_doc_tiep_633d731b : S.s_doc_5709880c;
  // Đang nghe cuốn này: mở đúng chương đang phát (màn đọc tự tới câu đang nghe) - sửa câu vừa nghe không phải tìm lại (soát a70).
  const read = () => navigate(`/book/${book.id}/read${listening && player.track ? `/${player.track.chapterId}` : ""}`);
  const restart = async () => {
    const first = chapters.find(canPlay);
    if (!first) return;
    if (listening) {
      // Cuốn đang nạp trong trình phát: nhảy như mọi cú nhảy khác - trình phát nhớ chỗ cũ (nút ↺ "Quay lại chỗ vừa nghe"
      // + thông báo), không chỉ một thông báo 8 giây rồi mất (soát UX 29-09).
      player.jumpTo(first.id, 0);
      return;
    }
    const before = point;
    const started = playBook(book, first.id, 0);
    if (before && (before.chapter.id !== first.id || before.at > 30)) {
      toast(S.s_dang_nghe_lai_tu_dau_5ad4fe3c, {
        // Có nút thao tác: đủ lâu để kịp bấm (mặc định 4 giây quá ngắn - soát UX 29-09).
        duration: 8000,
        action: { label: S.s_quay_lai_cho_cu_fea69b14, onClick: () => void playBook(book, before.chapter.id, before.at) },
      });
    }
    await started;
  };
  // Nút chính: đang phát cuốn này thì nút là "Tạm dừng", chỉ dừng. Còn lại nút là "nghe": phát rồi mở trình phát của cuốn (DESIGN.md L3b).
  const listenNow = async () => {
    if (listening && player.playing) {
      player.toggle();
      return;
    }
    if (finished) await restart();
    else if (listening) player.toggle();
    else await playBook(book);
    setExpanded(true);
  };

  return (
    <div
      data-book-layout={split ? "split" : "stacked"}
      // Khối nội dung rộng đúng cột trái + 32 + danh sách (tối đa 640), cộng hai lề 40, căn giữa - như Qt (compositionWidth).
      style={split ? ({ "--book-left": `${bookLeftWidth(contentWidth)}px`, width: `min(100%, ${bookLeftWidth(contentWidth) + 32 + BOOK_LIST_MEASURE + 80}px)` } as CSSProperties) : undefined}
      className={cn("motion-reveal page-x mx-auto", split ? "flex h-full flex-col pb-4" : "max-w-[1180px] pb-16")}
    >
      {/* Nút ← chung của màn con (ScreenHeader) đứng riêng một hàng: tên sách nằm cạnh bìa bên dưới. */}
      <ScreenHeader back={{ label: S.s_ve_thu_vien_992fad7b, onClick: () => navigate("/") }} />
      {/* Hai cột (nội dung từ 840 px): bìa + thông tin + nút bên trái, tab Chương / Lịch sử / Nhân vật bên phải, mỗi bên cuộn riêng như Qt. Một cột: `contents`
          - hai khối nằm thẳng trong trang như trước. Cùng một cây ở cả hai bố cục nên đổi bố cục không dựng lại bìa. */}
      <div className={split ? "grid min-h-0 flex-1 grid-cols-[var(--book-left)_minmax(0,1fr)] gap-x-8" : "contents"}>
      {/* Bìa · tên · tác giả · giọng · thời lượng · tiến độ mảnh; dưới là MỘT nút chính và một hàng nút phụ cùng kiểu (docs/DESIGN.md mục 7).
          Điện thoại: hàng nút trải hết bề ngang dưới bìa; máy tính: nằm dưới tên, cạnh bìa. */}
      <header ref={infoFade.ref} style={infoFade.style} className={cn("mt-5 grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-4 sm:gap-x-7", split && "-mx-1 min-h-0 grid-cols-1 content-start gap-x-0 overflow-y-auto px-1 pb-6 sm:gap-x-0")}>
        {/* Cuốn đang nạp: bấm bìa mở trình phát (DESIGN.md L3b). Lớp nút phủ lên bìa, nên bắt đầu / thôi nghe không dựng lại bìa. */}
        <div className={cn("press relative w-28 sm:row-span-2 sm:w-44", split && "w-48 sm:row-span-1 sm:w-48")}>
          <BookCover bookKey={book.id} title={book.title} part={book.series?.part} size="lg" image={book.cover} playing={listening && player.playing} className="aspect-[2/3] w-full" />
          {listening && <button type="button" data-book-cover-open aria-label={S.s_mo_man_hinh_dang_nghe_2426b4ad} onClick={() => setExpanded(true)} className="absolute inset-0 rounded-cover" />}
        </div>
        <div className={cn("min-w-0", split && "mt-5")}>
          <h1 data-content-title="" className={cn(SCREEN_TITLE, "leading-tight")}>{displayTitle(book.title)}</h1>
          <p className="mt-1.5 text-sm text-fg-2">
            <DotJoin
              parts={[
                book.author,
                book.narrator && S.s_giong_0_c554bb1b(book.narrator),
                ...(textOnly
                  ? [S.s_0_chuong_04093412(book.chaptersTotal)]
                  : phonePartial
                    ? [S.s_0_phan_da_co_022a3375(formatLength(book.duration))] // số chương đã nằm ở dòng "Sách này có x/y chương đã thu" ngay dưới
                    : [book.complete ? S.s_0_chuong_04093412(book.chaptersTotal) : S.s_0_1_chuong_co_audio_9706857d(book.chaptersAvailable, book.chaptersTotal), formatLength(book.duration)]),
              ]}
            />
          </p>
          {/* Tình trạng của cuốn: một dòng chữ nhỏ, không hộp, không viên thuốc màu. */}
          {textOnly && <p className="mt-1.5 text-sm text-fg-2">{textBookLine(speaks)}</p>}
          {!book.complete && !textOnly && (
            <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-accent-text">
              {book.producing && <Vu className="h-2.5" />}
              {book.producing
                ? S.s_dang_thu_chuong_moi_tu_hien_khi_xong_123d0db2
                : book.remote
                  ? remoteUnfinishedLine(book)
                  : book.imported
                    ? S.s_chua_du_chuong_mo_file_sach_moi_hon_de_ngh_ca290cd2
                    : phonePartial
                      ? partialBookLine(book.chaptersAvailable, book.chaptersTotal)
                      : S.s_chua_du_chuong_dang_dung_thu_3653bcf7}
              {studioLink?.(book)}
            </p>
          )}
          {book.missingFiles ? (
            <p className="mt-1.5 text-sm text-warning">
              {book.missingFiles}{S.s_chuong_mat_file_tren_may_nay_09492c4c}{book.stage === "text"
                ? S.s_ban_hay_them_lai_dung_file_sach_goc_epub_w_0833d0ba
                : S.s_ban_hay_mo_lai_file_sach_abook_cua_cuon_na_4efff7a0}
            </p>
          ) : null}
          {book.remote && !downloaded && (
            // Biểu tượng cao đúng một dòng chữ: chữ xuống hai dòng thì biểu tượng vẫn thẳng dòng đầu, không trôi vào giữa.
            <p className="mt-1.5 flex items-start gap-1.5 text-sm text-fg-2">
              <span className="grid h-[1lh] shrink-0 place-items-center"><Laptop className="size-4" /></span>
              {typeof book.remote === "object"
                ? S.s_nghe_thang_tu_0_chuong_nghe_toi_duoc_giu_l_a6a23b61(book.remote.computer || S.s_may_khac_95db1846)
                : S.s_nghe_thang_tu_may_tinh_tai_ve_de_nghe_ca_k_44e792bc}
            </p>
          )}
          {notice?.(book)}
          {syncs && <EditsSyncBanner book={book} />}
          <LocalEditsBanner book={book} />
          <EditsNoticesBanner book={book} />
          {textOnly && editable && <BookSuggestions book={book} />}
          <div className="mt-4 max-w-md">
            {!textOnly && (
              <>
                <Progress value={book.progress.fraction} tone={book.progress.finished ? "success" : "accent"} size="sm" label={S.s_da_nghe_1e0f8d88} />
                {/* Một dòng. "Còn" tính theo phần ĐÃ PHỦ (chỗ tua qua vẫn là chưa nghe), khác "còn X" theo vị trí ở màn "Đang nghe" - nói rõ
                    "chưa nghe" để hai con số không trông như mâu thuẫn (soát UX 29-09). */}
                <p className="mt-1.5 text-xs text-fg-2">
                  {book.progress.finished || book.progress.caughtUp ? bookStatusText(book) : heard > 0 ? <TickingValue><DotJoin parts={[S.s_da_nghe_0_2f78a962(formatLength(heard)), S.s_con_0_chua_nghe_4959c9c5(formatLength(left))]} /></TickingValue> : listening ? (player.error ? S.s_chua_phat_duoc_3ecb850e : S.s_dang_nghe_9310d8cf) : S.s_chua_nghe_2fbea4c8}
                </p>
              </>
            )}
            <RecordPicker book={book} dialog={recordDialog} setDialog={setRecordDialog} />
          </div>
        </div>
        {/* Máy tính: cột rộng đúng bằng nút chính (ít nhất 16rem cho 4 nút phụ) - hàng nút phụ trải đúng bề ngang nút chính, hai đầu thẳng nhau.
            Cột nút là vùng chuyển cảnh riêng: phát / dừng đổi nhãn nút chính thì chỉ cột này so dấu, không phải cả trang (vùng cả trang từng
            chụp lại hơn nghìn nút DOM mỗi lần bấm phát trên sách 2500 chương rồi bỏ đi - docs/PERF_WEB.md). */}
        <MotionRegion as="div" className={cn("col-span-2 mt-6 flex max-w-md flex-col gap-3 sm:col-span-1 sm:col-start-2 sm:mt-5 sm:w-fit sm:min-w-[16rem]", split && "col-span-1 col-start-1 sm:col-start-1 sm:w-full")}>
          {caughtUp ? (
            <p className="text-sm text-fg-2">{S.s_da_nghe_het_phan_da_co_chuong_moi_se_hien_4b18ca13}</p>
          ) : (
            // Đúng MỘT nút chính: nghe (hay nghe tiếp) - sách không nghe được ở máy này thì nút chính là "Đọc".
            <Button
              variant="primary"
              size="lg"
              data-book-primary
              icon={listenFirst ? (listening && player.playing ? Pause : finished ? RotateCcw : Play) : BookOpen}
              onClick={listenFirst ? withFeedback("playPause", () => void listenNow()) : read}
              // Tên chương dài (truyện dịch) hay chữ hệ thống to: cắt "…" trong nút thay vì tràn ra hai mép màn hình (soát UX a9).
              className="min-w-0 max-w-full max-sm:w-full"
            >
              <span className="min-w-0 truncate">{listenFirst ? primaryLabel : readLabel}</span>
            </Button>
          )}
          {/* Hàng phụ: luôn cùng bốn chỗ, cùng thứ tự - nút chưa dùng được thì mờ đi chứ không biến mất (không nhảy chỗ khi bắt đầu nghe). */}
          {/* Đầu trái là "Đọc" (24,8 px) hay "Tìm" (22,1 px), đầu phải "⋯" (không nhãn, chừa chỗ nhãn): mỗi đầu một --slot để cả hai sát mép nút chính. */}
          <div role="group" aria-label={S.s_viec_voi_sach_9582a854} data-book-secondary className={cn("slot-row items-start [--slot:1.4rlh]", listenFirst || caughtUp ? "[--slot-start:1.0333rlh]" : "[--slot-start:0.9208rlh]")}>
            {/* Nhãn luôn một chữ "Đọc" (hàng cách đều theo tâm, nhãn đầu mút sát mép - "Đọc tiếp" dài gấp đôi sẽ lòi ra); "tiếp" nói cho trình đọc màn hình. */}
            {(listenFirst || caughtUp) && <ActionButton icon={BookOpen} label={S.s_doc_5709880c} aria-label={readLabel === S.s_doc_5709880c ? undefined : readLabel} onClick={read} />}
            <ActionButton icon={Search} label={S.s_tim_bbe47492} aria-label={S.s_tim_chu_trong_sach_7bc2c2ee} disabled={!chapters.length} onClick={() => setFinding(true)} />
            {!textOnly || point ? <ActionButton icon={RotateCcw} label={S.s_tu_dau_89ef6d78} aria-label={S.s_nghe_lai_tu_dau_e251d632} disabled={!(started && point && !finished)} onClick={restart} /> : null}
            {moreMenu && <ActionMenu title={S.s_viec_voi_sach_9582a854} trigger={<ActionButton icon={MoreHorizontal} label={<span aria-hidden className="inline-block h-3" />} aria-label={S.s_them_tuy_chon_a0b4bb6e} />}>
                  {/* Một hồ sơ thì không có nút hồ sơ nghe: tạo / chuyển / đổi tên / xoá hồ sơ duy nhất nằm ở đây (soát a105 F9), dùng chung hộp thoại của RecordPicker. */}
                  {source.records && singleRecordActions(book).filter(action => !action.danger).map((action) => (
                    <DropdownMenu.Item key={action.key} onSelect={() => setRecordDialog(action.dialog)} className={MENU_ITEM}>
                      <action.icon className="size-4" /> {action.label}
                    </DropdownMenu.Item>
                  ))}
                  {!textOnly && (
                    <DropdownMenu.Item onSelect={() => mutations.finished.mutate(!book.progress.finished)} className={MENU_ITEM}>
                      <CheckCheck className="size-4" />
                      {book.progress.finished ? S.s_chua_nghe_xong_6b821209 : S.s_da_nghe_xong_d276b702}
                    </DropdownMenu.Item>
                  )}
                  {editing !== false && editable && (
                    <>
                      <DropdownMenu.Separator className="my-1 h-px bg-line" />
                      <DropdownMenu.Item onSelect={() => setEditOpen(true)} className={MENU_ITEM}>
                        <Pencil className="size-4" />{S.s_sua_thong_tin_1a8800ae}</DropdownMenu.Item>
                      {textOnly && <PlaylistSubmenu bookId={book.id} />}
                      {syncs && <SendEditsItem book={book} />}
                      {!remoteEdit && !workshop && !syncs && !book.capabilities?.local && saver.available && (
                        <>
                          <DropdownMenu.Item
                            disabled={!(book.unsaved ?? book.edits) || saver.busy}
                            onSelect={() => void saver.save()}
                            className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
                          >
                            <Save className="size-4" />{S.s_luu_thay_doi_db80391d}</DropdownMenu.Item>
                          <DropdownMenu.Item onSelect={() => setSaveAsOpen(true)} className={MENU_ITEM}>
                            <FileDown className="size-4" />{S.s_luu_thanh_897f6d4d}</DropdownMenu.Item>
                          {sharer.available && (
                            <DropdownMenu.Item
                              disabled={sharer.busy}
                              onSelect={() => void sharer.share()}
                              className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
                            >
                              <Share2 className="size-4" />{S.s_chia_se_fc043a3b}</DropdownMenu.Item>
                          )}
                        </>
                      )}
                      {!remoteEdit && !workshop && Boolean(book.wishes) && (
                        <DropdownMenu.Item onSelect={() => setWishesOpen(true)} className={MENU_ITEM}>
                          <Hourglass className="size-4" />{S.s_viec_dang_cho_44ba5812}{book.wishes})
                        </DropdownMenu.Item>
                      )}
                    </>
                  )}
                  {editing !== false && !remoteEdit && <EditBlockedItem book={book} />}
                  {editing !== false && !remoteEdit && <StudioOnlyItem book={book} />}
                  {editing !== false && !remoteEdit && <ProjectFileItems book={book} onViews={() => setViewsOpen(true)} />}
                  {editing !== false && !remoteEdit && <TextBookItems book={book} />}
                  {extra}
                  {(source.records || danger) && <DropdownMenu.Separator className="my-2 h-px bg-line" />}
                  {source.records && singleRecordActions(book).filter(action => action.danger).map(action => <Fragment key={action.key}>
                    <DropdownMenu.Item onSelect={() => setRecordDialog(action.dialog)} className={cn(MENU_ITEM, "text-danger")}>
                      <action.icon className="size-4" /> {action.label}
                    </DropdownMenu.Item>
                  </Fragment>)}
                  {danger}
            </ActionMenu>}
          </div>
          {chapters.length > 0 && <FindInBook book={book} open={finding} onOpenChange={setFinding} />}
        </MotionRegion>
      </header>
      {/* Đổi bố cục không dựng lại danh sách: Windowed (layout) và nhớ chỗ cuộn quan sát lại khung cuộn mới, chỗ đang xem được đặt lại (keepChapterPlace). */}
      <Tabs value={tab} onValueChange={(value) => setParams({ tab: value }, { replace: true })} className={split ? "mt-5 flex min-h-0 flex-col" : "mt-8"}>
        <TabsList label={S.s_muc_cua_sach_37e9b664}>
          <TabsTrigger value="chapters" count={chapters.length}>{S.s_chuong_2d157977}</TabsTrigger>
          <TabsTrigger value="history">{S.s_lich_su_0a235708}</TabsTrigger>
          {!textOnly && <TabsTrigger value="cast">{S.s_nhan_vat_d4940c17}</TabsTrigger>}
        </TabsList>
        {/* Hai cột: hàng tab đứng yên ở đầu cột phải, chỉ phần bên dưới cuộn. */}
        {/* -mx-4 px-4 pt-1: khung cuộn cắt mọi thứ tràn ra ngoài nó - nền rê chuột (-inset-x-3) và vòng tiêu điểm (4) của hàng mở/gập và của chính
            ngăn tab ở mép sát khung; lề cho chúng chỗ. */}
        <div ref={listFade.ref} style={listFade.style} data-book-list className={split ? "-mx-4 min-h-0 flex-1 overflow-y-auto px-4 pt-1 pb-6" : undefined}>
        <TabsPanels value={tab}>
        <TabsContent value="chapters" className="mt-2" ref={chapterList}>
          <ChapterGroups book={book} currentChapter={point?.chapter.id} onDone={(chapterId, done) => mutations.chapterDone.mutate({ chapterId, done })} onRename={editable ? setRenamingChapter : undefined} prepared={prepared} layout={split ? "split" : "stacked"} />
        </TabsContent>
        <TabsContent value="history">
          <HistoryTab book={book} />
        </TabsContent>
        <TabsContent value="cast">
          <CastList
            bookId={book.id}
            reached={reachedTitles(chapters, point?.chapter.id)}
            onRename={editable ? setRenamingPerson : undefined}
            onGender={waiting ? setGenderPerson : undefined}
            onMerge={waiting ? setMergingPerson : undefined}
            waiting={waiting}
          />
        </TabsContent>
        </TabsPanels>
        </div>
      </Tabs>
      </div>
      {editing !== false && editable && (
        <>
          <EditBookDialog book={book} open={editOpen} onOpenChange={setEditOpen} onOpenStudio={editing.onOpenStudio ? () => editing.onOpenStudio?.(book) : undefined} computer={editing.remote} />
          <RenameChapterDialog book={book} chapter={renamingChapter} onClose={() => setRenamingChapter(null)} />
          <RenamePersonDialog bookId={book.id} person={renamingPerson} onClose={() => setRenamingPerson(null)} onSaved={() => refreshAfterEdit(client, book.id)} />
          {!remoteEdit && (
            <>
              <SaveAsDialog book={book} open={saveAsOpen} onOpenChange={setSaveAsOpen} pickFolder={editing.pickFolder} />
              <ProjectViewsDialog book={book} open={viewsOpen} onOpenChange={setViewsOpen} />
            </>
          )}
          {waiting && (
            <>
              <GenderDialog bookId={book.id} person={genderPerson} onClose={() => setGenderPerson(null)} waiting onSaved={() => refreshAfterEdit(client, book.id)} />
              <MergeDialog
                bookId={book.id}
                person={mergingPerson}
                people={castView?.characters ?? []}
                onClose={() => setMergingPerson(null)}
                onSaved={() => refreshAfterEdit(client, book.id)}
              />
              <WishesDialog bookId={book.id} count={book.edits ?? 0} open={wishesOpen} onOpenChange={setWishesOpen} syncs={syncs} />
            </>
          )}
        </>
      )}
    </div>
  );
  };
  // Khung đo bề rộng nội dung: luôn có mặt (kể cả lúc đang nạp). Hai cột cần chiều cao cố định bằng vùng nội dung (mỗi cột tự cuộn) nên cả chuỗi bao h-full.
  return (
    <div ref={frame} data-book-frame className={split ? "h-full" : undefined}>
      <LoadingCrossfade loading={isLoading} placeholder={placeholder} className={split ? "h-full grid-rows-[minmax(0,1fr)] [&>.motion-loading-content]:h-full" : undefined}>
        <MotionRegion className={split ? "h-full" : undefined}>{content()}</MotionRegion>
      </LoadingCrossfade>
    </div>
  );
}
