import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRightLeft, AudioLines, BookOpen, BookOpenText, Check, CheckCheck, ChevronDown, CircleDashed, CloudDownload, FileDown, GitMerge, History, Hourglass, Laptop, Loader2, MoreHorizontal, Pause, Pencil, Play, Plus, RotateCcw, Save, Search, Share2, SlidersHorizontal, Trash2, UserRound } from "lucide-react";
import { useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { holderName } from "@/shared/editsSync";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { syncsToComputer } from "@/shared/capabilities";
import { usePageTitle } from "@/shared/title";
import { formatClock, formatLength, formatNumber } from "@/shared/format";
import { toneLabel } from "./voiceTone";
import { Button, Dialog, EmptyState, IconButton, Progress, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger, Tooltip, Vu } from "@/shared/ui";
import { GenderDialog, RenamePersonDialog } from "@/studio/CastEdits";
import { MergeDialog } from "@/studio/MergePeople";
import { useClip } from "./clip";
import { FindInBook } from "./FindInBook";
import { canEditBook, EditBlockedItem, EditBookDialog, refreshAfterEdit, RenameChapterDialog, SaveAsDialog, StudioOnlyItem, useSaveBook, useShareBook } from "./EditBook";
import { bookStatusText, usePlayListenBook } from "./LibraryScreen";
import { bookmarkReadPath, canPlay, chapterHeard, chaptersByPart, resumePoint, type CastMember, type ListenBook, type ListenChapter } from "./model";
import { keepTogether, partialBookLine, primaryListenLabel, textBookLine, textChapterLine } from "./labels";
import { usePlayer } from "./player";
import { BookmarkList, chapterStatusLabel, usePreparedChapters } from "./PlayerViews";
import { EditsSyncBanner, LocalEditsBanner, SendEditsItem } from "./SendEdits";
import { PlaylistSubmenu } from "./PlaylistChoice";
import { ProjectFileItems, ProjectViewsDialog, TextBookItems } from "./ProjectFileItems";
import { BookSuggestions } from "./ReadingSuggestions";
import { WishesDialog } from "./WishesDialog";
import { useBookVoice, useCast, useListenBook, useListenLibrary, useListenMutations, useSource } from "./source";

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

function ChapterRow({
  book,
  chapter,
  onDone,
  onRename,
  prepared = false,
  voice = "",
}: {
  book: ListenBook;
  chapter: ListenChapter;
  /** "Làm trước" đã đọc sẵn chương này bằng giọng của cuốn: nghe ngay, không cần mạng hay chờ. */
  prepared?: boolean;
  /** Tên giọng đang đọc cuốn (useBookVoice) - dòng phụ của chương chỉ-có-chữ nói đúng giọng ấy. */
  voice?: string;
  onDone: (chapterId: number, done: boolean) => void;
  /** Sách sửa được trên máy này (shared/capabilities.ts): "Đổi tên chương…" - cái tên hiện trên màn hình, không đổi audio. */
  onRename?: (chapter: ListenChapter) => void;
}) {
  const player = usePlayer();
  const playBook = usePlayListenBook();
  const navigate = useNavigate();
  const current = player.track?.bookId === book.id && player.track.chapterId === chapter.id;
  const heard = chapterHeard(book.state, chapter);
  const done = heard >= 1;
  const onPlay = () => {
    if (!canPlay(chapter)) return;
    if (current) player.toggle();
    else void playBook(book, chapter.id, heard > 0 && heard < 1 ? (book.state.chapters[String(chapter.id)]?.heard ?? 0) : 0);
  };
  const name = chapter.subtitle || chapter.title;
  return (
    <div
      className={cn(
        "group flex items-center gap-3 rounded-xl px-2 py-2.5 sm:px-3",
        current ? "bg-accent-soft" : canPlay(chapter) && "hover:bg-hover",
      )}
    >
      <button
        type="button"
        onClick={onPlay}
        disabled={!canPlay(chapter)}
        aria-label={current && player.playing ? `Tạm dừng ${chapter.fullTitle}` : `Nghe ${chapter.fullTitle}`}
        className="grid size-9 shrink-0 place-items-center rounded-full text-fg-2 hover:bg-panel hover:text-fg disabled:text-fg-3 disabled:hover:bg-transparent"
      >
        {current && player.playing ? (
          <Vu className="h-3 text-accent" />
        ) : done ? (
          <Check className="size-4 text-success" strokeWidth={3} aria-label="Đã nghe" />
        ) : canPlay(chapter) ? (
          <Play className="size-4 translate-x-[1px]" fill="currentColor" strokeWidth={0} />
        ) : (
          <CircleDashed className="size-4" />
        )}
      </button>
      {/* Chương chưa có audio vẫn đọc được: bấm vào dòng là mở màn đọc (soát UX 29-09 - trước đây cả dòng bị vô hiệu, chỉ
          nút "…" hiện khi rê chuột mới có "Đọc chương này"). */}
      <button
        type="button"
        onClick={canPlay(chapter) ? onPlay : () => navigate(`/book/${book.id}/read/${chapter.id}`)}
        aria-label={canPlay(chapter) ? undefined : `Đọc ${chapter.fullTitle} (chưa có audio)`}
        className="min-w-0 flex-1 text-left"
      >
        <div className={cn("truncate text-sm font-medium", current && "text-accent-text", (done || !canPlay(chapter)) && !current && "text-fg-2")}>
          {name}
        </div>
        <div className="tabular truncate text-xs text-fg-2">
          {chapter.subtitle ? `${chapter.title} · ` : ""}
          {chapter.available
            ? formatLength(chapter.duration)
            : chapter.state === "text"
              ? textChapterLine(Boolean(chapter.speech), voice)
              : chapterStatusLabel(book.producing)}
          {prepared && (
            <span className="ml-1.5 inline-flex items-center gap-0.5 rounded bg-accent-soft px-1 align-[1px] text-[11px] font-medium text-accent-text">
              <CloudDownload className="size-3" aria-hidden />
              Đã làm sẵn
            </span>
          )}
        </div>
        {heard > 0 && heard < 1 && (
          <div className="mt-1.5 h-[3px] w-24 overflow-hidden rounded-full bg-line-strong">
            <div className="h-full bg-accent" style={{ width: `${heard * 100}%` }} />
          </div>
        )}
      </button>
      <div className="size-8 shrink-0 max-sm:size-[44px]">
        {(
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                aria-label={`Tuỳ chọn ${chapter.fullTitle}`}
                className="grid size-8 place-items-center rounded-md text-fg-2 opacity-0 hover:bg-panel hover:text-fg group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100 max-sm:size-[44px]"
              >
                <MoreHorizontal className="size-4" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-52 rounded-xl border border-line bg-panel p-1.5 shadow-float">
                {canPlay(chapter) && (
                  <DropdownMenu.Item onSelect={() => void playBook(book, chapter.id, 0)} className={MENU_ITEM}>
                    <Play className="size-4" /> Nghe từ đầu chương
                  </DropdownMenu.Item>
                )}
                <DropdownMenu.Item onSelect={() => navigate(`/book/${book.id}/read/${chapter.id}`)} className={MENU_ITEM}>
                  <BookOpen className="size-4" /> Đọc chương này
                </DropdownMenu.Item>
                {canPlay(chapter) && (
                  <DropdownMenu.Item onSelect={() => onDone(chapter.id, !done)} className={MENU_ITEM}>
                    {done ? <CircleDashed className="size-4" /> : <CheckCheck className="size-4" />}
                    {done ? "Đánh dấu chưa nghe" : "Đánh dấu đã nghe xong"}
                  </DropdownMenu.Item>
                )}
                {onRename && (
                  <DropdownMenu.Item onSelect={() => onRename(chapter)} className={MENU_ITEM}>
                    <Pencil className="size-4" /> Đổi tên chương…
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        )}
      </div>
    </div>
  );
}

function BookmarksTab({ book }: { book: ListenBook }) {
  const playBook = usePlayListenBook();
  const navigate = useNavigate();
  if (!book.state.bookmarks.length) {
    return (
      <EmptyState icon={BookOpenText} title="Chưa có dấu trang" className="mt-2">
        Khi đang nghe, bấm biểu tượng dấu trang (hoặc phím B) để đánh dấu đoạn muốn quay lại. Khi đang đọc, chọn một câu rồi bấm “Đặt dấu trang ở câu này”.
      </EmptyState>
    );
  }
  return (
    <div className="mt-3 -mx-3">
      <BookmarkList
        bookId={book.id}
        chapters={book.chapters ?? []}
        marks={book.state.bookmarks}
        onJump={(mark) => {
          // Dấu đặt ở màn đọc trỏ tới câu: mở màn đọc đúng câu ấy; dấu đặt khi nghe thì nghe tiếp từ chỗ đó.
          const path = bookmarkReadPath(book.id, mark);
          if (path) navigate(path);
          else void playBook(book, mark.chapterId, mark.seconds);
        }}
      />
    </div>
  );
}

function SampleButton({ id, url, label }: { id: string; url: string; label: string }) {
  const clip = useClip();
  const active = clip.current === id;
  return (
    <Tooltip label={active ? "Dừng" : label}>
      <button
        type="button"
        aria-label={active ? "Dừng nghe thử" : label}
        onClick={() => clip.toggle(id, url)}
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-full border transition-colors",
          active ? "border-accent bg-accent text-accent-ink" : "border-line text-fg-2 hover:border-line-strong hover:text-fg",
        )}
      >
        {active && clip.loading ? <Loader2 className="size-4 animate-spin" /> : active ? <Vu className="h-3" /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
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
    <div className="flex min-w-0 items-center gap-3 rounded-xl border border-line bg-panel p-3">
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
        {person.originalName && <div className="break-words text-xs text-fg-3">(tên gốc: {cleanName(person.originalName)})</div>}
        <div className="mt-0.5 break-words text-xs text-fg-2">
          <AudioLines className="mr-1 inline size-3.5 -translate-y-px text-fg-3" />
          {person.voice ? `${person.voice.preset}${person.voice.tone ? ` · ${toneLabel(person.voice.tone)}` : ""}` : "Chưa có giọng"}
        </div>
        {/* Việc của Studio (giọng người nghe đã chọn, chưa áp) - trang nghe không cần (soát UX 29-09). */}
        {person.pendingVoice && (onPickVoice || waiting) && (
          <div className="mt-0.5 truncate text-xs font-medium text-accent-text">
            {waiting ? "Đang chờ máy làm sách" : "Chờ áp dụng"}:{" "}
            {[person.pendingVoice.preset && `giọng ${person.pendingVoice.preset}`, person.pendingVoice.gender.toLowerCase()]
              .filter(Boolean)
              .join(" · ")}
          </div>
        )}
        <div className="tabular mt-1 text-xs text-fg-2">
          {formatNumber(person.lines)} câu
          {person.seconds > 0 ? ` · ${formatLength(person.seconds)}` : ""}
          {person.firstChapter ? ` · từ ${keepTogether(person.firstChapter)}` : ""}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {person.sampleId ? <SampleButton id={`sample-${bookId}-${person.sampleId}`} url={source.sampleUrl(bookId, person.sampleId)} label={`Nghe ${name} nói`} /> : null}
        {onPickVoice && person.voice && person.lines > 0 ? (
          <IconButton label={`Đổi giọng ${name}`} icon={SlidersHorizontal} size="sm" onClick={() => onPickVoice(person)} />
        ) : null}
        {onRename || onGender || canMerge ? (
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                aria-label={`Thêm tuỳ chọn cho ${name}`}
                className="grid size-8 place-items-center rounded-md text-fg-2 hover:bg-hover hover:text-fg data-[state=open]:bg-hover"
              >
                <MoreHorizontal className="size-4" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-48 rounded-xl border border-line bg-panel p-1.5 shadow-float">
                {canMerge && (
                  <DropdownMenu.Item onSelect={() => onMerge?.(person)} className={MENU_ITEM}>
                    <GitMerge className="size-4" /> Gộp vào người khác…
                  </DropdownMenu.Item>
                )}
                {onRename && (
                  <DropdownMenu.Item onSelect={() => onRename(person)} className={MENU_ITEM}>
                    <Pencil className="size-4" /> Đổi tên
                  </DropdownMenu.Item>
                )}
                {onGender && person.voice && person.lines > 0 && (
                  <DropdownMenu.Item onSelect={() => onGender(person)} className={MENU_ITEM}>
                    <UserRound className="size-4" /> Đổi giới tính
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        ) : null}
      </div>
    </div>
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
export function CastList({ bookId, onPickVoice, onMerge, onRename, onGender, reached, waiting }: {
  bookId: string;
  onPickVoice?: (person: CastMember) => void;
  onMerge?: (person: CastMember) => void;
  onRename?: (person: CastMember) => void;
  onGender?: (person: CastMember) => void;
  reached?: Set<string>;
  /** Cuốn không có xưởng: đổi giới tính, gộp người ghi thành ý muốn chờ Studio (docs/EDITING.md, P2a). */
  waiting?: boolean;
}) {
  const source = useSource();
  const { data: cast, isLoading } = useCast(bookId);
  const [extras, setExtras] = useState(false);
  const [later, setLater] = useState(false);
  const [carried, setCarried] = useState(false);
  const carriedPeople = onPickVoice ? (cast?.carried ?? []) : [];
  if (isLoading) return <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="h-[84px] rounded-xl" />)}</div>;
  if (!cast || (!cast.characters.length && !cast.extras.length && !carriedPeople.length)) {
    return (
      <EmptyState icon={AudioLines} title="Chưa có dàn nhân vật" className="mt-2">
        Dàn nhân vật hiện ra khi truyện đã được phân vai.
      </EmptyState>
    );
  }
  return (
    <div className="mt-4">
      <div className="flex items-center gap-3 rounded-2xl border border-line bg-panel p-4">
        <div className="grid size-11 place-items-center rounded-full bg-accent-soft text-accent-text">
          <BookOpenText className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-[0.08em] text-fg-2">Người kể chuyện</div>
          <div className="mt-0.5 font-semibold">{cast.narrator.voice || "Mặc định"}</div>
          <div className="tabular text-xs text-fg-2">{formatNumber(cast.narrator.lines)} câu dẫn truyện · {formatLength(cast.narrator.seconds)}</div>
        </div>
        {cast.narrator.voice && <SampleButton id={`voice-${cast.narrator.voice}`} url={source.voiceUrl(cast.narrator.voice)} label={`Nghe giọng ${cast.narrator.voice}`} />}
      </div>
      <h3 className="mb-3 mt-6 text-sm font-semibold">
        Nhân vật <span className="font-normal text-fg-2">· {cast.characters.length} người có lời thoại</span>
      </h3>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {cast.characters
          .filter((person) => later || !reached || !person.firstChapter || reached.has(person.firstChapter))
          .map((person) => <PersonRow key={person.name} bookId={bookId} person={person} onPickVoice={onPickVoice} onMerge={onMerge} onRename={onRename} onGender={onGender} waiting={waiting} />)}
      </div>
      {reached && ahead(cast.characters, reached) > 0 && (
        <button type="button" onClick={() => setLater((value) => !value)} className="mt-3 text-sm font-medium text-fg-2 hover:text-fg">
          {later ? "Ẩn" : "Hiện"} {ahead(cast.characters, reached)} người chỉ xuất hiện ở chương sau chỗ đang nghe
        </button>
      )}
      {cast.extras.length > 0 && (
        <div className="mt-6">
          <button type="button" onClick={() => setExtras((value) => !value)} className="text-sm font-medium text-fg-2 hover:text-fg">
            {extras ? "Ẩn" : "Hiện"} {cast.extras.length} vai phụ chỉ xuất hiện trong một cảnh
          </button>
          {extras && <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{cast.extras.map((person) => <PersonRow key={person.name} bookId={bookId} person={person} onPickVoice={onPickVoice} onMerge={onMerge} onRename={onRename} onGender={onGender} waiting={waiting} />)}</div>}
        </div>
      )}
      {/* Phần nối tiếp: dàn mang sang chưa nói ở phần này (soát UX a6 01-10, B2 - tab từng ghi "Chưa có dàn"). Mở sẵn khi chưa ai
          nói câu nào - lúc ấy đây là cả dàn. */}
      {carriedPeople.length > 0 && (
        <div className="mt-6">
          {cast.characters.length ? (
            <button type="button" onClick={() => setCarried((value) => !value)} className="text-sm font-medium text-fg-2 hover:text-fg">
              {carried ? "Ẩn" : "Hiện"} {carriedPeople.length} người từ phần trước (chưa xuất hiện ở phần này)
            </button>
          ) : (
            <h3 className="text-sm font-semibold">
              Từ phần trước (chưa xuất hiện ở phần này) <span className="font-normal text-fg-2">· {carriedPeople.length} người giữ nguyên giọng</span>
            </h3>
          )}
          {(carried || !cast.characters.length) && (
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {carriedPeople.map((person) => <PersonRow key={person.name} bookId={bookId} person={person} onPickVoice={onPickVoice} onRename={onRename} onGender={onGender} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const TABS = ["chapters", "bookmarks", "history", "cast"] as const;

function dayLabel(epoch: number): string {
  const date = new Date(epoch * 1000);
  const today = new Date();
  const days = Math.round(
    (new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() - new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) /
      86_400_000,
  );
  if (days === 0) return "Hôm nay";
  if (days === 1) return "Hôm qua";
  return date.toLocaleDateString("vi-VN", { weekday: "long", day: "numeric", month: "numeric" });
}

function clockOf(epoch: number): string {
  return new Date(epoch * 1000).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

/** Lịch sử nghe: mỗi phiên một dòng, gom theo ngày; bấm để nghe tiếp từ cuối phiên ấy. */
function HistoryTab({ book }: { book: ListenBook }) {
  const source = useSource();
  const playBook = usePlayListenBook();
  const { data: sessions } = useQuery({
    queryKey: ["listen", "sessions", book.id],
    queryFn: () => source.sessions!(book.id),
    enabled: Boolean(source.sessions),
  });
  const titleOf = (chapterId: number) => {
    const chapter = book.chapters?.find((item) => item.id === chapterId);
    return chapter ? chapter.title : "chương đã gỡ";
  };
  if (!sessions?.length) {
    return (
      <EmptyState icon={History} title="Chưa có lịch sử nghe" className="mt-2">
        Mỗi lần nghe (bấm phát tới lúc dừng) sẽ hiện ở đây - để biết hôm nào nghe tới đâu.
      </EmptyState>
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
      <p className="text-sm text-fg-2">
        7 ngày qua: <span className="font-semibold text-fg">{formatLength(week)}</span> nghe cuốn này.
      </p>
      {[...groups.entries()].map(([day, items]) => (
        <section key={day} className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-fg-2">{day}</h3>
          <ul className="mt-2 divide-y divide-line">
            {items.map((item) => (
              <li key={item.id} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="tabular text-sm font-medium">
                    {/* Cùng phút thì một mốc giờ, không "13:57-13:57" (soát UX 29-09). */}
                    {clockOf(item.startedAt) === clockOf(item.endedAt) ? clockOf(item.startedAt) : `${clockOf(item.startedAt)}-${clockOf(item.endedAt)}`} ·{" "}
                    {formatLength(item.listened)}
                  </div>
                  <div className="tabular truncate text-xs text-fg-2">
                    {titleOf(item.from.chapterId)} {formatClock(item.from.seconds)} → {titleOf(item.to.chapterId)} {formatClock(item.to.seconds)}
                  </div>
                </div>
                {/* Nút nhảy tới CUỐI phiên nghe ấy - nói rõ tới đâu, "Nghe từ đây" mơ hồ (soát UX 29-09). */}
                <Button size="sm" variant="ghost" icon={Play} onClick={() => void playBook(book, item.to.chapterId, item.to.seconds)}>
                  Nghe tiếp từ {formatClock(item.to.seconds)}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

type RecordDialog = { kind: "create" | "rename" | "delete" | "move"; name: string; target?: { id: string; title: string } } | null;

/** Hộp "Nghe lại từ đầu (hồ sơ mới)" mở sẵn tên gợi ý. */
function newRecordDialog(book: ListenBook): RecordDialog {
  return { kind: "create", name: `Lần nghe ${(book.records?.length ?? 0) + 1}` };
}

/** Chọn cuốn nhận hồ sơ: mọi cuốn trong thư viện trừ cuốn này. Chỉ hỏi thư viện lúc hộp đang mở. */
function MoveTarget({ book, value, onChange }: { book: ListenBook; value: string; onChange: (target: { id: string; title: string }) => void }) {
  const { data, isLoading } = useListenLibrary();
  const others = (data ?? []).filter((item) => item.id !== book.id);
  if (isLoading) return <p className="text-sm text-fg-2">Đang mở thư viện…</p>;
  if (!others.length) return <p className="text-sm text-fg-2">Thư viện chưa có cuốn nào khác.</p>;
  return (
    <select
      aria-label="Chuyển sang cuốn"
      autoFocus
      value={value}
      onChange={(event) => {
        const chosen = others.find((item) => item.id === event.target.value);
        if (chosen) onChange({ id: chosen.id, title: chosen.title });
      }}
      className="h-10 rounded-lg border border-line bg-panel px-2 text-sm outline-none focus:border-accent"
    >
      <option value="" disabled>
        Chọn cuốn…
      </option>
      {others.map((item) => (
        <option key={item.id} value={item.id}>
          {item.title}
        </option>
      ))}
    </select>
  );
}

/**
 * Hồ sơ nghe của cuốn: dữ liệu nghe độc lập với sách, app giữ liên kết - một cuốn nhiều hồ sơ (nghe lại từ đầu mà giữ
 * lần trước, mỗi người trong nhà một hồ sơ). Cuốn đang nạp trong trình phát thì trình phát theo sang hồ sơ mới.
 * Chỉ có một hồ sơ (gần như mọi người): không hiện nút "Hồ sơ nghe: Mặc định"; "Nghe lại từ đầu (hồ sơ mới)…" nằm trong menu "Tuỳ chọn khác"
 * (soát UX 03-10) - vì thế trang sách giữ `dialog`, menu ấy mở được cùng hộp.
 */
function RecordPicker({ book, dialog, setDialog }: { book: ListenBook; dialog: RecordDialog; setDialog: Dispatch<SetStateAction<RecordDialog>> }) {
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
    if (dialog.kind === "create") switchTo(() => mutations.createRecord.mutateAsync(name), `Hồ sơ mới “${name || "không tên"}” - nghe từ chương đầu`, true);
    if (dialog.kind === "rename" && name) void done("Đã đổi tên hồ sơ")(mutations.renameRecord.mutateAsync({ recordId: active.id, name }));
    if (dialog.kind === "delete") switchTo(() => mutations.removeRecord.mutateAsync(active.id), `Đã xoá hồ sơ “${active.name}”`);
    // Bản làm lại của cùng truyện, hay lỡ nghe nhầm cuốn: hồ sơ (chỗ nghe, dấu trang, lịch sử) sang cuốn kia, thành hồ sơ đang dùng ở đó.
    const target = dialog.target;
    if (dialog.kind === "move" && target) {
      void player
        .switchRecord(book.id, () => mutations.moveRecord.mutateAsync({ recordId: active.id, toBook: target.id }))
        .then(() =>
          toast(`Đã chuyển hồ sơ “${active.name}” sang “${target.title}”`, {
            action: { label: "Mở cuốn ấy", onClick: () => navigate(`/book/${target.id}`) },
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
            className="mt-3 inline-flex h-8 max-w-full items-center gap-1.5 rounded-full border border-line px-3 text-xs text-fg-2 hover:bg-hover hover:text-fg"
          >
            <UserRound className="size-3.5 shrink-0" />
            <span className="shrink-0">Hồ sơ nghe:</span>
            <span className="truncate font-medium text-fg">{active.name}</span>
            <ChevronDown className="size-3.5 shrink-0" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={6} collisionPadding={12} className="z-50 w-72 rounded-xl border border-line bg-panel p-1.5 shadow-float">
            <p className="px-2 pb-1.5 pt-1 text-xs text-fg-2">
              Mỗi hồ sơ giữ chỗ nghe, dấu trang và lịch sử riêng - để nghe lại từ đầu mà giữ lần trước, hay mỗi người một hồ sơ.
            </p>
            {records.map((record) => (
              <DropdownMenu.Item
                key={record.id}
                onSelect={() => {
                  if (!record.active) switchTo(() => mutations.activateRecord.mutateAsync(record.id), `Đang dùng hồ sơ “${record.name}”`);
                }}
                className={cn(MENU_ITEM, "h-auto py-1.5")}
              >
                <Check className={cn("size-4 shrink-0", record.active ? "opacity-100" : "opacity-0")} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{record.name}</span>
                  <span className="block text-xs text-fg-3">
                    {record.last
                      ? `${book.chapters?.find((chapter) => chapter.id === record.last!.chapterId)?.title ?? "Chương"} · ${formatClock(record.last.seconds)} · `
                      : ""}
                    {record.updatedAt ? `nghe gần nhất ${dayLabel(record.updatedAt).toLowerCase()}` : "chưa nghe"}
                  </span>
                </span>
              </DropdownMenu.Item>
            ))}
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
            <DropdownMenu.Item onSelect={() => setDialog(newRecordDialog(book))} className={MENU_ITEM}>
              <Plus className="size-4" /> Nghe lại từ đầu (hồ sơ mới)…
            </DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setDialog({ kind: "rename", name: active.name })} className={MENU_ITEM}>
              <Pencil className="size-4" /> Đổi tên hồ sơ này…
            </DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setDialog({ kind: "move", name: active.name })} className={MENU_ITEM}>
              <ArrowRightLeft className="size-4" /> Chuyển sang cuốn khác…
            </DropdownMenu.Item>
            <DropdownMenu.Item onSelect={() => setDialog({ kind: "delete", name: active.name })} className={cn(MENU_ITEM, "text-danger")}>
              <Trash2 className="size-4" /> Xoá hồ sơ này…
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      )}
      <Dialog
        open={dialog !== null}
        onOpenChange={(open) => !open && setDialog(null)}
        title={
          dialog?.kind === "create"
            ? "Nghe lại từ đầu"
            : dialog?.kind === "rename"
              ? "Đổi tên hồ sơ"
              : dialog?.kind === "move"
                ? `Chuyển hồ sơ “${active.name}” sang cuốn khác`
                : `Xoá hồ sơ “${active.name}”?`
        }
        description={
          dialog?.kind === "create"
            ? "Hồ sơ mới bắt đầu từ chương đầu; hồ sơ đang dùng giữ nguyên chỗ nghe, dấu trang, lịch sử - quay lại lúc nào cũng được."
            : dialog?.kind === "move"
              ? `Chỗ nghe, dấu trang và lịch sử đi theo hồ sơ, thành hồ sơ đang dùng ở cuốn kia - vd khi có bản làm lại của cùng truyện.${
                  records.length > 1 ? " Cuốn này chuyển sang hồ sơ nghe gần nhất còn lại." : " Cuốn này sẽ như chưa nghe lần nào."
                }`
            : dialog?.kind === "delete"
              ? `Chỗ nghe, dấu trang và lịch sử của hồ sơ này mất hẳn, trên mọi máy đã ghép nối. Sách không bị ảnh hưởng${
                  records.length > 1 ? " - cuốn chuyển sang hồ sơ nghe gần nhất còn lại." : "; đây là hồ sơ duy nhất nên cuốn sẽ như chưa nghe lần nào."
                }`
              : undefined
        }
        width="max-w-md"
      >
        <form
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
              aria-label="Tên hồ sơ"
              placeholder="Tên hồ sơ"
              value={dialog?.name ?? ""}
              onChange={(event) => setDialog((current) => (current ? { ...current, name: event.target.value } : current))}
              className="h-10 rounded-lg border border-line bg-panel px-3 text-sm outline-none focus:border-accent"
            />
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setDialog(null)}>
              Huỷ
            </Button>
            <Button
              type="submit"
              variant={dialog?.kind === "delete" ? "danger" : "primary"}
              disabled={(dialog?.kind === "rename" && !dialog.name.trim()) || (dialog?.kind === "move" && !dialog.target)}
            >
              {dialog?.kind === "create" ? "Tạo và nghe từ đầu" : dialog?.kind === "delete" ? "Xoá hồ sơ" : dialog?.kind === "move" ? "Chuyển" : "Lưu"}
            </Button>
          </div>
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
}

export function BookScreen({
  extraActions,
  studioLink,
  notice,
  editing = {},
}: {
  extraActions?: (book: ListenBook) => ReactNode;
  /** Máy tính: lối sang Studio ngay trên dòng trạng thái của sách đang làm. */
  studioLink?: (book: ListenBook) => ReactNode;
  /** Dòng tình trạng riêng của nền tảng dưới tên sách (máy tính: tải sách của máy khác về máy). */
  notice?: (book: ListenBook) => ReactNode;
  editing?: false | EditingOptions;
}) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const requested = params.get("tab");
  const tab = TABS.includes(requested as (typeof TABS)[number]) ? (requested as string) : "chapters";
  const { data: book, isLoading, error } = useListenBook(id);
  const player = usePlayer();
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
  // Sách của máy khác đã tải về máy: dòng "Đã tải về máy" (desktop/RemoteDownload.tsx, cùng khoá truy vấn) đã nói đủ, bỏ dòng "Nghe thẳng"
  // đi cùng nó - hai dòng ngược nghĩa nhau (soát UX a11). Chỉ đọc bộ nhớ tạm, không tự hỏi máy chủ.
  const downloaded = useQuery<{ state?: string }>({ queryKey: ["listen", "download", id], enabled: false }).data?.state === "done";
  // Hook không được đặt sau `return` sớm: cuốn chưa nạp xong thì dùng một cuốn rỗng (nút lưu chưa hiện lúc ấy).
  const saver = useSaveBook(book ?? ({ id: id ?? "" } as ListenBook));
  const sharer = useShareBook(book ?? ({ id: id ?? "" } as ListenBook));
  // Chương đã "Làm trước" (điện thoại, PrepareAhead.kt): dấu "Đã làm sẵn" ở danh sách chương.
  const voice = useBookVoice(id);
  const prepared = usePreparedChapters(id ?? "", Boolean(book?.chapters?.some((chapter) => chapter.state === "text" && chapter.speech)));
  // Điện thoại: mở sách là hỏi máy tính đã ghép bản mới nhất của hồ sơ nghe (chỗ nghe, tên, hồ sơ vừa chọn bên ấy) -
  // không thì chỉ biết khi chính điện thoại phát hay dừng cuốn này.
  useEffect(() => {
    if (!id || !source.refreshListening) return;
    void source.refreshListening(id).then(() => client.invalidateQueries({ queryKey: ["listen", "book", id] })).catch(() => undefined);
  }, [client, id, source]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-[1180px] px-4 pt-6 sm:px-10">
        <Skeleton className="h-5 w-24" />
        <div className="mt-6 flex gap-6"><Skeleton className="size-36 rounded-lg" /><div className="flex-1 space-y-3 pt-3"><Skeleton className="h-7 w-2/3" /><Skeleton className="h-4 w-1/3" /></div></div>
      </div>
    );
  }
  if (error || !book) {
    return (
      <EmptyState icon={BookOpenText} title="Không tìm thấy sách này" className="mt-20" action={<Button onClick={() => navigate("/")}>Về thư viện</Button>}>
        Sách có thể đã bị chuyển sang thư mục khác hoặc bị xoá khỏi thư viện.
      </EmptyState>
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
  const waiting = editable && !workshop;
  const point = resumePoint(book, chapters);
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
  const restart = () => {
    const first = chapters.find(canPlay);
    if (!first) return;
    if (listening) {
      // Cuốn đang nạp trong trình phát: nhảy như mọi cú nhảy khác - trình phát nhớ chỗ cũ (nút ↺ "Quay lại chỗ vừa nghe"
      // + thông báo), không chỉ một thông báo 8 giây rồi mất (soát UX 29-09).
      player.jumpTo(first.id, 0);
      return;
    }
    const before = point;
    void playBook(book, first.id, 0);
    if (before && (before.chapter.id !== first.id || before.at > 30)) {
      toast("Đang nghe lại từ đầu", {
        // Có nút thao tác: đủ lâu để kịp bấm (mặc định 4 giây quá ngắn - soát UX 29-09).
        duration: 8000,
        description: `Chỗ cũ: ${before.chapter.title} · ${formatClock(before.at)}`,
        action: { label: "Quay lại chỗ cũ", onClick: () => void playBook(book, before.chapter.id, before.at) },
      });
    }
  };

  return (
    <div className="mx-auto max-w-[1180px] px-4 pb-16 pt-5 sm:px-10 sm:pt-7">
      <button type="button" onClick={() => navigate("/")} className="inline-flex items-center gap-1.5 text-sm text-fg-2 hover:text-fg">
        <ArrowLeft className="size-4" /> Thư viện
      </button>
      <header className="mt-5 flex flex-col gap-5 sm:flex-row sm:gap-7">
        <BookCover title={book.title} part={book.series?.part} size="lg" image={book.cover} playing={listening && player.playing} className="w-40 max-sm:mx-auto sm:w-44" />
        <div className="min-w-0 flex-1 max-sm:text-center">
          <h1 className="text-2xl font-bold leading-tight tracking-tight sm:text-[30px]">{book.title}</h1>
          {book.author && <p className="mt-1.5 text-[15px] text-fg-2">{book.author}</p>}
          <p className="tabular mt-2 text-sm text-fg-2">
            {book.narrator && `Giọng kể ${book.narrator} · `}
            {textOnly
              ? `${book.chaptersTotal} chương`
              : phonePartial
                ? `${formatLength(book.duration)} phần đã có` // số chương đã nằm ở dòng "Sách này có x/y chương đã thu" ngay dưới
                : book.complete
                  ? `${book.chaptersTotal} chương · ${formatLength(book.duration)}`
                  : `${book.chaptersAvailable}/${book.chaptersTotal} chương có audio · ${formatLength(book.duration)} phần đã có`}
          </p>
          {textOnly && (
            <p className="mt-2 inline-flex flex-wrap items-center gap-2 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-text">
              {textBookLine(speaks)}
            </p>
          )}
          {!book.complete && !textOnly && (
            <p className="mt-2 inline-flex flex-wrap items-center gap-2 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-text">
              {book.producing && <Vu className="h-2.5" />}
              {book.producing
                ? "Đang thu âm - chương mới tự hiện ra khi xong"
                : book.imported
                  ? "Chưa hoàn thành - file sách này chỉ có các chương đã làm; mở bản mới hơn để nghe tiếp"
                  : phonePartial
                    ? partialBookLine(book.chaptersAvailable, book.chaptersTotal)
                    : "Chưa hoàn thành - việc thu đang dừng"}
              {studioLink?.(book)}
            </p>
          )}
          {book.remote && !downloaded && (
            <p className="mt-2 inline-flex flex-wrap items-center gap-1.5 rounded-full bg-info-soft px-3 py-1 text-xs font-medium text-info">
              <Laptop className="size-3.5" />{" "}
              {typeof book.remote === "object"
                ? `Nghe thẳng từ ${book.remote.computer || "máy khác"} - chương nghe tới được giữ lại trên máy này`
                : "Nghe thẳng từ máy tính - tải về để nghe cả khi không có mạng"}
            </p>
          )}
          {notice?.(book)}
          {syncs && <EditsSyncBanner book={book} />}
          <LocalEditsBanner book={book} />
          {textOnly && editable && <BookSuggestions book={book} />}
          <div className="mt-4 max-w-md max-sm:mx-auto">
            {!textOnly && (
              <>
                <Progress value={book.progress.fraction} tone={book.progress.finished ? "success" : "accent"} size="sm" label="Đã nghe" />
                <div className="tabular mt-1.5 flex justify-between text-xs text-fg-2">
                  <span>{book.progress.finished || book.progress.caughtUp ? bookStatusText(book) : heard > 0 ? `Đã nghe ${formatLength(heard)}` : listening ? "Đang nghe" : "Chưa nghe"}</span>
                  {/* Tính theo phần ĐÃ PHỦ (chỗ tua qua vẫn là chưa nghe), khác "còn X" theo vị trí ở màn "Đang nghe" - nói rõ để hai con
                      số không trông như mâu thuẫn (soát UX 29-09). */}
                  {!book.progress.finished && !book.progress.caughtUp && heard > 0 && <span>còn {formatLength(left)} chưa nghe</span>}
                </div>
              </>
            )}
            <RecordPicker book={book} dialog={recordDialog} setDialog={setRecordDialog} />
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-2 max-sm:justify-center">
            {point && !caughtUp && (
              <Button
                variant="primary"
                size="lg"
                icon={listening && player.playing ? Pause : finished ? RotateCcw : Play}
                onClick={() => (finished ? restart() : listening ? player.toggle() : void playBook(book))}
                // Điện thoại: nút chính một hàng riêng, các nút phụ luôn ở hàng dưới theo cùng thứ tự - nhãn đổi độ dài khi
                // phát/dừng từng làm hàng xuống dòng khác đi, "Từ đầu" nhảy sang chỗ nút khác (soát UX 29-09).
                className="min-w-0 max-w-full max-sm:w-full"
              >
                {/* Tên chương dài (truyện dịch) hay chữ hệ thống to: cắt "…" trong nút thay vì tràn ra hai mép màn hình (soát UX a9). */}
                <span className="min-w-0 truncate">{primaryLabel}</span>
              </Button>
            )}
            {caughtUp && (
              <p className="rounded-xl bg-hover px-4 py-2.5 text-sm text-fg-2">Đã nghe hết phần đã có. Chương mới sẽ hiện ở đây khi làm xong.</p>
            )}
            <Tooltip label="Đọc bằng mắt - đọc được cả chương chưa thu âm; “Nghe từ đây” chuyển sang nghe đúng câu đang đọc">
              <Button
                variant={textOnly && !point ? "primary" : "outline"}
                size="lg"
                icon={BookOpen}
                onClick={() => navigate(`/book/${book.id}/read/${book.state.reading?.chapterId ?? point?.chapter.id ?? chapters[0]?.id ?? ""}`)}
              >
                {book.state.reading ? "Đọc tiếp" : "Đọc"}
              </Button>
            </Tooltip>
            {chapters.length > 0 && (
              <>
                <IconButton label="Tìm chữ trong sách" icon={Search} size="lg" onClick={() => setFinding(true)} />
                <FindInBook book={book} open={finding} onOpenChange={setFinding} />
              </>
            )}
            {started && point && !finished && (
              <Tooltip label="Nghe lại từ chương đầu tiên">
                <Button variant="ghost" size="lg" icon={RotateCcw} onClick={restart}>
                  Từ đầu
                </Button>
              </Tooltip>
            )}
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <IconButton label="Tuỳ chọn khác" icon={MoreHorizontal} size="lg" />
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content align="start" sideOffset={6} collisionPadding={12} className="z-50 min-w-56 max-w-[min(20rem,calc(100vw-24px))] rounded-xl border border-line bg-panel p-1.5 shadow-float">
                  {source.records && book.records?.length === 1 && (
                    <DropdownMenu.Item onSelect={() => setRecordDialog(newRecordDialog(book))} className={MENU_ITEM}>
                      <Plus className="size-4" /> Nghe lại từ đầu (hồ sơ mới)…
                    </DropdownMenu.Item>
                  )}
                  {/* Một hồ sơ thì không có nút hồ sơ nghe: chuyển chỗ nghe sang cuốn khác (bản làm lại của cùng truyện) nằm ở đây. */}
                  {source.records && book.records?.length === 1 && (
                    <DropdownMenu.Item onSelect={() => setRecordDialog({ kind: "move", name: book.records![0].name })} className={MENU_ITEM}>
                      <ArrowRightLeft className="size-4" /> Chuyển chỗ nghe sang cuốn khác…
                    </DropdownMenu.Item>
                  )}
                  {!textOnly && (
                    <DropdownMenu.Item onSelect={() => mutations.finished.mutate(!book.progress.finished)} className={MENU_ITEM}>
                      <CheckCheck className="size-4" />
                      {book.progress.finished ? "Đánh dấu chưa nghe xong" : "Đánh dấu đã nghe xong"}
                    </DropdownMenu.Item>
                  )}
                  {editing !== false && editable && (
                    <>
                      <DropdownMenu.Separator className="my-1 h-px bg-line" />
                      <DropdownMenu.Item onSelect={() => setEditOpen(true)} className={MENU_ITEM}>
                        <Pencil className="size-4" /> {textOnly ? "Sửa tên, bìa…" : "Sửa tên, bìa, nhạc nền…"}
                      </DropdownMenu.Item>
                      {textOnly && <PlaylistSubmenu bookId={book.id} />}
                      {syncs && <SendEditsItem book={book} />}
                      {!workshop && !syncs && !book.capabilities?.local && saver.available && (
                        <>
                          <DropdownMenu.Item
                            disabled={!book.edits || saver.busy}
                            onSelect={() => void saver.save()}
                            className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
                          >
                            <Save className="size-4" /> {book.edits ? `Lưu (${book.edits} thay đổi)` : "Lưu (chưa có thay đổi)"}
                          </DropdownMenu.Item>
                          <DropdownMenu.Item onSelect={() => setSaveAsOpen(true)} className={MENU_ITEM}>
                            <FileDown className="size-4" /> Lưu thành…
                          </DropdownMenu.Item>
                          {sharer.available && (
                            <DropdownMenu.Item
                              disabled={sharer.busy}
                              onSelect={() => void sharer.share()}
                              className={cn(MENU_ITEM, "data-[disabled]:opacity-50")}
                            >
                              <Share2 className="size-4" /> Chia sẻ…
                            </DropdownMenu.Item>
                          )}
                        </>
                      )}
                      {!workshop && Boolean(book.wishes) && (
                        <DropdownMenu.Item onSelect={() => setWishesOpen(true)} className={MENU_ITEM}>
                          <Hourglass className="size-4" /> Việc đang chờ {syncs ? `gửi về ${holderName(book.remote)}` : "máy làm sách"} ({book.wishes})
                        </DropdownMenu.Item>
                      )}
                    </>
                  )}
                  {editing !== false && <EditBlockedItem book={book} />}
                  {editing !== false && <StudioOnlyItem book={book} />}
                  {editing !== false && <ProjectFileItems book={book} onViews={() => setViewsOpen(true)} />}
                  {editing !== false && <TextBookItems book={book} />}
                  {extraActions?.(book)}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>
        </div>
      </header>
      <Tabs value={tab} onValueChange={(value) => setParams({ tab: value }, { replace: true })} className="mt-8">
        <TabsList>
          <TabsTrigger value="chapters" count={chapters.length}>Chương</TabsTrigger>
          <TabsTrigger value="bookmarks" count={book.state.bookmarks.length || undefined}>Dấu trang</TabsTrigger>
          <TabsTrigger value="history">Lịch sử</TabsTrigger>
          {!textOnly && <TabsTrigger value="cast">Nhân vật</TabsTrigger>}
        </TabsList>
        <TabsContent value="chapters" className="mt-2">
          {chaptersByPart(chapters, book.parts).map((group, index) => (
            <section key={group.heading ?? index} aria-label={group.heading ?? undefined}>
              {group.heading && <h3 className="px-2 pb-1 pt-4 text-sm font-semibold text-fg-2 sm:px-3">{group.heading}</h3>}
              {group.chapters.map((chapter) => (
                <ChapterRow
                  key={chapter.id}
                  book={book}
                  chapter={chapter}
                  onDone={(chapterId, done) => mutations.chapterDone.mutate({ chapterId, done })}
                  onRename={editable ? setRenamingChapter : undefined}
                  prepared={chapter.state === "text" && prepared.has(chapter.id)}
                  voice={voice}
                />
              ))}
            </section>
          ))}
        </TabsContent>
        <TabsContent value="bookmarks">
          <BookmarksTab book={book} />
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
      </Tabs>
      {editing !== false && editable && (
        <>
          <EditBookDialog book={book} open={editOpen} onOpenChange={setEditOpen} onOpenStudio={editing.onOpenStudio ? () => editing.onOpenStudio?.(book) : undefined} />
          <RenameChapterDialog book={book} chapter={renamingChapter} onClose={() => setRenamingChapter(null)} />
          <RenamePersonDialog bookId={book.id} person={renamingPerson} onClose={() => setRenamingPerson(null)} onSaved={() => refreshAfterEdit(client, book.id)} />
          <SaveAsDialog book={book} open={saveAsOpen} onOpenChange={setSaveAsOpen} pickFolder={editing.pickFolder} />
          <ProjectViewsDialog book={book} open={viewsOpen} onOpenChange={setViewsOpen} />
          {waiting && (
            <>
              <GenderDialog bookId={book.id} person={genderPerson} onClose={() => setGenderPerson(null)} waiting onSaved={() => refreshAfterEdit(client, book.id)} />
              <MergeDialog
                bookId={book.id}
                person={mergingPerson}
                people={castView?.characters ?? []}
                onClose={() => setMergingPerson(null)}
                waiting
                onSaved={() => refreshAfterEdit(client, book.id)}
              />
              <WishesDialog bookId={book.id} count={book.edits ?? 0} open={wishesOpen} onOpenChange={setWishesOpen} syncs={syncs} />
            </>
          )}
        </>
      )}
    </div>
  );
}
