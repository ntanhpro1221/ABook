import type { AudioEngine, EngineEvent, TrackInfo } from "./engine";
import type { Script, ScriptSegment } from "./model";
import { isSpeakable, sceneBreakGaps } from "./textScript";
import { usableWords, type WordSpan } from "./words";

export { isSpeakable };

// "Nghe ngay" cho chương CHỈ-CÓ-CHỮ (docs/LISTEN_ANYTHING.md mục 1 và 3): giọng máy đọc từng đoạn của chương thành một "clip" (audio ở tốc độ 1,0
// + mốc từng chữ, `abook/readaloud`), bộ máy này ghép các clip thành một chương có đồng hồ riêng và điền thời gian vào kịch bản chữ - màn đọc
// (ReaderScreen) sáng đoạn và chữ đang đọc y như với sách nói của Studio, không có trường hợp riêng nào.
//
// Đồng hồ ảo: mỗi đoạn có [start, end] giây. Đoạn chưa có clip được ƯỚC (~14 ký tự mỗi giây) và sửa lại khi clip về; đồng hồ = đầu đoạn đang đọc +
// currentTime của clip, tổng thời lượng = tổng các đoạn. Tốc độ đổi bằng playbackRate của phần tử audio, không bao giờ đọc lại (bộ đệm dùng chung).

export interface ReadAloudVoice {
  /** "edge:vi-VN-HoaiMyNeural", "device:<mã Windows>"... */
  id: string;
  name: string;
  provider: string;
  /** Gửi chữ của sách ra ngoài máy. */
  online: boolean;
  default?: boolean;
  /** "female" / "male" / "" (không rõ) - gợi ý trong Cài đặt. */
  gender?: string;
  /** Chỉnh độ to lúc phát (dB, <= 0) cho các giọng khác nhau về độ to - abook/readaloud/loudness.py. */
  gainDb?: number;
}

export interface ReadAloudClip {
  /** Đường dẫn file audio (đã có mã phiên nếu cần). */
  url: string;
  durationMs: number;
  /** Một cặp [bắt đầu_ms, kết thúc_ms] cho mỗi chữ hiện (`\S+`), tính từ đầu clip. */
  words: WordSpan[];
  /** Giọng đã đọc clip này (có thể khác giọng đã chọn nếu rơi về giọng máy) - cho độ to. */
  gainDb?: number;
}

export interface ClipOptions {
  /** Chỉ tra bộ đệm, không đọc mới: chưa có thì lỗi `reason` "uncached". */
  cachedOnly?: boolean;
  /** Cuốn đang nghe: máy tính dùng nó để biết cuốn gốc Nhật / Hàn (đọc tên theo luật phiên âm, abook/readaloud/names.py) và cách đọc riêng
   *  người nghe đã đặt cho cuốn ("Đọc từ này là…", listen/readings.ts). */
  bookId?: string;
  /** "Nghe thử" một cách đọc chưa lưu: dùng bảng này thay cho cách đọc riêng của cuốn ({} = không cách đọc riêng nào). */
  readings?: Record<string, string>;
  /** Bộ máy sẽ tự thử lại nếu lần này hỏng vì lỗi thoáng qua ([isTransientClipError]): bộ lấy clip đừng vội bỏ giọng ấy / rơi sang giọng khác, cứ ném lỗi gốc lên. */
  willRetry?: boolean;
}

export type ClipFetcher = (voice: string, text: string, options?: ClipOptions) => Promise<ReadAloudClip>;

/** Lỗi lấy clip. `reason`: "offline", "timeout", "rejected", "service", "voice", "empty", "uncached", và với giọng dùng khoá riêng "auth" /
 *  "quota" (abook/readaloud/model.py VoiceError). */
export class ReadAloudError extends Error {
  reason: string;
  constructor(message: string, reason = "service") {
    super(message);
    this.reason = reason;
  }
}

/** Những gì trình phát đưa cho bộ máy khi nạp một chương chỉ-có-chữ (`TrackInfo.speech`). */
export interface SpeechTrack {
  /** Các đoạn của chương (textScript); gọi một lần lúc nạp. Kịch bản đã `timed` (lần nghe trước) thì dùng luôn độ dài đã biết. */
  script(): Promise<Script>;
  /** Giọng đang chọn, hỏi lại trước mỗi clip ("" = giọng mặc định): đổi giọng giữa chừng có hiệu lực từ đoạn kế. */
  voice(): string;
  fetchClip: ClipFetcher;
  /** Cuốn đang nghe: để biết cách đọc riêng nào vừa đổi ([READINGS_CHANGED_EVENT]) là của cuốn này. */
  bookId?: string;
  /** Giọng đang chọn chạy trên máy này (hỏi lại trước mỗi lượt): nó dùng hết CPU cho MỘT đoạn, xin 4 đoạn cùng lúc thì đoạn người nghe đang chờ chỉ nhận một phần
   *  tư máy (nhảy tới câu xa: 3-5 s thay vì ~1,3 s) - nên xin lần lượt, đoạn gần chỗ nghe nhất trước. Vắng / false (giọng trực tuyến): cả cửa sổ đọc trước chạy song song. */
  serial?(): boolean;
  /** Chữ các đoạn của chương kế nếu nó là chương chỉ-có-chữ cùng cuốn, rỗng khi không có. Khi chương này sắp hết, bộ máy xin trước vài clip đầu của chương ấy
   *  (tiêu đề + đoạn đầu) để chương kế mở ra có tiếng ngay - giọng trực tuyến làm một đoạn hai câu chậm cỡ thời gian nghe (soát a44: im lặng 9-20 giây sau mỗi tiêu đề). */
  after?(): Promise<string[]>;
  /** Kịch bản có mốc thời gian mới (mỗi khi clip về) - trình phát ghi vào bộ nhớ của react-query để màn đọc sáng đúng đoạn / chữ. */
  onScript(script: Script): void;
}

/** Mốc thời gian của chương chỉ-có-chữ do nơi khác đọc (lõi native Android, plugin ReadAloud.script): từng câu theo thứ tự trong chương -
 *  `start` / `end` giây, `words` ms tính từ ĐẦU CHƯƠNG (cùng quy ước words.ts), vắng khi câu chưa đọc (chỉ có mốc ước). */
export interface ReadAloudTimings {
  segments: { start: number; end: number; words?: WordSpan[] }[];
}

/** Gắn mốc của nơi khác vào kịch bản chữ: màn đọc sáng đoạn / chữ đúng như khi bộ máy web tự điền (ReadAloudEngine.publish). */
export function mergeTimings(script: Script, timings: ReadAloudTimings): Script {
  if (!timings.segments.length) return script;
  const segments = script.segments.map((segment, i): ScriptSegment => {
    const timed = timings.segments[i];
    if (!timed || !Number.isFinite(timed.start) || !Number.isFinite(timed.end)) return segment;
    return { ...segment, start: timed.start, end: timed.end, words: timed.words && timed.words.length ? timed.words : undefined };
  });
  const duration = segments.reduce((most, segment) => Math.max(most, segment.end ?? 0), 0);
  return { ...script, timed: true, duration, segments };
}

