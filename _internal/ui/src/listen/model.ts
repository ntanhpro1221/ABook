import type { Capabilities } from "@/shared/capabilities";
import type { EditsSyncState } from "@/shared/editsSync";
import type { CoverImage } from "@/shared/cover";
// Hợp đồng dữ liệu của phía NGHE - chung cho máy tính và Android.
// Máy tính: server cục bộ dựng từ project (abook/webui/listen_view.py).
// Android: đọc từ gói sách đã tải về (book.json cùng hình dạng).

export interface ListenChapter {
  id: number;
  index: number;
  title: string;
  subtitle: string;
  fullTitle: string;
  duration: number;
  available: boolean;
  /** Cả bộ trong một file .abook (phiên bản 3): số phần chứa chương này; sách một phần: không có. */
  part?: number | null;
  /** "text": chương chỉ có chữ - đọc được, chưa có âm thanh (phiên bản 5, docs/LISTEN_ANYTHING.md mục 1); chương nghe được: không có. */
  state?: "text" | null;
  /** Chương chỉ-có-chữ mà máy này có giọng đọc cho (source.tsx `withReadAloud`): nghe ngay được, dù chưa có audio. */
  speech?: boolean;
  /** Dòng người nghe đã bỏ khỏi phần đọc (lớp sửa `skip`, gợi ý dòng ghi công): màn đọc và đọc to bỏ qua - textScript.ts `withoutLines`. */
  skip?: string[];
}

/** Bấm nghe được: chương có audio, hay chương chỉ-có-chữ mà máy có giọng đọc. */
export function canPlay(chapter: Pick<ListenChapter, "available" | "speech">): boolean {
  return chapter.available || chapter.speech === true;
}

/** Giai đoạn của cả cuốn: "text" = chỉ có chữ (chưa chương nào có audio, thư viện ghi "Chỉ có chữ"); không có = sách nghe được như mọi sách. */
export type BookStage = "text";

/** Một phần của sách mở từ file cả bộ (`parts` của book.json, webui/bookfile.pack_series). `chapters`: mã chương đầu và cuối. */
export interface BookPart {
  part: number;
  title: string;
  chapters: [number, number];
  duration: number;
  narrator: string;
}

export interface Bookmark {
  id: string;
  chapterId: number;
  seconds: number;
  note: string;
  at: number;
  /** Dấu đặt ở màn đọc trỏ tới CÂU: thứ tự câu trong chương (như `?at=`) và ~60 chữ đầu câu. Dấu đặt từ trình phát không có hai trường này. */
  index?: number;
  quote?: string;
  /** Máy chủ trả về dấu đã có ngay chỗ ấy (±5 giây, hay cùng câu) thay vì tạo dấu trùng. */
  existing?: boolean;
}

/** Màn đọc mở đúng câu của một dấu trang đặt ở màn đọc (`?at=` - ReaderScreen); dấu đặt từ trình phát (không có câu) thì null. */
export function bookmarkReadPath(bookId: string, mark: Bookmark): string | null {
  return typeof mark.index === "number" ? `/book/${bookId}/read/${mark.chapterId}?at=${mark.index}` : null;
}

/** Câu mà dấu trang đặt ở màn đọc trỏ tới. */
export interface BookmarkSentence {
  index: number;
  quote: string;
}

export interface ChapterState {
  heard: number;
  done: boolean;
  duration?: number;
  at?: number;
}

export interface ListeningState {
  last?: { chapterId: number; seconds: number; at: number };
  chapters: Record<string, ChapterState>;
  rate?: number;
  finished?: boolean;
  /** Lúc tự đánh dấu (chưa) nghe xong - nghe tiếp sau mốc này nghĩa là đang nghe lại. */
  finishedAt?: number;
  bookmarks: Bookmark[];
  /** Chỗ đọc dở ở chế độ đọc (câu thứ `index` của chương). */
  reading?: { chapterId: number; index: number; at: number };
  updatedAt?: number;
}

export interface BookProgress {
  heardSeconds: number;
  totalSeconds: number;
  fraction: number;
  chaptersDone: number;
  finished: boolean;
  /** Sách đang làm dở, đã nghe hết phần đã có - chưa phải "nghe xong". */
  caughtUp?: boolean;
  /** Đã nghe hết rồi quay lại nghe một đoạn: tiến độ theo chỗ đang nghe, không còn "nghe xong". */
  rewound?: boolean;
}

