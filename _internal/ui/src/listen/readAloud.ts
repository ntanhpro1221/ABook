import type { AudioEngine, EngineEvent, TrackInfo } from "./engine";
import type { Script, ScriptSegment } from "./model";
import { LiveClip } from "./liveClip";
import { LiveFeed, type MediaSourceLike } from "./liveFeed";
import { isSpeakable, sceneBreakGaps } from "./textScript";
import { absoluteWords, countTokens, usableWords, WORD_LEAD_MS, wordIndexAt, type WordSpan } from "./words";

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
  /** Chính file audio, đã tải xong ([fetchClipBytes]): phần tử audio phát từ blob: URL của nó, không tự đi tải `url` (trình duyệt xếp yêu cầu <audio> sau các lượt POST clip còn treo - soát a55: 4-5 giây trễ). */
  bytes?: Blob;
  /** Clip Edge đang được đọc, nhận dần từ máy chủ ([clipFromStream]): `url` / `durationMs` / `words` / `bytes` còn chưa có (độ dài 0, mốc rỗng) tới khi `live` báo xong - phần tử audio phát từ MediaSource
   *  nối các khúc đã về ([LiveFeed]); bộ máy giữ độ dài ước của đoạn tới khi xong. */
  live?: LiveClip;
  /** Clip đuôi (bấm giữa đoạn, [ClipOptions.tailFrom]): chỉ đọc từ chữ này (0-based, đếm `\S+`) tới hết đoạn; `words` / `durationMs` tính trên phần đuôi (chữ 0 của clip = chữ `fromWord` của đoạn). Vắng = clip đủ cả đoạn. */
  fromWord?: number;
  /** Clip do bộ máy tự ghép từ hai phần (clip đứt giữa chừng + clip đuôi xin tiếp, [ReadAloudEngine.salvage]): chỉ có trong `bytes`, không có `url` riêng - bỏ file thì bỏ cả clip. */
  joined?: boolean;
}