export const CHARS_PER_SECOND = 14;
export const MIN_SEGMENT_SECONDS = 0.6;
/** Sự kiện cửa sổ: người nghe đổi giọng đọc (readAloudVoice.ts). */
export const VOICE_CHANGED_EVENT = "abook:readaloud-voice";
/** Sự kiện cửa sổ: người nghe vừa đặt / bỏ cách đọc riêng của một từ trong cuốn ("Đọc từ này là…", readings.ts) - các đoạn có từ ấy mà đã đọc sẵn phải đọc lại.
 *  `detail`: { bookId, surfaces }. */
export const READINGS_CHANGED_EVENT = "abook:readaloud-readings";
export interface ReadingsChanged {
  bookId: string;
  surfaces: string[];
  /** Mọi đoạn của cuốn đều phải lấy lại (người nghe vừa xoá bản đọc đã làm của cuốn: file clip không còn nữa); `bookId` rỗng = của mọi cuốn (dọn cả máy). */
  all?: boolean;
}
/** Lỗi lấy clip thoáng qua (thử lại là xong): máy chủ báo "service" (Edge cắt lượt / bận / 5xx / không với tới máy chủ cục bộ) hay "timeout" (chậm quá). Mất mạng ("offline"),
 *  bị từ chối ("rejected"), giọng / khoá hỏng, chữ không đọc được... thì không - dừng ngay như cũ. Lỗi do bộ lấy clip đã tự quyết xong (`final`: đã thử hết
 *  giọng, hay giọng đang nghỉ) cũng không thử lại thêm. */
const TRANSIENT_REASONS = new Set(["service", "timeout"]);
export function isTransientClipError(error: unknown): boolean {
  const found = error as { reason?: string; final?: boolean } | null;
  return !found?.final && TRANSIENT_REASONS.has(found?.reason ?? "");
}
/** Nghỉ trước mỗi lần thử lại một clip hỏng vì lỗi thoáng qua (ms): 1 + 2,5 + 4,5 + 7 = 15 giây, trong lúc ấy các clip đã đọc sẵn vẫn phát. */
export const CLIP_RETRY_DELAYS_MS = [1000, 2500, 4500, 7000];
/** Số lần thử lại một clip hỏng vì lỗi thoáng qua trước khi dừng (nếu người nghe đã tới đoạn ấy). */
export const CLIP_RETRIES = CLIP_RETRY_DELAYS_MS.length;
// Máy tính: đọc trước tối thiểu 3 đoạn (rẻ - clip chỉ vài chục KB; đoạn ngắn liên tiếp không còn bắt người nghe chờ). Điện thoại tự đọc trước (ReadAloud.kt).
const READ_AHEAD = 3;
/** Giọng trực tuyến chậm từng lúc (soát a45: Edge có lúc 9-24 s một đoạn, giọng im 9 giây giữa chương): chỉ đọc sẵn 3 đoạn thì đoạn ngắn (đối thoại) chỉ đủ vài giây. Nên đọc sẵn đủ SỐ GIÂY
 *  ÂM THANH: tối thiểu `MIN_BUFFER_SECONDS`, và khi mấy clip gần đây về chậm thì `BUFFER_FACTOR` lần thời gian lấy clip ở phân vị 80 - để một quãng chậm không tới tai người nghe. Mô phỏng
 *  (Edge nhanh 1-3 s xen quãng chậm 9-24 s, 12 lượt x 10 phút): số lần im > 2 giây từ 17 xuống 0. Trần: `MAX_READ_AHEAD` đoạn (mỗi đoạn là một lượt gọi Edge, đoạn nào người nghe bỏ đi là uổng) và
 *  `MAX_BUFFER_SECONDS`. Số lượt gọi CÙNG LÚC không tăng theo (vẫn đọc trước + 1 như trước đây: Edge hạn chế khi dồn nhiều kết nối) - chỉ hàng đợi dài ra. Chương đã nằm trong bộ đệm (lấy về
 *  trong vài chục ms, không tính là số đo) và giọng chạy trên máy ([SpeechTrack.serial]) không đổi gì. */
const MAX_READ_AHEAD = 8;
const BUFFER_FACTOR = 2;
const MIN_BUFFER_SECONDS = 20;
const MAX_BUFFER_SECONDS = 60;
/** Chỉ tính lượt lấy clip THẬT (qua dịch vụ): lấy từ bộ đệm của máy chủ về trong vài chục ms, làm loãng số đo. */
const REAL_FETCH_SECONDS = 0.25;
const FETCH_SAMPLES = 8;
const SLOW_FAILURE_SECONDS = 4;
/** Lượt gọi còn chưa về mà đã chờ từ ngần này giây thì tính như một số đo (chặn dưới): quãng chậm hiện ra ngay khi nó bắt đầu, không phải sau khi vài clip chậm về xong (lúc ấy đoạn đọc sẵn đã cạn). */
const STALL_SECONDS = 3;
/** Nhịp xét lại độ sâu đọc trước trong lúc còn lượt gọi chưa về (ms). */
const WATCH_MS = 1000;
/** Chương kế: xin trước chừng này clip đầu (tiêu đề + đoạn đầu) khi chương này sắp hết ([SpeechTrack.after]). */
export const NEXT_CHAPTER_AHEAD = 2;
const RESTORE_LIMIT = 400;
/** Nhịp đồng hồ của quãng lặng ở dòng ngăn cảnh (ms). */
const SILENCE_TICK_MS = 100;
/** Nhảy liên tiếp (kéo thanh tua, bấm hết câu này tới câu kia): giọng chạy trên máy làm một clip một lúc và không dừng giữa chừng được, nên mỗi lượt xin gửi
 *  sớm cho một đích sắp bị bỏ là cả một clip làm uổng mà đích cuối phải chờ sau. Nhảy tiếp trong vòng `JUMP_BURST_MS` sau lần nhảy trước thì lượt xin mới chỉ
 *  được gửi khi người nghe ngừng nhảy `JUMP_SETTLE_MS` (lần nhảy đầu vẫn gửi ngay; và chỉ khi giọng chậm - [SLOW_CLIP_MS]). */
const JUMP_BURST_MS = 1500;
const JUMP_SETTLE_MS = 800;
/** Chỉ giữ lượt xin khi giọng làm một clip lâu (clip vừa xong, hay lượt đang chạy, từ ngần này ms): máy nhanh thì clip cũ xong ngay trong lúc người nghe còn nhảy,
 *  giữ chỉ thêm chờ; máy chậm thì mỗi clip uổng là cả giây người nghe phải chờ thêm. */
const SLOW_CLIP_MS = 1000;

/** Ước thời gian đọc một đoạn khi chưa có clip. Đoạn không có chữ nào đọc được ("* * *") không tốn thời gian (quãng lặng của dòng ngăn cảnh
 *  tính riêng - [sceneBreakGaps]). */