/** Một hồ sơ nghe gắn với cuốn: dữ liệu nghe độc lập với sách, app giữ liên kết - một cuốn nhiều hồ sơ
 *  (webui/listening.py, Android Store). `updatedAt`: lần nghe gần nhất của hồ sơ. */
export interface ListeningRecord {
  id: string;
  name: string;
  createdAt?: number | null;
  updatedAt?: number | null;
  active: boolean;
  /** Chỗ nghe cuối của hồ sơ (máy tính); điện thoại chưa gửi thì không có. */
  last?: { chapterId: number; seconds: number } | null;
}

export interface ListenBook {
  id: string;
  title: string;
  /** Tác giả ghi trong file sách (EPUB / DOCX / PDF); trống khi không có. */
  author?: string;
  narrator: string;
  duration: number;
  chaptersTotal: number;
  chaptersAvailable: number;
  complete: boolean;
  producing: boolean;
  /** Chưa làm xong và cũng không đang làm (Studio đã dừng). */
  paused?: boolean;
  /** Đang làm mà tạm dừng (người dùng bấm "Tạm dừng", hay máy tính chạy pin) - tiến trình vẫn sống. */
  pauseReason?: "battery" | "listener" | null;
  /** Máy tính: cuốn mở từ file `.abook` (webui/packages.py) - nghe được, không có dự án trong Studio. */
  imported?: boolean;
  /** Giai đoạn của cuốn; `null` / không có: sách nghe được như mọi sách. */
  stage?: BookStage | null;
  /** Máy tính, sách chỉ-chữ: mã dự án Studio đã làm từ cuốn này ("Làm sách nói từ cuốn này"), nếu còn trong thư viện. */
  studioProject?: string | null;
  updatedAt: number | null;
  /** Giây Unix lúc sách vào thư viện này ("Mới thêm" ở ô xếp); không biết thì thiếu - xếp theo `updatedAt`. */
  addedAt?: number | null;
  state: ListeningState;
  progress: BookProgress;
  lastChapterTitle?: string;
  /** Ảnh bìa thật (webui/covers.py); không có thì vẽ bìa từ tên. */
  cover?: CoverImage | null;
  /** Sách đang làm: ước lượng của giai đoạn hiện tại (máy tính). */
  eta?: { phase: string; seconds: number } | null;
  chapters?: ListenChapter[];
  /** File cả bộ nhiều phần: các phần theo thứ tự (danh sách chương gom theo phần); sách một phần: rỗng hay không có. */
  parts?: BookPart[];
  /** Điện thoại: cuốn này nằm trên máy tính, nghe thẳng qua mạng (chưa tải về). */
  /** Cuốn nằm ở máy khác, nghe thẳng qua mạng: điện thoại - `true` (trên máy tính đã ghép); máy tính - tên máy tính
   *  kia (webui/remote_books.py). */
  remote?: boolean | { computer: string; device?: string };
  /** Phần nối tiếp của "Làm tiếp cuốn này" (continues.json của máy tính): mã phần đầu + thứ tự phần; phần đầu và sách lẻ:
   *  null. Có ở sách của máy tính, sách nghe thẳng và sách đã tải về điện thoại (book.json). */
  series?: SeriesLink | null;
  /** Hồ sơ nghe gắn với cuốn này (chưa nghe lần nào thì rỗng). */
  records?: ListeningRecord[];
  /** Máy này làm được gì với cuốn này (shared/capabilities.ts): có xưởng không, nghe thẳng từ máy khác không, có Studio không. */
  capabilities?: Capabilities;
  /** Số thay đổi người nghe đã làm trên cuốn nhập từ file (lớp sửa, docs/EDITING.md); không có thì 0. */
  edits?: number;
  /** Trong số `edits`: bao nhiêu là ý muốn chờ Studio (đổi giọng, giới, gộp người, cách đọc...) - chưa áp vào audio. */
  wishes?: number;
  /** Cuốn tải từ máy tính (điện thoại): phần sửa chưa gửi về máy tính và kết quả lần gửi gần nhất (EditsSync.kt). */
  editsSync?: EditsSyncState;
  /** Cuốn nhập từ file dự án `.abookproj` (docs/EDITING.md, P3); cuốn từ file `.abook`: null. `workshop` "present" - xưởng đi theo cuốn
   *  để lưu lại; "pending" - chỉ có phần nghe, chờ "Dựng xưởng" (`built` = mã dự án đã dựng). `views`: bản chụp chỉ đọc có trong file. */
  projectFile?: { workshop: "present" | "pending"; views: ("work" | "casting" | "names")[]; built?: string | null } | null;
}

