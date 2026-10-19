import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { toast } from "sonner";
import { api } from "@/studio/api";
import { coverArtwork, type CoverImage } from "@/shared/cover";
import { formatClock } from "@/shared/format";
import { Clock, ClockContext } from "./clock";
import { isNative, type AudioEngine } from "./engine";
import { tellSceneMusic } from "./musicHint";
import { MUSIC_CHANGED_ALL, MUSIC_CHANGED_EVENT, MusicBed, NextChapterWarm, type MusicCredit } from "./musicBed";
import { SceneCues, isSceneCues, sceneRetryDelay } from "./sceneCues";
import { nextPlaylistBed, PlaylistClock, PlaylistDriver, type PlaylistBedState } from "./playlistBed";
import { canPlay, newerElsewhere, resumePoint, startingRate, type Bookmark, type ListenBook, type ListenChapter, type NightPosition, type Script } from "./model";
import { NightRecorder } from "./night";
import { leftWithPeer, watchUntilBack } from "./peerBack";
import {
  DEFAULT_EXTEND_MINUTES,
  DEFAULT_FADE_SECONDS,
  fadeGain,
  rewindAfter,
  sleepExtended,
  sleepFrom,
  sleepLeftMs,
  sleepPaused,
  sleepResumed,
  type SleepMode,
  type SleepRequest,
} from "./sleep";
import { VOICE_CHANGED_EVENT, type ReadAloudVoice, type SpeechTrack } from "./readAloud";
import { chooseVoice, chosenVoice, forgetVoiceTrouble, ONLINE_NOTICE, resolveVoice, runsOnThisMachine, speechFetcher, voicesOf } from "./readAloudVoice";
import { askOnlineConsent, needsOnlineConsent } from "./onlineConsent";
import { OnlineVoicePrompt } from "./OnlineVoicePrompt";
import { chapterScriptQuery, useListenBook, useSource } from "./source";
import { withFreshSkips } from "./textScript";
import { caughtUpDetail } from "./labels";
import { reportSaveFailure } from "./saveFailure";
import { letterShortcutsOn } from "@/shared/letterShortcuts";
import { prefersReducedMotion } from "@/shared/motion";

export type { SleepMode, SleepRequest } from "./sleep";

// Trình phát sách nói - chung cho máy tính và Android. Hành vi theo chuẩn Audible / Apple Books / Smart AudioBook
// Player: nhớ vị trí và tốc độ từng cuốn, tự sang chương kế, hẹn giờ ngủ nhỏ dần và gia hạn được, tự lùi khi nghe
// lại theo độ dài lần dừng, "quay lại chỗ vừa nghe" sau mỗi cú nhảy xa, dấu trang một chạm, phím tắt, nút media.
//
// Bộ máy web (máy tính): trình phát tự lo hàng đợi, hẹn giờ, nhật ký đêm, lưu vị trí.
// Bộ máy native (Android): lõi Media3 lo hết những việc đó - trình phát chỉ chuyển lệnh và phản chiếu trạng thái.
//
// Thời gian phát KHÔNG nằm trong context này mà ở Clock (clock.ts): nó đổi nhiều lần mỗi giây.

export interface Track {
  bookId: string;
  bookTitle: string;
  bookCover?: CoverImage | null;
  narrator: string;
  chapterId: number;
  chapterTitle: string;
  /** Hồ sơ nghe đang phát (bộ máy web): mọi lần lưu vào đúng hồ sơ này, kể cả khi máy khác vừa đổi hồ sơ đang dùng. */
  recordId?: string;
}

/** Chữ thứ `word` của câu thứ `segment` trong chương: bấm vào một chữ ở màn đọc là nghe từ đúng chữ ấy. Chương có audio đi bằng giây (`at`);
 *  chương đọc to chưa biết chỗ chữ trong clip thì bộ máy đọc đoạn ấy rồi bắt đầu ở chữ (readAloud.ts `seekWord`). */
export interface WordTarget {
  segment: number;
  word: number;
}

/** "review": nghe kiểm trong Studio - không ghi đè chỗ đang nghe dở của người nghe. */
export type Purpose = "listen" | "review";

/** Lịch đêm: bấm nghe trong khung giờ này thì tự hẹn giờ ngủ (giờ dạng "22:00", khung có thể qua nửa đêm). */
export interface SleepSchedule {
  from: string;
  to: string;
  minutes: number;
}

export interface PlayerOptions {
  fadeSeconds: number;
  extendMinutes: number;
  /** Phát liên tục chừng này giờ mà không ai chạm máy thì tự nhỏ dần rồi dừng (0 = tắt) - lưới cho người ngủ quên. */
  safetyStopHours: number;
  schedule: SleepSchedule | null;
}

function minutesOf(clock: string): number {
  const [hours, minutes] = clock.split(":").map(Number);
  return (hours || 0) * 60 + (minutes || 0);
}

/** Đang trong khung giờ của lịch? Trả về khoá của đêm ấy (ngày bắt đầu khung) để biết người dùng đã tắt nó chưa. */
export function scheduleWindow(schedule: SleepSchedule | null, now = new Date()): string | null {
  if (!schedule) return null;
  const from = minutesOf(schedule.from);
  const to = minutesOf(schedule.to);
  const current = now.getHours() * 60 + now.getMinutes();
  const overnight = from > to;
  const inside = overnight ? current >= from || current < to : current >= from && current < to;
  if (!inside) return null;
  const start = new Date(now);
  if (overnight && current < to) start.setDate(start.getDate() - 1);
  return start.toDateString();
}

type BookRef = Pick<ListenBook, "id" | "title" | "narrator" | "state" | "cover" | "records" | "remote"> & { complete?: boolean; stage?: ListenBook["stage"] };

function activeRecord(book: BookRef): string | undefined {
  return book.records?.find((record) => record.active)?.id;
}

interface PlayerState {
  track: Track | null;
  queue: ListenChapter[];
  playing: boolean;
  buffering: boolean;
  rate: number;
  volume: number;
  sleep: SleepMode;
  /** Đang nhỏ dần trước khi tự tắt. */
  fading: boolean;
  /** Lúc hẹn giờ vừa dừng phát (ms) - để nói "Đã tắt lúc 23:42" và mời bật lại. */
  sleepStoppedAt: number | null;
  lastSleepMinutes: number;
  purpose: Purpose;
  /** Phát hết chương cuối đã có: "finished" nếu cuốn đã đủ, "caughtUp" nếu cuốn còn đang làm. */
  atEnd: "none" | "caughtUp" | "finished";
  /** Ghi công bài nhạc nền đang nghe được (CC BY): null = không có nhạc / bài chưa có thông tin. */
  musicCredit: MusicCredit | null;
  /** Bài nhạc nền của chương đang nghe không phát được (file hỏng, mất kết nối): đoạn ấy im lặng - hộp "Nhạc nền" nói ra. */
  musicBroken: boolean;
  /** Lời báo "mất mạng" khi nhạc nền đang bị giữ lại vì mạng (điện thoại, MusicBed.kt): bài còn lại tải khi có mạng - hộp "Nhạc nền" nói ra; rỗng khi ổn. */
  musicOffline: string;
  /** Máy đang xếp hàng bài của danh sách nhạc vừa chọn (150 bài mất vài giây): nút "Nhạc nền" quay vòng chờ tới khi nhạc sẵn sàng. */
  musicLoading: boolean;
  canGoBack: boolean;
  error: string;
  /** Lời nhắn không phải lỗi, vẫn đang phát (giọng trực tuyến hỏng - tạm đọc bằng giọng của máy); tự ẩn. */
  notice: string;
  options: PlayerOptions;
}

interface PlayerActions {
  /** `extra.rate`: tốc độ dùng khi cuốn chưa có tốc độ riêng (nghe nối từ phần trước - startingRate). */
  play: (book: BookRef, chapters: ListenChapter[], chapterId: number, at?: number, extra?: { purpose?: Purpose; word?: WordTarget; rate?: number }) => void;
  /** Nạp sẵn ở trạng thái dừng (mở lại app: thanh phát có ngay cuốn đang nghe dở, bấm Space là nghe tiếp). */
  prepare: (book: BookRef, chapters: ListenChapter[], chapterId: number, at: number) => void;
  toggle: () => void;
  resume: () => void;
  /** "Thử lại" sau lỗi phát: nạp lại nguồn ở đúng chỗ đang đứng (resume chỉ bấm phát lại nguồn đã hỏng - soát a27 lỗi 3). */
  retry: () => void;
  /** Bỏ thông báo lỗi đang hiện mà không phát gì (vd. mạng đã về: lời "không có mạng" hết đúng, nhưng đừng tự phát lại giữa chừng). */
  dismissError: () => void;
  /** Người nghe đang muốn nghe: đã bấm phát (ở app, thông báo, xe…) và chưa bấm dừng. Mạng về chỉ tự "Thử lại" khi đúng vậy - lỗi sinh lúc mở
   *  app, chưa bấm phát gì, thì chỉ gỡ lời báo (soát a66: cuốn tự đọc khi người nghe đang ở Cài đặt). */
  wantsPlay: () => boolean;
  pause: () => void;
  seek: (seconds: number) => void;
  skip: (delta: number) => void;
  next: () => void;
  previous: () => void;
  /** `note`: chỗ tới nói bằng lời ("Nghe từ “…”") thay cho giờ trong toast "Đã tới 0:41" - người vừa bấm một câu nhận ra câu,
   *  không nhận ra con số (soát UX 29-09). */
  jumpTo: (chapterId: number, at?: number, note?: string, word?: WordTarget) => void;
  goBack: () => void;
  /** Nghe lại cuốn đang nạp từ chương đầu (hết sách: "Nghe lại từ đầu"). */
  restart: () => void;
  setRate: (rate: number) => void;
  setVolume: (volume: number) => void;
  setSleep: (request: SleepRequest) => void;
  extendSleep: (minutes?: number) => void;
  addBookmark: (note?: string) => Promise<Bookmark | null>;
  close: () => void;
  /** Đổi hồ sơ nghe của một cuốn (`change` gọi máy chủ); cuốn đang nạp thì trình phát theo sang hồ sơ mới.
   *  `startOver`: xong thì phát từ chương đầu (nghe lại từ đầu bằng hồ sơ mới). */
  switchRecord: (bookId: string, change: () => Promise<unknown>, startOver?: boolean) => Promise<void>;
  /** Lần cuối vị trí trên máy này được nạp hoặc lưu (ms) - vị trí trên máy chủ mới hơn mốc này là từ thiết bị khác. */
  positionStamp: () => number;
  /** Cuốn `bookId` có phần sau nghe nối (useContinueIntoNextPart; null = không): hết nó thì đừng nói "Đã nghe hết sách" (soát a26 L1). */
  setContinues: (bookId: string | null) => void;
}

