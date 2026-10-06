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
// Máy tính: đọc trước 3 đoạn (rẻ - clip chỉ vài chục KB; đoạn ngắn liên tiếp không còn bắt người nghe chờ). Điện thoại tự đọc trước (ReadAloud.AHEAD).
const READ_AHEAD = 3;
const RESTORE_LIMIT = 400;
/** Nhịp đồng hồ của quãng lặng ở dòng ngăn cảnh (ms). */
const SILENCE_TICK_MS = 100;

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

/** Đoạn đang chờ mà lấy clip hỏng: thử lại chừng này lần trước khi dừng. */
export const CLIP_RETRIES = 2;

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
    if (typeof window !== "undefined") window.addEventListener(VOICE_CHANGED_EVENT, this.onVoice);
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
    const current = this.slots[this.target.index];
    current?.audio?.pause();
    this.finished = false;
    this.target = target;
    const slot = this.slots[target.index];
    if (slot) slot.started = false;
    this.releaseOutside();
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

  /** Lấy clip cho đoạn `index` và vài đoạn kế (đọc trước). */
  private prefetch(index: number): void {
    for (let i = index; i <= index + this.readAhead && i < this.slots.length; i += 1) this.request(i);
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
    const id = this.loadId;
    speech
      .fetchClip(speech.voice(), slot.text)
      .then((clip) => {
        if (id !== this.loadId) return;
        slot.fetching = false;
        slot.failures = 0;
        this.onClip(index, clip);
      })
      .catch((error) => {
        if (id !== this.loadId) return;
        slot.fetching = false;
        slot.failures += 1;
        if (index !== this.target.index || !this.wanted) return;
        // Đoạn người nghe đang chờ: lỗi thoáng qua (Edge thỉnh thoảng trả 502) thì thử lại (1 s, 2 s) rồi mới dừng hẳn và báo
        // lỗi; mất mạng thì thử lại cũng vô ích - báo ngay.
        const offline = (error as { reason?: string } | null)?.reason === "offline";
        if (!offline && slot.failures <= CLIP_RETRIES) {
          setTimeout(() => {
            if (id === this.loadId && this.wanted && index === this.target.index) this.request(index);
          }, 1000 * slot.failures);
          return;
        }
        this.fail(error);
      });
  }

  private onClip(index: number, clip: ReadAloudClip): void {
    const was = this.slots[index].duration;
    this.adopt(index, clip);
    this.layout();
    const waiting = index === this.target.index;
    if (waiting) this.resolveTarget(clip);
    if (index >= this.target.index - 1 && index <= this.target.index + this.readAhead) this.audioFor(index);
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
    this.fire("time");
    this.playCurrent();
  }

  /** Giữ phần tử audio của đoạn trước, hiện tại và vài đoạn sau; thả phần còn lại (tránh giữ hàng trăm file đã nạp). */
  private releaseOutside(): void {
    const low = this.target.index - 1;
    const high = this.target.index + this.readAhead;
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

  private voiceChanged(): void {
    if (!this.ready) return;
    // Đoạn đang đọc nói nốt bằng giọng cũ; từ đoạn sau lấy lại clip bằng giọng mới (độ dài về ước tính cho tới khi clip mới về).
    for (let i = this.target.index + 1; i < this.slots.length; i += 1) {
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
    if (typeof window !== "undefined") window.removeEventListener(VOICE_CHANGED_EVENT, this.onVoice);
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