export interface SeriesPlace {
  /** Khoá gom nhóm: chuỗi "Làm tiếp cuốn này" của máy chủ ("chain:<phần đầu>") hay tên bộ ("title:<tên>") - hai kiểu không
   *  bao giờ trộn: dự án lạ tên "X · Phần 2" không vào nhóm các phần thật của X (soát UX 29-09, N10). */
  key: string;
  /** Tên hiện của bộ. */
  series: string;
  volume: number | null;
  /** Chữ gọi một tập của bộ, viết thường: "tập", "quyển" hay "phần". */
  unit: string;
}

/** Chỗ của một phần trong chuỗi "Làm tiếp cuốn này" (continues.json, máy chủ tính): mã phần đầu + thứ tự phần. */
export interface SeriesLink {
  root: string;
  part: number;
}

/** Bộ và số tập từ tên sách ("Throne of Magical Arcana · Tập 16" -> bộ "Throne of Magical Arcana", tập 16; "Truyện · Phần 2"
 * -> phần 2, tên phần sau mà "Làm tiếp cuốn này" đặt). */
export function seriesOf(title: string): SeriesPlace {
  const match = title.match(/^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(\d+)\b/i);
  if (!match) return { key: `title:${title.trim()}`, series: title.trim(), volume: null, unit: "tập" };
  const word = match[2].toLowerCase();
  const series = match[1].trim();
  return { key: `title:${series}`, series, volume: Number(match[3]), unit: word === "quyển" || word === "phần" ? word : "tập" };
}

/** Bộ và số tập của mọi cuốn trong thư viện. Phần của một cuốn làm nhiều đợt ("Làm tiếp cuốn này") đi theo chuỗi máy chủ
 * biết (`series`) - đổi tên một phần không làm mất nhóm; nhóm mang tên phần đầu. Còn lại theo tên (`seriesOf`), thêm một
 * luật: cuốn KHÔNG đánh số mà tên đúng bằng tên một bộ có tập đánh số là tập 1 của bộ ấy (sách nhập từ file .abook, máy chủ
 * cũ không gửi chuỗi) - nhưng chỉ khi có ĐÚNG MỘT cuốn như thế. Hai bản cùng tên không số (bản sách nói và bản chỉ-chữ của một
 * truyện, bản nhập hai lần) thì không biết bản nào là tập 1: để cả hai đứng lẻ, đừng gom thành "4 tập" không số (soát UX 05-10).
 * Có cả bản nghe được lẫn bản chỉ-chữ thì bản chỉ-chữ không tranh chỗ tập 1. */
export function seriesIndex(books: { id: string; title: string; series?: SeriesLink | null; stage?: string | null }[]): Map<string, SeriesPlace> {
  const titles = new Map(books.map((book) => [book.id, book.title]));
  const places = new Map<string, SeriesPlace>();
  for (const book of books) {
    if (!book.series) continue;
    const name = seriesOf(titles.get(book.series.root) ?? book.title).series;
    places.set(book.id, { key: `chain:${book.series.root}`, series: name, volume: book.series.part, unit: "phần" });
  }
  // Phần đầu không mang `series` (máy chủ chỉ gắn cho phần nối tiếp): nó là sách mà phần khác trỏ về.
  const roots = new Set(books.map((book) => book.series?.root));
  for (const book of books) {
    if (!places.has(book.id) && roots.has(book.id)) {
      places.set(book.id, { key: `chain:${book.id}`, series: seriesOf(book.title).series, volume: 1, unit: "phần" });
    }
  }
  const byTitle = new Map(books.filter((book) => !places.has(book.id)).map((book) => [book.id, seriesOf(book.title)]));
  const units = new Map<string, string>();
  for (const place of byTitle.values()) if (place.volume !== null && !units.has(place.key)) units.set(place.key, place.unit);
  // Ứng viên tập 1 của mỗi bộ: các cuốn không số mà bộ có tập đánh số; chọn trong số cuốn nghe được trước, chỉ-chữ sau.
  const stages = new Map(books.map((book) => [book.id, book.stage]));
  const candidates = new Map<string, string[]>();
  for (const [id, place] of byTitle) {
    if (place.volume === null && units.has(place.key)) candidates.set(place.key, [...(candidates.get(place.key) ?? []), id]);
  }
  const first = new Set<string>();
  for (const ids of candidates.values()) {
    const heard = ids.filter((id) => stages.get(id) !== "text");
    const pool = heard.length ? heard : ids;
    if (pool.length === 1) first.add(pool[0]);
  }
  for (const [id, place] of byTitle) {
    places.set(id, first.has(id) ? { ...place, volume: 1, unit: units.get(place.key)! } : place);
  }
  return places;
}