export type PlayerValue = PlayerState & PlayerActions;

const PlayerContext = createContext<PlayerValue | null>(null);
const NowPlayingContext = createContext<{ expanded: boolean; setExpanded: (expanded: boolean) => void } | null>(null);

export function usePlayer(): PlayerValue {
  const value = useContext(PlayerContext);
  if (!value) throw new Error("usePlayer ngoài PlayerProvider");
  return value;
}

/** Màn hình "Đang nghe" mở hay đóng - tách khỏi trình phát để mở/đóng không render lại cả cây. */
export function useNowPlaying() {
  const value = useContext(NowPlayingContext);
  if (!value) throw new Error("useNowPlaying ngoài PlayerProvider");
  return value;
}

export const SPEEDS = [0.75, 0.9, 1, 1.1, 1.2, 1.3, 1.5, 1.75, 2, 2.5, 3];
export const SKIP_SECONDS = 15;
const SAVE_EVERY_MS = 10_000;
/** Nghe tiếp chờ chỗ nghe mới nhất tối đa chừng này (máy chủ đổi chỗ nghe với máy kia trong 1,5 giây, máy kia tắt thì thôi). */
const FRESH_SPOT_MS = 1600;
/** Lời nhắn (notice) tự ẩn sau chừng này. */
const NOTICE_MS = 12_000;
/** Nhảy xa hơn chừng này (tua, chương, dấu trang) thì mời "quay lại chỗ vừa nghe". */
const JUMP_SECONDS = 30;
const HISTORY = 5;
/** Nhạc theo cảnh dựng nền (music_nnscene.py): hỏi lại mốc của chương chưa dựng xong mỗi chừng này, tối đa chừng ấy lần (~2 phút). */
const SCENE_POLL_MS = 1500;
const SCENE_POLLS = 80;
/** Sự kiện mở ô ghi chú cho một dấu trang (từ toast "Thêm dấu trang"). */
export const EDIT_BOOKMARK_EVENT = "abook:edit-bookmark";

function availableAfter(queue: ListenChapter[], chapterId: number, step: 1 | -1): ListenChapter | undefined {
  const index = queue.findIndex((chapter) => chapter.id === chapterId);
  for (let cursor = index + step; cursor >= 0 && cursor < queue.length; cursor += step) {
    if (canPlay(queue[cursor])) return queue[cursor];
  }
  return undefined;
}

function nearestSpeed(rate: number, step: 1 | -1): number {
  if (step === 1) return SPEEDS.find((speed) => speed > rate + 1e-6) ?? SPEEDS[SPEEDS.length - 1];
  return [...SPEEDS].reverse().find((speed) => speed < rate - 1e-6) ?? SPEEDS[0];
}