export function estimateSeconds(text: string): number {
  return isSpeakable(text) ? Math.max(MIN_SEGMENT_SECONDS, text.length / CHARS_PER_SECOND) : 0;
}

/** Giây bắt đầu ước của từng đoạn khi chưa có clip nào (màn đọc dùng để "Nghe từ đây" trước khi bộ máy chạy). */
export function estimatedStarts(segments: { text: string; sceneBreak?: boolean }[]): number[] {
  const gaps = sceneBreakGaps(segments);
  let at = 0;
  return segments.map((segment, i) => {
    const start = at;
    at += estimateSeconds(segment.text) + gaps[i] / 1000;
    return start;
  });
}

// ---- phần tử audio -------------------------------------------------------------------------------------------------

/** Phần dùng của HTMLAudioElement (để bài thử thay bằng đồ giả). */
export interface AudioLike {
  src: string;
  currentTime: number;
  readonly paused: boolean;
  readonly duration: number;
  playbackRate: number;
  volume: number;
  muted: boolean;
  preload: string;
  play(): Promise<void>;
  pause(): void;
  removeAttribute(name: string): void;
  load(): void;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

function realAudio(url: string): AudioLike {
  const audio = new Audio();
  audio.preload = "auto";
  audio.src = url;
  return audio;
}

function muteRequested(): boolean {
  try {
    // ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như WebAudioEngine).
    return new URLSearchParams(window.location.search).get("mute") === "1";
  } catch {
    return false;
  }
}

interface Slot {
  text: string;
  speakable: boolean;
  /** Quãng lặng cố định (giây) của dòng ngăn cảnh: không clip, không gửi giọng đọc; > 0 thì phát bằng đồng hồ ([startSilence]). */
  silence: number;
  estimate: number;
  /** Giây; clip về thì là độ dài thật. */
  duration: number;
  start: number;
  clip: ReadAloudClip | null;
  /** Mốc từng chữ tương đối đầu đoạn (ms): từ clip, hay từ kịch bản của lần nghe trước. */
  words: WordSpan[] | null;
  audio: AudioLike | null;
  detach: (() => void) | null;
  /** Đã đặt currentTime / phát: `time` đọc từ phần tử audio thay vì `offset`. */
  started: boolean;
  fetching: boolean;
  /** Số lần lấy clip đã hỏng liên tiếp (Edge thỉnh thoảng trả 502 thoáng qua). */
  failures: number;
  /** Tăng mỗi khi clip của đoạn bị bỏ vì cách đọc đổi: clip về từ lượt hỏi cũ (epoch cũ) thì không dùng. */
  epoch: number;
  /** Cách đọc có chữ trong đoạn này vừa đổi mà đoạn đang nói (không cắt ngang): lần phát lại kế tiếp lấy clip mới. */
  stale: boolean;
}

interface Target {
  index: number;
  /** Giây trong clip. */
  offset: number;
  /** Chưa có clip: vị trí tính theo tỉ lệ đoạn (kéo thanh tua vào đoạn chưa đọc). */
  fraction?: number;
  /** Chưa có clip: bắt đầu từ chữ này khi clip về (bấm vào một chữ). */
  word?: number;
}

export interface ReadAloudOptions {
  createAudio?: (url: string) => AudioLike;
  muted?: boolean;
  readAhead?: number;
}

type Handlers = Map<EngineEvent, Set<() => void>>;

/** Số đoạn nên đọc trước sau đoạn đang nghe. `base`: số tối thiểu. `fetchSeconds`: thời gian lấy clip THẬT của vài clip gần nhất (giây). `aheadSeconds`: độ dài (thật hay ước) của
 *  các đoạn kế tiếp, theo thứ tự. Cần đọc sẵn max([MIN_BUFFER_SECONDS], [BUFFER_FACTOR] lần thời gian lấy clip ở phân vị 80) giây âm thanh (tối đa [MAX_BUFFER_SECONDS]): thêm đoạn vào cửa sổ cho tới khi đủ, tối
 *  đa [MAX_READ_AHEAD] đoạn. Chưa đủ số đo (< 2) hay clip về nhanh (cần ít hơn `base` đoạn) thì đúng `base` - hành vi cũ. */
export function readAheadCount(base: number, fetchSeconds: number[], aheadSeconds: number[]): number {
  if (fetchSeconds.length < 2) return base;
  const sorted = [...fetchSeconds].sort((a, b) => a - b);
  const p80 = sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.8) - 1)];
  const wanted = Math.min(MAX_BUFFER_SECONDS, Math.max(MIN_BUFFER_SECONDS, BUFFER_FACTOR * p80));
  const cap = Math.max(base, MAX_READ_AHEAD);
  let count = 0;
  let seconds = 0;
  while (count < cap && count < aheadSeconds.length && (count < base || seconds < wanted)) {
    seconds += aheadSeconds[count];
    count += 1;
  }
  return Math.max(base, count);
}

export class ReadAloudEngine implements AudioEngine {
  private slots: Slot[] = [];
  private base: Script | null = null;
  private speech: SpeechTrack | null = null;
  private handlers: Handlers = new Map();
  private target: Target = { index: 0, offset: 0 };
  private wanted = false;
  private finished = false;
  private ready = false;
  private loadId = 0;
  /** Lượt xin clip đang chờ tới lượt gửi (đoạn gần chỗ nghe nhất đi trước) và số lượt đang chạy ([pump]). */
  private queued: { index: number; epoch: number }[] = [];
  private inflight = 0;
  private lastJumpAt = 0;
  private holdUntil = 0;
  private lastClipMs = 0;
  private sentAt = 0;
  /** Giây lấy clip THẬT của vài clip gần nhất (cả lượt hỏng): số đo cho độ sâu đọc trước ([depth]). */
  private fetchSeconds: number[] = [];
  /** Lượt gọi đang chạy -> lúc gửi (ms): tuổi của chúng là số đo chặn dưới ([depth]). */
  private pending = new Map<number, number>();
  private watch: ReturnType<typeof setInterval> | null = null;
  private holdTimer: ReturnType<typeof setTimeout> | null = null;
  /** Đã xin trước clip đầu của chương kế (một lần cho mỗi lần nạp chương). */
  private warmedNext = false;
  private rate = 1;
  private volume = 1;
  private loadingTime = 0;
  private lastError = "";
  private readonly createAudio: (url: string) => AudioLike;
  private readonly muted: boolean;
  private readonly readAhead: number;
  private silenceTimer: ReturnType<typeof setInterval> | null = null;
  private silenceAt = 0;
  private onVoice = () => this.voiceChanged();
  private onReadings = (event: Event) => this.readingsChanged((event as CustomEvent<ReadingsChanged>).detail);

  constructor(options: ReadAloudOptions = {}) {
    this.createAudio = options.createAudio ?? realAudio;
    this.muted = options.muted ?? muteRequested();
    this.readAhead = options.readAhead ?? READ_AHEAD;
  }