/** Nhãn tập cho cuốn trong bộ mà bìa không tự có: tên không mang số và không phải phần nối tiếp ("Tập 1" của cuốn không số - soát UX 05-10:
 *  Tập 2 có nhãn mà Tập 1 thì không). Tên có số / phần nối tiếp đã có nhãn riêng trên bìa. */
export function volumeBadge(book: { title: string; series?: SeriesLink | null }, volume: number | null, unit: string): string | null {
  if (volume === null || seriesOf(book.title).volume !== null || (book.series?.part ?? 0) > 1) return null;
  return `${unit.charAt(0).toUpperCase()}${unit.slice(1)} ${volume}`;
}

/** Một phiên nghe: bấm phát tới lúc dừng. */
export interface ListeningSession {
  id: string;
  device: string;
  startedAt: number;
  endedAt: number;
  listened: number;
  from: { chapterId: number; seconds: number };
  to: { chapterId: number; seconds: number };
}

// ---- Nhật ký đêm (hẹn giờ ngủ) ------------------------------------------------------------------------------
// Cùng hình dạng với nhật ký của lõi phát Android (Bedtime.kt); máy tính ghi bằng NightRecorder (night.ts).

export interface NightPosition {
  chapterId: number | null;
  chapterTitle: string;
  seconds: number;
}

export interface NightEvent {
  type: "timer" | "touch" | "shake" | "extend" | "still" | "moved" | "fading" | "stopped";
  at: number;
  action?: string;
  minutes?: number;
  position: NightPosition;
}

export interface NightSession {
  id?: string;
  device?: string;
  bookId?: string;
  bookTitle: string;
  startedAt: number;
  endedAt?: number | null;
  dismissed?: boolean;
  events: NightEvent[];
  timeline: (NightPosition & { at: number })[];
}

export interface ScriptSegment {
  id: number;
  paragraph: number;
  text: string;
  kind: "narration" | "dialogue" | "thought" | "heading" | string;
  speaker: string;
  start: number | null;
  end: number | null;
  status: string;
  /** Mã ổn định + băm chữ của câu (sách đóng gói mang theo): ý muốn chờ Studio trỏ tới câu bằng cặp này. */
  stableId?: string;
  textSha256?: string;
  /** Cảm xúc / mức của câu (sách đời cũ không có) và chữ đem đọc đã áp thay chữ sách. */
  emotion?: string;
  intensity?: number;
  spoken?: string;
  /** Mốc từng chữ hiện: [bắt đầu_ms, kết thúc_ms] tính từ đầu MP3 chương, một cặp cho mỗi chữ (listen/words.ts); sách chưa căn thì không có. */
  words?: [number, number][];
  /** Chương chỉ-có-chữ: đoạn này là dòng ngăn cảnh ("***") - không đọc, người nghe nghe một quãng lặng (textScript.ts `sceneBreakGaps`). */
  sceneBreak?: boolean;
}

export interface Script {
  chapterId: number;
  title: string;
  timed: boolean;
  duration: number;
  segments: ScriptSegment[];
}