export function PlayerProvider({
  engine,
  children,
  defaultRate = 1,
  defaultVolume = 0.9,
  keyboard = true,
  fadeSeconds = DEFAULT_FADE_SECONDS,
  extendMinutes = DEFAULT_EXTEND_MINUTES,
  safetyStopHours = 2,
  sleepSchedule = null,
}: {
  engine: AudioEngine;
  children: ReactNode;
  defaultRate?: number;
  defaultVolume?: number;
  keyboard?: boolean;
  fadeSeconds?: number;
  extendMinutes?: number;
  safetyStopHours?: number;
  sleepSchedule?: SleepSchedule | null;
}) {
  const source = useSource();
  const client = useQueryClient();
  const native = isNative(engine) ? engine : null;
  const clock = useMemo(() => new Clock(), []);
  const night = useMemo(
    () => new NightRecorder(source.saveNight ? (bookId, session) => source.saveNight!(bookId, session) : undefined),
    [source],
  );
  const scheduleKey = sleepSchedule ? `${sleepSchedule.from}-${sleepSchedule.to}-${sleepSchedule.minutes}` : "";
  const options = useMemo<PlayerOptions>(
    () => ({ fadeSeconds, extendMinutes, safetyStopHours, schedule: sleepSchedule }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fadeSeconds, extendMinutes, safetyStopHours, scheduleKey],
  );

  const [track, setTrack] = useState<Track | null>(null);
  const [queue, setQueue] = useState<ListenChapter[]>([]);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [rate, setRateState] = useState(defaultRate);
  const [volume, setVolumeState] = useState(defaultVolume);
  const [sleep, setSleepState] = useState<SleepMode>({ kind: "off" });
  const [fading, setFading] = useState(false);
  const [sleepStoppedAt, setSleepStoppedAt] = useState<number | null>(null);
  const [lastSleepMinutes, setLastSleepMinutes] = useState(30);
  const [purpose, setPurpose] = useState<Purpose>("listen");
  const [atEnd, setAtEnd] = useState<PlayerState["atEnd"]>("none");
  const [canGoBack, setCanGoBack] = useState(false);
  const [musicCredit, setMusicCredit] = useState<MusicCredit | null>(null);
  const [musicBroken, setMusicBroken] = useState(false);
  const [musicOffline, setMusicOffline] = useState("");
  const [musicLoading, setMusicLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState("");
  /** Dừng việc chờ máy kia trả lời lại (peerBack.ts) - đổi chương, gạt lời báo, thử lại. */
  const stopPeerWatch = useRef<() => void>(() => undefined);
  const errorRef = useRef(error);
  errorRef.current = error;
  const [notice, setNotice] = useState("");
  const noticeTimer = useRef<number | undefined>(undefined);

  const refs = useRef({
    track: null as Track | null,
    queue: [] as ListenChapter[],
    book: null as { id: string; title: string; complete: boolean; remote?: ListenBook["remote"] } | null,
    sleep: { kind: "off" } as SleepMode,
    purpose: "listen" as Purpose,
    fading: false,
    pausedAt: 0,
    lastSaved: 0,
    volume: defaultVolume,
    rate: defaultRate,
    defaultRate,
    history: [] as { chapterId: number; seconds: number }[],
    bookmarking: false,
    muted: 0,
    stamp: 0,
    /** Chỗ lần gần nhất đã lưu (hay vừa nạp từ chỗ đã lưu) - đổi hồ sơ mà trình phát chưa nhúc nhích thì khỏi lưu lại. */
    savedSpot: null as { chapterId: number; seconds: number } | null,
    session: null as { id: string; startedAt: number; from: { chapterId: number; seconds: number }; bookId: string; recordId?: string; listened: number; mark: number } | null,
    lastActivity: Date.now(),
    lastActivityPosition: null as NightPosition | null,
    scheduleOffFor: "",
    atEnd: "none" as PlayerState["atEnd"],
    /** Màn "Đang nghe" đang mở: nó đã có khối báo hết sách / hết phần đã có, toast chỉ nói lại. */
    expanded: false,
    /** Cuốn có phần sau nghe nối (setContinues). */
    continues: null as string | null,
    /** Ý định phát của người nghe (PlayerActions.wantsPlay): bật khi bấm phát / trình phát bắt đầu phát, tắt khi bấm dừng, hẹn giờ dừng, đóng. */
    wantsPlay: false,
  });
  refs.current.track = track;
  refs.current.queue = queue;
  refs.current.volume = volume;
  refs.current.rate = rate;
  refs.current.defaultRate = defaultRate;
  refs.current.atEnd = atEnd;
  refs.current.expanded = expanded;
  // Dòng ghi công người nghe tích / bỏ tích SAU khi nạp sách (trang sách): hàng đợi theo `skip` mới nhất, để giọng đọc và kịch bản dựng sẵn không còn đọc
  // theo bản cũ (kịch bản cũ nằm lại trong bộ nhớ đệm, màn đọc mở ra vẫn hiện dòng ấy).
  const { data: playingBook } = useListenBook(track?.bookId, false);
  useEffect(() => {
    setQueue((current) => withFreshSkips(current, playingBook?.chapters));
  }, [playingBook]);

  const position = useCallback(
    (): NightPosition => ({
      chapterId: refs.current.track?.chapterId ?? null,
      chapterTitle: refs.current.track?.chapterTitle ?? "",
      seconds: engine.time,
    }),
    [engine],
  );

  const applySleep = useCallback((mode: SleepMode) => {
    refs.current.sleep = mode;
    setSleepState(mode);
  }, []);

  const refreshLists = useCallback((bookId: string) => {
    void client.invalidateQueries({ queryKey: ["listen", "library"] });
    void client.invalidateQueries({ queryKey: ["listen", "book", bookId] });
  }, [client]);

  const save = useCallback((force = false) => {
    const current = refs.current.track;
    if (!current || native || refs.current.purpose === "review") return;
    const now = Date.now();
    if (!force && now - refs.current.lastSaved < SAVE_EVERY_MS) return;
    refs.current.lastSaved = now;
    refs.current.stamp = now;
    refs.current.savedSpot = { chapterId: current.chapterId, seconds: engine.time };
    void source.saveProgress(current.bookId, current.chapterId, engine.time, engine.duration, current.recordId).catch(reportSaveFailure);
    if (force) refreshLists(current.bookId);
  }, [engine, native, source, refreshLists]);

  const showNotice = useCallback((message: string) => {
    window.clearTimeout(noticeTimer.current);
    setNotice(message);
    if (message) noticeTimer.current = window.setTimeout(() => setNotice(""), NOTICE_MS);
  }, []);
  useEffect(() => () => window.clearTimeout(noticeTimer.current), []);

  /** Cái bộ máy đọc to cần để đọc một chương chỉ-có-chữ: kịch bản chữ, giọng, nơi lấy clip, nơi ghi mốc thời gian (khoá đúng của màn đọc).
   *  Lời nhắn của bộ lấy clip hiện ngay trong trình phát (PlayerAlert); lời báo "giọng trực tuyến gửi chữ đi" thì không - người nghe đã được
   *  hỏi TRƯỚC khi phát (withConsent). */
  const speechOf = useCallback((bookId: string, chapter: ListenChapter): SpeechTrack => {
    const query = chapterScriptQuery(source, bookId, chapter);
    return {
      script: () => client.fetchQuery(query),
      voice: () => chosenVoice(bookId),
      serial: () => runsOnThisMachine(voicesRef.current ? resolveVoice(voicesRef.current, chosenVoice(bookId)) : undefined),
      bookId,
      fetchClip: speechFetcher(source, bookId, (message) => message !== ONLINE_NOTICE && showNotice(message)),
      // Chương kế chỉ-có-chữ: chữ của nó để bộ máy xin trước tiêu đề + đoạn đầu khi chương này sắp hết (chữ lấy bằng đúng khoá kịch bản của lần nạp sau).
      after: async () => {
        const next = availableAfter(refs.current.queue, chapter.id, 1);
        if (!next || next.state !== "text") return [];
        return (await client.fetchQuery(chapterScriptQuery(source, bookId, next))).segments.map((segment) => segment.text);
      },
      onScript: (script) => client.setQueryData(query.queryKey, script),
    };
  }, [client, showNotice, source]);

  // Giọng của máy này, giữ sẵn để hỏi đồng ý ngay trong cú bấm (không chờ mạng); mỗi lần hỏi cũng làm mới.
  const voicesRef = useRef<ReadAloudVoice[] | null>(null);
  /** Phát một chương chỉ có chữ bằng giọng trực tuyến mà người nghe chưa đồng ý gửi chữ cho nhà cung cấp ấy: hỏi trước (onlineConsent.ts) -
   *  "Nghe" thì chạy `run`, chọn giọng khác thì đổi giọng rồi chạy, đóng hộp thì thôi. Không chữ nào rời máy trước câu trả lời. Chương có
   *  audio, giọng của máy, hay đã đồng ý: chạy ngay. Máy tính và điện thoại như nhau (lõi Android cũng chỉ đọc khi được lệnh phát). */
  const withConsent = useCallback((bookId: string, chapter: ListenChapter | undefined, run: () => void) => {
    if (chapter?.state !== "text") {
      run();
      return;
    }
    const decide = (voices: ReadAloudVoice[]) => {
      const voice = resolveVoice(voices, chosenVoice(bookId));
      if (!needsOnlineConsent(voice)) {
        run();
        return;
      }
      void askOnlineConsent(voice, voices).then((picked) => {
        if (picked === null) return;
        // Chọn trong danh sách là lựa chọn cho cuốn, kể cả chọn lại đúng giọng đang hỏi (soát a66: không nhớ thì tải giọng trên máy xong cuốn
        // tự sang giọng mặc định khác). "Nghe" thì không: cuốn vẫn theo giọng mặc định.
        if (picked.chosen) chooseVoice(bookId, picked.voice);
        run();
      });
    };
    const fresh = voicesOf(source).then((voices) => (voicesRef.current = voices));
    if (voicesRef.current) decide(voicesRef.current);
    else void fresh.then(decide);
  }, [source]);

  const load = useCallback((next: Track, at: number, autoplay: boolean) => {
    save(true);
    setError("");
    stopPeerWatch.current();
    setAtEnd("none");
    setTrack(next);
    refs.current.track = next;
    refs.current.savedSpot = { chapterId: next.chapterId, seconds: at };
    clock.set(at, 0);
    refs.current.stamp = Date.now();
    const chapter = refs.current.queue.find((item) => item.id === next.chapterId);
    engine.load(
      {
        // Chương chỉ-có-chữ: không có file, bộ máy đọc to tự dựng chương từ các đoạn chữ (readAloud.ts).
        url: chapter?.state === "text" ? "" : source.audioUrl(next.bookId, next.chapterId),
        speech: chapter?.state === "text" && !native ? speechOf(next.bookId, chapter) : undefined,
        title: next.chapterTitle,
        album: next.bookTitle,
        artist: next.narrator,
        // Ảnh bìa thật cho bảng điều khiển media của hệ điều hành (đường dẫn tuyệt đối); không có thì vẽ từ tên.
        artwork: next.bookCover ? new URL(next.bookCover.url, window.location.href).href : coverArtwork(next.bookTitle),
      },
      at,
      autoplay,
    );
  }, [clock, engine, native, source, save, speechOf]);

  const remember = useCallback((from: { chapterId: number; seconds: number }, to: { chapterId: number; seconds: number }, note?: string) => {
    // Nhảy xa là một đoạn nghe khác: phiên cũ kết thúc ở chỗ trước khi nhảy.
    splitSessionRef.current(from);
    const history = refs.current.history;
    history.push(from);
    if (history.length > HISTORY) history.shift();
    setCanGoBack(true);
    const sameChapter = from.chapterId === to.chapterId;
    const title = refs.current.queue.find((chapter) => chapter.id === from.chapterId)?.title ?? "";
    toast(note ?? `Đã tới ${sameChapter ? formatClock(to.seconds) : refs.current.queue.find((c) => c.id === to.chapterId)?.title ?? ""}`, {
      id: "jump",
      duration: 8000,
      // Tên chương cũ nằm ở dòng mô tả, không ở nhãn nút: nhãn dài chiếm hết bề ngang toast trên điện thoại, chữ của toast bị bóp còn vài ký tự một hàng (soát UX a11).
      ...(sameChapter ? {} : { description: `Chỗ cũ: ${title} · ${formatClock(from.seconds)}` }),
      action: {
        label: sameChapter ? `Quay lại ${formatClock(from.seconds)}` : "Quay lại chỗ cũ",
        onClick: () => goBackRef.current(),
      },
    });
  }, []);

  // Nhạc nền (musicBed.ts): chỉ bộ máy phát web (máy tính); lõi native Android chưa có. Rãnh nhạc tắt / chưa dựng thì
  // nguồn trả không mốc nào - trình phát chạy như cũ.
  const bed = useMemo(() => (native || !source.musicCues ? null : new MusicBed(undefined, source.musicWarm && ((link) => source.musicWarm?.(link)))), [native, source]);
  // Tải sẵn bài mốc đầu của chương kế khi chương này còn <= 120 giây (musicBed.ts NextChapterWarm): chương mới mở bằng bài đã có trong bộ đệm máy chủ.
  const nextWarm = useMemo(
    () =>
      bed && source.musicCues
        ? new NextChapterWarm(
            (chapterId) => source.musicCues!(refs.current.track?.bookId ?? "", chapterId),
            (link) => bed.warmLink(link),
          )
        : null,
    [bed, source],
  );
  const bedChapter = track ? `${track.bookId}:${track.chapterId}` : "";
  // Nhạc nền THEO CẢNH của sách chỉ có chữ (sceneCues.ts): mốc của máy chủ đặt lại theo đồng hồ đọc, bài đổi khi đoạn đầu cảnh bắt đầu phát.
  const scene = useMemo(
    () =>
      bed
        ? new SceneCues(bed, () => {
            const current = refs.current.track;
            return current ? client.getQueryData<Script>(["listen", "script", current.bookId, current.chapterId, "text"]) : undefined;
          })
        : null,
    [bed, client],
  );
  // Dòng ghi công (CC BY): bài đang nghe được -> thông tin tác giả của chương này, theo `link` của mốc.
  const bedCredits = useRef<Record<string, MusicCredit>>({});
  // Studio vừa sửa nhạc của cuốn đang nghe (cùng phiên): nạp lại mốc của chương này, bài đổi ngay không cần tải lại trang.
  const [bedVersion, setBedVersion] = useState(0);
  const bedBook = track?.bookId;
  useEffect(() => {
    const onChanged = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      if (detail === bedBook || detail === MUSIC_CHANGED_ALL) setBedVersion((version) => version + 1);
    };
    window.addEventListener(MUSIC_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(MUSIC_CHANGED_EVENT, onChanged);
  }, [bedBook]);
  useEffect(() => {
    if (native) {
      // Điện thoại: lõi native chơi nhạc nền (MusicBed.kt) và gửi ghi công bài đang kêu trong trạng thái của nó.
      let last = "";
      let lastOffline = "";
      const sync = () => {
        setMusicBroken(native.musicBroken);
        const offline = native.musicOffline;
        if (offline !== lastOffline) {
          // Như máy tính (Studio báo khi tải nhạc dừng vì mất mạng): nói một lần lúc nhạc vừa bị giữ lại, không im lặng.
          if (offline) toast.warning("Chưa tải được nhạc", { id: "music-offline", description: offline });
          lastOffline = offline;
          setMusicOffline(offline);
        }
        const credit = native.musicCredit;
        if (credit && native.musicScene) tellSceneMusic();
        const key = JSON.stringify(credit);
        if (key === last) return;
        last = key;
        setMusicCredit(credit);
      };
      sync();
      const off = engine.on("time", sync);
      return () => {
        off();
        setMusicCredit(null);
        setMusicBroken(false);
        setMusicOffline("");
      };
    }
    if (!bed) {
      setMusicCredit(null);
      setMusicBroken(false);
      return;
    }
    const off = bed.onActiveChange((link) => {
      if (link && sceneHeard.current) tellSceneMusic();
      setMusicCredit(link ? bedCredits.current[link] ?? null : null);
      setMusicBroken(bed.failing);
    });
    const offLoad = bed.onLoadResult(() => setMusicBroken(bed.failing));
    return () => {
      off();
      offLoad();
      setMusicCredit(null);
      setMusicBroken(false);
    };
  }, [bed, engine, native]);
  // Danh sách phát người nghe chọn cho cả cuốn (sách chỉ có chữ - playlistBed.ts): có bài thì nhạc chạy theo đồng hồ nhạc của cuốn,
  // không theo mốc của chương; hỏi lại khi đổi cuốn hay khi lựa chọn đổi (bedVersion), không hỏi lại mỗi chương.
  const [playlistBed, setPlaylistBed] = useState<PlaylistBedState | null>(null);
  const playlistAsked = useRef<{ key: string; queue: ReturnType<NonNullable<typeof source.musicPlaylist>> | null } | null>(null);
  const cuesChapter = useRef("");
  /** Chương mà mốc đang nằm trong `bed` thuộc về: sang chương khác thì engine.load chạy trước lúc hiệu ứng bỏ mốc cũ, nhịp "time" đầu tiên không được mở bài đầu của chương CŨ. */
  const bedCuesFor = useRef("");
  /** Đã có nhạc theo cảnh cho cuốn này (nhắc người nghe một lần ở bài đầu tiên kêu, musicHint.ts). */
  const sceneHeard = useRef(false);
  useEffect(() => {
    if (!bed || !track || !source.musicCues) {
      setMusicLoading(false);
      return;
    }
    let cancelled = false;
    const book = track.bookId;
    const asked = `${book}#${bedVersion}`;
    if (playlistAsked.current?.key !== asked) {
      playlistAsked.current = { key: asked, queue: source.musicPlaylist?.(book) ?? null };
    }
    // Sang chương khác: bỏ mốc chương cũ ngay, trước khi hỏi mốc mới - chương mới đã phát từ giây 0 thì không được mở lại bài
    // đầu hay chơi tiếp bài cuối của chương cũ trong lúc chờ (MIX_QA 3.3). Danh sách phát chạy theo đồng hồ của cuốn: không đụng.
    if (cuesChapter.current !== bedChapter) {
      cuesChapter.current = bedChapter;
      bedCuesFor.current = bedChapter;
      scene?.reset();
      if (!playlistBed) bed.setCues([], undefined, 0);
    }
    // Nhạc theo cảnh dựng nền: chương chưa xong thì máy chủ trả `pending` (giọng không chờ nhạc) - hỏi lại, xong thì nhạc vào ở đầu câu kế.
    let retry: ReturnType<typeof setTimeout> | undefined;
    // `misses`: số lần hỏi đã trả "chưa có" (unavailable / hỏng) - hỏi lại sau quãng lùi dần ([sceneRetryDelay]), không đợi tới chương sau.
    const askAgain = (misses: number) => {
      const delay = sceneRetryDelay(misses);
      if (delay !== null) retry = setTimeout(() => void chapterCues(0, misses + 1), delay);
    };
    const chapterCues = (attempt = 0, misses = 0): Promise<void> =>
      source.musicCues!(book, track.chapterId)
        .then((result) => {
          if (cancelled) return;
          bedCredits.current = result.credits ?? {};
          setMusicOffline(result.unavailable ?? ""); // danh mục chưa tải được: hộp "Nhạc nền" nói lý do (rỗng thì thôi)
          if (result.pending && attempt < SCENE_POLLS) {
            retry = setTimeout(() => void chapterCues(attempt + 1, misses), SCENE_POLL_MS);
            return;
          }
          if (result.unavailable) askAgain(misses);
          if (scene && isSceneCues(result.cues)) {
            sceneHeard.current = true;
            scene.arrive(result.cues, result.estSeconds ?? 0, result.levelDb, engine.time);
          } else {
            scene?.reset(); // nhạc theo cảnh vừa tắt ("Tự chọn nhạc nền"): mốc thô cũ không được đặt lại khi clip về
            bed.setCues(result.cues, result.levelDb);
          }
          setMusicBroken(bed.failing);
        })
        .catch(() => {
          if (cancelled) return;
          bedCredits.current = {};
          bed.setCues([], -20);
          askAgain(misses);
        });
    const queue = playlistAsked.current.queue;
    if (!queue) {
      setMusicLoading(false);
      setPlaylistBed(null);
      void chapterCues();
    } else {
      setMusicLoading(true);
      void queue.then(
        (result) => {
          if (cancelled) return;
          setMusicLoading(false);
          if (!result.playlist || !result.tracks.length) {
            setPlaylistBed(null);
            void chapterCues();
            return;
          }
          bedCredits.current = result.credits ?? {};
          const key = `${book}:${result.playlist}`;
          setPlaylistBed((previous) => nextPlaylistBed(previous, key, result));
        },
        () => {
          if (cancelled) return;
          setMusicLoading(false);
          setPlaylistBed(null);
          void chapterCues();
        },
      );
    }
    return () => {
      cancelled = true;
      clearTimeout(retry);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bed, source, bedChapter, bedVersion]);
  useEffect(() => {
    if (!bed) return;
    if (playlistBed) {
      // Đồng hồ nhạc của cuốn chạy khi giọng chạy: sang chương, tua, đổi tốc độ không làm nhạc bắt đầu lại.
      bed.setCues(playlistBed.cues, playlistBed.levelDb);
      const driver = new PlaylistDriver(bed, new PlaylistClock(playlistBed.key), playlistBed.cues);
      const update = () => driver.update(!engine.paused);
      const offs = [engine.on("time", update), engine.on("play", update), engine.on("pause", update), engine.on("ended", update)];
      update();
      return () => {
        offs.forEach((off) => off());
        driver.stop();
        bed.stop();
      };
    }
    let last = engine.time;
    const sync = () => {
      const current = refs.current.track;
      if (current && bedCuesFor.current !== `${current.bookId}:${current.chapterId}`) return; // mốc trong bed còn của chương cũ
      const now = engine.time;
      const seeked = Math.abs(now - last) > 3;
      if (seeked) scene?.seeked(now);
      bed.sync(now, !engine.paused, seeked);
      if (current && nextWarm) nextWarm.update(`${current.bookId}:${current.chapterId}`, availableAfter(refs.current.queue, current.chapterId, 1)?.id ?? null, engine.duration - now);
      last = now;
    };
    // Clip về (giây thật của đoạn thay giây ước): mốc nhạc theo cảnh đặt lại cho khớp.
    const offs = [engine.on("time", sync), engine.on("play", sync), engine.on("pause", sync), engine.on("ended", sync), engine.on("duration", () => scene?.refresh(engine.time))];
    return () => {
      offs.forEach((off) => off());
      bed.stop();
    };
  }, [bed, engine, nextWarm, playlistBed, scene]);
  useEffect(() => bed?.setVolume(volume), [bed, volume]);

  const applyRate = useCallback((value: number) => {
    refs.current.rate = value;
    setRateState(value);
    engine.setRate(value);
  }, [engine]);

  const adoptBook = useCallback((book: BookRef, chapters: ListenChapter[], purposeValue: Purpose, carriedRate?: number) => {
    setQueue(chapters);
    refs.current.queue = chapters;
    // Sách chỉ-có-chữ không "đang làm": hết chương cuối là hết cuốn, không phải "chờ Studio làm tiếp".
    refs.current.book = { id: book.id, title: book.title, complete: book.stage === "text" || (book.complete ?? true), remote: book.remote };
    refs.current.purpose = purposeValue;
    setPurpose(purposeValue);
    const { rate: bookRate, keep } = startingRate(book.state?.rate, carriedRate, refs.current.defaultRate);
    if (bookRate !== refs.current.rate) applyRate(bookRate);
    if (keep && purposeValue === "listen") void source.setRate(book.id, bookRate).catch(() => undefined);
    return bookRate;
  }, [applyRate, source]);

  const playNow = useCallback((book: BookRef, chapters: ListenChapter[], chapter: ListenChapter, at: number | undefined, extra: Parameters<PlayerActions["play"]>[4]) => {
    refs.current.wantsPlay = true;
    const chapterId = chapter.id;
    const current = refs.current.track;
    const sameSpot = current && current.bookId === book.id && current.chapterId === chapterId && at === undefined;
    const bookRate = adoptBook(book, chapters, extra?.purpose ?? "listen", extra?.rate);
    const next: Track = { bookId: book.id, bookTitle: book.title, bookCover: book.cover ?? null, narrator: book.narrator, chapterId, chapterTitle: chapter.fullTitle,
      recordId: native ? undefined : activeRecord(book) };
    if (native) {
      setTrack(next);
      refs.current.track = next;
      if (sameSpot) native.play();
      else native.loadQueue({ bookId: book.id, bookTitle: book.title, narrator: book.narrator, chapters, chapterId, at: at ?? 0, rate: bookRate, autoplay: true,
        readAloudVoice: chosenVoice(book.id) });
      // Bấm một chữ của chương đọc to khi cuốn chưa phát: hàng đợi vừa nạp, rồi lõi vào đúng chữ ấy.
      if (!sameSpot && extra?.word && chapter.state === "text") native.jumpTo(chapterId, at ?? 0, extra.word);
      return;
    }
    if (sameSpot) {
      resumeRef.current();
      return;
    }
    // Nghe tiếp đúng chỗ đã lưu: lùi theo độ dài lần dừng (mở lại app sáng hôm sau thì lùi hẳn 30 giây).
    let start = at ?? 0;
    const last = book.state?.last;
    if (at !== undefined && last && last.chapterId === chapterId && Math.abs(last.seconds - at) < 1) {
      start = Math.max(0, at - rewindAfter(Date.now() - last.at * 1000));
    }
    load(next, start, true);
    if (extra?.word) engine.seekWord?.(extra.word.segment, extra.word.word);
  }, [adoptBook, engine, load, native]);

  const play = useCallback<PlayerActions["play"]>((book, chapters, chapterId, at, extra) => {
    const chapter = chapters.find((item) => item.id === chapterId);
    if (!chapter) return;
    withConsent(book.id, chapter, () => playNow(book, chapters, chapter, at, extra));
  }, [playNow, withConsent]);

  const prepare = useCallback<PlayerActions["prepare"]>((book, chapters, chapterId, at) => {
    if (refs.current.track) return;
    const chapter = chapters.find((item) => item.id === chapterId && canPlay(item));
    if (!chapter) return;
    const bookRate = adoptBook(book, chapters, "listen");
    const next: Track = { bookId: book.id, bookTitle: book.title, bookCover: book.cover ?? null, narrator: book.narrator, chapterId, chapterTitle: chapter.fullTitle,
      recordId: native ? undefined : activeRecord(book) };
    if (native) {
      setTrack(next);
      refs.current.track = next;
      if (!native.bookId) {
        native.loadQueue({ bookId: book.id, bookTitle: book.title, narrator: book.narrator, chapters, chapterId, at, rate: bookRate, autoplay: false,
          readAloudVoice: chosenVoice(book.id) });
      }
      return;
    }
    const last = book.state?.last;
    const back = last ? rewindAfter(Date.now() - last.at * 1000) : 0;
    refs.current.pausedAt = 0;
    // `load` tự gắn cuốn vào trình phát SAU lần lưu chỗ cũ của nó; gắn trước thì lần lưu ấy ghi 0:00 (chưa nạp audio)
    // vào chỗ nghe dở của chính cuốn này - mỗi lần mở lại app là mất chỗ nghe.
    load(next, Math.max(0, at - back), false);
  }, [adoptBook, load, native]);

  /** Hết sách mà người nghe bấm phát: nói ra và mời nghe lại từ đầu (soát UX 03-10 - trước đây không có gì xảy ra). */
  const finishedToast = useCallback(() => {
    // Màn "Đang nghe" đang mở thì khối trong màn đã nói (kèm "Nghe lại từ đầu"): một chỗ báo, không thêm toast (soát UX 03-10).
    if (refs.current.expanded) return;
    toast("Đã nghe hết sách", { id: "finished", duration: 8000, action: { label: "Nghe lại từ đầu", onClick: () => restartRef.current() } });
  }, []);
  const caughtUpToast = useCallback((description?: string) => {
    if (refs.current.expanded) return;
    toast("Đã nghe hết phần đã có", description ? { description } : undefined);
  }, []);

  const resumeNow = useCallback(() => {
    const current = refs.current.track;
    if (!current) return;
    night.touch("play", position(), true);
    if (native) {
      if (refs.current.atEnd === "finished") finishedToast();
      else native.play();
      return;
    }
    if (engine.ended) {
      const target = availableAfter(refs.current.queue, current.chapterId, 1);
      if (target) load({ ...current, chapterId: target.id, chapterTitle: target.fullTitle }, 0, true);
      else if (refs.current.book?.complete === false) caughtUpToast();
      else finishedToast();
      return;
    }
    const back = refs.current.pausedAt ? rewindAfter(Date.now() - refs.current.pausedAt) : 0;
    if (back) engine.seek(Math.max(0, engine.time - back));
    engine.play();
  }, [caughtUpToast, engine, finishedToast, load, native, night, position]);

  const resume = useCallback(() => {
    const current = refs.current.track;
    if (!current) return;
    refs.current.wantsPlay = true;
    // Nguồn đã hỏng (máy kia tắt, mất mạng): bấm phát ở đâu cũng là nạp lại đúng chỗ - phát lại nguồn hỏng chỉ ra lỗi cũ (soát a27 lỗi 3).
    if (errorRef.current && !native) {
      retryRef.current();
      return;
    }
    // Thiết bị khác đã nghe xa hơn SAU lần cuối máy này nạp/lưu: tới chỗ ấy (toast có nút quay lại), đừng phát chỗ cũ rồi lưu đè (soát a27 lỗi 2).
    // Bản sách đang đệm có thể là lúc trước (cửa sổ vừa đưa lên, hỏi lại 30 s một lần): hỏi lại máy chủ - nó tự đổi chỗ nghe với máy kia - chờ
    // tối đa FRESH_SPOT_MS rồi mới quyết. Mọi đường nghe tiếp (nút chính trang sách, thẻ, Space, phím tai nghe) đều qua đây.
    const resumeHere = () => withConsent(current.bookId, refs.current.queue.find((chapter) => chapter.id === current.chapterId), resumeNow);
    const decide = () => {
      if (refs.current.track !== current || !engine.paused) return;
      const book = client.getQueryData<ListenBook>(["listen", "book", current.bookId]);
      const active = book?.records?.find((record) => record.active)?.id;
      const away = !(current.recordId && active && current.recordId !== active)
        ? newerElsewhere(book?.state.last, refs.current.stamp, { chapterId: current.chapterId, seconds: engine.time })
        : null;
      if (away && refs.current.queue.some((chapter) => chapter.id === away.chapterId && canPlay(chapter))) {
        jumpToRef.current(away.chapterId, away.seconds, `Nghe tiếp từ chỗ thiết bị khác đã nghe tới (${formatClock(away.seconds)})`);
        return;
      }
      resumeHere();
    };
    if (native || refs.current.purpose !== "listen" || !engine.paused || engine.ended) {
      resumeHere();
      return;
    }
    const fresh = client.fetchQuery({ queryKey: ["listen", "book", current.bookId], queryFn: () => source.book(current.bookId), staleTime: 0 });
    void Promise.race([fresh.catch(() => undefined), new Promise((done) => window.setTimeout(done, FRESH_SPOT_MS))]).then(decide);
  }, [client, engine, native, resumeNow, source, withConsent]);
  const resumeRef = useRef(resume);
  resumeRef.current = resume;
  const retry = useCallback(() => {
    const current = refs.current.track;
    if (!current) return;
    forgetVoiceTrouble(); // "Thử lại" gọi lại dịch vụ thật, không nhắc lại lỗi cũ của giọng trực tuyến
    stopPeerWatch.current();
    if (native) {
      resume();
      return;
    }
    const at = engine.time;
    withConsent(current.bookId, refs.current.queue.find((chapter) => chapter.id === current.chapterId), () => {
      const now = refs.current.track;
      if (now) load(now, at, true);
    });
  }, [engine, load, native, resume, withConsent]);
  const retryRef = useRef(retry);
  retryRef.current = retry;
  const wantsPlay = useCallback(() => refs.current.wantsPlay, []);
  const dismissError = useCallback(() => {
    stopPeerWatch.current();
    setError("");
  }, []);
  // Người nghe đổi giọng (của cuốn đang nghe, hay của mọi cuốn): lời báo lỗi của giọng cũ không còn đúng nữa.
  useEffect(() => {
    const onVoice = (event: Event) => {
      const bookId = (event as CustomEvent<string>).detail;
      if (!bookId || bookId === refs.current.track?.bookId) setError("");
    };
    window.addEventListener(VOICE_CHANGED_EVENT, onVoice);
    return () => window.removeEventListener(VOICE_CHANGED_EVENT, onVoice);
  }, []);

  const pause = useCallback(() => {
    refs.current.wantsPlay = false;
    night.touch("pause", position(), true);
    engine.pause();
  }, [engine, night, position]);

  const toggle = useCallback(() => {
    if (!refs.current.track) return;
    if (engine.paused) resume();
    else pause();
  }, [engine, pause, resume]);

  const seek = useCallback((seconds: number) => {
    const current = refs.current.track;
    if (!current) return;
    const from = engine.time;
    // Tua (về đầu chương bằng Home, "Nghe từ đây", dấu trang) sau khi đã nghe hết: bỏ dòng "Đã nghe hết phần đã có" - soát UX
    // 29-09: dòng ấy còn nguyên trong lúc chương đang phát lại ở 4:52, tới khi tải lại trang.
    setAtEnd("none");
    engine.seek(seconds);
    clock.set(Math.max(0, seconds), engine.duration);
    night.touch("seek", position());
    if (Math.abs(seconds - from) > JUMP_SECONDS) remember({ chapterId: current.chapterId, seconds: from }, { chapterId: current.chapterId, seconds });
  }, [clock, engine, night, position, remember]);

  const skip = useCallback((delta: number) => {
    if (!refs.current.track) return;
    night.touch("skip", position());
    if (native) {
      native.skipBy(delta);
      return;
    }
    const target = Math.max(0, engine.time + delta);
    if (delta < 0) setAtEnd("none");
    engine.seek(target);
    clock.set(target, engine.duration);
  }, [clock, engine, native, night, position]);

  const jumpNow = useCallback((current: Track, chapter: ListenChapter, at: number, note?: string, word?: WordTarget) => {
    const chapterId = chapter.id;
    setAtEnd("none");
    night.touch("chapter", position(), true);
    const from = { chapterId: current.chapterId, seconds: engine.time };
    if (chapterId !== current.chapterId || Math.abs(at - from.seconds) > JUMP_SECONDS) remember(from, { chapterId, seconds: at }, note);
    if (native) {
      native.jumpTo(chapterId, at, word && chapter.state === "text" ? word : undefined);
      return;
    }
    if (chapterId === current.chapterId) {
      // Bấm vào một chữ của chương đọc to: bộ máy tự vào đúng mốc chữ (đã biết thì ngay, chưa thì sau khi đọc xong đoạn ấy).
      if (word && chapter.state === "text" && engine.seekWord) engine.seekWord(word.segment, word.word);
      else engine.seek(at);
      clock.set(engine.time, engine.duration);
      engine.play();
      return;
    }
    load({ ...current, chapterId, chapterTitle: chapter.fullTitle }, at, true);
    if (word && chapter.state === "text") engine.seekWord?.(word.segment, word.word);
  }, [clock, engine, load, native, night, position, remember]);

  const jumpTo = useCallback((chapterId: number, at = 0, note?: string, word?: WordTarget) => {
    const current = refs.current.track;
    const chapter = refs.current.queue.find((item) => item.id === chapterId);
    if (!current || !chapter || !canPlay(chapter)) return;
    withConsent(current.bookId, chapter, () => {
      const now = refs.current.track;
      if (now) jumpNow(now, chapter, at, note, word);
    });
  }, [jumpNow, withConsent]);
  const jumpToRef = useRef(jumpTo);
  jumpToRef.current = jumpTo;

  const goBack = useCallback(() => {
    const target = refs.current.history.pop();
    setCanGoBack(refs.current.history.length > 0);
    toast.dismiss("jump");
    const current = refs.current.track;
    if (!target || !current) return;
    if (native) {
      native.jumpTo(target.chapterId, target.seconds);
      return;
    }
    if (target.chapterId === current.chapterId) {
      engine.seek(target.seconds);
      clock.set(target.seconds, engine.duration);
      return;
    }
    const chapter = refs.current.queue.find((item) => item.id === target.chapterId);
    if (chapter) load({ ...current, chapterId: chapter.id, chapterTitle: chapter.fullTitle }, target.seconds, !engine.paused);
  }, [clock, engine, load, native]);
  const goBackRef = useRef(goBack);
  goBackRef.current = goBack;

  const step = useCallback((direction: 1 | -1) => {
    const current = refs.current.track;
    if (!current) return;
    night.touch(direction === 1 ? "next" : "previous", position(), true);
    if (native) {
      if (direction === 1) native.next();
      else native.previous();
      return;
    }
    if (direction === -1 && engine.time > 5) {
      engine.seek(0);
      clock.set(0, engine.duration);
      return;
    }
    const target = availableAfter(refs.current.queue, current.chapterId, direction);
    if (!target) {
      // Chương sau có mà chưa có audio: nói ra, kèm đường đọc chữ - trước đây nút mờ và Shift+→ im lặng (soát UX 29-09).
      const queue = refs.current.queue;
      const waiting = direction === 1 ? queue[queue.findIndex((chapter) => chapter.id === current.chapterId) + 1] : undefined;
      if (waiting && !canPlay(waiting)) {
        toast("Chương sau chưa có audio", {
          description: waiting.fullTitle,
          duration: 8000,
          action: { label: "Đọc chương ấy", onClick: () => { window.location.hash = `#/book/${current.bookId}/read/${waiting.id}`; } },
        });
      }
      return;
    }
    remember({ chapterId: current.chapterId, seconds: engine.time }, { chapterId: target.id, seconds: 0 });
    load({ ...current, chapterId: target.id, chapterTitle: target.fullTitle }, 0, !engine.paused || engine.ended);
  }, [clock, engine, load, native, night, position, remember]);

  /** Sang chương chỉ có chữ bằng nút Trước / Sau cũng là bắt đầu đọc chương ấy: hỏi đồng ý như mọi lần phát. */
  const stepChecked = useCallback((direction: 1 | -1) => {
    const current = refs.current.track;
    if (!current) return;
    withConsent(current.bookId, availableAfter(refs.current.queue, current.chapterId, direction), () => step(direction));
  }, [step, withConsent]);
  const next = useCallback(() => stepChecked(1), [stepChecked]);
  const previous = useCallback(() => stepChecked(-1), [stepChecked]);

  const restart = useCallback(() => {
    const first = refs.current.queue.find(canPlay);
    if (first) jumpTo(first.id, 0);
  }, [jumpTo]);
  const restartRef = useRef(restart);
  restartRef.current = restart;

  const setRate = useCallback((value: number) => {
    applyRate(value);
    night.touch("rate", position());
    const current = refs.current.track;
    if (current && !native && refs.current.purpose !== "review") {
      // Tốc độ nhớ riêng của cuốn cũng nằm trong bộ nhớ của trang sách / thư viện (ListenBook.state.rate): đổi ngay ở đó, không thì "Nghe lại từ đầu" /
      // "Nghe tiếp" ngay sau phím [ ] nạp lại tốc độ cũ của cuốn đè lên tốc độ vừa chọn (adoptBook).
      const remember = (book: ListenBook): ListenBook => ({ ...book, state: { ...(book.state ?? { chapters: {} }), rate: value } });
      client.setQueryData<ListenBook>(["listen", "book", current.bookId], (book) => book && remember(book));
      client.setQueryData<ListenBook[]>(["listen", "library"], (books) => books?.map((book) => (book.id === current.bookId ? remember(book) : book)));
      void source.setRate(current.bookId, value).catch(() => undefined);
    }
  }, [applyRate, client, native, night, position, source]);

  const setVolume = useCallback((value: number) => {
    const clamped = Math.max(0, Math.min(1, value));
    refs.current.volume = clamped;
    setVolumeState(clamped);
    if (!refs.current.fading) engine.setVolume(clamped);
    night.touch("volume", position());
  }, [engine, night, position]);

  const endFade = useCallback(() => {
    if (refs.current.fading) {
      refs.current.fading = false;
      setFading(false);
    }
    engine.setVolume(refs.current.volume);
  }, [engine]);

  const setSleep = useCallback((request: SleepRequest) => {
    if (native) {
      native.setSleep(request);
      return;
    }
    endFade();
    applySleep(sleepFrom(request, !engine.paused, Date.now()));
    const book = refs.current.book;
    if (request.kind === "off") {
      night.cancel(position());
      // Tự tắt hẹn giờ trong khung lịch đêm: đêm ấy không tự bật lại nữa.
      refs.current.scheduleOffFor = scheduleWindow(options.schedule) ?? "";
      return;
    }
    if (request.kind === "minutes") setLastSleepMinutes(request.minutes);
    setSleepStoppedAt(null);
    if (book && refs.current.purpose === "listen") night.start(book, request.kind === "minutes" ? request.minutes : null, position());
  }, [applySleep, endFade, engine, native, night, options.schedule, position]);

  const setSleepRef = useRef(setSleep);
  setSleepRef.current = setSleep;

  const extendSleep = useCallback((minutes = options.extendMinutes) => {
    if (native) {
      native.extendSleep(minutes);
      return;
    }
    if (refs.current.sleep.kind === "off") return;
    endFade();
    applySleep(sleepExtended(refs.current.sleep, minutes, !engine.paused, Date.now()));
    night.extend(minutes, position());
    toast.success(`Nghe thêm ${minutes} phút`, { id: "sleep-extend", duration: 2500 });
  }, [applySleep, endFade, engine, native, night, options.extendMinutes, position]);

  const addBookmark = useCallback(async (note = "") => {
    const current = refs.current.track;
    if (!current || refs.current.bookmarking) return null;
    refs.current.bookmarking = true;
    try {
      const mark = native
        ? await native.addBookmark(note)
        : await source.addBookmark(current.bookId, current.chapterId, engine.time, note ?? "", current.recordId);
      night.touch("bookmark", position(), true);
      refreshLists(current.bookId);
      return mark;
    } finally {
      refs.current.bookmarking = false;
    }
  }, [engine, native, night, position, refreshLists, source]);

  const close = useCallback(() => {
    refs.current.wantsPlay = false;
    save(true);
    night.cancel(position());
    engine.stop();
    setTrack(null);
    refs.current.track = null;
    setPlaying(false);
    setExpanded(false);
    endFade();
    applySleep({ kind: "off" });
    setPurpose("listen");
    refs.current.purpose = "listen";
    refs.current.history = [];
    setCanGoBack(false);
  }, [applySleep, endFade, engine, night, position, save]);

  // Thôi ghép máy kia khi đang nạp một cuốn của nó: cuốn rời Thư viện thì trình phát đóng và nói vì sao (soát a27 lỗi 11). Chỉ đọc danh sách
  // Thư viện đã có trong bộ đệm (Thư viện, hộp thôi ghép làm mới nó) - không hỏi thêm.
  const library = useQuery<ListenBook[]>({ queryKey: ["listen", "library"], enabled: false });
  useEffect(() => {
    const book = refs.current.book;
    if (!track || !book || track.bookId !== book.id || !leftWithPeer(book, library.data)) return;
    const computer = typeof book.remote === "object" && book.remote ? book.remote.computer : "";
    close();
    toast.info(`“${book.title}” đã rời Thư viện`, { description: `Sách này nằm trên ${computer || "máy kia"} - đã thôi ghép nên trình phát đóng lại.` });
  }, [close, library.data, track]);

  const positionStamp = useCallback(() => refs.current.stamp, []);

  const splitSessionRef = useRef<(at: { chapterId: number; seconds: number }) => void>(() => undefined);

  // Phiên nghe (bộ máy web; lõi native chưa ghi): mở lúc bắt đầu phát, đóng lúc dừng. Phiên dưới 20 giây nghe
  // thật thì bỏ - bấm phát rồi dừng ngay không phải là "đã nghe".
  const openSession = useCallback(() => {
    const current = refs.current.track;
    if (native || !current || refs.current.purpose !== "listen" || !source.addSession) return;
    if (refs.current.session && refs.current.session.bookId === current.bookId && refs.current.session.recordId === current.recordId) {
      refs.current.session.mark = Date.now();
      return;
    }
    refs.current.session = {
      id: Math.random().toString(16).slice(2, 14),
      startedAt: Date.now() / 1000,
      from: { chapterId: current.chapterId, seconds: engine.time },
      bookId: current.bookId,
      recordId: current.recordId,
      listened: 0,
      mark: Date.now(),
    };
  }, [engine, native, source]);

  const closeSession = useCallback((leaving = false): Promise<unknown> | undefined => {
    const session = refs.current.session;
    const current = refs.current.track;
    if (!session || !current || !source.addSession) return;
    session.listened += (Date.now() - session.mark) / 1000;
    session.mark = Date.now();
    refs.current.session = null;
    if (session.listened < 20 || session.bookId !== current.bookId) return;
    if (leaving && source.addSessionOnExit) {
      source.addSessionOnExit(session.bookId, {
        id: session.id,
        device: "desktop",
        startedAt: session.startedAt,
        endedAt: Date.now() / 1000,
        listened: session.listened,
        from: session.from,
        to: { chapterId: current.chapterId, seconds: engine.time },
      }, session.recordId);
      return;
    }
    return source
      .addSession(session.bookId, {
        id: session.id,
        device: "desktop",
        startedAt: session.startedAt,
        endedAt: Date.now() / 1000,
        listened: session.listened,
        from: session.from,
        to: { chapterId: current.chapterId, seconds: engine.time },
      }, session.recordId)
      .catch(reportSaveFailure);
  }, [engine, source]);

  // Chỗ nghe, phiên nghe của cuốn đang nạp vào hồ sơ CŨ (mọi lần lưu mang theo hồ sơ đang phát), ghi và chờ, gỡ cuốn
  // khỏi trình phát, đổi, rồi nạp lại đúng chỗ của hồ sơ mới ở trạng thái dừng. Trình phát chưa nhúc nhích từ lần lưu
  // trước thì khỏi lưu: lưu lại là đóng dấu giờ mới lên chỗ CŨ, đè chỗ mới hơn mà máy khác vừa đồng bộ tới.
  // Lõi Android làm cả lượt ấy trên luồng chính của nó (Playback.switchRecord), ở đây chỉ việc chờ máy chủ.
  const switchRecord = useCallback<PlayerActions["switchRecord"]>(async (bookId, change, startOver = false) => {
    const current = refs.current.track;
    const loaded = !native && current?.bookId === bookId && refs.current.purpose === "listen";
    if (current && loaded) {
      const saved = refs.current.savedSpot;
      const moved = !engine.paused || !saved || saved.chapterId !== current.chapterId || Math.abs(saved.seconds - engine.time) > 1;
      const writes = [
        moved
          ? source.saveProgress(current.bookId, current.chapterId, engine.time, engine.duration, current.recordId).catch(reportSaveFailure)
          : undefined,
        closeSession(),
      ];
      refs.current.lastSaved = Date.now();
      night.cancel(position());
      engine.stop();
      refs.current.track = null;
      setTrack(null);
      setPlaying(false);
      endFade();
      applySleep({ kind: "off" });
      refs.current.history = [];
      setCanGoBack(false);
      await Promise.all(writes);
    }
    await change();
    if (!loaded && !startOver) return;
    const book = await source.book(bookId);
    const chapters = book.chapters ?? [];
    if (startOver) {
      const first = chapters.find(canPlay);
      if (first) play(book, chapters, first.id, 0);
      return;
    }
    const point = resumePoint(book, chapters);
    if (point) prepare(book, chapters, point.chapter.id, point.at);
  }, [applySleep, closeSession, endFade, engine, native, night, play, position, prepare, source]);

  splitSessionRef.current = (at) => {
    const session = refs.current.session;
    if (!session || native) return;
    const book = session.bookId;
    session.listened += (Date.now() - session.mark) / 1000;
    refs.current.session = null;
    if (session.listened >= 20 && source.addSession) {
      void source
        .addSession(book, { id: session.id, device: "desktop", startedAt: session.startedAt, endedAt: Date.now() / 1000,
          listened: session.listened, from: session.from, to: at }, session.recordId)
        .catch(reportSaveFailure);
    }
    if (!engine.paused) window.setTimeout(() => openSession(), 0);
  };

  /** Hẹn giờ vừa hết: dừng, trả âm lượng, ghi mốc "tự dừng" cho buổi sáng. */
  const stopBySleep = useCallback(() => {
    refs.current.wantsPlay = false;
    night.stop(position());
    engine.pause();
    endFade();
    applySleep({ kind: "off" });
    setSleepStoppedAt(Date.now());
    save(true);
  }, [applySleep, endFade, engine, night, position, save]);

  // ---- sự kiện của bộ máy phát ----------------------------------------------------------------------------

  useEffect(() => {
    engine.setRate(refs.current.rate);
    engine.setVolume(refs.current.volume);
    const syncClock = () => clock.set(engine.time, engine.duration);
    const offs = [
      engine.on("time", () => {
        syncClock();
        save();
      }),
      engine.on("duration", syncClock),
      engine.on("play", () => {
        refs.current.wantsPlay = true;
        setPlaying(true);
        setError(""); // phát lại được (vd có mạng lại khi nghe thẳng): thông báo lỗi cũ không còn đúng
        refs.current.pausedAt = 0;
        openSession();
        if (!native) applySleep(sleepResumed(refs.current.sleep, Date.now()));
      }),
      engine.on("pause", () => {
        setPlaying(false);
        closeSession();
        syncClock();
        refs.current.pausedAt = Date.now();
        if (!native) applySleep(sleepPaused(refs.current.sleep, Date.now()));
        save(true);
      }),
      engine.on("waiting", () => setBuffering(true)),
      engine.on("playing", () => setBuffering(false)),
      engine.on("ended", () => {
        const current = refs.current.track;
        if (!current) return;
        const target = availableAfter(refs.current.queue, current.chapterId, 1);
        if (native) {
          if (!target) setAtEnd(refs.current.book?.complete === false ? "caughtUp" : "finished");
          refreshLists(current.bookId);
          return;
        }
        save(true);
        if (refs.current.sleep.kind === "chapter") {
          // Hẹn "hết chương": dừng ở đây, nhưng nạp sẵn chương kế ở 0:00 và lưu nó làm chỗ nghe tiếp - sáng mai
          // bấm Tiếp tục là vào chương mới, không phải nghe lại chương vừa xong từ đầu.
          stopBySleep();
          if (target) {
            load({ ...current, chapterId: target.id, chapterTitle: target.fullTitle }, 0, false);
            if (refs.current.purpose === "listen") {
              void source.saveProgress(current.bookId, target.id, 0, target.duration, current.recordId).then(() => refreshLists(current.bookId)).catch(reportSaveFailure);
            }
          }
          return;
        }
        if (target) {
          // Chương audio hết, chương kế chỉ có chữ, giọng trực tuyến chưa được đồng ý: sang chương ấy nhưng đứng yên ở 0:00 tới khi
          // người nghe trả lời - không chữ nào rời máy trước "Nghe" (đóng hộp thì cứ đứng đó, bấm Phát là hỏi lại).
          const next = { ...current, chapterId: target.id, chapterTitle: target.fullTitle };
          let answered = false;
          let parked = false;
          withConsent(current.bookId, target, () => {
            answered = true;
            if (!parked) load(next, 0, true);
            else if (refs.current.track?.bookId === next.bookId && refs.current.track.chapterId === next.chapterId && engine.paused) engine.play();
          });
          if (!answered) {
            parked = true;
            load(next, 0, false);
          }
          return;
        }
        const caughtUp = refs.current.book?.complete === false;
        setAtEnd(caughtUp ? "caughtUp" : "finished");
        if (caughtUp) caughtUpToast(caughtUpDetail());
        else if (refs.current.continues !== current.bookId) finishedToast();
      }),
      engine.on("recovered", () => setError("")),
      engine.on("error", () => {
        // Lõi Android nói đúng lý do (nghe thẳng mà mất kết nối với máy tính khác hẳn file hỏng).
        const fallback = native?.error || engine.error || "Không phát được chương này - file có thể đã bị xoá hoặc đang được ghi lại.";
        setError(fallback);
        setBuffering(false);
        // Không có tiếng thì không phải "đang phát": nút chính về "Phát", thẻ thôi ghi "đang phát" (soát a27 lỗi 3).
        if (!native) {
          if (!engine.paused) engine.pause();
          setPlaying(false);
        }
        // Sách “Trên máy khác” nghe thẳng trên máy tính: chương chưa tải về mà không phát được thường là máy kia đã tắt / mất mạng - hỏi máy ấy
        // rồi nói đúng lý do, thay vì đổ cho file.
        const bookId = refs.current.book?.id;
        const remote = refs.current.book?.remote;
        if (!native && remote && typeof remote === "object" && remote.device) {
          void api<{ reachable: boolean }>(`/api/computers/${remote.device}/reachable`)
            .then((answer) => {
              if (answer.reachable || refs.current.book?.id !== bookId) return;
              const message = `Máy ${remote.computer || "kia"} không trả lời (tắt hay mất mạng) - chương này chưa tải về máy này.`;
              setError((current) => (current === fallback ? message : current));
              // Máy ấy trả lời lại thì tự thử một lần, đúng chỗ đang đứng.
              const chapterId = refs.current.track?.chapterId;
              stopPeerWatch.current();
              stopPeerWatch.current = watchUntilBack(
                () => api<{ reachable: boolean }>(`/api/computers/${remote.device}/reachable`).then((again) => again.reachable),
                () => {
                  if (refs.current.book?.id === bookId && refs.current.track?.chapterId === chapterId) retryRef.current();
                },
              );
            })
            .catch(() => undefined);
        }
      }),
      engine.on("chapter", () => {
        if (!native || native.chapterId === null || !native.bookId) return;
        const same = refs.current.track?.bookId === native.bookId ? refs.current.track : null;
        const next: Track = {
          bookId: native.bookId,
          bookTitle: native.bookTitle,
          bookCover: same?.bookCover ?? null,
          narrator: same?.narrator ?? "",
          chapterId: native.chapterId,
          chapterTitle: native.chapterTitle,
        };
        refs.current.track = next;
        setTrack(next);
        setAtEnd("none");
        refreshLists(native.bookId);
        // Lõi native khôi phục bài đang nghe (mở lại app) chỉ biết tên sách: hỏi kho sách để có ảnh bìa và giọng kể,
        // nếu không thanh phát và màn "Đang nghe" hiện bìa vẽ dù sách có ảnh bìa thật (27-09, thấy trên máy ảo).
        // Máy tính bấm "Phát trên điện thoại" cũng đổi sách từ lõi: khi ấy danh sách chương còn là của cuốn cũ.
        if (!same) {
          const bookId = native.bookId;
          void source.book(bookId).then((book) => {
            const current = refs.current.track;
            if (!current || current.bookId !== bookId) return;
            const filled = { ...current, bookCover: book.cover ?? null, narrator: current.narrator || book.narrator };
            refs.current.track = filled;
            setTrack(filled);
            if (book.chapters && refs.current.book?.id !== bookId) {
              setQueue(book.chapters);
              refs.current.queue = book.chapters;
              refs.current.book = { id: book.id, title: book.title, complete: book.complete };
            }
          }).catch(() => undefined);
        }
      }),
      engine.on("sleep", () => {
        if (!native) return;
        const previousKind = refs.current.sleep.kind;
        applySleep(native.sleep);
        if (previousKind !== "off" && native.sleep.kind === "off" && native.paused) setSleepStoppedAt(Date.now());
      }),
    ];
    return () => offs.forEach((off) => off());
  }, [applySleep, caughtUpToast, clock, closeSession, engine, finishedToast, load, native, openSession, refreshLists, save, source, stopBySleep, withConsent]);

  // Đồng hồ chạy theo khung hình khi đang phát: nhãn giây đổi đúng nhịp 1 giây thay vì theo timeupdate (~4 lần/giây,
  // lệch tới 270 ms). Chỉ component nào chọn giá trị đổi mới render lại.
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      clock.set(engine.time, engine.duration);
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [clock, engine, playing]);

  // Hẹn giờ (bộ máy web): kiểm hạn bằng nhịp riêng - không dựa vào timeupdate - và nhỏ dần theo dB.
  useEffect(() => {
    if (native || !playing || sleep.kind === "off") return;
    const tick = () => {
      const mode = refs.current.sleep;
      const now = Date.now();
      let left: number | null = null;
      if (mode.kind === "minutes") left = sleepLeftMs(mode, now);
      else if (mode.kind === "chapter" && engine.duration > 0) {
        left = ((engine.duration - engine.time) / Math.max(0.25, refs.current.rate)) * 1000;
      }
      if (left === null) return;
      if (mode.kind === "minutes" && left <= 0) {
        stopBySleep();
        return;
      }
      const fadeMs = options.fadeSeconds * 1000;
      if (left < fadeMs) {
        engine.setVolume(refs.current.volume * fadeGain(left, fadeMs));
        if (!refs.current.fading) {
          refs.current.fading = true;
          setFading(true);
          night.fading(position());
        }
      } else if (refs.current.fading) {
        endFade();
      }
      night.checkpoint(position());
    };
    tick();
    const timer = window.setInterval(tick, 100);
    return () => window.clearInterval(timer);
  }, [endFade, engine, native, night, options.fadeSeconds, playing, position, sleep.kind, stopBySleep]);

  // Máy tính: chạm phím/chuột lúc đang nhỏ dần = "lắc máy" - nghe thêm. Phím ấy không làm gì khác (không tạm dừng).
  useEffect(() => {
    if (native || !fading) return;
    const names = ["keydown", "pointerdown", "pointermove", "wheel"] as const;
    const onActivity = (event: Event) => {
      if (event.type === "keydown") {
        event.preventDefault();
        event.stopPropagation();
      }
      extendSleep();
    };
    names.forEach((name) => window.addEventListener(name, onActivity, { capture: true, once: true }));
    return () => names.forEach((name) => window.removeEventListener(name, onActivity, { capture: true }));
  }, [extendSleep, fading, native]);

  // Mọi thao tác trên máy là bằng chứng "còn thức": cho lưới an toàn ngủ quên, và cho nhật ký đêm khi đang hẹn giờ.
  useEffect(() => {
    if (native) return;
    const onActivity = () => {
      refs.current.lastActivity = Date.now();
      if (refs.current.track) refs.current.lastActivityPosition = position();
      if (refs.current.sleep.kind !== "off") night.touch("activity", position());
    };
    const names = ["keydown", "pointerdown", "wheel"] as const;
    names.forEach((name) => window.addEventListener(name, onActivity, { passive: true }));
    return () => names.forEach((name) => window.removeEventListener(name, onActivity));
  }, [native, night, position]);

  // Lưới an toàn: phát liên tục quá lâu mà không ai chạm máy (ngủ quên, quên hẹn giờ) thì tự hẹn 1 phút - nhỏ dần
  // rồi dừng như hẹn giờ thường - và ghi nhật ký đêm để sáng ra thẻ "Tối qua" vẫn giúp tìm lại chỗ.
  useEffect(() => {
    if (native || !playing || sleep.kind !== "off" || options.safetyStopHours <= 0) return;
    const check = () => {
      if (refs.current.sleep.kind !== "off" || refs.current.purpose !== "listen") return;
      if (Date.now() - refs.current.lastActivity < options.safetyStopHours * 3_600_000) return;
      const book = refs.current.book;
      if (book) {
        night.start(book, 1, position(), "safety");
        const before = refs.current.lastActivityPosition;
        if (before) night.touchAt(refs.current.lastActivity, "last-activity", before);
      }
      applySleep(sleepFrom({ kind: "minutes", minutes: 1 }, true, Date.now()));
      toast(`Không thấy ai chạm máy suốt ${options.safetyStopHours} giờ - sẽ tắt sau 1 phút`, {
        id: "safety-stop",
        duration: 60_000,
        action: { label: "Vẫn đang nghe", onClick: () => setSleepRef.current({ kind: "off" }) },
      });
    };
    const timer = window.setInterval(check, 30_000);
    return () => window.clearInterval(timer);
  }, [applySleep, native, night, options.safetyStopHours, playing, position, sleep.kind]);

  // Lịch đêm: bắt đầu nghe trong khung giờ thì tự hẹn giờ (trừ khi đêm nay người dùng đã tự tắt nó).
  useEffect(() => {
    if (native || !playing || sleep.kind !== "off" || refs.current.purpose !== "listen") return;
    const night_ = scheduleWindow(options.schedule);
    if (!night_ || !options.schedule || refs.current.scheduleOffFor === night_) return;
    setSleepRef.current({ kind: "minutes", minutes: options.schedule.minutes });
    toast(`Đã tự hẹn giờ ${options.schedule.minutes} phút`, {
      id: "sleep-schedule",
      description: `Lịch đêm ${options.schedule.from}-${options.schedule.to}. Tắt ở nút mặt trăng nếu chưa muốn ngủ.`,
    });
  }, [native, options.schedule, playing, sleep.kind]);

  useEffect(() => {
    const onHide = () => {
      save(true);
      closeSession(true);
      night.flush();
    };
    window.addEventListener("pagehide", onHide);
    return () => window.removeEventListener("pagehide", onHide);
  }, [closeSession, night, save]);

  // Phím tắt (máy tính). Không tranh phím với ô nhập, thanh trượt, tab, menu, hộp thoại; Space trên một nút chỉ
  // kích hoạt nút đó khi người dùng Tab tới nó bằng bàn phím (:focus-visible) - bấm chuột xong thì Space vẫn là
  // phát/tạm dừng như Spotify, YouTube.
  useEffect(() => {
    if (!keyboard || native) return;
    // Focus đến từ chuột hay bàn phím? Chỉ khi người dùng Tab tới một nút thì Space mới kích hoạt nút ấy.
    let keyboardNavigation = false;
    const onPointer = () => {
      keyboardNavigation = false;
    };
    const onTab = (event: KeyboardEvent) => {
      if (event.key === "Tab" || event.key.startsWith("Arrow")) keyboardNavigation = true;
    };
    window.addEventListener("pointerdown", onPointer, true);
    window.addEventListener("keydown", onTab, true);
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
      // Sự kiện bắn thẳng vào `document` (không phải phần tử) thì không có `closest`: bỏ qua thay vì văng lỗi.
      const target = event.target instanceof HTMLElement ? event.target : null;
      if (!target || !refs.current.track) return;
      if (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (target.closest('[role="menu"],[role="listbox"],[role="dialog"]')) return;
      const widget = target.closest('[role="slider"],[role="tab"],[role="radio"],[role="option"],[role="menuitem"]');
      const keyboardFocused = target !== document.body && keyboardNavigation;
      // Phím một chữ cái (B, M, [ ]) tắt ở Cài đặt › Phím tắt (WCAG 2.1.4); Space và mũi tên vẫn chạy.
      if (event.key.length === 1 && event.key !== " " && !letterShortcutsOn()) return;
      switch (event.key) {
        case " ": {
          // Thanh trượt không dùng Space vào việc gì: Space trên thanh tua vẫn là phát/tạm dừng.
          const activatable = target.tagName === "BUTTON" || target.tagName === "A" || (widget && widget.getAttribute("role") !== "slider");
          if (activatable && keyboardFocused) return;
          event.preventDefault();
          toggle();
          break;
        }
        case "ArrowLeft":
        case "ArrowRight": {
          if (widget) return;
          event.preventDefault();
          const forward = event.key === "ArrowRight";
          if (event.shiftKey) (forward ? next : previous)();
          else skip(forward ? SKIP_SECONDS : -SKIP_SECONDS);
          break;
        }
        case "b":
        case "B":
          event.preventDefault();
          window.dispatchEvent(new CustomEvent("abook:bookmark"));
          break;
        case "m":
        case "M":
          event.preventDefault();
          if (refs.current.volume > 0) {
            refs.current.muted = refs.current.volume;
            setVolume(0);
          } else {
            setVolume(refs.current.muted || 0.9);
          }
          break;
        case "[":
        case "]":
          event.preventDefault();
          setRate(nearestSpeed(refs.current.rate, event.key === "]" ? 1 : -1));
          break;
        default:
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointer, true);
      window.removeEventListener("keydown", onTab, true);
    };
  }, [keyboard, native, next, previous, setRate, setVolume, skip, toggle]);

  // Nút media của hệ điều hành (bộ máy web; lõi native tự lo phần này).
  useEffect(() => {
    if (native || !("mediaSession" in navigator) || !track) return;
    const handlers: [MediaSessionAction, MediaSessionActionHandler][] = [
      ["play", () => resume()],
      ["pause", () => pause()],
      ["stop", () => pause()],
      ["seekbackward", () => skip(-SKIP_SECONDS)],
      ["seekforward", () => skip(SKIP_SECONDS)],
      ["previoustrack", () => previous()],
      ["nexttrack", () => next()],
      ["seekto", (details) => {
        if (details.seekTime !== undefined) seek(details.seekTime);
      }],
    ];
    for (const [action, handler] of handlers) {
      try {
        navigator.mediaSession.setActionHandler(action, handler);
      } catch {
        /* không hỗ trợ */
      }
    }
  }, [native, next, pause, previous, resume, seek, skip, track]);

  useEffect(() => {
    if (native || !("mediaSession" in navigator) || !track) return;
    navigator.mediaSession.playbackState = playing ? "playing" : "paused";
    const report = () => {
      const duration = engine.duration;
      if (!duration) return;
      try {
        navigator.mediaSession.setPositionState({ duration, playbackRate: refs.current.rate, position: Math.min(engine.time, duration) });
      } catch {
        /* vị trí không hợp lệ lúc đang nạp */
      }
    };
    report();
    const timer = playing ? window.setInterval(report, 5000) : undefined;
    const off = engine.on("duration", report);
    return () => {
      window.clearInterval(timer);
      off();
    };
  }, [engine, native, playing, rate, track]);

  const setContinues = useCallback((bookId: string | null) => {
    refs.current.continues = bookId;
  }, []);

  const value = useMemo<PlayerValue>(() => ({
    track, queue, playing, buffering, rate, volume, sleep, fading, sleepStoppedAt, lastSleepMinutes, purpose, atEnd,
    canGoBack, error, notice, options, musicCredit, musicBroken, musicOffline, musicLoading,
    play, prepare, toggle, resume, retry, dismissError, wantsPlay, pause, seek, skip, next, previous, jumpTo, goBack, restart, setRate, setVolume, setSleep,
    extendSleep, addBookmark, close, switchRecord, positionStamp, setContinues,
  }), [track, queue, playing, buffering, rate, volume, sleep, fading, sleepStoppedAt, lastSleepMinutes, purpose, atEnd,
    canGoBack, error, notice, options, musicCredit, musicBroken, musicOffline, musicLoading, play, prepare, toggle, resume, retry, dismissError, wantsPlay, pause, seek, skip, next, previous, jumpTo, goBack, restart,
    setRate, setVolume, setSleep, extendSleep, addBookmark, close, switchRecord, positionStamp, setContinues]);

  // Mở/đóng "Đang nghe" qua View Transitions: bìa ở thanh phát bay lên thành bìa lớn (và bay về), phần còn lại mờ
  // chéo - xem .cover-morph trong styles.css. Không có API (trình duyệt cũ) hay người dùng xin giảm chuyển động thì
  // đổi thẳng, không hoạt ảnh.
  const expandedNow = useRef(expanded);
  expandedNow.current = expanded;
  const setExpandedAnimated = useCallback((value: boolean) => {
    // Không đổi gì thì không chạy View Transition rỗng: mục thanh bên gọi setExpanded(false) mỗi lần bấm, và một chuyển
    // cảnh rỗng khi cửa sổ không được vẽ (thu nhỏ, ẩn) bị trình duyệt huỷ thành lỗi console (soát UX 29-09).
    if (expandedNow.current === value) return;
    const start = (document as Document & { startViewTransition?: (update: () => void) => unknown }).startViewTransition;
    if (!start || prefersReducedMotion()) {
      setExpanded(value);
      return;
    }
    const transition = start.call(document, () => flushSync(() => setExpanded(value))) as
      | { ready?: Promise<unknown>; finished?: Promise<unknown> }
      | undefined;
    // Chuyển cảnh bị huỷ (TimeoutError) thì trạng thái vẫn đã đổi trong flushSync - chỉ là không có hoạt ảnh.
    transition?.ready?.catch(() => undefined);
    transition?.finished?.catch(() => undefined);
  }, []);
  const nowPlaying = useMemo(() => ({ expanded, setExpanded: setExpandedAnimated }), [expanded, setExpandedAnimated]);

  return (
    <ClockContext.Provider value={clock}>
      <PlayerContext.Provider value={value}>
        <NowPlayingContext.Provider value={nowPlaying}>
          {children}
          <OnlineVoicePrompt />
        </NowPlayingContext.Provider>
      </PlayerContext.Provider>
    </ClockContext.Provider>
  );
}