  // ---- giao diện AudioEngine ------------------------------------------------------------------------------------

  load(track: TrackInfo, startAt: number, autoplay: boolean): void {
    this.dispose();
    const speech = track.speech;
    if (!speech) throw new Error("ReadAloudEngine cần track.speech");
    this.speech = speech;
    const id = ++this.loadId;
    this.wanted = autoplay;
    this.finished = false;
    this.ready = false;
    this.lastError = "";
    this.loadingTime = Math.max(0, startAt);
    this.warmedNext = false;
    if (typeof window !== "undefined") {
      window.addEventListener(VOICE_CHANGED_EVENT, this.onVoice);
      window.addEventListener(READINGS_CHANGED_EVENT, this.onReadings);
    }
    if (autoplay) {
      this.fire("play");
      this.fire("waiting");
    }
    void speech
      .script()
      .then((script) => {
        if (id === this.loadId) return this.init(script, startAt, id);
      })
      .catch((error) => {
        if (id === this.loadId) this.fail(error);
      });
  }

  play(): void {
    if (this.finished || (!this.ready && this.wanted)) return;
    const was = this.wanted;
    this.wanted = true;
    this.lastError = "";
    if (!was) this.fire("play");
    if (!this.ready) {
      this.fire("waiting");
      return;
    }
    this.playCurrent();
  }

  pause(): void {
    if (!this.wanted) return;
    this.wanted = false;
    this.stopSilence();
    this.slots[this.target.index]?.audio?.pause();
    this.fire("pause");
  }

  seek(seconds: number): void {
    if (!this.ready) {
      this.loadingTime = Math.max(0, seconds);
      return;
    }
    const total = this.duration;
    if (total <= 0) return;
    const time = Math.max(0, Math.min(total - 0.01, seconds));
    const index = this.indexAt(time);
    const slot = this.slots[index];
    const inside = time - slot.start;
    // Đoạn đã có clip: vào đúng chỗ trong clip. Chưa có: theo tỉ lệ độ dài ước, chỉnh lại khi clip về.
    if (slot.clip) this.moveTo({ index, offset: Math.max(0, Math.min(slot.duration - 0.01, inside)) });
    else this.moveTo({ index, offset: 0, fraction: slot.duration > 0 ? Math.max(0, Math.min(1, inside / slot.duration)) : 0 });
  }

  /** Bấm vào chữ thứ `word` của đoạn `segment`: nghe từ đúng chữ ấy. Đoạn đã có mốc thì nhảy ngay vào clip; chưa có thì đợi đọc xong đoạn
   *  ấy rồi bắt đầu ở mốc của chữ. */
  seekWord(segment: number, word: number): void {
    if (!this.ready) {
      this.pendingWord = { segment, word };
      return;
    }
    const index = Math.max(0, Math.min(this.slots.length - 1, segment));
    const slot = this.slots[index];
    if (!slot) return;
    const span = slot.words?.[word];
    if (slot.clip && span) this.moveTo({ index, offset: Math.min(span[0] / 1000, Math.max(0, slot.duration - 0.01)) });
    else this.moveTo({ index, offset: 0, word });
  }

  private pendingWord: { segment: number; word: number } | null = null;