export interface CastMember {
  name: string;
  displayName: string;
  /** Tên gốc khi người nghe đã "Đổi tên" (displayName là tên đã đổi) - chỉ có khi đã đổi. */
  originalName?: string;
  gender: string;
  age: string;
  lines: number;
  seconds: number;
  voice: { key: string; preset: string; tone: string } | null;
  sampleId: number | null;
  firstChapter: string;
  /** Sách cả bộ: những phần người này lên tiếng. */
  parts?: number[];
  /** Số câu đã có tiếng (store.cast) - "Đổi giới tính" nói trước bấy nhiêu câu có thể phải thu lại. */
  recorded?: number;
  /** Giọng/giới người nghe đã chọn mà dây chuyền chưa áp (store.pending_voices). */
  pendingVoice?: { preset: string; gender: string } | null;
  /** Đã "Gộp vào…" người khác mà chưa áp (store.cast): tên người sẽ nhận các câu của người này. */
  mergedInto?: string | null;
}

export interface Cast {
  /** `pendingVoice`: giọng người kể người nghe đã chọn ở Studio mà dây chuyền chưa áp (store.cast). */
  narrator: { voice: string; lines: number; seconds: number; pendingVoice?: { preset: string; gender: string } | null; /** Câu kể chờ thu lại theo sửa của người nghe. */ redo?: number };
  characters: CastMember[];
  extras: CastMember[];
  /** Studio, phần nối tiếp: giọng mang từ phần trước của những người chưa nói câu nào ở phần này. */
  carried?: CastMember[];
}

/** "Phần 2 · Tên": tên phần là tên cuốn không kèm hậu tố "· Phần N" mà `parts[].title` mang theo. */
export function partHeading(part: BookPart): string {
  const name = seriesOf(part.title).series;
  return name ? `Phần ${part.part} · ${name}` : `Phần ${part.part}`;
}

/** Danh sách chương gom theo phần: chỉ khi cuốn có nhiều hơn một phần (không thì một nhóm không tiêu đề). Chương thuộc phần
 *  theo `chapter.part`, thiếu thì theo khoảng mã chương của `parts`; chương liền nhau cùng phần vào một nhóm. */
export function chaptersByPart(chapters: ListenChapter[], parts: BookPart[] | undefined): { heading: string | null; chapters: ListenChapter[] }[] {
  if (!parts || parts.length < 2) return [{ heading: null, chapters }];
  const partOf = (chapter: ListenChapter) =>
    chapter.part ?? parts.find((part) => chapter.id >= part.chapters[0] && chapter.id <= part.chapters[1])?.part ?? null;
  const groups: { heading: string | null; chapters: ListenChapter[]; part: number | null }[] = [];
  for (const chapter of chapters) {
    const part = partOf(chapter);
    const last = groups[groups.length - 1];
    if (last && last.part === part) last.chapters.push(chapter);
    else {
      const found = parts.find((item) => item.part === part);
      groups.push({ heading: found ? partHeading(found) : null, chapters: [chapter], part });
    }
  }
  return groups.map(({ heading, chapters: items }) => ({ heading, chapters: items }));
}

/** Cuốn của thẻ "Đang nghe dở" ở Thư viện: cuốn đang nằm trong trình phát (chưa chắc thư viện đã tải đã biết chỗ nghe của nó - chỉ làm mới
 *  khi dừng), không thì cuốn chưa xong nghe gần nhất. Trước đây chỉ xét chỗ nghe đã lưu nên bấm phát cuốn khác mà thẻ vẫn đứng ở cuốn cũ. */
export function listeningBook(books: readonly ListenBook[], playingBookId: string | null | undefined): ListenBook | undefined {
  const playing = playingBookId ? books.find((book) => book.id === playingBookId && !book.progress.finished) : undefined;
  if (playing) return playing;
  return books
    .filter((book) => book.state.last && !book.progress.finished)
    .sort((a, b) => (b.state.last?.at ?? 0) - (a.state.last?.at ?? 0))[0];
}

/** Các cuốn mời nghe khi vừa hết một cuốn ("Nghe cuốn khác", tối đa `limit`): cuốn đang nghe dở trước (gần nhất trước), rồi cuốn chưa nghe
 *  (theo thứ tự thư viện). Bỏ cuốn vừa nghe, cuốn đã nghe xong / đã nghe hết phần có, cuốn chưa có chương nào nghe được, và sách chỉ có chữ khi
 *  máy chưa có giọng đọc (`speaks` false) - bấm vào đó không phát được. */
