// Lớp nhạc nền của trình phát máy tính: một (hai, khi chuyển cảnh) <audio> chạy song song với giọng đọc, theo các MỐC
// nhạc của chương (GET /api/books/<id>/music/chapters/<n> - webui/music_plan.py). Nhạc nền không cần khớp từng mili-giây
// như lời thoại với hình: chỉ cần đổi đúng bài khi sang đoạn mới, chuyển mờ dần, lặp liền, dừng / chạy theo giọng đọc,
// nhảy đúng chỗ khi người nghe tua. Âm lượng = âm lượng người nghe x `gainDb` của mốc (máy chủ tính từ `levelDb` = nhạc
// thấp hơn giọng bao nhiêu LU, độ to và độ lấn dải tiếng nói của từng bài - Pha 4 của docs/MUSIC_RESEARCH.md).
// Lặp bằng MỜ CHÉO vào chính bài trong đoạn nghe được [audibleStart, audibleEnd] (mô hình chung ở webui/music_mix.py), không
// dùng audio.loop - nối thẳng để lại tiếng tách, đuôi bị cắt, lỗ im (MIX_QA 3.2, 9). Hằng số đọc từ music_mix.json, một file
// cho cả ba bên. Android: MusicBed.kt, cùng quy tắc.
import mix from "../../../abook/webui/assets/music_mix.json";

export interface MusicCue {
  start: number;
  end: number;
  link: string;
  key: string;
  src: string;
  /** Độ khuếch đại (dB, <= 0) máy chủ đã tính cho bài này để nó nằm `levelDb` LU dưới giọng (music_plan.cue_gain_db):
   *  trình phát chỉ áp con số này, không tự tính. Thiếu (máy chủ cũ) -> mức chung `levelDb` của cuốn như trước. */
  gainDb?: number;
  /** Bước âm lượng trong cảnh (music_plan.chapter_cues): từ giây `at` của chương, mức là `gainDb + db` (dB, vẫn <= 0). Máy chủ
   *  tính, trình phát chỉ cộng; đổi bước thì trượt dần STEP_RAMP_SECONDS, tua thì vào thẳng mức tại chỗ tua. */
  steps?: MusicStep[];
  /** Mốc nối bài anh em ở điểm kết bài trong cùng cảnh: mờ chéo dài SIBLING_FADE_SECONDS, bài cũ chơi nốt phần còn lại rồi
   *  thôi (không quay lại đầu bài). */
  sibling?: boolean;
  /** Mốc kết đúng ở điểm kết bài (bài anh em vào ngay sau, hay bài kết sớm - music_plan.chapter_cues): ở vòng cuối bài thôi
   *  lặp để kết tự nhiên, không quay lại phần dạo đầu; hết sớm hơn mốc thì mốc kế vào ngay. */
  tail?: boolean;
  /** Đoạn nghe được của bài (giây trong bài, > -60 dBFS - music_plan.audible_bounds): lặp mờ chéo từ `audibleEnd` về
   *  `audibleStart`. Thiếu (sách đóng gói cũ, bài chưa đo) thì 0 và độ dài thật. */
  audibleStart?: number;
  audibleEnd?: number;
  /** Nhạc theo cảnh của sách chỉ có chữ (music_nnscene.py, sceneCues.ts): mốc MỞ một cảnh mang mã đoạn của màn đọc nơi cảnh bắt đầu - bài đổi đúng lúc
   *  đoạn ấy bắt đầu phát; giây `start` / `end` của máy chủ chỉ là giây ước, trình phát đặt lại theo đồng hồ đọc. */
  firstSegment?: number;
}

/** Lời đáp của máy chủ cho mốc nhạc một chương (GET /api/books/<id>/music/chapters/<n>). Nhạc theo cảnh (`scene`): `estSeconds` là độ dài chương theo giây ƯỚC của
 *  mốc; `pending` = chương chưa dựng xong (chưa có mốc, hỏi lại sau - giọng không chờ nhạc). */
export interface MusicCues {
  cues: MusicCue[];
  levelDb: number;
  credits?: Record<string, MusicCredit>;
  scene?: boolean;
  estSeconds?: number;
  pending?: boolean;
}