  setRate(rate: number): void {
    this.rate = rate;
    for (const slot of this.slots) if (slot.audio) slot.audio.playbackRate = rate;
  }

  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    for (const slot of this.slots) this.applyVolume(slot);
  }

  stop(): void {
    this.dispose();
    this.wanted = false;
  }

  get time(): number {
    if (!this.ready) return this.loadingTime;
    const slot = this.slots[this.target.index];
    if (!slot) return 0;
    const pending = this.target.fraction !== undefined ? this.target.fraction * slot.duration : this.target.offset;
    const inside = slot.started && slot.audio ? slot.audio.currentTime : pending;
    return slot.start + Math.min(inside, Math.max(slot.duration, 0));
  }

  get duration(): number {
    const last = this.slots[this.slots.length - 1];
    return last ? last.start + last.duration : 0;
  }

  get paused(): boolean {
    return !this.wanted;
  }

  get ended(): boolean {
    return this.finished;
  }

  get error(): string {
    return this.lastError;
  }

  on(event: EngineEvent, handler: () => void): () => void {
    let set = this.handlers.get(event);
    if (!set) this.handlers.set(event, (set = new Set()));
    set.add(handler);
    return () => set.delete(handler);
  }

  // ---- khởi tạo -------------------------------------------------------------------------------------------------

  private async init(script: Script, startAt: number, id: number): Promise<void> {
    this.base = script;
    const gaps = sceneBreakGaps(script.segments);
    this.slots = script.segments.map((segment, i) => this.slotFrom(segment, gaps[i] / 1000));
    this.layout();
    if (startAt > 1) await this.restore(startAt, id);
    if (id !== this.loadId) return;
    const index = this.indexAt(startAt);
    const slot = this.slots[index];
    this.target = { index, offset: slot ? Math.max(0, Math.min(slot.duration, startAt - slot.start)) : 0 };
    if (slot && !slot.clip && startAt > slot.start && slot.duration > 0) {
      this.target.offset = 0;
      this.target.fraction = (startAt - slot.start) / slot.duration;
    }
    this.ready = true;
    const word = this.pendingWord;
    this.pendingWord = null;
    this.publish();
    this.fire("duration");
    this.fire("time");
    if (word) this.seekWord(word.segment, word.word);
    if (this.wanted) this.playCurrent();
  }

  private slotFrom(segment: ScriptSegment, silence: number): Slot {
    const speakable = isSpeakable(segment.text);
    const estimate = speakable ? estimateSeconds(segment.text) : silence;
    // Kịch bản đã có mốc (lần nghe trước ghi vào bộ nhớ): giữ độ dài và mốc chữ đã biết để đồng hồ nhất quán với `start` màn đọc đang dùng.
    const known = segment.start !== null && segment.end !== null && segment.end > segment.start && usableWords(segment.text, segment.words);
    const words = known && segment.words ? segment.words.map(([a, b]) => [a - segment.start! * 1000, b - segment.start! * 1000] as WordSpan) : null;
    return {
      text: segment.text,
      speakable,
      silence,
      estimate,
      duration: speakable && known ? segment.end! - segment.start! : estimate,
      start: 0,
      clip: null,
      words,
      audio: null,
      detach: null,
      started: false,
      fetching: false,
      failures: 0,
      epoch: 0,
      stale: false,
    };
  }

  /** Đồng hồ ảo đã biết một số đoạn từ bộ đệm: đưa chúng vào trước khi tìm chỗ nghe dở, để giây đã lưu rơi đúng câu. Chỉ tra bộ đệm. */
  private async restore(startAt: number, id: number): Promise<void> {
    const speech = this.speech;
    if (!speech) return;
    let done = 0;
    for (let round = 0; round < 4; round += 1) {
      const upTo = Math.min(this.indexAt(startAt), RESTORE_LIMIT);
      if (upTo < done) break;
      const wanted: number[] = [];
      for (let i = done; i <= upTo; i += 1) if (this.slots[i].speakable && !this.slots[i].clip) wanted.push(i);
      done = upTo + 1;
      if (!wanted.length) continue;
      const voice = speech.voice();
      for (let at = 0; at < wanted.length; at += 6) {
        await Promise.all(
          wanted.slice(at, at + 6).map((i) =>
            speech
              .fetchClip(voice, this.slots[i].text, { cachedOnly: true })
              .then((clip) => {
                if (id === this.loadId) this.adopt(i, clip);
              })
              .catch(() => undefined),
          ),
        );
        if (id !== this.loadId) return;
      }
      this.layout();
    }
  }

  // ---- đồng hồ ảo -----------------------------------------------------------------------------------------------

  private layout(): void {
    let at = 0;
    for (const slot of this.slots) {
      slot.start = at;
      at += slot.duration;
    }
  }

  /** Đoạn chứa giây `time`: đoạn cuối cùng bắt đầu không sau `time`, bỏ qua đoạn rỗng (không có chữ). */
  private indexAt(time: number): number {
    let low = 0;
    let high = this.slots.length - 1;
    let found = 0;
    while (low <= high) {
      const middle = (low + high) >> 1;
      if (this.slots[middle].start <= time + 1e-9) {
        found = middle;
        low = middle + 1;
      } else {
        high = middle - 1;
      }
    }
    while (found > 0 && this.slots[found].duration <= 0) found -= 1;
    return found;
  }

  private adopt(index: number, clip: ReadAloudClip): void {
    const slot = this.slots[index];
    if (!slot) return;
    slot.clip = clip;
    slot.words = clip.words;
    slot.duration = clip.durationMs / 1000;
  }

  /** Dựng kịch bản có mốc thời gian từ đồng hồ ảo và đưa cho trình phát (màn đọc đọc kịch bản này). */
  private publish(): void {
    if (!this.base || !this.speech) return;
    const segments = this.base.segments.map((segment, i): ScriptSegment => {
      const slot = this.slots[i];
      const origin = slot.start * 1000;
      return {
        ...segment,
        start: slot.start,
        end: slot.start + slot.duration,
        words: slot.words ? slot.words.map(([a, b]) => [Math.round(origin + a), Math.round(origin + b)] as WordSpan) : undefined,
      };
    });
    this.speech.onScript({ ...this.base, timed: true, duration: this.duration, segments });
  }

  // ---- phát -----------------------------------------------------------------------------------------------------

  private moveTo(target: Target): void {
    this.stopSilence();
    const now = Date.now();
    const slow = Math.max(this.lastClipMs, this.inflight > 0 ? now - this.sentAt : 0) >= SLOW_CLIP_MS;
    this.holdUntil = slow && this.speech?.serial?.() && now - this.lastJumpAt < JUMP_BURST_MS ? now + JUMP_SETTLE_MS : 0;
    this.lastJumpAt = now;
    const current = this.slots[this.target.index];
    current?.audio?.pause();
    this.finished = false;
    this.target = target;
    const slot = this.slots[target.index];
    if (slot) slot.started = false;
    this.releaseOutside();
    this.dropQueuedOutside();
    this.fire("time");
    if (this.wanted) this.playCurrent();
  }

  private playCurrent(): void {
    const speech = this.speech;
    if (!speech || !this.ready) return;
    const index = this.target.index;
    const slot = this.slots[index];
    if (!slot) return;
    if (!slot.speakable) {
      if (slot.silence > 0) {
        // Dòng ngăn cảnh: không có clip, chỉ lặng; clip của các đoạn sau vẫn được đọc trước trong lúc lặng.
        this.prefetch(index);
        this.startSilence(slot);
      } else {
        this.advance();
      }
      return;
    }
    if (slot.stale && !slot.started) this.dropClip(slot); // cách đọc đổi lúc đoạn này đang nói: nghe lại thì lấy clip mới
    this.prefetch(index);
    if (!slot.clip) {
      this.fire("waiting");
      return;
    }
    const audio = this.audioFor(index);
    if (!audio) return;
    const at = this.target.offset;
    if (!slot.started) audio.currentTime = at;
    slot.started = true;
    audio.playbackRate = this.rate;
    this.applyVolume(slot);
    void audio.play().then(
      () => undefined,
      () => {
        // Trình duyệt chặn phát tự động: coi như tạm dừng, người nghe bấm phát là được.
        if (this.wanted && index === this.target.index) {
          this.wanted = false;
          this.fire("pause");
        }
      },
    );
  }

  /** Lặng ở dòng ngăn cảnh: không có phần tử audio nên một bộ hẹn giờ đẩy `target.offset` đi theo tốc độ nghe (lặng cũng nhanh lên khi nghe nhanh,
   *  như mọi đoạn khác), tới hết quãng thì sang đoạn kế. Tạm dừng / tua dừng nó ([stopSilence]) và giữ nguyên chỗ đã tới. */
  private startSilence(slot: Slot): void {
    this.stopSilence();
    const target = this.target;
    if (target.fraction !== undefined) {
      target.offset = target.fraction * slot.duration;
      target.fraction = undefined;
    }
    target.word = undefined;
    slot.started = true;
    this.silenceAt = Date.now();
    this.silenceTimer = setInterval(() => this.silenceTick(slot), SILENCE_TICK_MS);
    this.fire("playing");
  }

  private silenceTick(slot: Slot): void {
    if (this.slots[this.target.index] !== slot || !this.wanted) {
      this.stopSilence(false);
      return;
    }
    this.target.offset = Math.min(slot.duration, this.target.offset + this.silenceElapsed());
    if (this.target.offset + 1e-6 < slot.duration) {
      this.fire("time");
      return;
    }
    this.stopSilence(false);
    this.advance();
  }

  /** Giây nghe đã trôi từ lần đồng hồ lặng đo trước. */
  private silenceElapsed(): number {
    const now = Date.now();
    const seconds = ((now - this.silenceAt) / 1000) * this.rate;
    this.silenceAt = now;
    return seconds;
  }

  /** Dừng đồng hồ lặng; `settle`: ghi nốt phần đã trôi vào `target.offset` (tạm dừng giữa chừng). */
  private stopSilence(settle = true): void {
    if (this.silenceTimer === null) return;
    clearInterval(this.silenceTimer);
    this.silenceTimer = null;
    const slot = this.slots[this.target.index];
    if (settle && slot) this.target.offset = Math.min(slot.duration, this.target.offset + this.silenceElapsed());
  }

  /** Lấy clip cho đoạn `index` và vài đoạn kế (đọc trước). `fresh`: bỏ qua đoạn đã hỏng lần nào (cửa sổ dài ra khi clip về chậm, không được dồn lại đoạn đang chờ nghỉ / đã hết lần thử). */
  private prefetch(index: number, fresh = false): void {
    const last = index + this.depth(index);
    for (let i = index; i <= last && i < this.slots.length; i += 1) {
      if (fresh && this.slots[i].failures > 0) continue;
      this.request(i);
    }
    this.warmNext();
  }

  /** Số đoạn đang đọc trước sau đoạn đang nghe (xem [readAheadCount]); thấy được để bài thử kiểm. */
  get lookahead(): number {
    return this.depth(this.target.index);
  }

  private depth(index: number): number {
    if (this.speech?.serial?.()) return this.readAhead;
    const now = Date.now();
    const stalled = [...this.pending.values()].map((at) => (now - at) / 1000).filter((age) => age >= STALL_SECONDS);
    return readAheadCount(this.readAhead, [...this.fetchSeconds, ...stalled], this.slots.slice(index + 1, index + 1 + MAX_READ_AHEAD).map((slot) => slot.duration));
  }

  private noteFetch(milliseconds: number): void {
    if (milliseconds / 1000 < REAL_FETCH_SECONDS) return;
    this.fetchSeconds.push(milliseconds / 1000);
    if (this.fetchSeconds.length > FETCH_SAMPLES) this.fetchSeconds.shift();
  }

  /** Cửa sổ đọc trước đã chạm cuối chương và mọi clip của chương này đã xin xong: xin trước vài clip đầu của chương kế ([SpeechTrack.after]). Máy chủ nhớ clip theo
   *  (giọng, chữ) nên bộ máy của chương kế nạp lên là có sẵn - tiêu đề và đoạn đầu không còn bắt người nghe chờ. Giọng chạy trên máy cũng lần lượt, không giành
   *  CPU với clip của chương đang nghe (đã xong hết lúc này). Lỗi thì bỏ qua: chương kế sẽ tự xin lại khi nạp. */
  private warmNext(): void {
    const speech = this.speech;
    if (this.warmedNext || !speech?.after || !this.ready || !this.wanted) return;
    if (this.target.index + this.depth(this.target.index) < this.slots.length - 1 || this.inflight > 0 || this.queued.length > 0) return;
    this.warmedNext = true;
    const id = this.loadId;
    void speech
      .after()
      .then(async (texts) => {
        if (id !== this.loadId) return;
        const wanted = texts.filter(isSpeakable).slice(0, NEXT_CHAPTER_AHEAD);
        const voice = speech.voice();
        if (speech.serial?.()) for (const text of wanted) await speech.fetchClip(voice, text);
        else await Promise.all(wanted.map((text) => speech.fetchClip(voice, text)));
      })
      .catch(() => undefined);
  }

  private request(index: number): void {
    const speech = this.speech;
    const slot = this.slots[index];
    if (!speech || !slot || !slot.speakable) return;
    if (slot.clip) {
      this.audioFor(index);
      return;
    }
    if (slot.fetching) return;
    slot.fetching = true;
    this.queued.push({ index, epoch: slot.epoch });
    this.pump();
  }

  /** Gửi các lượt xin đang chờ, tối đa [SpeechTrack.parallel] lượt cùng lúc; mỗi lần chọn đoạn gần chỗ đang nghe nhất (đoạn đang chờ trước, rồi các đoạn sau). */
  private pump(): void {
    const speech = this.speech;
    if (!speech) return;
    const limit = speech.serial?.() ? 1 : this.readAhead + 1;
    const hold = this.holdUntil - Date.now();
    if (hold > 0 && this.inflight < limit) {
      this.holdTimer ??= setTimeout(() => {
        this.holdTimer = null;
        this.pump();
      }, hold);
      return;
    }
    while (this.inflight < limit) {
      const next = this.takeQueued();
      if (next === null) return;
      this.send(next);
    }
  }

  private takeQueued(): number | null {
    const target = this.target.index;
    const rank = (index: number) => (index >= target ? index - target : this.slots.length + target - index);
    let best = -1;
    for (let i = this.queued.length - 1; i >= 0; i -= 1) {
      const { index, epoch } = this.queued[i];
      const slot = this.slots[index];
      if (!slot || !slot.fetching || slot.clip || slot.epoch !== epoch) {
        this.queued.splice(i, 1); // đã có clip, hay cách đọc / giọng đổi sau khi xếp hàng
        if (best > i) best -= 1;
        continue;
      }
      if (best < 0 || rank(index) < rank(this.queued[best].index)) best = i;
    }
    return best < 0 ? null : this.queued.splice(best, 1)[0].index;
  }

  /** Nhảy tới chỗ khác: lượt xin chưa gửi của các đoạn ngoài cửa sổ mới bỏ (đoạn đã gửi thì máy chủ làm nốt, clip về vẫn dùng được); lượt của đoạn
   *  vừa nhảy tới nhờ vậy được gửi trước, không chờ cả cửa sổ cũ. */
  private dropQueuedOutside(): void {
    const low = this.target.index;
    const high = this.target.index + this.depth(this.target.index);
    this.queued = this.queued.filter(({ index, epoch }) => {
      const slot = this.slots[index];
      if (!slot) return false;
      if (index >= low && index <= high) return true;
      if (slot.epoch === epoch) slot.fetching = false;
      return false;
    });
  }

  private send(index: number): void {
    const speech = this.speech;
    const slot = this.slots[index];
    if (!speech || !slot) return;
    const id = this.loadId;
    const epoch = slot.epoch;
    this.inflight += 1;
    const sentAt = Date.now();
    this.sentAt = sentAt;
    this.pending.set(index, sentAt);
    this.watching();
    speech
      .fetchClip(speech.voice(), slot.text, { willRetry: slot.failures < CLIP_RETRIES })
      .then((clip) => {
        this.lastClipMs = Date.now() - sentAt;
        if (id !== this.loadId) return;
        this.noteFetch(this.lastClipMs);
        // Cách đọc đổi trong lúc đoạn này đang được đọc: clip này theo cách đọc cũ - bỏ (lượt hỏi mới đã được xếp bởi [readingsChanged]).
        if (epoch !== slot.epoch) return;
        slot.fetching = false;
        slot.failures = 0;
        this.onClip(index, clip);
      })
      .catch((error) => {
        if (id !== this.loadId || epoch !== slot.epoch) return;
        // Lượt hỏng mà phải chờ lâu thì nói lên tốc độ của giọng; lượt hỏng ngay (502 tức thì) thì không.
        if (Date.now() - sentAt >= SLOW_FAILURE_SECONDS * 1000) this.noteFetch(Date.now() - sentAt);
        slot.fetching = false;
        slot.failures += 1;
        // Lỗi thoáng qua (Edge cắt lượt / bận / chậm): thử lại sau một quãng nghỉ lùi dần, ở nền - các clip đã đọc sẵn vẫn phát, người nghe chỉ phải dừng nếu tới đoạn này mà
        // hết lần thử. Lỗi khác (mất mạng, bị từ chối, giọng / khoá hỏng...) thử lại cũng vô ích: đoạn người nghe đang chờ thì dừng ngay và báo.
        if (isTransientClipError(error) && slot.failures <= CLIP_RETRIES) {
          this.retryLater(index, epoch, id);
          return;
        }
        if (index !== this.target.index || !this.wanted) return;
        this.fail(error);
      })
      .finally(() => {
        if (id !== this.loadId) return;
        if (this.pending.get(index) === sentAt) this.pending.delete(index);
        this.inflight -= 1;
        this.pump();
        // Số đo mới có thể làm cửa sổ đọc trước dài ra (hay co lại); cũng là chỗ xin trước chương kế khi cửa sổ chạm cuối chương.
        if (this.ready && this.wanted) this.prefetch(this.target.index, true);
        else this.warmNext();
      });
  }

  /** Trong lúc còn lượt gọi chưa về, mỗi [WATCH_MS] xét lại cửa sổ đọc trước: tuổi của lượt gọi đang chờ có thể làm nó dài ra trước khi clip chậm về. */
  private watching(): void {
    if (this.watch !== null) return;
    const id = this.loadId;
    this.watch = setInterval(() => {
      if (id !== this.loadId || this.pending.size === 0) {
        if (this.watch !== null) clearInterval(this.watch);
        this.watch = null;
        return;
      }
      if (this.ready && this.wanted) this.prefetch(this.target.index, true);
    }, WATCH_MS);
  }

  /** Xếp lại đoạn `index` sau quãng nghỉ của lần hỏng thứ `slot.failures`. Trong lúc nghỉ đoạn vẫn "đang lấy" (không ai xếp thêm lượt); hết nghỉ mà người nghe đã đi xa hay
   *  đang tạm dừng thì bỏ - lần phát / đọc trước kế tiếp sẽ xin lại. */
  private retryLater(index: number, epoch: number, id: number): void {
    const slot = this.slots[index];
    slot.fetching = true;
    setTimeout(() => {
      if (id !== this.loadId || slot.epoch !== epoch || slot.clip) return;
      const target = this.target.index;
      if (!this.wanted || index < target || index > target + this.depth(target)) {
        slot.fetching = false;
        return;
      }
      this.queued.push({ index, epoch });
      this.pump();
    }, CLIP_RETRY_DELAYS_MS[Math.min(slot.failures, CLIP_RETRY_DELAYS_MS.length) - 1]);
  }

  private onClip(index: number, clip: ReadAloudClip): void {
    const was = this.slots[index].duration;
    this.adopt(index, clip);
    this.layout();
    const waiting = index === this.target.index;
    if (waiting) this.resolveTarget(clip);
    if (index >= this.target.index - 1 && index <= this.target.index + this.depth(this.target.index)) this.audioFor(index);
    this.publish();
    if (Math.abs(was - this.slots[index].duration) > 1e-6) this.fire("duration");
    if (waiting && this.wanted) this.playCurrent();
    else if (waiting) this.fire("time");
  }

  /** Clip của đoạn đang chờ vừa về: đổi chỗ chờ (tỉ lệ / chữ) thành giây thật trong clip. */
  private resolveTarget(clip: ReadAloudClip): void {
    const target = this.target;
    if (target.word !== undefined) {
      const span = clip.words[target.word];
      target.offset = span ? Math.min(span[0] / 1000, Math.max(0, clip.durationMs / 1000 - 0.01)) : 0;
      target.word = undefined;
    } else if (target.fraction !== undefined) {
      target.offset = target.fraction * (clip.durationMs / 1000);
      target.fraction = undefined;
    }
  }

  private audioFor(index: number): AudioLike | null {
    const slot = this.slots[index];
    if (!slot?.clip) return null;
    if (slot.audio) return slot.audio;
    const audio = this.createAudio(slot.clip.url);
    audio.preload = "auto";
    audio.muted = this.muted;
    audio.playbackRate = this.rate;
    const ended = () => this.audioEnded(index);
    const tick = () => {
      if (index === this.target.index) this.fire("time");
    };
    const playing = () => {
      if (index === this.target.index) this.fire("playing");
    };
    const waiting = () => {
      if (index === this.target.index && this.wanted) this.fire("waiting");
    };
    const broken = () => {
      if (index === this.target.index && this.wanted) this.fail(new ReadAloudError("Không phát được clip giọng đọc.", "service"));
    };
    audio.addEventListener("ended", ended);
    audio.addEventListener("timeupdate", tick);
    audio.addEventListener("playing", playing);
    audio.addEventListener("waiting", waiting);
    audio.addEventListener("error", broken);
    slot.detach = () => {
      audio.removeEventListener("ended", ended);
      audio.removeEventListener("timeupdate", tick);
      audio.removeEventListener("playing", playing);
      audio.removeEventListener("waiting", waiting);
      audio.removeEventListener("error", broken);
    };
    slot.audio = audio;
    this.applyVolume(slot);
    return audio;
  }

  private applyVolume(slot: Slot): void {
    if (!slot.audio) return;
    const gain = Math.pow(10, Math.min(0, slot.clip?.gainDb ?? 0) / 20);
    slot.audio.volume = Math.max(0, Math.min(1, this.volume * gain));
  }

  private audioEnded(index: number): void {
    if (index !== this.target.index || !this.wanted) return;
    this.advance();
  }

  private advance(): void {
    const next = this.target.index + 1;
    const slot = this.slots[this.target.index];
    if (slot) slot.started = false;
    if (next >= this.slots.length) {
      this.wanted = false;
      this.finished = true;
      this.target = { index: this.slots.length - 1, offset: this.slots[this.slots.length - 1]?.duration ?? 0 };
      this.fire("time");
      this.fire("pause");
      this.fire("ended");
      return;
    }
    this.target = { index: next, offset: 0 };
    this.releaseOutside();
    this.dropQueuedOutside();
    this.fire("time");
    this.playCurrent();
  }

  /** Giữ phần tử audio của đoạn trước, hiện tại và vài đoạn sau; thả phần còn lại (tránh giữ hàng trăm file đã nạp). */
  private releaseOutside(): void {
    const low = this.target.index - 1;
    const high = this.target.index + this.depth(this.target.index);
    this.slots.forEach((slot, i) => {
      if (i >= low && i <= high) return;
      this.releaseSlot(slot);
    });
  }

  private releaseSlot(slot: Slot): void {
    if (!slot.audio) return;
    slot.detach?.();
    slot.audio.pause();
    slot.audio.removeAttribute("src");
    slot.audio.load();
    slot.audio = null;
    slot.detach = null;
    slot.started = false;
  }

  /** Bỏ clip của đoạn (thả audio, độ dài về ước tính) để lần sau lấy lại. */
  private dropClip(slot: Slot): void {
    this.releaseSlot(slot);
    slot.clip = null;
    slot.words = null;
    slot.duration = slot.estimate;
    slot.stale = false;
    slot.epoch += 1;
  }

  /** Cách đọc riêng của cuốn vừa đổi: mọi đoạn có từ ấy mà đã đọc sẵn bỏ clip để lần phát sau hỏi máy chủ lại (khoá bộ đệm của máy chủ đã gồm cách đọc). Đoạn đang
   *  nói nói nốt; nghe lại đoạn ấy thì lấy clip mới ([playCurrent]). */
  private readingsChanged(detail: ReadingsChanged | undefined): void {
    // `bookId` rỗng + `all`: bản đọc của cả máy vừa được dọn - cuốn nào đang mở cũng phải lấy lại clip.
    if (!this.ready || !this.speech || !detail || (detail.bookId ? this.speech.bookId !== detail.bookId : !detail.all)) return;
    const surfaces = detail.surfaces.map((surface) => surface.normalize("NFC")).filter(Boolean);
    let changed = false;
    this.slots.forEach((slot, i) => {
      if (!slot.speakable || (!slot.clip && !slot.fetching) || !(detail.all || surfaces.some((surface) => slot.text.normalize("NFC").includes(surface)))) return;
      if (i === this.target.index && slot.clip) {
        slot.stale = true;
        return;
      }
      this.dropClip(slot);
      slot.fetching = false;
      changed = true;
    });
    if (!changed) return;
    this.layout();
    this.publish();
    this.fire("duration");
    if (this.wanted) this.prefetch(this.target.index);
  }

  private voiceChanged(): void {
    if (!this.ready) return;
    // Đoạn đang đọc nói nốt bằng giọng cũ; từ đoạn sau lấy lại clip bằng giọng mới (độ dài về ước tính cho tới khi clip mới về). Đoạn hiện tại chưa có clip
    // (giọng cũ hỏng, đang dừng chờ "Thử lại") cũng lấy lại bằng giọng mới - không thì "Thử lại" lại hỏi giọng cũ và báo lỗi cũ.
    const current = this.slots[this.target.index];
    const start = current && !current.clip ? this.target.index : this.target.index + 1;
    for (let i = start; i < this.slots.length; i += 1) {
      const slot = this.slots[i];
      this.releaseSlot(slot);
      slot.clip = null;
      slot.words = null;
      slot.duration = slot.estimate;
    }
    this.layout();
    this.publish();
    this.fire("duration");
    if (this.wanted) this.prefetch(this.target.index);
  }

  private fail(error: unknown): void {
    this.lastError = error instanceof Error && error.message ? error.message : "Giọng đọc không phản hồi.";
    const was = this.wanted;
    this.wanted = false;
    const slot = this.slots[this.target.index];
    this.stopSilence();
    // Người nghe bấm phát lại thì được thử lại từ đầu.
    if (slot) slot.failures = 0;
    slot?.audio?.pause();
    if (was) this.fire("pause");
    this.fire("error");
  }

  private dispose(): void {
    this.stopSilence(false);
    this.loadId += 1;
    this.queued = [];
    this.inflight = 0;
    if (this.holdTimer !== null) clearTimeout(this.holdTimer);
    this.holdTimer = null;
    this.holdUntil = 0;
    this.lastClipMs = 0;
    this.fetchSeconds = [];
    this.pending.clear();
    if (this.watch !== null) clearInterval(this.watch);
    this.watch = null;
    if (typeof window !== "undefined") {
      window.removeEventListener(VOICE_CHANGED_EVENT, this.onVoice);
      window.removeEventListener(READINGS_CHANGED_EVENT, this.onReadings);
    }
    for (const slot of this.slots) this.releaseSlot(slot);
    this.slots = [];
    this.base = null;
    this.speech = null;
    this.ready = false;
    this.finished = false;
    this.pendingWord = null;
    this.target = { index: 0, offset: 0 };
  }

  private fire(event: EngineEvent): void {
    this.handlers.get(event)?.forEach((handler) => handler());
  }
}