/** Tải file audio của clip bằng fetch (không đi qua phần tử <audio>); lỗi nào cũng là clip hỏng (`service`, đi đường thử lại như lúc máy chủ trả lỗi). */
export async function fetchClipBytes(url: string, get: (url: string) => Promise<Response> = (target) => fetch(target)): Promise<Blob> {
  try {
    const response = await get(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.blob();
  } catch {
    throw new ReadAloudError("Không tải được đoạn giọng đọc.", "service");
  }
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
  /** Quỹ thời gian thử lại ([CLIP_RETRY_BUDGET_MS]): từ mốc này (Date.now) lần thử lại sẽ không còn kịp - `willRetry` coi như tắt, bộ lấy clip rơi sang giọng kế ngay trong lần hỏng này. */
  retryBefore?: number;
  /** Lần hỏi MỚI cho đoạn mà các lần thử lại trước đã hết ([PROBE_MS], hay người nghe vừa tới đoạn ấy): bộ lấy clip quên lệnh "giọng vừa hỏng, nghỉ 5 phút" của giọng này và gọi dịch vụ thật - nếu không thì
   *  dịch vụ đã khoẻ lại mà lần hỏi mới vẫn bị chặn ngay, không một lượt gọi nào đi ra. */
  fresh?: boolean;
  /** Số đoạn người nghe phải nghe trước đoạn này: 0 = đang đứng chờ đúng nó (vừa nhảy tới / đầu chương), 1 = đoạn kế... Hết chỗ kết nối tới Edge thì máy chủ cho đoạn gần người nghe hơn đi trước
   *  (abook/readaloud/edge.py ConnectionSlots); vắng = việc nền. */
  rank?: number;
  /** Cần clip trọn vẹn (đủ file, đủ mốc) ngay lúc clip về, không phát dần: chỗ chờ theo tỉ lệ / theo chữ giữa đoạn chỉ đổi thành giây thật khi biết độ dài và mốc. Nguồn có phát luồng (httpSource)
   *  chỉ phát luồng khi `rank` 0 và không `whole`. */
  whole?: boolean;
  /** Người nghe vừa bấm vào chữ này (> 0) của đoạn chưa có clip: nguồn phát luồng được thì chỉ đọc từ chữ ấy tới hết đoạn và trả clip có `fromWord` (nghe sau ~2 giây thay vì chờ đọc cả đoạn). Nguồn không làm được
   *  (không phát luồng, bộ đệm đã có cả đoạn...) thì trả clip đủ cả đoạn như thường - bộ máy đổi chữ thành giây bằng mốc của clip. */
  tailFrom?: number;
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
/** Lỗi thuộc loại "dịch vụ đang trục trặc" (kể cả lời cuối `final` của bộ lấy clip sau khi hết lần thử): đoạn hỏng vì thế được hỏi lại ([PROBE_MS], và khi người nghe tới đoạn ấy). */
function isServiceTrouble(error: unknown): boolean {
  return TRANSIENT_REASONS.has((error as { reason?: string } | null)?.reason ?? "");
}
export function isTransientClipError(error: unknown): boolean {
  const found = error as { reason?: string; final?: boolean } | null;
  return !found?.final && TRANSIENT_REASONS.has(found?.reason ?? "");
}
/** Nghỉ trước mỗi lần thử lại một clip hỏng vì lỗi thoáng qua (ms): 1 + 2,5 + 4,5 + 7 = 15 giây, trong lúc ấy các clip đã đọc sẵn vẫn phát. */
export const CLIP_RETRY_DELAYS_MS = [1000, 2500, 4500, 7000];
/** Số lần thử lại một clip hỏng vì lỗi thoáng qua trước khi dừng (nếu người nghe đã tới đoạn ấy). */
export const CLIP_RETRIES = CLIP_RETRY_DELAYS_MS.length;
/** Trần tổng thời gian thử lại một clip, tính từ lần lấy đầu (mạng còn nối mà máy chủ Edge im lìm: mỗi lần chờ tin 25 giây - 5 lần thì cả phút; bản trước quỹ này là ~140 giây). Một lần thử lại chỉ bắt đầu
 *  nếu sau quãng nghỉ của nó còn ít nhất `CLIP_MIN_ATTEMPT_MS`; hết quỹ thì rơi sang giọng kế / báo lỗi ngay. Lần lấy đầu không bị cắt. Cùng quỹ với điện thoại (ClipBudget ở ClipRetry.kt). */
export const CLIP_RETRY_BUDGET_MS = 20_000;
export const CLIP_MIN_ATTEMPT_MS = 4_000;
/** Đoạn đã hết lần thử lại vì dịch vụ trục trặc mà vẫn nằm trong cửa sổ đọc trước: cứ chừng này ms hỏi lại MỘT lần (một lượt gọi, không thử lại, đoạn gần người nghe nhất) cho tới khi được -
 *  mạng khoẻ lại thì đoạn đã sẵn sàng trước khi người nghe tới, mà cả lúc mất mạng dài cũng chỉ ~6 lượt gọi mỗi phút (a46: 74 giây mất mạng = 13 lượt gọi trước khi bỏ cuộc; sau đó thêm tối đa 1 lượt mỗi 10 giây). */
export const PROBE_MS = 10_000;
/** Mốc (Date.now) sau đó lần thử lại thứ `failed + 1` không còn kịp, cho clip bắt đầu lấy lúc `began`. */
export function clipRetryBefore(began: number, failed: number): number {
  return began + CLIP_RETRY_BUDGET_MS - CLIP_MIN_ATTEMPT_MS - CLIP_RETRY_DELAYS_MS[Math.min(failed, CLIP_RETRY_DELAYS_MS.length - 1)];
}
// Máy tính: đọc trước tối thiểu 3 đoạn (rẻ - clip chỉ vài chục KB; đoạn ngắn liên tiếp không còn bắt người nghe chờ). Điện thoại tự đọc trước (ReadAloud.kt).
const READ_AHEAD = 3;
/** Số đoạn vừa nghe còn giữ file (bytes) trong bộ nhớ để nghe lại ngay ([ReadAloudEngine.releaseOutside]): nhỏ, vì mỗi clip vài trăm KB. */
export const KEEP_BEHIND = 2;
/** Giọng trực tuyến chậm từng lúc (soát a45: Edge có lúc 9-24 s một đoạn, giọng im 9 giây giữa chương): chỉ đọc sẵn 3 đoạn thì đoạn ngắn (đối thoại) chỉ đủ vài giây. Nên đọc sẵn đủ SỐ GIÂY
 *  ÂM THANH: tối thiểu `MIN_BUFFER_SECONDS`, và khi mấy clip gần đây về chậm thì `BUFFER_FACTOR` lần thời gian lấy clip ở phân vị 80 - để một quãng chậm không tới tai người nghe. Mô phỏng
 *  (Edge nhanh 1-3 s xen quãng chậm 9-24 s, 12 lượt x 10 phút): số lần im > 2 giây từ 17 xuống 0. Trần: `MAX_READ_AHEAD` đoạn (mỗi đoạn là một lượt gọi Edge, đoạn nào người nghe bỏ đi là uổng) và
 *  `MAX_BUFFER_SECONDS`. Số lượt gọi CÙNG LÚC không tăng theo (vẫn đọc trước + 1 như trước đây: Edge hạn chế khi dồn nhiều kết nối) - chỉ hàng đợi dài ra. Chương đã nằm trong bộ đệm (lấy về
 *  trong vài chục ms, không tính là số đo) và giọng chạy trên máy ([SpeechTrack.serial]) không đổi gì. */
const MAX_READ_AHEAD = 8;
/** Rank lớn nhất của việc xin trước chương kế: máy chủ nhận 0-98 (99 trở lên là việc nền), nên đoạn xa mấy cũng vẫn đứng trước "Làm trước" / xuất sách nói. */
export const MAX_WARM_RANK = 98;

/** Đoạn từ chừng này ký tự mới là đoạn "dài": đủ lâu để người nghe kịp chờ clip kế trong lúc nghe nó (máy chủ cũng chỉ cắt đoạn từ chừng này, edge.py WHOLE_CHARS; điện thoại EdgePieces.WHOLE_CHARS).
 *  Đoạn ngắn đứng trước (tiêu đề chương, một dòng đối thoại) không tính vào rank của đoạn sau nó (a56: đoạn 1 sau tiêu đề 2 giây phải chờ ~4 giây nữa vì rank 1 chỉ cắt 3 mảnh). */
export const WHOLE_CHARS = 100;

export function isLongParagraph(text: string): boolean {
  return text.length >= WHOLE_CHARS;
}

/** Rank của đoạn thứ `position` (0 = tiêu đề) của chương kế: `behind` = số đoạn DÀI của chương này từ chỗ người nghe tới hết chương (đoạn họ đang nghe tính nếu dài), rồi số đoạn dài của chương kế đứng
 *  trước nó, tối đa [MAX_WARM_RANK]; tối thiểu 1 (rank 0 là đoạn người nghe đang đứng chờ). Điện thoại cùng luật (StalledClips.listenerRank: số đoạn dài từ đoạn đang phát). */
export function warmRankOf(behind: number, position: number): number {
  return Math.min(MAX_WARM_RANK, Math.max(1, behind + position));
}
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
  /** blob: URL đang đặt cho `audio` (từ `clip.bytes`): thu hồi khi thả audio. */
  objectUrl: string | null;
  /** Clip đang về: bộ nối khúc vào MediaSource của `audio` ([LiveFeed]); thả cùng audio. */
  feed: LiveFeed | null;
  /** Gỡ theo dõi `clip.live` (mốc chữ tạm / xong / hỏng); gỡ khi bỏ clip. */
  unlive: (() => void) | null;
  /** Bối cảnh lượt lấy của clip đang về (cho [ReadAloudEngine.feedBroken]). */
  liveCtx: FetchContext | null;
  detach: (() => void) | null;
  /** Đã đặt currentTime / phát: `time` đọc từ phần tử audio thay vì `offset`. */
  started: boolean;
  fetching: boolean;
  /** Số lần lấy clip đã hỏng liên tiếp (Edge thỉnh thoảng trả 502 thoáng qua). */
  failures: number;
  /** Lúc (Date.now) bắt đầu lần lấy đầu của chuỗi lần hỏng hiện tại: gốc của quỹ [CLIP_RETRY_BUDGET_MS]. */
  began: number;
  /** Tăng mỗi khi clip của đoạn bị bỏ vì cách đọc đổi: clip về từ lượt hỏi cũ (epoch cũ) thì không dùng. */
  epoch: number;
  /** Cách đọc có chữ trong đoạn này vừa đổi mà đoạn đang nói (không cắt ngang): lần phát lại kế tiếp lấy clip mới. */
  stale: boolean;
  /** Hết lần thử lại vì dịch vụ trục trặc (đoạn chưa phải của người nghe nên chưa báo lỗi): chờ [ReadAloudEngine.probe] hay người nghe tới đoạn ấy. */
  gaveUp: boolean;
  /** Lượt xin kế tiếp là lần hỏi MỚI ([ClipOptions.fresh]): "fresh" - người nghe vừa tới đoạn, quỹ thử lại tính lại từ đầu; "probe" - hỏi thăm ngầm một lần, không thử lại. */
  ask: "fresh" | "probe" | null;
  /** Clip phát dần của đoạn đứt giữa chừng mà phần đã về vẫn đang phát, phần tiếp đang được xin / nối vào cùng phần tử audio ([ReadAloudEngine.salvage]). */
  rest: Rest | null;
}

/** Phần tiếp của một clip đứt giữa chừng (uxfix58, a58 e: 17,9 giây tiếng đã về mà người nghe chỉ nghe 3,45 giây rồi báo lỗi). Phần đã về phát hết trong phần tử audio hiện có; phần tiếp là clip ĐUÔI của CÙNG đoạn từ
 *  chữ đầu tiên chưa có tiếng, được nối vào sau khúc cuối của phần đã về (cùng MediaSource - [LiveFeed.chain]) nên nghe liền, có thể lặp vài chữ ở chỗ nối. Đồng hồ của đoạn: phần tiếp bắt đầu sau `base` giây. */
interface Rest {
  /** Chữ (của đoạn, 0-based) phần tiếp bắt đầu đọc: chữ đầu tiên chưa có tiếng. */
  from: number;
  /** Giây tiếng đã có của phần đầu. */
  base: number;
  /** Phần đầu (clip đứt): các khúc tiếng đã về, để ghép file khi cả hai phần xong. */
  head: LiveClip;
  /** Mốc của các chữ trước `from` (theo chữ của đoạn, ms từ đầu phần tử audio; chữ trước clip đuôi [0, 0]). */
  words: WordSpan[];
  /** Phần tiếp đã về (đang về hoặc xong). */
  tail: LiveClip | null;
  /** Gỡ theo dõi `tail`. */
  unlive: (() => void) | null;
  /** Lượt xin phần tiếp hỏng hẳn: phần đã có phát hết thì báo lỗi này (một lần), không sang đoạn kế. */
  error: unknown;
  /** Xin SỚM (uxfix63, [ReadAloudEngine.salvageEarly]): phần đầu còn đang về (một mảnh giữa clip đã hỏng, các mảnh trước nó vẫn về) - `base` / `words` chưa có, phần tiếp về thì chờ ở `held`. */
  early: boolean;
  /** Phần tiếp về trong lúc phần đầu còn đang về: nối khi phần đầu đóng và đúng là tiếng dừng ở `from` ([ReadAloudEngine.settleRest]). */
  held: ReadAloudClip | null;
  /** Chữ của lượt xin phần tiếp gửi gần nhất: khác `from` (chỗ nối đã dời sớm hơn) thì clip của lượt ấy không dùng. */
  asked: number;
}

/** Bối cảnh của một lượt lấy clip ([ReadAloudEngine.send]): để lỗi giữa chừng của clip đang về đi đúng đường lỗi của lượt ấy. */
interface FetchContext {
  epoch: number;
  id: number;
  ask: Slot["ask"];
  sentAt: number;
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
  /** MediaSource cho clip đang về ([ReadAloudClip.live]); mặc định là của trình duyệt. */
  createSource?: () => MediaSourceLike;
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
  private probeTimer: ReturnType<typeof setTimeout> | null = null;
  private holdTimer: ReturnType<typeof setTimeout> | null = null;
  /** Đã xin trước clip đầu của chương kế (một lần cho mỗi lần nạp chương). */
  private warmedNext = false;
  private rate = 1;
  private volume = 1;
  private loadingTime = 0;
  private lastError = "";
  /** Đang dừng VÌ LỖI (đoạn người nghe chờ hỏng lúc họ đang nghe - [fail]), không phải do họ bấm dừng: lỗi cũ gỡ đi vì dịch vụ trả lời lại thì tự phát tiếp ([resumeAfterError]). */
  private errorPause = false;
  /** Lỗi vừa gỡ, đã xin lại đoạn đang chờ: clip của nó về là tự phát tiếp ([onClip]). Người nghe bấm gì (phát, dừng, tua) thì bỏ. */
  private resuming = false;
  private readonly createAudio: (url: string) => AudioLike;
  private readonly createSource: () => MediaSourceLike;
  private readonly muted: boolean;
  private readonly readAhead: number;
  private silenceTimer: ReturnType<typeof setInterval> | null = null;
  private silenceAt = 0;
  private onVoice = () => this.voiceChanged();
  private onReadings = (event: Event) => this.readingsChanged((event as CustomEvent<ReadingsChanged>).detail);

  constructor(options: ReadAloudOptions = {}) {
    this.createAudio = options.createAudio ?? realAudio;
    this.createSource = options.createSource ?? (() => new MediaSource() as unknown as MediaSourceLike);
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
    this.errorPause = false;
    this.resuming = false;
    this.lastError = "";
    if (!was) this.fire("play");
    if (!this.ready) {
      this.fire("waiting");
      return;
    }
    this.playCurrent();
  }

  pause(): void {
    this.errorPause = false;
    this.resuming = false;
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
    const from = slot.clip?.fromWord ?? 0;
    const span = word >= from ? slot.words?.[word] : undefined; // chữ trước clip đuôi: không có mốc, xin clip khác ([dropTailIfOutside])
    // Clip đuôi: chữ đầu của nó ở giây 0, mà offset 0 là "vào đoạn từ đầu" ([dropTailIfOutside]) - nhích một chút để vẫn ở trong clip.
    if (slot.clip && span) this.moveTo({ index, offset: Math.min(Math.max(span[0] / 1000, from > 0 ? 0.001 : 0), Math.max(0, slot.duration - 0.01)) });
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
      objectUrl: null,
      feed: null,
      unlive: null,
      liveCtx: null,
      detach: null,
      started: false,
      fetching: false,
      failures: 0,
      began: 0,
      epoch: 0,
      stale: false,
      gaveUp: false,
      ask: null,
      rest: null,
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
    const live = clip.live;
    if (live && live.state !== "failed") {
      if (live.final) {
        clip = { ...clip, url: live.final.url, durationMs: live.final.durationMs, words: live.final.words, bytes: live.final.bytes }; // đã về đủ ngay trong lúc bộ máy nhận clip
      } else {
        // Còn đang về: giữ độ dài ước của đoạn (đồng hồ ảo không nhảy) tới khi xong ([liveDone]).
        slot.clip = clip;
        slot.words = absoluteWords(clip.fromWord ?? 0, live.shownWords);
        return;
      }
    }
    slot.clip = clip;
    slot.words = absoluteWords(clip.fromWord ?? 0, clip.words);
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
    this.errorPause = false;
    this.resuming = false;
    const current = this.slots[this.target.index];
    current?.audio?.pause();
    // Ô bị rời không giữ vị trí cũ: lần vào kế (nhất là advance() từ đoạn trước) phải đặt lại currentTime ([playCurrent]).
    if (current) current.started = false;
    this.finished = false;
    this.dropTailIfOutside(target.index, target);
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
    return readAheadCount(this.readAhead, this.fetchMeasures(), this.slots.slice(index + 1, index + 1 + MAX_READ_AHEAD).map((slot) => slot.duration));
  }

  /** Số đo tốc độ giọng cho [readAheadCount]: giây lấy clip thật của vài clip gần nhất + tuổi của các lượt gọi đang chờ quá [STALL_SECONDS]. */
  private fetchMeasures(): number[] {
    const now = Date.now();
    const stalled = [...this.pending.values()].map((at) => (now - at) / 1000).filter((age) => age >= STALL_SECONDS);
    return [...this.fetchSeconds, ...stalled];
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
        const speakable = texts.filter(isSpeakable);
        const serial = Boolean(speech.serial?.());
        // Cùng luật với đọc trước giữa chương ([readAheadCount]): giọng nhanh thì NEXT_CHAPTER_AHEAD clip, giọng chậm thì đủ số giây âm thanh (đoạn kế của chương sau không còn về trễ ~5 giây - soát a46).
        const count = serial ? NEXT_CHAPTER_AHEAD : readAheadCount(NEXT_CHAPTER_AHEAD, this.fetchMeasures(), speakable.slice(0, MAX_READ_AHEAD).map(estimateSeconds));
        const wanted = speakable.slice(0, count);
        const voice = speech.voice();
        // Mỗi clip kèm `rank` = số đoạn người nghe còn phải nghe trước nó (phần còn lại của chương này + vị trí trong chương kế, tối đa [MAX_WARM_RANK]): đứng sau mọi đoạn của chương
        // đang nghe nhưng trước việc nền (Làm trước, xuất sách nói) khi hết chỗ kết nối Edge ([ClipOptions.rank]). Tính lúc gửi - người nghe đã đi tiếp thì rank nhỏ lại.
        const options = (position: number): ClipOptions => ({ rank: this.warmRank(wanted, position) });
        if (serial) {
          for (const [position, text] of wanted.entries()) await speech.fetchClip(voice, text, options(position));
          return;
        }
        // Không quá `readAhead + 1` lượt cùng lúc (như [pump]): Edge hạn chế khi dồn nhiều kết nối.
        let next = 0;
        const lane = async () => {
          while (next < wanted.length) {
            const position = next++;
            await speech.fetchClip(voice, wanted[position], options(position)).catch(() => undefined);
          }
        };
        await Promise.all(Array.from({ length: Math.min(this.readAhead + 1, wanted.length) }, lane));
      })
      .catch(() => undefined);
  }

  /** Rank của đoạn thứ `position` trong `wanted` (các đoạn đọc được của chương kế) lúc này ([warmRankOf]): chỉ đoạn DÀI đứng trước nó mới tính ([isLongParagraph]). */
  private warmRank(wanted: string[], position: number): number {
    return warmRankOf(this.longAhead(this.slots.length), wanted.slice(0, position).filter(isLongParagraph).length);
  }

  /** Số đoạn dài đọc được từ chỗ người nghe (kể cả đoạn họ đang nghe) tới trước đoạn `end`. */
  private longAhead(end: number): number {
    let count = 0;
    for (let i = this.target.index; i < end; i += 1) {
      const slot = this.slots[i];
      if (slot?.speakable && isLongParagraph(slot.text)) count += 1;
    }
    return count;
  }

  private request(index: number): void {
    const speech = this.speech;
    const slot = this.slots[index];
    if (!speech || !slot || !slot.speakable) return;
    // Đoạn nằm SAU chỗ nghe mà còn giữ clip đuôi (người nghe bấm giữa đoạn ấy rồi bỏ đi chỗ khác): người nghe sẽ vào nó từ đầu nên clip đuôi vô dụng - thay ngay bằng clip đủ cả đoạn ngay trong lúc nghe
    // đoạn trước, không đợi tới lúc vào ([advance] mới bỏ thì phải đọc nguội: a58 b2, lặng 2,2 giây).
    if (slot.clip && index > this.target.index) this.dropTailIfOutside(index, { index, offset: 0 });
    if (slot.clip) {
      // Phần tiếp của clip đứt giữa chừng chưa được xin (lượt xin bị bỏ lúc tạm dừng...): xin lại.
      if (slot.rest && !slot.rest.tail && !slot.rest.held && !slot.rest.error && !slot.fetching) this.requestRest(index);
      this.audioFor(index);
      return;
    }
    if (slot.fetching) return;
    // Người nghe tới một đoạn đã hỏng từ trước (hết lần thử lại lúc nó còn ở xa, hay dịch vụ vừa khoẻ lại): hỏi MỚI một lần trước khi báo lỗi - dịch vụ có thể đã dậy từ lâu (a46: Edge về sau 28 giây,
    // người nghe tới đoạn ấy lúc 39,5 giây mà bị dừng với "Thử lại", bấm là xong ngay).
    if (slot.failures > 0 && slot.ask === null && index === this.target.index) slot.ask = "fresh";
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
    // Giọng trực tuyến: đoạn người nghe đang chờ đi NGAY, không đợi chỗ trong [limit] - bốn lượt đọc trước của cửa sổ cũ đang chạy (nhảy xa) có thể mất 5-12 giây mới có chỗ trống. Máy chủ cho
    // lượt này đi trước mọi lượt đọc trước khi hết chỗ kết nối Edge ([ClipOptions.rank]). Giọng chạy trên máy (serial) xin lần lượt như cũ: một lượt dùng hết CPU.
    if (!speech.serial?.()) {
      const waiting = this.takeQueued(this.target.index);
      if (waiting !== null) this.send(waiting);
    }
    while (this.inflight < limit) {
      const next = this.takeQueued();
      if (next === null) return;
      this.send(next);
    }
  }

  /** Lượt xin kế tiếp: đoạn gần chỗ đang nghe nhất. `only`: chỉ lấy lượt của đoạn ấy (null nếu nó không đang xếp hàng). */
  private takeQueued(only?: number): number | null {
    const target = this.target.index;
    const rank = (index: number) => (index >= target ? index - target : this.slots.length + target - index);
    let best = -1;
    for (let i = this.queued.length - 1; i >= 0; i -= 1) {
      const { index, epoch } = this.queued[i];
      const slot = this.slots[index];
      if (!slot || !slot.fetching || (slot.clip && !slot.rest) || slot.epoch !== epoch) {
        this.queued.splice(i, 1); // đã có clip, hay cách đọc / giọng đổi sau khi xếp hàng
        if (best > i) best -= 1;
        continue;
      }
      if (only !== undefined && index !== only) continue;
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
    const ask = slot.ask;
    slot.ask = null;
    if (ask === "fresh") {
      // Quỹ thử lại tính lại từ đầu cho lần hỏi này.
      slot.failures = 0;
      slot.gaveUp = false;
    }
    if (slot.failures === 0) slot.began = sentAt;
    const options: ClipOptions = { willRetry: ask !== "probe" && slot.failures < CLIP_RETRIES, retryBefore: clipRetryBefore(slot.began, slot.failures) };
    if (ask) options.fresh = true;
    // Rank = số đoạn DÀI người nghe phải nghe trước đoạn này ([isLongParagraph]): tiêu đề chương hay một dòng đối thoại đứng trước không đẩy đoạn dài kế nó xuống rank 1 (cắt 3 mảnh thay vì 6).
    if (index >= this.target.index) options.rank = this.longAhead(index);
    // Chỗ chờ theo tỉ lệ / theo giây giữa đoạn chỉ đổi được thành giây thật khi đã biết độ dài và mốc của clip: không phát dần ([ClipOptions.whole]). Bấm vào một chữ giữa đoạn thì xin clip đuôi
    // (từ chữ ấy) - nguồn phát luồng được mới làm, không thì trả clip đủ cả đoạn ([ClipOptions.tailFrom]).
    if (index === this.target.index) {
      if (this.target.fraction !== undefined || this.target.offset > 0) options.whole = true;
      else if ((this.target.word ?? 0) > 0) options.tailFrom = this.target.word;
    }
    // Phần tiếp của clip đứt giữa chừng: clip đuôi từ chữ đầu tiên chưa có tiếng, phát luồng như thường ([salvage]).
    if (slot.rest) {
      delete options.whole;
      if (slot.rest.from > 0) options.tailFrom = slot.rest.from;
      else delete options.tailFrom;
      slot.rest.asked = slot.rest.from;
    }
    speech
      .fetchClip(speech.voice(), slot.text, options)
      .then((clip) => {
        this.lastClipMs = Date.now() - sentAt;
        if (id !== this.loadId) return;
        // Clip đang về (phát dần): thời gian lấy clip thật là tới lúc về đủ, không phải tới byte đầu.
        const live = clip.live;
        if (live && live.state === "open") {
          const note = live.on((event) => {
            if (event === "done" || event === "failed") note();
            if (event === "done" && id === this.loadId) this.noteFetch(Date.now() - sentAt);
          });
        } else this.noteFetch(this.lastClipMs);
        // Cách đọc đổi trong lúc đoạn này đang được đọc: clip này theo cách đọc cũ - bỏ (lượt hỏi mới đã được xếp bởi [readingsChanged]).
        if (epoch !== slot.epoch) return;
        slot.fetching = false;
        slot.failures = 0;
        slot.gaveUp = false;
        this.onClip(index, clip);
        if (live) this.watchLive(index, clip, { epoch, id, ask, sentAt });
        // Một lượt gọi THẬT (không phải clip lấy từ bộ đệm của máy chủ, nó về được cả khi Edge đang chết) vừa xong: dịch vụ khoẻ lại, các đoạn đã bỏ cuộc trong lúc mất mạng được hỏi lại ngay.
        if (ask || this.lastClipMs / 1000 >= REAL_FETCH_SECONDS) {
          this.reviveGaveUp();
          // Lỗi cũ ("đang không dùng được"...) còn treo trên màn mà dịch vụ đã trả lời lại: bỏ lỗi, trình phát gỡ thông báo (không chờ người nghe bấm phát).
          // Đang dừng VÌ lỗi và sắp tự xin lại đoạn đang chờ: lời báo đứng nguyên tới khi lượt ấy phát được ([play] gỡ) hay hỏng nữa ([fail] cập nhật đúng lời báo đó) - gỡ rồi dựng lại là hai lời báo cho một chỗ hỏng (a59d).
          if (this.lastError && !this.resumeAfterError()) {
            this.lastError = "";
            this.fire("recovered");
          }
        }
      })
      .catch((error) => this.clipFailed(index, error, { epoch, id, ask, sentAt }))
      .finally(() => {
        if (id !== this.loadId) return;
        if (this.pending.get(index) === sentAt) this.pending.delete(index);
        this.inflight -= 1;
        this.afterFetch();
      });
  }

  /** Một lượt lấy clip vừa xong (về, hỏng, hay clip đang về mà hỏng giữa chừng): gửi lượt xếp hàng kế, xét lại cửa sổ đọc trước. */
  private afterFetch(): void {
    this.pump();
    // Số đo mới có thể làm cửa sổ đọc trước dài ra (hay co lại); cũng là chỗ xin trước chương kế khi cửa sổ chạm cuối chương.
    if (this.ready && this.wanted) this.prefetch(this.target.index, true);
    else this.warmNext();
    this.scheduleProbe();
  }

  /** Lấy clip hỏng (máy chủ trả lỗi, file không tải được, hay clip đang về đứt giữa chừng - [liveFailed]). */
  private clipFailed(index: number, error: unknown, ctx: FetchContext): void {
    const { epoch, id, ask, sentAt } = ctx;
    const slot = this.slots[index];
    if (id !== this.loadId || !slot || epoch !== slot.epoch) return;
    // Lượt hỏng mà phải chờ lâu thì nói lên tốc độ của giọng; lượt hỏng ngay (502 tức thì) thì không.
    if (Date.now() - sentAt >= SLOW_FAILURE_SECONDS * 1000) this.noteFetch(Date.now() - sentAt);
    slot.fetching = false;
    slot.failures += 1;
    // Lỗi thoáng qua (Edge cắt lượt / bận / chậm): thử lại sau một quãng nghỉ lùi dần, ở nền - các clip đã đọc sẵn vẫn phát, người nghe chỉ phải dừng nếu tới đoạn này mà
    // hết lần thử. Lỗi khác (mất mạng, bị từ chối, giọng / khoá hỏng...) thử lại cũng vô ích: đoạn người nghe đang chờ thì dừng ngay và báo.
    if (ask !== "probe" && isTransientClipError(error) && slot.failures <= CLIP_RETRIES && Date.now() < clipRetryBefore(slot.began, slot.failures - 1)) {
      this.retryLater(index, epoch, id);
      return;
    }
    // Lượt xin phần tiếp của clip đứt giữa chừng cũng hỏng hẳn: phần đã về phát hết rồi mới báo ([restGaveUp]).
    if (slot.rest) {
      this.restGaveUp(index, slot, error);
      return;
    }
    // Hết lần thử vì dịch vụ trục trặc: đoạn chưa phải của người nghe thì để đó, [probe] hỏi thăm dần và người nghe tới nơi thì hỏi mới ([request]).
    slot.gaveUp = isServiceTrouble(error);
    if (index !== this.target.index || !(this.wanted || this.resuming)) return;
    this.fail(error);
  }

  // ---- clip đang về (phát dần) ----------------------------------------------------------------------------------

  /** Theo dõi clip đang về: mốc chữ tạm cập nhật mốc của đoạn; xong thì đổi độ dài ước thành độ dài thật; hỏng giữa chừng thì như clip hỏng ([liveFailed]). */
  private watchLive(index: number, clip: ReadAloudClip, ctx: FetchContext): void {
    const live = clip.live;
    const slot = this.slots[index];
    if (!live || !slot || slot.clip?.live !== live || live.state === "done") return;
    slot.unlive?.();
    slot.unlive = null;
    slot.liveCtx = ctx;
    if (live.state === "failed") {
      this.liveFailed(index, live, ctx);
      return;
    }
    slot.unlive = live.on((event) => {
      if (this.slots[index] !== slot || slot.clip?.live !== live || ctx.id !== this.loadId) return;
      if (event === "words") {
        slot.words = absoluteWords(slot.clip?.fromWord ?? 0, live.shownWords);
        this.publish();
      } else if (event === "cut") {
        this.salvageEarly(index, slot, live);
      } else if (event === "done") {
        this.liveDone(index, slot, live);
      } else if (event === "failed") {
        this.liveFailed(index, live, ctx);
      }
    });
    if (live.cutAt !== null) this.salvageEarly(index, slot, live);
  }

  private liveDone(index: number, slot: Slot, live: LiveClip): void {
    const final = live.final;
    slot.unlive?.();
    slot.unlive = null;
    if (!final || !slot.clip) return;
    slot.clip = { ...slot.clip, url: final.url, durationMs: final.durationMs, words: final.words, bytes: final.bytes };
    slot.words = absoluteWords(slot.clip.fromWord ?? 0, final.words);
    const was = slot.duration;
    slot.duration = final.durationMs / 1000;
    // Người nghe bấm một chữ của đoạn đang về mà lúc ấy chưa có mốc của chữ: giờ đã có, nhảy tới đó.
    if (index === this.target.index && this.target.word !== undefined && this.target.word >= (slot.clip.fromWord ?? 0)) {
      this.resolveTarget(slot.clip);
      if (slot.audio && slot.started) slot.audio.currentTime = this.target.offset;
    }
    this.layout();
    this.publish();
    if (Math.abs(was - slot.duration) > 1e-6) this.fire("duration");
    if (index === this.target.index) this.fire("time");
  }

  /** Clip đang về đứt giữa chừng: bỏ phần tử audio (MediaSource) và clip, rồi đi đường lỗi + thử lại như mọi clip hỏng. */
  private liveFailed(index: number, live: LiveClip, ctx: FetchContext, salvageable = true): void {
    const slot = this.slots[index];
    if (!slot || slot.clip?.live !== live) return;
    if (salvageable && this.salvage(index, slot, live)) return;
    // Nghe dở thì nhớ chỗ đã nghe: clip lấy lại (thử lại) đón người nghe ở đó ([send]: đích có `offset` thì không phát dần).
    if (index === this.target.index && slot.started && slot.audio) {
      const from = slot.clip?.fromWord ?? 0;
      if (from > 0) {
        // Clip đuôi: giây của nó không phải giây của đoạn - nhớ chữ đang đọc (theo mốc tạm), lần lấy lại là clip đuôi mới từ chữ ấy.
        this.target.offset = 0;
        this.target.word = from + Math.max(0, wordIndexAt(live.shownWords, slot.audio.currentTime * 1000));
      } else this.target.offset = Math.max(0, slot.audio.currentTime);
    }
    this.dropClip(slot, false);
    this.layout();
    this.publish();
    this.fire("duration");
    if (index === this.target.index && this.wanted) this.fire("waiting");
    this.clipFailed(index, live.error ?? new ReadAloudError("Mất kết nối với giọng đọc giữa chừng.", "service"), ctx);
    this.afterFetch();
  }

  // ---- clip đứt giữa chừng: phần đã về vẫn phát hết, xin tiếp phần còn lại (uxfix58) ----------------------------------

  /** Chữ (đếm trong clip, 0-based) đầu tiên CHƯA có tiếng đầy đủ trong phần đã về của clip `live`: chữ có mốc kết thúc sau chỗ tiếng đã tới, hay bắt đầu từ chỗ ấy trở đi (chữ chưa tới bị máy chủ dồn về cuối phần đã
   *  có, nên chỉ nhìn mốc kết thúc thì bỏ sót cả loạt chữ). Chỗ tiếng đã tới = ngắn hơn trong hai số: mốc hết chữ thật cuối cùng Edge đã báo (`heardMs`) và số byte đã về. Chưa có mốc nào (hay máy chủ cũ không gửi
   *  `heardMs`) thì 0 - xin lại từ đầu clip; trả `live.words.length` khi mọi chữ đã có tiếng. */
  private firstUnheard(live: LiveClip): number {
    if (!live.words.length || live.heardMs === null) return 0;
    const cut = Math.min(live.heardMs, live.receivedMs);
    for (let i = 0; i < live.words.length; i += 1) {
      const [start, end] = live.words[i];
      if (end > cut || start >= cut) return i;
    }
    return live.words.length;
  }

  /** Clip phát dần của `slot` đứt giữa chừng (lỗi giữa luồng / đứt sau byte đầu): phần đã về VẪN phát hết - phần tử audio và MediaSource giữ nguyên, không báo lỗi - và NGAY xin tiếp phần còn lại bằng clip đuôi của cùng đoạn từ chữ
   *  đầu tiên chưa có tiếng ([firstUnheard]; người nghe có thể nghe lặp vài chữ), phát luồng như thường; clip tiếp về thì nối vào sau khúc cuối của phần đã về trong cùng phần tử audio ([joinRest]). Chỉ khi lượt xin tiếp ấy cũng
   *  hỏng hẳn mới đi đường lỗi ([restGaveUp]: phát hết phần đã có rồi báo MỘT lời). Trả false khi không giữ được (không có phần tử audio đang nối): đi đường bỏ clip như cũ. */
  private salvage(index: number, slot: Slot, live: LiveClip): boolean {
    const clip = slot.clip;
    const early = slot.rest?.early && slot.rest.head === live ? slot.rest : null;
    if (!clip || !slot.audio || !slot.feed || (slot.rest && !early)) return false;
    const from = clip.fromWord ?? 0;
    const total = countTokens(slot.text);
    const heard = this.firstUnheard(live);
    const resume = from + heard;
    if (early) {
      this.settleRest(index, slot, live, early, resume);
      return true;
    }
    if (resume >= total) {
      // Mọi chữ đã có tiếng (đứt đúng ở cuối): coi như clip xong ở byte cuối.
      const words = absoluteWords(from, live.words);
      slot.clip = { ...clip, url: "", durationMs: live.receivedMs, words: live.words, bytes: new Blob(live.chunks as BlobPart[], { type: "audio/mpeg" }), live: undefined, joined: true };
      slot.words = words;
      slot.unlive?.();
      slot.unlive = null;
      slot.duration = live.receivedMs / 1000;
      slot.feed.finish();
      this.layout();
      this.publish();
      this.fire("duration");
      if (index === this.target.index) this.fire("time");
      return true;
    }
    const head = heard > 0 ? absoluteWords(from, live.words.slice(0, heard)) : Array.from({ length: from }, (): WordSpan => [0, 0]);
    slot.unlive?.();
    slot.unlive = null;
    slot.rest = { from: resume, base: live.receivedMs / 1000, head: live, words: head, tail: null, unlive: null, error: null, early: false, held: null, asked: resume };
    slot.failures = 0;
    slot.gaveUp = false;
    slot.began = Date.now();
    slot.words = this.restWords(slot);
    this.publish();
    this.requestRest(index);
    return true;
  }

  /** Một mảnh giữa clip phát dần của `slot` hỏng hẳn trong lúc các mảnh trước nó còn đang về ([LiveClip.cutAt], uxfix63): tiếng sẽ dừng đúng trước chữ ấy, nên xin phần tiếp từ chữ ấy NGAY - không đợi
   *  phần đầu về hết và luồng báo lỗi (a59d e1: đợi thì người nghe chỉ còn 2,8 giây tiếng mà phần nối cần 4,8 giây, lặng 2,11 giây). Phần đầu vẫn phát và cập nhật mốc như thường; khi nó đóng,
   *  [settleRest] kiểm lại chỗ tiếng dừng rồi nối như [salvage]. */
  private salvageEarly(index: number, slot: Slot, live: LiveClip): void {
    const clip = slot.clip;
    const cut = live.cutAt;
    if (!clip || clip.live !== live || !slot.audio || !slot.feed || slot.rest || cut === null || live.state !== "open") return;
    const from = (clip.fromWord ?? 0) + cut;
    if (from >= countTokens(slot.text)) return;
    slot.rest = { from, base: 0, head: live, words: [], tail: null, unlive: null, error: null, early: true, held: null, asked: from };
    slot.failures = 0;
    slot.gaveUp = false;
    slot.began = Date.now();
    this.requestRest(index);
  }

  /** Phần đầu của lượt xin sớm ([salvageEarly]) vừa đóng ở chữ `resume` (chữ đầu tiên chưa có tiếng, [firstUnheard]): giờ mới biết độ dài phần đầu và mốc chữ của nó. Tiếng dừng sớm hơn chỗ đã xin (mảnh
   *  trước cũng hỏng): chỗ nối dời về `resume`, phần tiếp đã xin bỏ, xin lại - không bao giờ bỏ sót chữ. Phần tiếp đang chờ ở `held` thì nối luôn ([joinRest]). */
  private settleRest(index: number, slot: Slot, live: LiveClip, rest: Rest, resume: number): void {
    const from = slot.clip?.fromWord ?? 0;
    slot.unlive?.();
    slot.unlive = null;
    rest.early = false;
    rest.base = live.receivedMs / 1000;
    const heard = Math.min(resume, rest.from) - from;
    rest.words = heard > 0 ? absoluteWords(from, live.words.slice(0, heard)) : Array.from({ length: from }, (): WordSpan => [0, 0]);
    const held = rest.held;
    rest.held = null;
    const moved = resume < rest.from;
    if (moved) {
      rest.from = resume;
      // Lượt xin sớm còn đang đi: clip của nó bị bỏ khi về ([joinRest]) rồi mới xin lại. Đã hỏng hẳn: phần đầu phát hết rồi báo lỗi, "Thử lại" từ chỗ nối mới.
      if (held || (!slot.fetching && !rest.error)) this.requestRest(index);
    }
    slot.words = this.restWords(slot);
    this.publish();
    if (held && !moved) this.joinRest(index, held);
  }

  /** Mốc chữ của cả đoạn khi đang ghép: chữ đã có tiếng (phần đầu) rồi chữ của phần tiếp dời `base` giây (chữ đầu của phần tiếp coi như bắt đầu ngay chỗ nối - không thì quãng lặng đầu clip làm chữ liền trước sáng lóe, như
   *  [absoluteWords]); chữ chưa có mốc đứng cuối. Chữ chưa tới không bao giờ sáng trong lúc phát phần đầu. */
  private restWords(slot: Slot): WordSpan[] {
    const rest = slot.rest;
    if (!rest) return slot.words ?? [];
    const total = countTokens(slot.text);
    const baseMs = rest.base * 1000;
    const tail = (rest.tail?.words ?? []).slice(0, Math.max(0, total - rest.words.length));
    const shifted = tail.map(([a, b], i): WordSpan => [baseMs + (i === 0 ? 0 : a), baseMs + b]);
    // Chữ chưa có mốc đứng sau chỗ nối đủ xa để không sáng trong lúc phát phần đầu ([wordIndexAt] sáng sớm [WORD_LEAD_MS]).
    const end = shifted.length ? shifted[shifted.length - 1][1] : baseMs + WORD_LEAD_MS + 1;
    const pad = Array.from({ length: Math.max(0, total - rest.words.length - shifted.length) }, (): WordSpan => [end, end]);
    return [...rest.words, ...shifted, ...pad];
  }

  /** Xếp lượt xin phần tiếp của `slot` (như một lượt xin clip, đi cùng đường [pump] / [send] / thử lại). */
  private requestRest(index: number): void {
    const slot = this.slots[index];
    if (!slot?.rest) return;
    slot.fetching = true;
    this.queued.push({ index, epoch: slot.epoch });
    this.pump();
  }

  /** Clip xin tiếp về: nối vào cùng MediaSource sau phần đã về. Nguồn không đưa được clip đuôi từ đúng chữ ấy (trả cả đoạn từ bộ đệm...) thì không nối được: bỏ phần đã có, nghe từ chữ đang nghe trong clip đó. */
  private joinRest(index: number, clip: ReadAloudClip): void {
    const slot = this.slots[index];
    const rest = slot?.rest;
    if (!slot || !rest) return;
    if (rest.asked !== rest.from && (clip.fromWord ?? 0) === rest.asked) {
      this.requestRest(index); // lượt xin sớm từ chữ cũ, chỗ nối đã dời sớm hơn ([settleRest])
      return;
    }
    if (rest.early) {
      rest.held = clip; // phần đầu còn đang về: nối khi nó đóng
      return;
    }
    if ((clip.fromWord ?? 0) !== rest.from) {
      this.replaceByWhole(index, slot, clip);
      return;
    }
    const id = this.loadId;
    const epoch = slot.epoch;
    const attach = (tail: LiveClip): void => {
      if (id !== this.loadId || this.slots[index] !== slot || slot.rest !== rest || slot.epoch !== epoch) return;
      rest.tail = tail;
      slot.feed?.chain(tail);
      rest.unlive = tail.on((event) => {
        if (id !== this.loadId || slot.rest !== rest) return;
        if (event === "words") {
          slot.words = this.restWords(slot);
          this.publish();
        } else if (event === "done") this.finishRest(index, slot);
        else if (event === "failed") this.restGaveUp(index, slot, tail.error);
      });
      slot.words = this.restWords(slot);
      this.publish();
      if (tail.state === "done") this.finishRest(index, slot);
      else if (tail.state === "failed") this.restGaveUp(index, slot, tail.error);
    };
    if (clip.live) {
      attach(clip.live);
      return;
    }
    // Clip đã về trọn (không phát luồng): đổi thành một clip "đã xong" để nối chung đường.
    void (async () => {
      const bytes = clip.bytes ?? (await fetchClipBytes(clip.url));
      const done = new LiveClip();
      done.push(new Uint8Array(await bytes.arrayBuffer()));
      done.finish({ url: clip.url, durationMs: clip.durationMs, words: clip.words, bytes });
      return done;
    })().then(attach, (error) => {
      if (id === this.loadId && slot.rest === rest && slot.epoch === epoch) this.restGaveUp(index, slot, error);
    });
  }

  /** Phần tiếp về đủ: ghép hai phần thành một clip (file = phần đầu + phần tiếp), độ dài thật = phần đầu + phần tiếp, đồng hồ dựng lại. */
  private finishRest(index: number, slot: Slot): void {
    const rest = slot.rest;
    const clip = slot.clip;
    const tail = rest?.tail;
    const final = tail?.final;
    if (!rest || !clip || !tail || !final) return;
    rest.unlive?.();
    const from = clip.fromWord ?? 0;
    const words = this.restWords(slot);
    const durationMs = rest.base * 1000 + final.durationMs;
    slot.rest = null;
    slot.clip = { ...clip, url: "", durationMs, words: words.slice(from), bytes: new Blob([...rest.head.chunks, ...tail.chunks] as BlobPart[], { type: "audio/mpeg" }), live: undefined, joined: true };
    slot.words = words;
    const was = slot.duration;
    slot.duration = durationMs / 1000;
    if (index === this.target.index && this.target.word !== undefined && this.target.word >= from) {
      this.resolveTarget(slot.clip);
      if (slot.audio && slot.started) slot.audio.currentTime = this.target.offset;
    }
    this.layout();
    this.publish();
    if (Math.abs(was - slot.duration) > 1e-6) this.fire("duration");
    if (index === this.target.index) this.fire("time");
  }

  /** Lượt xin phần tiếp hỏng hẳn. Đoạn người nghe đang nghe: MediaSource đóng ở cuối phần đã về để nó phát HẾT, rồi [audioEnded] báo lỗi (một lời, không sang đoạn kế). Đoạn khác: bỏ clip, đoạn sẽ được xin lại nguyên vẹn. */
  private restGaveUp(index: number, slot: Slot, error: unknown): void {
    const rest = slot.rest;
    if (!rest) return;
    rest.unlive?.();
    rest.unlive = null;
    slot.fetching = false;
    if (index !== this.target.index) {
      this.dropClip(slot);
      this.layout();
      this.publish();
      this.fire("duration");
      return;
    }
    rest.error = error ?? new ReadAloudError("Mất kết nối với giọng đọc giữa chừng.", "service");
    slot.feed?.finish();
  }

  /** Phần đã về phát hết mà phần tiếp không xin được: báo lỗi MỘT lần; "Thử lại" xin lại từ chữ chưa nghe. */
  private failRest(slot: Slot): void {
    const rest = slot.rest;
    if (!rest) return;
    const error = rest.error;
    this.target.offset = 0;
    this.target.fraction = undefined;
    this.target.word = rest.from > 0 ? rest.from : undefined;
    this.dropClip(slot);
    slot.fetching = false;
    this.layout();
    this.publish();
    this.fire("duration");
    this.fail(error);
  }

  /** Chữ (của đoạn) đang nghe trong phần tử audio của `slot`; chưa nghe thì chữ đầu clip. */
  private positionWord(slot: Slot): number {
    const from = slot.clip?.fromWord ?? 0;
    if (!slot.started || !slot.audio || !slot.words) return from;
    return Math.max(from, wordIndexAt(slot.words, slot.audio.currentTime * 1000));
  }

  /** Clip trả về cho lượt xin phần tiếp không phải clip đuôi từ đúng chữ: bỏ phần đã có, nghe tiếp từ chữ đang nghe trong clip này. */
  private replaceByWhole(index: number, slot: Slot, clip: ReadAloudClip): void {
    const word = this.positionWord(slot);
    this.dropClip(slot, false);
    slot.fetching = false;
    if (index === this.target.index) {
      this.target.offset = 0;
      this.target.fraction = undefined;
      this.target.word = word > 0 ? word : undefined;
    }
    this.onClip(index, clip);
  }

  /** Ghép hai phần không nối được (MediaSource không nhận khúc): bỏ clip, xin lại từ chữ đang nghe. */
  private abandonRest(index: number, slot: Slot): void {
    const word = this.positionWord(slot);
    const wasTarget = index === this.target.index;
    this.dropClip(slot);
    slot.fetching = false;
    if (wasTarget) {
      this.target.offset = 0;
      this.target.fraction = undefined;
      this.target.word = word > 0 ? word : undefined;
    }
    this.layout();
    this.publish();
    this.fire("duration");
    if (wasTarget && this.wanted) {
      this.fire("waiting");
      this.playCurrent();
    }
  }

  private clearRest(slot: Slot): void {
    slot.rest?.unlive?.();
    slot.rest = null;
  }

  /** MediaSource không nhận khúc MP3 (nối lỗi): clip đang về thì coi như hỏng; đã về đủ thì phát tiếp từ file (blob) ở chỗ đang nghe. */
  private feedBroken(index: number, slot: Slot): void {
    const live = slot.clip?.live;
    if (this.slots[index] !== slot || !slot.clip) return;
    if (slot.rest) {
      this.abandonRest(index, slot); // phần đầu + phần tiếp chưa ghép xong mà MediaSource không nhận: bỏ, xin lại từ chữ đang nghe
      return;
    }
    if (!live) return;
    if (live.state === "open" && slot.liveCtx) {
      this.liveFailed(index, live, slot.liveCtx, false); // MediaSource đã hỏng: không còn chỗ nối phần tiếp
      return;
    }
    const at = slot.audio?.currentTime ?? 0;
    const wasStarted = slot.started;
    this.releaseSlot(slot);
    if (index !== this.target.index) return;
    this.target.offset = wasStarted ? at : this.target.offset;
    if (this.wanted) this.playCurrent();
  }

  /** Đoạn gần người nghe nhất trong cửa sổ đọc trước đã bỏ cuộc vì dịch vụ trục trặc (không tính đoạn đang nghe: người nghe tới đoạn ấy là hỏi mới rồi - [request]). */
  private gaveUpSlot(): number | null {
    const target = this.target.index;
    const last = target + this.depth(target);
    for (let i = target + 1; i <= last && i < this.slots.length; i += 1) {
      const slot = this.slots[i];
      if (slot.gaveUp && !slot.fetching && !slot.clip && slot.speakable) return i;
    }
    return null;
  }

  /** Còn đoạn bỏ cuộc trong cửa sổ thì hẹn [probe] sau [PROBE_MS] (mỗi lượt gọi xong lại hẹn tiếp: hỏi thăm lần lượt, không bao giờ hai lượt cùng lúc). */
  private scheduleProbe(): void {
    if (this.probeTimer !== null || !this.ready || !this.wanted || this.gaveUpSlot() === null) return;
    const id = this.loadId;
    this.probeTimer = setTimeout(() => {
      this.probeTimer = null;
      if (id === this.loadId) this.probe();
    }, PROBE_MS);
  }

  private probe(): void {
    if (!this.ready || !this.wanted) return;
    const index = this.gaveUpSlot();
    if (index === null) return;
    this.slots[index].ask = "probe";
    this.request(index); // xong (được hay hỏng) thì [send] hẹn lượt hỏi thăm kế
  }

  /** Dịch vụ vừa trả lời thật: các đoạn đã bỏ cuộc (không phải đoạn đang chờ) được hỏi lại như mới, với quỹ thử lại đủ. */
  private reviveGaveUp(): void {
    for (const slot of this.slots) {
      if (!slot.gaveUp || slot.fetching || slot.clip) continue;
      slot.gaveUp = false;
      slot.failures = 0;
    }
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
      if (id !== this.loadId || slot.epoch !== epoch || (slot.clip && !slot.rest)) return;
      const target = this.target.index;
      if (!(this.wanted || (this.resuming && index === target)) || index < target || index > target + this.depth(target)) {
        slot.fetching = false;
        return;
      }
      this.queued.push({ index, epoch });
      this.pump();
    }, CLIP_RETRY_DELAYS_MS[Math.min(slot.failures, CLIP_RETRY_DELAYS_MS.length) - 1]);
  }

  private onClip(index: number, clip: ReadAloudClip): void {
    const waitingRest = this.slots[index].rest;
    if (waitingRest && !waitingRest.tail) {
      this.joinRest(index, clip);
      return;
    }
    const was = this.slots[index].duration;
    this.adopt(index, clip);
    // Clip đuôi về mà người nghe đã đổi chỗ sang trước chữ đầu của nó trong lúc chờ: không dùng, xin lại ([dropTailIfOutside]).
    if (index === this.target.index && this.dropTailIfOutside(index, this.target)) {
      if (this.wanted) this.playCurrent();
      return;
    }
    // Clip đuôi về cho đoạn mà người nghe đã lùi ra TRƯỚC nó trong lúc chờ: người nghe sẽ vào đoạn ấy từ đầu - bỏ, xin clip đủ cả đoạn ([request]).
    if (index > this.target.index && this.dropTailIfOutside(index, { index, offset: 0 })) {
      if (this.ready && this.wanted) this.request(index);
      return;
    }
    this.layout();
    const waiting = index === this.target.index;
    if (waiting) this.resolveTarget(clip);
    if (index >= this.target.index - 1 && index <= this.target.index + this.depth(this.target.index)) this.audioFor(index);
    this.publish();
    if (Math.abs(was - this.slots[index].duration) > 1e-6) this.fire("duration");
    if (waiting && this.resuming && !this.wanted) this.play(); // lỗi đã gỡ và người nghe không đụng gì: đoạn họ đang chờ đã sẵn sàng, phát tiếp
    else if (waiting && this.wanted) this.playCurrent();
    else if (waiting) this.fire("time");
  }

  /** Dịch vụ vừa trả lời lại mà trình phát đang dừng VÌ lỗi ấy (không phải người nghe bấm dừng): xin lại đoạn đang chờ, clip về thì tự phát tiếp
   *  ([onClip]). Người nghe tự dừng thì ở yên dừng - [pause] / [moveTo] / [play] gỡ cờ. Trả true khi đã bắt đầu xin lại / phát (lời báo lỗi ở yên tới khi có kết quả), false khi để yên dừng. */
  private resumeAfterError(): boolean {
    if (!this.errorPause || this.wanted || !this.ready) return false;
    const slot = this.slots[this.target.index];
    if (!slot || slot.clip || !slot.speakable) {
      this.play(); // đã có clip (hay đoạn lặng): phát luôn
      return true;
    }
    this.resuming = true;
    this.request(this.target.index);
    return true;
  }

  /** Clip của đoạn đang chờ vừa về: đổi chỗ chờ (tỉ lệ / chữ) thành giây thật trong clip. */
  private resolveTarget(clip: ReadAloudClip): void {
    const target = this.target;
    if (target.word !== undefined) {
      const span = clip.words[target.word - (clip.fromWord ?? 0)]; // clip đuôi: mốc tính từ chữ `fromWord`
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
    // Clip đang về (phát dần): phát từ MediaSource, [LiveFeed] nối các khúc đã về và sẽ về. Dựng lại giữa chừng thì nối lại từ khúc đầu.
    const live = slot.clip.live;
    let source: MediaSourceLike | null = null;
    if (live && live.state === "open" && typeof URL.createObjectURL === "function") {
      source = this.createSource();
      slot.objectUrl = URL.createObjectURL(source as unknown as MediaSource);
    } else {
      // Có sẵn file (đã tải bằng fetch) thì phát từ blob: URL: phần tử <audio> không còn tự đi tải mạng.
      slot.objectUrl = slot.clip.bytes && typeof URL.createObjectURL === "function" ? URL.createObjectURL(slot.clip.bytes) : null;
    }
    const audio = this.createAudio(slot.objectUrl ?? slot.clip.url);
    if (source && live) slot.feed = new LiveFeed(source, live, () => this.feedBroken(index, slot));
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
    const rest = this.slots[index]?.rest;
    if (rest?.error !== undefined && rest.error !== null) {
      this.failRest(this.slots[index]);
      return;
    }
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
    // Đoạn kế có thể đã phát dở từ trước (người nghe bấm đi chỗ khác rồi quay lại từ đoạn trước): vào nó là từ đầu, không ở chỗ cũ ([playCurrent]).
    const entering = this.slots[next];
    if (entering) entering.started = false;
    this.dropTailIfOutside(next, this.target);
    this.releaseOutside();
    this.dropQueuedOutside();
    this.fire("time");
    this.playCurrent();
  }

  /** Clip đuôi ([ReadAloudClip.fromWord]) chỉ dùng khi chỗ nghe nằm TRONG nó: vào đoạn ấy ở chỗ trước chữ đầu của clip (chữ đứng trước, từ đoạn trước sang, tua về đầu đoạn) thì bỏ clip đuôi - lần phát sau xin
   *  clip đầy đủ (hay clip đuôi mới theo chữ vừa bấm). Trả true khi đã bỏ. */
  private dropTailIfOutside(index: number, target: Target): boolean {
    const slot = this.slots[index];
    const from = slot?.clip?.fromWord ?? 0;
    if (!slot || from <= 0) return false;
    const inside = target.word !== undefined ? target.word >= from : target.fraction === undefined && target.offset > 1e-6;
    if (inside) return false;
    this.dropClip(slot);
    slot.fetching = false;
    this.layout();
    this.publish();
    this.fire("duration");
    return true;
  }

  /** Giữ phần tử audio của đoạn trước, hiện tại và vài đoạn sau, và FILE (blob) của [KEEP_BEHIND] đoạn vừa nghe; thả phần còn lại (tránh giữ hàng trăm file đã nạp). */
  private releaseOutside(): void {
    const low = this.target.index - 1;
    const keepBytesFrom = this.target.index - KEEP_BEHIND;
    const high = this.target.index + this.depth(this.target.index);
    this.slots.forEach((slot, i) => {
      // Ra khỏi cửa sổ giữa lúc đang ghép hai phần, hay clip đã ghép (không có file riêng) mà file bị thả: bỏ cả clip, đoạn sẽ được xin lại nguyên vẹn khi tới gần.
      if ((i < low || i > high) && slot.rest) {
        this.dropClip(slot);
        slot.fetching = false;
        return;
      }
      if ((i < keepBytesFrom || i > high) && slot.clip?.joined) {
        this.dropClip(slot);
        slot.fetching = false;
        return;
      }
      if (i < low || i > high) this.releaseSlot(slot);
      // Ngoài cửa sổ không giữ cả file trong bộ nhớ (cả chương có thể hàng trăm clip), trừ vài đoạn vừa nghe: bấm "đoạn trước" thì phát lại từ file đã có (blob: URL mới), không đi tải
      // lại `url` - phần tử <audio> tự tải bị xếp sau các lượt POST clip còn treo (a55, a56). Đoạn xa hơn thì phát từ `url` như thường.
      if ((i < keepBytesFrom || i > high) && slot.clip?.bytes) slot.clip = { ...slot.clip, bytes: undefined };
    });
  }

  private releaseSlot(slot: Slot): void {
    if (!slot.audio) return;
    slot.detach?.();
    slot.feed?.close();
    slot.feed = null;
    slot.audio.pause();
    slot.audio.removeAttribute("src");
    slot.audio.load();
    slot.audio = null;
    if (slot.objectUrl) URL.revokeObjectURL(slot.objectUrl);
    slot.objectUrl = null;
    slot.detach = null;
    slot.started = false;
  }

  /** Bỏ clip của đoạn (thả audio, độ dài về ước tính) để lần sau lấy lại. `retire` false: không đổi `epoch` (lượt lấy của clip vừa bỏ còn là lượt hiện hành - [liveFailed]). */
  private dropClip(slot: Slot, retire = true): void {
    this.releaseSlot(slot);
    slot.unlive?.();
    slot.unlive = null;
    this.clearRest(slot);
    slot.clip = null;
    slot.words = null;
    slot.duration = slot.estimate;
    slot.stale = false;
    if (retire) slot.epoch += 1;
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
      slot.unlive?.();
      slot.unlive = null;
      this.clearRest(slot);
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
    this.errorPause = was || this.resuming; // dừng vì lỗi (lần xin lại sau khi gỡ lỗi mà hỏng nữa cũng vậy), khác người nghe bấm dừng
    this.resuming = false;
    this.wanted = false;
    const slot = this.slots[this.target.index];
    this.stopSilence();
    // Người nghe bấm phát lại thì được thử lại từ đầu.
    if (slot) {
      slot.failures = 0;
      slot.gaveUp = false;
    }
    slot?.audio?.pause();
    if (was) this.fire("pause");
    this.fire("error");
  }

  private dispose(): void {
    this.stopSilence(false);
    this.loadId += 1;
    this.queued = [];
    this.inflight = 0;
    this.errorPause = false;
    this.resuming = false;
    if (this.holdTimer !== null) clearTimeout(this.holdTimer);
    this.holdTimer = null;
    this.holdUntil = 0;
    this.lastClipMs = 0;
    this.fetchSeconds = [];
    this.pending.clear();
    if (this.watch !== null) clearInterval(this.watch);
    this.watch = null;
    if (this.probeTimer !== null) clearTimeout(this.probeTimer);
    this.probeTimer = null;
    if (typeof window !== "undefined") {
      window.removeEventListener(VOICE_CHANGED_EVENT, this.onVoice);
      window.removeEventListener(READINGS_CHANGED_EVENT, this.onReadings);
    }
    for (const slot of this.slots) {
      this.clearRest(slot);
      this.releaseSlot(slot);
    }
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

const EVENTS: EngineEvent[] = ["time", "duration", "play", "pause", "ended", "error", "recovered", "waiting", "playing"];

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