export interface MusicStep {
  at: number;
  db: number;
}

/** Ghi công tác giả một bài (CC BY đòi nêu tên ở nơi nhạc phát) - khoá theo `link` của mốc. */
export interface MusicCredit {
  title?: string;
  creator?: string;
  attribution?: string;
  landing?: string;
  license?: string;
  licenseUrl?: string;
}

/** MusicTab phát khi người dùng sửa / chọn lại nhạc của một cuốn (detail = mã sách): trình phát đang mở nạp lại mốc nhạc. */
export const MUSIC_CHANGED_EVENT = "abook:music-changed";

type BedAudio = Pick<HTMLAudioElement, "play" | "pause" | "paused" | "volume" | "loop" | "currentTime" | "duration"> & {
  /** `error`: bài không tải được (mất mạng, máy chủ không phát được). */
  addEventListener(type: "loadedmetadata" | "error", listener: () => void, options?: { once?: boolean }): void;
  /** Bài không lặp (bài cũ khi nối bài anh em) đã chơi hết: không phát lại. */
  readonly ended?: boolean;
};

/** <audio> thật; ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như engine.ts, clip.tsx). */
function browserAudio(src: string): BedAudio {
  const audio = new Audio(src);
  audio.muted = new URLSearchParams(window.location.search).get("mute") === "1";
  audio.preload = "auto";
  return audio;
}

export const FADE_SECONDS = mix.fadeSeconds;
export const SIBLING_FADE_SECONDS = mix.siblingFadeSeconds;
export const STEP_RAMP_SECONDS = mix.stepRampSeconds;
export const LOOP_CROSSFADE_SECONDS = mix.loopCrossfadeSeconds;
const STEP_MS = 50;
/** Bài tải hỏng (mất mạng): đoạn của nó im lặng, chừng ấy sau mới thử lại - như MusicFailures.RETRY_MS của Android. */
export const RETRY_MS = 5 * 60_000;

function cueAt(cues: MusicCue[], seconds: number): MusicCue | null {
  return cues.find((cue) => seconds >= cue.start && seconds < cue.end) ?? null;
}

/** Mức bước (dB) của mốc tại giây `seconds` của chương: bước cuối cùng đã tới, chưa tới bước nào thì 0. */
export function stepDbAt(cue: MusicCue, seconds: number): number {
  let db = 0;
  for (const step of cue.steps ?? []) {
    if (seconds < step.at) break;
    db = step.db;
  }
  return db;
}

/** Vòng lặp của một bài (webui/music_mix.py `loop_bounds`): vào từ `start` (A), hết ở `end` (E), lặp mỗi `period` giây
 *  (P = E - A - X). `crossfade` false: bài quá ngắn (E - A < 3X) lặp thường cả file như cũ (A 0, E = P = độ dài). */
export interface LoopBounds {
  start: number;
  end: number;
  period: number;
  crossfade: boolean;
}