// ---- bộ chuyển giữa audio thường và đọc to ----------------------------------------------------------------------------

const EVENTS: EngineEvent[] = ["time", "duration", "play", "pause", "ended", "error", "waiting", "playing"];

/** Bộ máy của trình phát trên máy tính: chương có audio đi qua `web` (WebAudioEngine), chương chỉ-có-chữ (`TrackInfo.speech`) đi qua một
 *  ReadAloudEngine mới cho mỗi lần nạp. Sự kiện chỉ lấy từ bộ máy đang chạy - bộ cũ dừng im lặng, trình phát không thấy "pause" giả. */
export class RoutedEngine implements AudioEngine {
  private active: AudioEngine;
  private speechEngine: ReadAloudEngine | null = null;
  private unsubscribe: (() => void)[] = [];
  private handlers: Handlers = new Map();
  private rate = 1;
  private volume = 1;

  constructor(
    private readonly web: AudioEngine,
    private readonly make: () => ReadAloudEngine = () => new ReadAloudEngine(),
  ) {
    this.active = web;
    for (const event of EVENTS) web.on(event, () => this.active === web && this.fire(event));
  }

  private fire(event: EngineEvent) {
    this.handlers.get(event)?.forEach((handler) => handler());
  }

  load(track: TrackInfo, startAt: number, autoplay: boolean): void {
    if (track.speech) {
      const previous = this.active;
      const next = this.make();
      this.drop();
      this.speechEngine = next;
      this.unsubscribe = EVENTS.map((event) => next.on(event, () => this.active === next && this.fire(event)));
      this.active = next;
      if (previous !== next) previous.stop();
      next.setRate(this.rate);
      next.setVolume(this.volume);
      next.load(track, startAt, autoplay);
      return;
    }
    if (this.active !== this.web) {
      this.drop();
      this.active = this.web;
    }
    this.web.load(track, startAt, autoplay);
  }