export function otherBooksToHear(books: readonly ListenBook[], currentId: string | undefined, speaks: boolean, limit = 3): ListenBook[] {
  const open = books.filter(
    (book) =>
      book.id !== currentId &&
      !book.progress.finished &&
      !book.progress.caughtUp &&
      // Sách chỉ có chữ chưa chương nào có audio (chaptersAvailable 0) nhưng giọng máy đọc được ngay.
      (book.stage === "text" ? speaks && book.chaptersTotal > 0 : book.chaptersAvailable > 0),
  );
  const started = (book: ListenBook) => Boolean(book.state.last);
  const listening = open.filter(started).sort((a, b) => (b.state.last?.at ?? 0) - (a.state.last?.at ?? 0));
  return [...listening, ...open.filter((book) => !started(book))].slice(0, limit);
}

/** Chương nên phát khi bấm "Nghe": chỗ đang nghe dở nếu chương ấy còn nghe được (nghe gần hết thì sang chương
 *  kế), không thì chương đầu tiên chưa nghe xong, cuối cùng là chương đầu. */
export function resumePoint(book: ListenBook, chapters: ListenChapter[]): { chapter: ListenChapter; at: number } | null {
  const playable = chapters.filter(canPlay);
  if (!playable.length) return null;
  const last = book.state.last;
  if (last) {
    const index = playable.findIndex((chapter) => chapter.id === last.chapterId);
    if (index >= 0) {
      const chapter = playable[index];
      const length = knownDuration(book.state, chapter);
      const nearEnd = length > 0 && length - last.seconds < 15;
      if (!nearEnd) return { chapter, at: last.seconds };
      if (playable[index + 1]) return { chapter: playable[index + 1], at: 0 };
      // Nghe tới cuối chương cuối ĐÃ CÓ của một cuốn còn đang làm: đứng yên ở đó, đừng quay về chương đầu.
      if (!book.complete) return { chapter, at: last.seconds };
    }
  }
  const unheard = playable.find((chapter) => !book.state.chapters[String(chapter.id)]?.done);
  return { chapter: unheard ?? playable[0], at: 0 };
}

/** Độ dài chương: của gói sách, hay - chương đọc to chưa có audio - độ dài trình phát đã ghi lúc nghe (giây ảo của bộ máy đọc to). */
export function knownDuration(state: ListeningState, chapter: ListenChapter): number {
  return chapter.duration > 0 ? chapter.duration : (state.chapters[String(chapter.id)]?.duration ?? 0);
}

export function chapterHeard(state: ListeningState, chapter: ListenChapter): number {
  const record = state.chapters[String(chapter.id)];
  if (!record) return 0;
  if (record.done) return 1;
  const length = knownDuration(state, chapter);
  return length > 0 ? Math.min(1, record.heard / length) : 0;
}

/** Tìm không dấu: "tap 16" khớp "Tập 16", "duc tri" khớp "Đức Trí". */
export function foldVietnamese(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
}

/** Nhãn cho hai cuốn cùng tên: dự án làm ở máy này, hay bản nhập từ file sách. Cuốn khác (sách chỉ-chữ, sách từ máy khác): không nhãn. */
export function twinKind(book: Pick<ListenBook, "capabilities" | "imported">): string {
  return book.capabilities?.workshop ? "Dự án" : book.imported ? "Đã nhập" : "";
}

/** Mã các cuốn mà thư viện còn một cuốn nữa CÙNG TÊN (hai bản của một truyện, hai lần thêm): lưới thêm một dòng phụ để phân biệt (soát UX a15). */
export function twinBookIds(books: readonly Pick<ListenBook, "id" | "title">[]): Set<string> {
  const count = new Map<string, number>();
  const key = (book: Pick<ListenBook, "title">) => foldVietnamese(book.title.trim().replace(/\s+/g, " "));
  for (const book of books) count.set(key(book), (count.get(key(book)) ?? 0) + 1);
  return new Set(books.filter((book) => (count.get(key(book)) ?? 0) > 1).map((book) => book.id));
}

/** Ô "Tìm sách": khớp tên, tác giả hoặc giọng kể, không phân biệt hoa thường và dấu ("nguyen" tìm ra "Nguyễn"). `folded` đã qua foldVietnamese. */
export function bookMatchesQuery(book: Pick<ListenBook, "title" | "author" | "narrator">, folded: string): boolean {
  return !folded || foldVietnamese(`${book.title} ${book.author ?? ""} ${book.narrator}`).includes(folded);
}