function finite(value: number | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Vòng lặp của bài của mốc `cue`, độ dài thật `duration` (chưa biết: NaN). Chưa biết độ dài lẫn E: bài không bao giờ hết. */
export function loopBounds(cue: Pick<MusicCue, "audibleStart" | "audibleEnd">, duration: number): LoopBounds {
  const total = Number.isFinite(duration) && duration > 0 ? duration : null;
  const start = Math.max(0, finite(cue.audibleStart) ?? 0);
  const audibleEnd = finite(cue.audibleEnd);
  let end = audibleEnd !== null && audibleEnd > 0 ? audibleEnd : total;
  if (end === null) return { start: 0, end: Infinity, period: Infinity, crossfade: false };
  if (total !== null) end = Math.min(end, total);
  if (end - start < 3 * LOOP_CROSSFADE_SECONDS) {
    const whole = total ?? end;
    return { start: 0, end: whole, period: whole, crossfade: false };
  }
  return { start, end, period: end - start - LOOP_CROSSFADE_SECONDS, crossfade: true };
}

/** Chỗ trong bài ứng với giây `seconds` của chương: A + ((giây - đầu mốc) mod P) - vào giữa chương hay tua thì nhạc cũng ở giữa
 *  bài, không chạy lại từ đầu (soát a26 L8). */
export function alignedPosition(cue: MusicCue, seconds: number, bounds: LoopBounds): number {
  const offset = Math.max(0, seconds - cue.start);
  return bounds.start + (Number.isFinite(bounds.period) ? offset % bounds.period : offset);
}

/** Phần tử đang kêu ở `currentTime` đã tới E - X: lúc mở phần tử lặp mới từ A. */
export function loopDue(bounds: LoopBounds, currentTime: number): boolean {
  return bounds.crossfade && currentTime >= bounds.end - LOOP_CROSSFADE_SECONDS;
}

/** Mốc `tail` đang ở vòng cuối: phần còn lại của mốc hơn phần còn lại của bài (tới E) chưa tới nửa chu kỳ - không mở phần tử lặp
 *  nữa, bài chơi tới E là hết (lô 1, tính theo E thay vì độ dài file). Chưa biết độ dài bài: chưa phải. */
export function finalLoop(cue: MusicCue, seconds: number, currentTime: number, bounds: LoopBounds): boolean {
  return !!cue.tail && Number.isFinite(bounds.end) && cue.end - seconds - (bounds.end - currentTime) < bounds.period / 2;
}

/** Bài đã hết: chơi tới E (phần sau là im) hay `ended`. */
export function finished(bounds: LoopBounds, currentTime: number, ended: boolean): boolean {
  return ended || currentTime >= bounds.end;
}

/** Nối bài anh em: bài cũ mờ ra trong SIBLING_FADE_SECONDS, hay trong phần còn lại thật của nó (tới E) nếu ngắn hơn - không bao
 *  giờ bị cắt khi còn kêu (MIX_QA 3.5). */
export function siblingFadeSeconds(bounds: LoopBounds, currentTime: number): number {
  return Math.max(STEP_MS / 1000, Math.min(SIBLING_FADE_SECONDS, bounds.end - currentTime));
}

interface Playing {
  cue: MusicCue;
  audio: BedAudio;
  /** Âm lượng đang hướng tới, và mỗi nhịp STEP_MS nhích bao nhiêu. */
  goal: number;
  perTick: number;
  /** Đang mờ vào (bài mới, phần tử lặp): tua lúc này không nhảy thẳng tới mức; mờ vào trong `fadeSeconds` giây. */
  entering: boolean;
  fadeSeconds: number;
  /** Vào sớm: bài trước đã kết tự nhiên trước đầu mốc này. Tới `cue.start` giọng vẫn ở mốc cũ - không chuyển ngược. */
  early?: boolean;
  /** Vòng cuối của mốc `tail`: không mở phần tử lặp nữa, bài chơi tới E là hết. */
  final?: boolean;
}

export class MusicBed {
  constructor(private readonly createAudio: (src: string) => BedAudio = browserAudio) {}

  private cues: MusicCue[] = [];
  private gain = 0.1;
  private userVolume = 1;
  private playing = false;
  private current: Playing | null = null;
  private fading: BedAudio[] = [];
  // âm lượng bớt mỗi nhịp khi mờ đi: bài to và bài nhỏ cùng tắt trong FADE_SECONDS (SIBLING_FADE_SECONDS khi nối bài anh em)
  private fadeStep = new WeakMap<BedAudio, number>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastTime = 0;
  private listeners = new Set<(link: string | null) => void>();
  private loadListeners = new Set<(link: string, ok: boolean) => void>();
  private announced: string | null = null;
  // Bài không phát được (`link` của mốc) -> lúc được thử lại (Date.now()); tải được thì xoá.
  private failed = new Map<string, number>();

  /** Mốc mới (`levelDb` bỏ trống = giữ mức chung cũ). `seconds`: chỗ đang tới theo mốc mới - danh sách phát dựng lại hàng bài thì đồng
   *  hồ nhạc rơi vào chỗ khác của hàng mới. */
  setCues(cues: MusicCue[], levelDb?: number, seconds = this.lastTime): void {
    this.cues = cues;
    if (levelDb !== undefined) this.gain = Math.pow(10, levelDb / 20);
    this.lastTime = seconds;
    this.switchTo(this.playableAt(seconds), seconds);
  }

  setVolume(volume: number): void {
    this.userVolume = Math.max(0, Math.min(1, volume));
    if (this.current) this.current.audio.volume = this.current.goal = this.target();
  }

  /** Gọi mỗi khi thời gian giọng đọc đổi (`seeked` = người nghe vừa tua). */
  sync(seconds: number, playing: boolean, seeked = false): void {
    this.lastTime = seconds;
    this.playing = playing;
    // Mốc của bài vừa tải hỏng tính như khoảng không nhạc; tới hạn thử lại thì lần đồng bộ này vào bài như mốc mới.
    let cue = this.playableAt(seconds);
    const current = this.current?.cue;
    if (this.current?.early) {
      // Bài vào sớm giữ chỗ tới đầu mốc của nó; tua thì theo mốc tại chỗ tua như thường.
      if (!seeked && seconds < this.current.cue.start) cue = this.current.cue;
      else this.current.early = false;
    }
    // Mốc anh em có thể cùng khoá đoạn với mốc trước (nối giữa một đoạn): phân biệt bằng cả giây bắt đầu.
    if (cue?.key !== current?.key || cue?.start !== current?.start || (seeked && cue)) {
      this.switchTo(cue, seconds, seeked);
    }
    this.retarget(seeked);
    this.finishTail(seconds);
    this.crossLoop(seconds);
    for (const audio of [this.current?.audio, ...this.fading]) {
      if (!audio) continue;
      if (playing && audio.paused && !audio.ended) void audio.play().catch(() => undefined);
      if (!playing && !audio.paused) audio.pause();
    }
  }

  /** Có bài của chương này đang bị bỏ vì không phát được (đoạn ấy im lặng, chờ thử lại) - hộp "Nhạc nền" nói ra thay vì chỉ "Bật"
   *  (soát a26 L7). */
  get failing(): boolean {
    const now = Date.now();
    return this.cues.some((cue) => (this.failed.get(cue.link) ?? 0) > now);
  }

  /** Bài đang phát (null = im lặng) - cho giao diện và bài thử. */
  get activeLink(): string | null {
    return this.current?.cue.link ?? null;
  }

  /** Báo mỗi khi bài đang phát đổi (kể cả thành im lặng = null): giao diện vẽ dòng ghi công theo đó. */
  onActiveChange(listener: (link: string | null) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** Báo mỗi bài tải xong (`ok` true) hay hỏng (false) - danh sách phát dựa vào đó cho bài sau dồn lên (PlaylistDriver). */
  onLoadResult(listener: (link: string, ok: boolean) => void): () => void {
    this.loadListeners.add(listener);
    return () => this.loadListeners.delete(listener);
  }

  stop(): void {
    for (const audio of [this.current?.audio, ...this.fading]) audio?.pause();
    this.current = null;
    this.fading = [];
    this.cues = [];
    this.failed.clear();
    this.emitActive();
  }

  /** Mốc tại giây `seconds`, trừ khi bài của nó đang chờ thử lại; bài đã tới hạn thì bỏ khỏi danh sách hỏng. */
  private playableAt(seconds: number): MusicCue | null {
    const cue = cueAt(this.cues, seconds);
    if (!cue) return null;
    const retryAt = this.failed.get(cue.link);
    if (retryAt === undefined) return cue;
    if (retryAt > Date.now()) return null;
    this.failed.delete(cue.link);
    return cue;
  }

  /** Bài `audio` của mốc `cue` không tải được: đoạn của nó im lặng, RETRY_MS sau mới thử lại. */
  private drop(cue: MusicCue, audio: BedAudio): void {
    this.failed.set(cue.link, Date.now() + RETRY_MS);
    audio.pause();
    this.fading = this.fading.filter((other) => other !== audio);
    if (this.current?.audio === audio) {
      this.current = null;
      this.emitActive();
    }
    for (const listener of [...this.loadListeners]) listener(cue.link, false);
  }

  private emitActive(): void {
    const link = this.activeLink;
    if (link === this.announced) return;
    this.announced = link;
    for (const listener of [...this.listeners]) listener(link);
  }

  /** Âm lượng mục tiêu của bài đang phát: gainDb của chính mốc (bài to / nhỏ khác nhau) cộng bước đang hiệu lực; không có
   *  gainDb thì mức chung. */
  private target(cue: MusicCue | undefined = this.current?.cue): number {
    const gainDb = cue?.gainDb;
    const step = cue ? stepDbAt(cue, this.lastTime) : 0;
    const gain = typeof gainDb === "number" && Number.isFinite(gainDb)
      ? Math.pow(10, Math.min(0, gainDb + step) / 20)
      : this.gain * Math.pow(10, step / 20);
    return Math.min(1, gain * this.userVolume);
  }

  /** Mức đích đổi (sang bước mới): trượt dần STEP_RAMP_SECONDS; vừa tua thì vào thẳng mức mới (trừ lúc bài đang mờ vào). */
  private retarget(seeked: boolean): void {
    const playing = this.current;
    if (!playing) return;
    const goal = this.target();
    if (Math.abs(goal - playing.goal) < 1e-6) return;
    playing.goal = goal;
    if (playing.entering) {
      playing.perTick = (goal * STEP_MS) / 1000 / playing.fadeSeconds;
    } else if (seeked) {
      playing.audio.volume = goal;
      return;
    } else {
      playing.perTick = (Math.abs(goal - playing.audio.volume) * STEP_MS) / 1000 / STEP_RAMP_SECONDS;
    }
    this.startFade();
  }

  /** Mốc `tail`: ở vòng cuối (`finalLoop` - theo độ dài thật của bài, không theo số danh mục) bài thôi lặp và kết tự nhiên ở E.
   *  Bài đã kết trước hết mốc (tới E hay `ended`) mà mốc kế bắt đầu đúng ở đó: mốc kế vào ngay, mờ vào như thường (bài anh em
   *  SIBLING_FADE_SECONDS), không để quãng im. Không có mốc kế (bài kết sớm) thì im tới hết mốc. */
  private finishTail(seconds: number): void {
    const playing = this.current;
    if (!playing?.cue.tail) return;
    const { audio, cue } = playing;
    const bounds = loopBounds(cue, audio.duration);
    if (!playing.final && audio.duration > 0 && finalLoop(cue, seconds, audio.currentTime, bounds)) {
      playing.final = true;
      audio.loop = false; // bài quá ngắn lặp thường: chơi nốt vòng này rồi thôi
    }
    const done = playing.final ? finished(bounds, audio.currentTime, !!audio.ended) : !!audio.ended;
    if (!done || seconds >= cue.end) return;
    const next = this.playableAt(cue.end);
    if (!next || next.start !== cue.end || next.link === cue.link) return;
    this.switchTo(next, seconds);
    if (this.current?.cue === next) this.current.early = true;
  }

  /** Lặp mờ chéo: phần tử đang kêu tới E - X thì một phần tử MỚI của chính bài vào từ A, mờ chéo LOOP_CROSSFADE_SECONDS; phần
   *  tử cũ mờ đi rồi dừng. Vòng cuối của mốc `tail` (`finishTail`) và bài quá ngắn (lặp thường) thì không. */
  private crossLoop(seconds: number): void {
    const playing = this.current;
    if (!playing || playing.final || seconds >= playing.cue.end || !(playing.audio.duration > 0)) return;
    const bounds = loopBounds(playing.cue, playing.audio.duration);
    if (!loopDue(bounds, playing.audio.currentTime)) return;
    const old = playing.audio;
    this.fadeStep.set(old, (Math.max(old.volume, 0.01) * STEP_MS) / 1000 / LOOP_CROSSFADE_SECONDS);
    this.fading.push(old);
    this.current = { ...this.open(playing.cue, seconds, LOOP_CROSSFADE_SECONDS, bounds.start), early: playing.early };
    this.startFade();
  }

  /** Đặt bài `audio` của mốc `cue` vào đúng chỗ ứng với giây `seconds` của chương (`alignedPosition`). Chưa biết độ dài bài thì
   *  chờ `loadedmetadata`. */
  private align(audio: BedAudio, cue: MusicCue, seconds: number): void {
    if (audio.duration > 0) audio.currentTime = alignedPosition(cue, seconds, loopBounds(cue, audio.duration));
  }

  /** Một phần tử <audio> mới của mốc `cue`, mờ vào trong `fadeSeconds` giây. `startAt` (phần tử lặp): vào đúng chỗ ấy (A), không căn
   *  theo giây chương - đồng hồ bài lệch giọng vài phần giây thì căn lại có khi rơi về cuối vòng. */
  private open(cue: MusicCue, seconds: number, fadeSeconds: number, startAt?: number): Playing {
    const audio = this.createAudio(cue.src);
    audio.loop = !loopBounds(cue, audio.duration).crossfade;
    audio.volume = 0;
    if (startAt !== undefined) audio.currentTime = startAt; // chưa có metadata: trình duyệt nhớ làm chỗ bắt đầu
    audio.addEventListener("loadedmetadata", () => {
      this.failed.delete(cue.link);
      audio.loop = !loopBounds(cue, audio.duration).crossfade && !(this.current?.audio === audio && this.current.final);
      // Bài tải xong sau khi giọng đã chạy tiếp (hay vừa tua): theo giây mới nhất, không phải giây lúc tạo bài.
      if (startAt === undefined) this.align(audio, cue, this.current?.audio === audio ? this.lastTime : seconds);
      else if (Math.abs(audio.currentTime - startAt) > 0.25) audio.currentTime = startAt;
      for (const listener of [...this.loadListeners]) listener(cue.link, true);
    }, { once: true });
    audio.addEventListener("error", () => this.drop(cue, audio), { once: true });
    const goal = this.target(cue);
    if (this.playing) void audio.play().catch(() => undefined);
    return { cue, audio, goal, perTick: (goal * STEP_MS) / 1000 / fadeSeconds, entering: true, fadeSeconds };
  }

  private switchTo(cue: MusicCue | null, seconds: number, seeked = false): void {
    if (this.current && cue && this.current.cue.link === cue.link) {
      // Cùng bài (đoạn kề): chơi tiếp, không bắt đầu lại. Vừa tua (hay vừa nạp chương ở giữa): dời nhạc theo chỗ mới.
      this.current.cue = cue;
      if (seeked) {
        // Vòng cuối của mốc `tail` tính lại theo chỗ mới (finishTail).
        this.current.final = false;
        this.current.audio.loop = !loopBounds(cue, this.current.audio.duration).crossfade;
        this.align(this.current.audio, cue, seconds);
      }
      return;
    }
    const fadeSeconds = cue?.sibling ? SIBLING_FADE_SECONDS : FADE_SECONDS;
    if (this.current) {
      const { audio: old, cue: was } = this.current;
      let fade = fadeSeconds;
      if (cue?.sibling) {
        old.loop = false; // bài cũ vừa hết vòng: chơi nốt rồi thôi, không quay lại đầu bài
        if (old.duration > 0) fade = siblingFadeSeconds(loopBounds(was, old.duration), old.currentTime);
      }
      this.fadeStep.set(old, (Math.max(old.volume, 0.01) * STEP_MS) / 1000 / fade);
      this.fading.push(old);
      this.current = null;
    }
    if (cue) this.current = this.open(cue, seconds, fadeSeconds);
    this.emitActive();
    this.startFade();
  }

  private startFade(): void {
    if (this.timer !== null) return;
    this.timer = globalThis.setInterval(() => {
      let busy = false;
      const playing = this.current;
      if (playing) {
        const { audio, goal } = playing;
        const move = Math.max(playing.perTick, 1e-5);
        if (audio.volume < goal) audio.volume = Math.min(goal, audio.volume + move);
        else if (audio.volume > goal) audio.volume = Math.max(goal, audio.volume - move);
        if (Math.abs(audio.volume - goal) < 1e-4) playing.entering = false;
        else busy = true;
      }
      this.fading = this.fading.filter((audio) => {
        audio.volume = Math.max(0, audio.volume - (this.fadeStep.get(audio) ?? (0.1 * STEP_MS) / 1000 / FADE_SECONDS));
        if (audio.volume <= 0.001) {
          audio.pause();
          return false;
        }
        busy = true;
        return true;
      });
      if (!busy && this.timer !== null) {
        globalThis.clearInterval(this.timer);
        this.timer = null;
      }
    }, STEP_MS);
  }
}