  private drop() {
    this.unsubscribe.forEach((off) => off());
    this.unsubscribe = [];
    this.speechEngine?.stop();
    this.speechEngine = null;
  }

  /** Bộ máy đọc to đang chạy (chương chỉ-có-chữ đang nạp)? */
  get speaking(): boolean {
    return this.active !== this.web;
  }

  seekWord(segment: number, word: number): void {
    this.speechEngine?.seekWord(segment, word);
  }

  play(): void {
    this.active.play();
  }
  pause(): void {
    this.active.pause();
  }
  seek(seconds: number): void {
    this.active.seek(seconds);
  }
  setRate(rate: number): void {
    this.rate = rate;
    this.web.setRate(rate);
    this.speechEngine?.setRate(rate);
  }
  setVolume(volume: number): void {
    this.volume = volume;
    this.web.setVolume(volume);
    this.speechEngine?.setVolume(volume);
  }
  stop(): void {
    this.active.stop();
  }
  get time(): number {
    return this.active.time;
  }
  get duration(): number {
    return this.active.duration;
  }
  get paused(): boolean {
    return this.active.paused;
  }
  get ended(): boolean {
    return this.active.ended;
  }
  get error(): string {
    return this.active.error ?? "";
  }
  on(event: EngineEvent, handler: () => void): () => void {
    let set = this.handlers.get(event);
    if (!set) this.handlers.set(event, (set = new Set()));
    set.add(handler);
    return () => set.delete(handler);
  }
}
