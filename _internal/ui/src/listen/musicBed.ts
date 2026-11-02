// Lớp nhạc nền của trình phát máy tính: một (hai, khi chuyển cảnh) <audio> chạy song song với giọng đọc, theo các MỐC
// nhạc của chương (GET /api/books/<id>/music/chapters/<n> - webui/music_plan.py). Nhạc nền không cần khớp từng mili-giây
// như lời thoại với hình: chỉ cần đổi đúng bài khi sang đoạn mới, chuyển mờ dần, lặp liền, dừng / chạy theo giọng đọc,
// nhảy đúng chỗ khi người nghe tua. Âm lượng = âm lượng người nghe x `gainDb` của mốc (máy chủ tính từ `levelDb` = nhạc
// thấp hơn giọng bao nhiêu LU, độ to và độ lấn dải tiếng nói của từng bài - Pha 4 của docs/MUSIC_RESEARCH.md).
// Lặp bằng MỜ CHÉO vào chính bài trong đoạn nghe được [audibleStart, audibleEnd] (bài có đoạn kết: giữa hai điểm vòng
// loopStart / loopEnd - mô hình chung ở webui/music_mix.py), không
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
  /** Điểm vòng của bài có đoạn kết (danh mục, Corpus/research/music/PLAN_loop.md §10): phần tử lặp mở ở `loopEnd` - X và phát từ
   *  `loopStart`; vòng cuối của mốc `tail` chơi qua `loopEnd` tới E. Thiếu hay không hợp lệ (`loopBounds`) thì như `audibleStart` /
   *  `audibleEnd`. */
  loopStart?: number;
  loopEnd?: number;
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
  /** Vì sao chưa có nhạc theo cảnh (danh mục chưa tải được...), bằng lời cho người nghe; vắng khi không có chuyện gì. */
  unavailable?: string;
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
/** `detail` của [MUSIC_CHANGED_EVENT] khi đổi cài đặt chung cho mọi cuốn ("Tự chọn nhạc nền"): cuốn nào đang nghe cũng nạp lại mốc nhạc. */
export const MUSIC_CHANGED_ALL = "*";

type BedAudio = Pick<HTMLAudioElement, "play" | "pause" | "paused" | "volume" | "loop" | "currentTime" | "duration"> & {
  /** `error`: bài không tải được (mất mạng, máy chủ không phát được). `playing`: bài THẬT SỰ đang kêu (đã có dữ liệu để phát, không còn chờ tải). */
  addEventListener(type: "loadedmetadata" | "error" | "playing", listener: () => void, options?: { once?: boolean }): void;
  /** HAVE_ENOUGH_DATA (4) = trình duyệt ước tải kịp tới hết bài: mới cho vào. Phần tử không khai báo (bản giả) thì không chờ tiếng: mờ vào như cũ. */
  readonly readyState?: number;
  /** Phần đã tải của <audio src> (trình duyệt không có MediaSource, như Safari iPhone): bài đang tải dở sắp hụt thì mờ ra thay vì tắt phụt. */
  readonly buffered?: Pick<TimeRanges, "length" | "start" | "end">;
  /** Bài không lặp (bài cũ khi nối bài anh em) đã chơi hết: không phát lại. */
  readonly ended?: boolean;
  /** [release]: bỏ nguồn rồi nạp lại để trình duyệt đóng kết nối tải bài. */
  removeAttribute?(name: string): void;
  load?(): void;
  /** [release] của bài phát qua MediaSource ([mseAudio]): thôi tải cả file, nhả URL đối tượng. */
  dispose?(): void;
};

/** <audio> thật; ?mute=1: kiểm thử tự động không được phát tiếng ra loa của người dùng (như engine.ts, clip.tsx). Trình duyệt có
 *  MediaSource nhận "audio/mpeg" thì bài đi qua [mseAudio] (bài mp3 tua đúng khung), không thì <audio src> như cũ. */
export function browserAudio(src: string): BedAudio {
  const audio = new Audio();
  audio.muted = new URLSearchParams(window.location.search).get("mute") === "1";
  audio.preload = "auto";
  if (typeof MediaSource !== "undefined" && MediaSource.isTypeSupported("audio/mpeg")) return mseAudio(audio, src);
  audio.src = src;
  return audio;
}

/** Chỗ đệm tiếng mặc định của một SourceBuffer ở Chromium (12 MB): bài lớn hơn thì nạp tới đó là QuotaExceededError khi phần tử còn đứng ở
 *  chỗ vào (chưa có phần đã phát để trình duyệt dọn), nên đi thẳng <audio src> thay vì tải phí một phần rồi mới lùi. */
const MSE_AUDIO_BYTES = 12 * 1024 * 1024;
/** Phần đầu file (sau thẻ ID3) giữ lại để đọc độ dài ([mp3Seconds]). */
const MP3_HEAD_BYTES = 1024 * 1024;

/** Cỡ thẻ ID3v2 đầu file (0 = không có), null = chưa đủ 10 byte. Thẻ chứa ảnh bìa có thể dài hơn mọi phần đầu giữ lại (dc28: 1,42 MB). */
export function id3Length(head: Uint8Array): number | null {
  if (head.length < 10) return null;
  if (head[0] !== 0x49 || head[1] !== 0x44 || head[2] !== 0x33) return 0;
  return 10 + (((head[6] & 0x7f) << 21) | ((head[7] & 0x7f) << 14) | ((head[8] & 0x7f) << 7) | (head[9] & 0x7f)) + (head[5] & 0x10 ? 10 : 0);
}

/** Độ dài (giây) của bài mp3 dài `total` byte, đọc từ phần đầu file `head`: khung Xing/Info có số khung thì đúng số khung, không có thì theo
 *  bitrate của khung đầu (đúng với CBR - bài danh mục incompetech không có Xing). null = chưa đủ byte hay không phải mp3 Layer III. MediaSource
 *  chỉ biết độ dài khi đã nạp hết, mà MusicBed cần nó ngay để căn chỗ vào và tính cổng [playsThrough]. */
export function mp3Seconds(head: Uint8Array, total: number): number | null {
  let at = id3Length(head);
  if (at === null) return null;
  for (; at + 4 <= head.length; at += 1) {
    if (head[at] !== 0xff || (head[at + 1] & 0xe0) !== 0xe0) continue;
    const version = (head[at + 1] >> 3) & 3; // 3 = MPEG-1, 2 = MPEG-2, 0 = MPEG-2.5
    const bitrate = head[at + 2] >> 4;
    const rate = (head[at + 2] >> 2) & 3;
    if (version === 1 || ((head[at + 1] >> 1) & 3) !== 1 || bitrate === 0 || bitrate === 15 || rate === 3) continue;
    const mpeg1 = version === 3;
    const kbps = (mpeg1 ? [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320] : [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160])[bitrate];
    const hz = [44100, 48000, 32000][rate] / (mpeg1 ? 1 : version === 2 ? 2 : 4);
    const mono = head[at + 3] >> 6 === 3;
    const tag = at + 4 + (mpeg1 ? (mono ? 17 : 32) : mono ? 9 : 17);
    if (tag + 12 > head.length) return null;
    const id = String.fromCharCode(head[tag], head[tag + 1], head[tag + 2], head[tag + 3]);
    if ((id === "Xing" || id === "Info") && head[tag + 7] & 1) {
      const frames = ((head[tag + 8] << 24) | (head[tag + 9] << 16) | (head[tag + 10] << 8) | head[tag + 11]) >>> 0;
      return (frames * (mpeg1 ? 1152 : 576)) / hz;
    }
    return ((total - at) * 8) / (kbps * 1000);
  }
  return null;
}

/** Bài mp3 có khung Xing kèm mục lục: <audio src> tua theo mục lục ấy, phần tử lặp vào từ loopStart lệch tới 2,2 s (loopfix). Nạp file vào
 *  MediaSource ("audio/mpeg") thì trình duyệt tua theo dấu thời gian từng khung (lệch <= 14 ms đo trên 40 bài). Nạp DẦN từng khúc đang tải về
 *  (không đợi cả file - nguồn chậm 11-30 KB/s thì đợi trọn bài là im hàng phút): biết độ dài từ đầu file ([mp3Seconds]) là báo `loadedmetadata`
 *  cho MusicBed, phần đã nạp là `buffered` của phần tử, cổng [playsThrough] quyết lúc vào như bài <audio src> đang tải dở; trình duyệt không ngừng
 *  tải khi phần tử tạm dừng (<audio src> của Chrome ngừng ở ~3,5 MB phía trước, đo 02-11). Trước lúc ấy `loadedmetadata` / `error` của phần
 *  tử bị giữ lại, `play()` hoãn. Máy chủ trả không phải mp3 (ogg, wav), bài lớn hơn [MSE_AUDIO_BYTES], tải hỏng / hết chỗ đệm / giải mã hỏng
 *  trước lúc ấy: lùi về <audio src> như cũ - lỗi của đường cũ mới tới MusicBed; hỏng sau lúc ấy: báo `error` (bài hỏng, thử lại sau). */
function mseAudio(audio: HTMLAudioElement, src: string): BedAudio {
  const abort = new AbortController();
  let url = "";
  let settled = false; // đã biết độ dài (nạp dần qua MediaSource) hay đã lùi về <audio src>: từ đây sự kiện đi thẳng tới MusicBed
  let wantPlay = false;
  const play = audio.play.bind(audio);
  const pause = audio.pause.bind(audio);
  const revoke = () => {
    if (url) URL.revokeObjectURL(url);
    url = "";
  };
  const settle = (plain: boolean) => {
    if (settled) return;
    settled = true;
    if (plain) {
      revoke();
      audio.src = src;
    } else {
      audio.dispatchEvent(new Event("loadedmetadata"));
    }
    if (wantPlay) void play().catch(() => undefined);
  };
  // Đăng ký trước MusicBed.open nên chặn được sự kiện của lúc nạp.
  audio.addEventListener("loadedmetadata", (event) => { if (!settled) event.stopImmediatePropagation(); });
  audio.addEventListener("error", (event) => {
    if (settled) return;
    event.stopImmediatePropagation();
    settle(true);
  });
  void (async () => {
    try {
      const response = await fetch(src, { signal: abort.signal });
      if (!response.ok || !(response.headers.get("Content-Type") ?? "").startsWith("audio/mpeg")) {
        abort.abort();
        settle(true);
        return;
      }
      const total = Number(response.headers.get("Content-Length") ?? Number.NaN);
      if (total > MSE_AUDIO_BYTES) {
        abort.abort();
        settle(true);
        return;
      }
      const source = new MediaSource();
      url = URL.createObjectURL(source);
      audio.src = url;
      await new Promise<void>((resolve) => source.addEventListener("sourceopen", () => resolve(), { once: true }));
      const buffer = source.addSourceBuffer("audio/mpeg");
      const append = (data: BufferSource) =>
        new Promise<void>((resolve, reject) => {
          buffer.addEventListener("updateend", () => resolve(), { once: true });
          buffer.addEventListener("error", () => reject(new Error("appendBuffer")), { once: true });
          buffer.appendBuffer(data); // QuotaExceededError ném ngay ở đây
        });
      const reader = response.body?.getReader();
      if (!reader) throw new Error("body");
      // Phần đầu để đọc độ dài bắt đầu ở byte `headAt` của file: biết cỡ thẻ ID3 thì bỏ cả thẻ, chỉ giữ từ khung đầu.
      let head = new Uint8Array(0);
      let headAt = 0;
      let read = 0;
      for (let part = await reader.read(); !part.done; part = await reader.read()) {
        await append(part.value);
        const from = read;
        read += part.value.length;
        if (settled || !(total > 0) || head.length >= MP3_HEAD_BYTES) continue;
        const fresh = part.value.subarray(Math.max(0, headAt + head.length - from));
        if (!fresh.length) continue;
        const grown = new Uint8Array(head.length + fresh.length);
        grown.set(head);
        grown.set(fresh, head.length);
        head = grown;
        if (headAt === 0) {
          const tag = id3Length(head);
          if (tag === null) continue;
          if (tag > 0) {
            headAt = tag;
            head = head.slice(Math.min(tag, head.length));
          }
        }
        const seconds = mp3Seconds(head, total - headAt);
        if (seconds === null) continue;
        source.duration = seconds;
        settle(false);
      }
      source.endOfStream(); // độ dài thành đúng số khung đã nạp
      settle(false);
    } catch {
      if (abort.signal.aborted) return;
      if (!settled) settle(true);
      else audio.dispatchEvent(new Event("error"));
    }
  })();
  return Object.assign(audio, {
    play: () => {
      if (settled) return play();
      wantPlay = true;
      return Promise.resolve();
    },
    pause: () => {
      wantPlay = false;
      pause();
    },
    dispose: () => {
      settled = true;
      abort.abort();
      revoke();
    },
  });
}

export const FADE_SECONDS = mix.fadeSeconds;
export const SIBLING_FADE_SECONDS = mix.siblingFadeSeconds;
export const STEP_RAMP_SECONDS = mix.stepRampSeconds;
export const LOOP_CROSSFADE_SECONDS = mix.loopCrossfadeSeconds;
/** Chu kỳ ngắn nhất (giây) để điểm vòng của danh mục được dùng (music_mix.loop_bounds). */
const LOOP_MIN_PERIOD_SECONDS = mix.loopMinPeriodSeconds;
const STEP_MS = 50;
/** Bài đang tải dở (<audio src>, hay mp3 đang nạp dần vào MediaSource) chỉ vào - và vào lại sau hụt - khi phát được tới chỗ bài thôi kêu ([playsThrough],
 *  [playEnd]): cùng công thức, cùng hằng số (music_mix.json, khoá underrun*) với `keepsUp` của bản máy tính (musicmixer.cpp) và StreamPace.kt của
 *  Android. Tốc độ tải đo bằng trung bình trượt [DOWNLOAD_WINDOW_SECONDS] giây của phần đã tải (giây bài mỗi giây đồng hồ), gộp đợt dồn
 *  [DOWNLOAD_BURST_SECONDS] đầu (phần bộ đệm đã có sẵn). */
const DOWNLOAD_WINDOW_SECONDS = mix.underrunRateWindowSeconds;
const DOWNLOAD_BURST_SECONDS = mix.underrunBurstSeconds;
/** Lề trần: dùng khi chưa đo đủ 2 cửa sổ, và trên mọi đường mà dự báo từng hụt quá chừng ấy ([DownloadPace.margin]). */
const DOWNLOAD_MARGIN = mix.underrunMargin;
/** Phần phải có sẵn trước con trỏ lúc vào. */
const DOWNLOAD_LEAD_SECONDS = mix.underrunLeadSeconds;
/** Tốc độ tụt giữa bài mà phần đã tải trước con trỏ còn dưới chừng này: mờ ra trong [UNDERRUN_FADE_SECONDS], tạm dừng tại chỗ, phát được tới chỗ thôi
 *  kêu thì mờ vào cũng trong chừng ấy - không tắt / bật phụt (NA1 01-11: nhạc im phụt 14 lần khi bài đang tải dở). */
const UNDERRUN_LOW_SECONDS = mix.underrunLowSeconds;
const UNDERRUN_FADE_SECONDS = mix.underrunFadeSeconds;
/** Lần vào (cả vào lại sau hụt) phải còn ít nhất chừng này tới chỗ bài thôi kêu: [DOWNLOAD_LEAD_SECONDS] đã tải, hụt lại ở [UNDERRUN_LOW_SECONDS], mờ vào
 *  rồi mờ ra mỗi lần [UNDERRUN_FADE_SECONDS] - ngắn hơn chỉ là một tiếng chớp (web 80->12 02-11: vào lại ở 119,5 s, đổi mốc 120 s, mờ ra 121,5 s). Suy từ
 *  các số trên, không phải số để chỉnh; cùng luật với musicmixer.cpp và MusicBed.kt. */
const MIN_ENTRY_SECONDS = DOWNLOAD_LEAD_SECONDS + UNDERRUN_LOW_SECONDS + 2 * UNDERRUN_FADE_SECONDS;
/** Bài tải hỏng (mất mạng): đoạn của nó im lặng, chừng ấy sau mới thử lại - như MusicFailures.RETRY_MS của Android. */
export const RETRY_MS = 5 * 60_000;
/** Mốc đầu chương kế chưa dựng xong (`pending`) hay hỏi hỏng: chừng ấy ms sau mới hỏi lại; cũng là nhịp xin lại trong [NEXT_CHAPTER_LAST_CHANCE_SECONDS]. */
const NEXT_CHAPTER_RETRY_MS = 15_000;
/** Giọng ưu tiên tuyệt đối: chỉ tải sẵn chương kế khi giọng đã sẵn chừng này giây phía trước người nghe (= đệm tối thiểu của giọng, readAloud.ts MIN_BUFFER_SECONDS). */
export const NEXT_CHAPTER_VOICE_SECONDS = 20;
/** Lưới cuối: chương còn chừng này giây thì xin lại bài đầu chương kế mỗi [NEXT_CHAPTER_RETRY_MS] (lần trước hỏng thì lần này tải; đã có thì máy chủ bỏ qua). */
export const NEXT_CHAPTER_LAST_CHANCE_SECONDS = 120;

function cueAt(cues: MusicCue[], seconds: number): MusicCue | null {
  return cues.find((cue) => seconds >= cue.start && seconds < cue.end) ?? null;
}

/** Giây chương mà bài của mốc `cue` thôi kêu: hết chuỗi mốc liền nhau cùng bài (bài chơi tiếp qua các mốc ấy, không bắt đầu lại) + thời gian mờ ra
 *  khi mốc kế vào (mốc anh em: [SIBLING_FADE_SECONDS], không thì [FADE_SECONDS]). Mốc `tail` chơi tới hết bài: vô cực. Bài đang tải dở chỉ cần tải
 *  kịp tới chỗ ấy mới vào - bài 863 s mà mốc chỉ dùng 342 s thì không phải chờ tải gần hết bài (musiclogic.h, MusicCues.kt cùng luật). */
export function playEnd(cues: MusicCue[], cue: MusicCue): number {
  let end = cue.end;
  let tail = cue.tail === true;
  for (let grew = true; grew; ) {
    grew = false;
    for (const other of cues) {
      if (other.link === cue.link && other.start <= end + 1e-6 && other.end > end) {
        end = other.end;
        tail ||= other.tail === true;
        grew = true;
      }
    }
  }
  if (tail) return Infinity;
  const next = cues.find((other) => other.link !== cue.link && Math.abs(other.start - end) <= 1e-6);
  return end + (next?.sibling ? SIBLING_FADE_SECONDS : FADE_SECONDS);
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
 *  (P = loopEnd - loopStart - X); phần tử lặp mở ở `loopEnd` - X và phát từ `loopStart` (không có điểm vòng: A và E). `crossfade`
 *  false: bài quá ngắn (E - A < 3X) lặp thường cả file như cũ (A 0, E = P = độ dài). */
export interface LoopBounds {
  start: number;
  end: number;
  period: number;
  crossfade: boolean;
  loopStart: number;
  loopEnd: number;
}

function finite(value: number | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Vòng lặp của bài của mốc `cue`, độ dài thật `duration` (chưa biết: NaN). Chưa biết độ dài lẫn E: bài không bao giờ hết. */
export function loopBounds(cue: Pick<MusicCue, "audibleStart" | "audibleEnd" | "loopStart" | "loopEnd">, duration: number): LoopBounds {
  const total = Number.isFinite(duration) && duration > 0 ? duration : null;
  const start = Math.max(0, finite(cue.audibleStart) ?? 0);
  const audibleEnd = finite(cue.audibleEnd);
  let end = audibleEnd !== null && audibleEnd > 0 ? audibleEnd : total;
  if (end === null) return { start: 0, end: Infinity, period: Infinity, crossfade: false, loopStart: 0, loopEnd: Infinity };
  if (total !== null) end = Math.min(end, total);
  if (end - start < 3 * LOOP_CROSSFADE_SECONDS) {
    const whole = total ?? end;
    return { start: 0, end: whole, period: whole, crossfade: false, loopStart: 0, loopEnd: whole };
  }
  const restart = finite(cue.loopStart);
  const rawOut = finite(cue.loopEnd);
  const out = rawOut === null || total === null || rawOut - LOOP_CROSSFADE_SECONDS > end ? rawOut : Math.min(rawOut, total);
  if (restart !== null && out !== null && start <= restart && restart < out - LOOP_CROSSFADE_SECONDS
      && out - LOOP_CROSSFADE_SECONDS <= end && out - restart - LOOP_CROSSFADE_SECONDS >= LOOP_MIN_PERIOD_SECONDS) {
    return { start, end, period: out - restart - LOOP_CROSSFADE_SECONDS, crossfade: true, loopStart: restart, loopEnd: out };
  }
  return { start, end, period: end - start - LOOP_CROSSFADE_SECONDS, crossfade: true, loopStart: start, loopEnd: end };
}

/** Chỗ trong bài sau `t` >= 0 giây kể từ lúc bài vào từ A (music_mix.loop_position): vòng đầu A + t, sau đó
 *  loopStart + ((t - (loopStart - A)) mod P) - không có điểm vòng thì đúng A + (t mod P) như trước. */
export function loopPosition(bounds: LoopBounds, t: number): number {
  if (!Number.isFinite(bounds.period)) return bounds.start + t;
  if (bounds.crossfade && t < bounds.loopEnd - LOOP_CROSSFADE_SECONDS - bounds.start) return bounds.start + t;
  return bounds.loopStart + ((t - (bounds.loopStart - bounds.start)) % bounds.period);
}

/** Lúc mở các phần tử lặp và lúc nhạc hết của một mốc dài `length` giây mà bài vào từ A ở giây 0 (music_mix.loop_schedule): lượt j
 *  hết tự nhiên (tới E) ở (E - A) + j·P, phần tử kế mở trước đó E - loopEnd + X giây. Mốc `tail`: thôi ở lượt đầu tiên mà phần còn
 *  lại của mốc hơn chỗ bài hết chưa tới nửa chu kỳ (như `finalLoop`), nhạc hết ở E của vòng ấy. */
export function loopSchedule(bounds: LoopBounds, length: number, tail = false): { opens: number[]; end: number } {
  let natural = bounds.end - bounds.start;
  const lead = bounds.end - bounds.loopEnd + LOOP_CROSSFADE_SECONDS;
  const opens: number[] = [];
  if (tail) {
    while (Number.isFinite(natural) && length - natural >= bounds.period / 2) {
      if (bounds.crossfade) opens.push(natural - lead);
      natural += bounds.period;
    }
    return { opens, end: natural };
  }
  while (bounds.crossfade && natural - lead < length) {
    opens.push(natural - lead);
    natural += bounds.period;
  }
  return { opens, end: length };
}

/** Chỗ trong bài ứng với giây `seconds` của chương (`loopPosition` từ đầu mốc) - vào giữa chương hay tua thì nhạc cũng ở giữa
 *  bài, không chạy lại từ đầu (soát a26 L8). */
export function alignedPosition(cue: MusicCue, seconds: number, bounds: LoopBounds): number {
  return loopPosition(bounds, Math.max(0, seconds - cue.start));
}

/** Phần tử đang kêu ở `currentTime` đã tới loopEnd - X: lúc mở phần tử lặp mới từ loopStart. */
export function loopDue(bounds: LoopBounds, currentTime: number): boolean {
  return bounds.crossfade && currentTime >= bounds.loopEnd - LOOP_CROSSFADE_SECONDS;
}

/** Nhịp đồng bộ với giọng của máy tính (`timeupdate` tới 250 ms): mốc hẹn giờ vào bản lặp tính theo nhịp này ([loopHandoffDelay]). */
export const SYNC_TICK_SECONDS = 0.25;
/** Lệch pha tối đa (giây) giữa bản lặp mới và bản cũ mà tai không nghe ra: dưới mức này không sửa pha ([loopDrift]). */
export const LOOP_DRIFT_TOLERANCE_SECONDS = 0.02;
/** Bản mới còn nhỏ hơn tỷ lệ này của âm lượng đích thì dời nó không ai nghe thấy ([MusicBed.fixHandoffDrift]). */
const LOOP_DRIFT_QUIET = 0.1;
/** Còn dưới chừng này giây tới hạn vào bản lặp thì tạo SẴN phần tử lặp ([MusicBed.prepareStandby]): đo thật máy tính, phần tử mới mất 53 ms (bài dài 601 ms, `mseAudio` tải + nạp
 *  cả file) mới có tiếng - tạo sẵn thì tới hạn chỉ còn `play()` (PLAN_loop §34-35). */
const LOOP_STANDBY_SECONDS = 3;
/** Hẹn giờ nổ mà bài cũ còn thiếu chút ít tới hạn (đồng hồ bài lệch đồng hồ máy) vẫn tính là tới hạn. */
const LOOP_TIMER_SLACK_SECONDS = 0.05;

/** Phần còn lại (giây, nhạc chạy 1x) tới lúc phải mở bản lặp (loopEnd - X) mà bài cũ đang ở `oldPos`, nếu nhỏ hơn 1,5 nhịp đồng bộ
 *  `tickSeconds` (lần đồng bộ kế có thể đến muộn hơn hạn nên phải hẹn giờ); 0 khi đã quá hạn; null khi chưa cần hẹn (hay bài không mờ chéo). */
export function loopHandoffDelay(bounds: LoopBounds, oldPos: number, tickSeconds: number): number | null {
  if (!bounds.crossfade) return null;
  const rem = bounds.loopEnd - LOOP_CROSSFADE_SECONDS - oldPos;
  if (rem <= 0) return 0;
  return rem < 1.5 * tickSeconds ? rem : null;
}

/** Chỗ bản lặp mới phải vào khi bài cũ đang ở `oldPos`: loopStart cộng phần đã trễ so với hạn loopEnd - X (bù độ trễ của lần đồng bộ). */
export function loopStartAt(bounds: LoopBounds, oldPos: number): number {
  return bounds.loopStart + Math.max(0, oldPos - (bounds.loopEnd - LOOP_CROSSFADE_SECONDS));
}

/** Bản mới đi chậm bao nhiêu giây so với bản cũ (dương = chậm): (cũ - (loopEnd - X)) - (mới - loopStart). Dời bản mới thêm đúng số này
 *  là hai bản cùng pha (bù độ trễ mở trình phát). */
export function loopDrift(bounds: LoopBounds, oldPos: number, newPos: number): number {
  return (oldPos - (bounds.loopEnd - LOOP_CROSSFADE_SECONDS)) - (newPos - bounds.loopStart);
}

/** Mốc `tail` đang ở vòng cuối: phần còn lại của mốc hơn phần còn lại của bài (tới E) chưa tới nửa chu kỳ - không mở phần tử lặp
 *  nữa, bài chơi (qua loopEnd) tới E là hết (lô 1, tính theo E thay vì độ dài file). Chưa biết độ dài bài: chưa phải. */
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
  /** Bài đang tải dở sắp hụt ([bufferedAhead] < [UNDERRUN_LOW_SECONDS]): đang mờ ra, tới 0 thì tạm dừng tại chỗ, chờ cổng như bài mới. */
  starving?: boolean;
  /** Cổng của bài đang tải dở: "wait" = tạm dừng ở chỗ vào, chờ phát được tới chỗ bài thôi kêu ([playsThrough]); "open" = đã qua. */
  gate?: "wait" | "open";
  pace?: DownloadPace;
}

/** Tốc độ tải (giây bài mỗi giây đồng hồ) của một bài đang tải dở - như StreamPace.kt của Android và DownloadRate của musicmixer.cpp. */
export class DownloadPace {
  private samples: [number, number][] = [];
  private began = -1;
  private lastNow = 0;
  private lastFrom = 0;
  /** Dự báo / thực tế lớn nhất đã thấy ở tầm một cửa sổ; null khi chưa đo đủ 2 cửa sổ. */
  private worst: number | null = null;

  /** `have`: giây bài đã tải liền tới (tính từ đầu bài), `from`: con trỏ phát, lúc `now` (ms). Phần đã tải lùi hay con trỏ nhảy (tua, dời chỗ vào): đo lại
   *  từ đầu - không thì cú nhảy của phần đã tải bị tính là tải được (StreamPace.kt, emulator 02-11). */
  add(now: number, have: number, from: number): void {
    const last = this.samples[this.samples.length - 1];
    const jumped = this.began >= 0 && (from < this.lastFrom - 0.05 || from > this.lastFrom + (now - this.lastNow) / 1000 + 1);
    if (this.began < 0 || jumped || (last && have < last[1] - 0.05)) {
      this.began = now;
      this.samples = [];
      this.worst = null;
    }
    this.lastNow = now;
    this.lastFrom = from;
    if (now - this.began < DOWNLOAD_BURST_SECONDS * 1000) this.samples = [];
    this.samples.push([now, have]);
    // Giữ hai cửa sổ (một mẫu ngay trước làm mốc đầu): cửa sổ trước là dự báo, cửa sổ sau là thực tế của dự báo ấy.
    const window = DOWNLOAD_WINDOW_SECONDS * 1000;
    while (this.samples.length > 2 && now - this.samples[1][0] > 2 * window) this.samples.shift();
    if (this.samples[0][0] <= now - 2 * window) {
      const at = (t: number) => this.samples.reduce((got, sample) => (sample[0] <= t ? sample[1] : got), this.samples[0][1]);
      const forecast = at(now - window) - at(now - 2 * window);
      const real = have - at(now - window);
      const ratio = real > 0 ? forecast / real : forecast > 0 ? Infinity : 1;
      this.worst = Math.max(this.worst ?? 1, ratio);
    }
  }

  /** Lề chia tốc độ đo được ([playsThrough]): dự báo theo trung bình trượt từng hụt tới đâu so với cái đã tới thật một cửa sổ sau, lấy lần tệ nhất, không
   *  quá [DOWNLOAD_MARGIN]. Chưa đo đủ 2 cửa sổ thì là [DOWNLOAD_MARGIN]. Đường đều (máy đo bóp tốc độ, cáp) co về ~1: bài vào sớm hơn; đường dao động
   *  mạnh giữ đúng [DOWNLOAD_MARGIN] - 76 vết HSDPA thật (Riiser 2013) mô phỏng đều chạm trần, nghe và hụt y như lề cố định (02-11). */
  margin(): number {
    return this.worst === null ? DOWNLOAD_MARGIN : Math.min(DOWNLOAD_MARGIN, this.worst);
  }

  /** Trung bình trượt tính tới `now` (nguồn đứng thì tụt dần về 0); null khi chưa đo đủ 1 giây. */
  rate(now: number): number | null {
    let first = this.samples[0];
    for (const sample of this.samples) if (now - sample[0] > DOWNLOAD_WINDOW_SECONDS * 1000) first = sample;
    if (!first) return null;
    const span = now - first[0];
    if (span < 1000) return null;
    return ((this.samples[this.samples.length - 1][1] - first[1]) * 1000) / span;
  }
}

/** Phát từ giây `from` tới giây `end` của bài (chỗ bài thôi kêu: min(độ dài, [playEnd])) mà không hụt, nếu tốc độ tải giữ ở `rate` chia `margin`
 *  ([DownloadPace.margin]; không biết thì lề trần): đã tải `have` + rate/lề·t, phát tới from + t - cả hai tuyến tính theo t, nên chỉ cần đúng bây giờ (có sẵn [DOWNLOAD_LEAD_SECONDS]) và lúc tới `end`. Đã tải
 *  tới `end` thì qua luôn. Chưa đo được tốc độ: chưa chắc, coi như không. */
export function playsThrough(have: number, from: number, end: number, rate: number | null, margin = DOWNLOAD_MARGIN): boolean {
  if (have >= end - 0.05) return true;
  return have - from >= DOWNLOAD_LEAD_SECONDS && rate !== null && rate > 0 && ((end - have) / rate) * margin <= end - from;
}

/** Giây đã tải trước con trỏ phát của bài đang tải dở (<audio src>, hay phần đã nạp vào MediaSource); null = đã tải trọn, hay phần tử không cho biết (bản giả). */
function bufferedAhead(audio: BedAudio): number | null {
  const ranges = audio.buffered;
  if (!ranges || !Number.isFinite(audio.duration) || audio.duration <= 0) return null;
  for (let i = 0; i < ranges.length; i += 1) {
    if (ranges.start(i) <= audio.currentTime + 0.05 && audio.currentTime <= ranges.end(i)) {
      return ranges.end(i) >= audio.duration - 0.05 ? null : ranges.end(i) - audio.currentTime;
    }
  }
  return 0;
}

/** Bài nằm sẵn trong sách: cuốn mở từ file `.abook` mang bài trong gói, máy chủ đưa qua `/music/files/` (server.py music_cues) - không có gì để xin
 *  máy chủ tải sẵn (soát a61: mở `.abook` ở máy mới vẫn tải danh mục + bài 6,4 MB mà gói đã có). */
export function carriedByBook(cue: Pick<MusicCue, "src">): boolean {
  return cue.src.includes("/music/files/");
}

/** Hỏi mốc chương kế rồi xin tải sẵn bài mốc ĐẦU của nó ngay từ khi chương này đã biết độ dài: chương mới mở bằng bài đã nằm trong bộ đệm của máy chủ, không
 *  im lặng chờ tải (đo 15,5 giây trung vị, PLAN_lx §2). Không đợi tới hai phút cuối: nguồn bài chậm (incompetech 30 KB/s, đo 01-11) thì bài 6 MB mất hơn 3 phút.
 *  Giọng trước: chỉ hỏi / xin khi giọng đã sẵn [NEXT_CHAPTER_VOICE_SECONDS] phía trước. Một lượt mỗi lúc; chương kế chưa dựng xong / hỏi hỏng thì hỏi lại sau
 *  [NEXT_CHAPTER_RETRY_MS]. [NEXT_CHAPTER_LAST_CHANCE_SECONDS] cuối chương: xin lại mỗi [NEXT_CHAPTER_RETRY_MS] (máy chủ bỏ qua bài đã có / đang tải). */
export class NextChapterWarm {
  /** Vé đã có lời đáp -> link bài đầu chương kế (null: chương kế không có nhạc / bài sách mang theo). */
  private done = new Map<string, string | null>();
  private asking: string | null = null;
  private retryAt = new Map<string, number>();

  constructor(
    private readonly ask: (chapterId: number) => Promise<MusicCues>,
    private readonly warm: (link: string) => void,
    private readonly now: () => number = Date.now,
  ) {}

  /** Gọi mỗi nhịp thời gian. `key`: chương đang nghe (cuốn:chương); `next`: mã chương kế (null = hết cuốn); `remaining`: giây còn lại của chương, <= 0 khi chưa biết;
   *  `voiceAhead`: giây giọng đã sẵn phía trước người nghe (AudioEngine.voiceAhead; chương audio: Infinity). */
  update(key: string, next: number | null, remaining: number, voiceAhead = Infinity): void {
    if (next === null || !(remaining > 0) || !(voiceAhead >= NEXT_CHAPTER_VOICE_SECONDS)) return;
    const ticket = `${key}>${next}`;
    if (this.asking !== null || (this.retryAt.get(ticket) ?? 0) > this.now()) return;
    if (this.done.has(ticket)) {
      const link = this.done.get(ticket);
      if (!link || remaining > NEXT_CHAPTER_LAST_CHANCE_SECONDS) return;
      this.retryAt.set(ticket, this.now() + NEXT_CHAPTER_RETRY_MS);
      this.warm(link);
      return;
    }
    this.asking = ticket;
    const later = () => this.retryAt.set(ticket, this.now() + NEXT_CHAPTER_RETRY_MS);
    this.ask(next).then(
      (result) => {
        const first = result.pending ? undefined : result.cues[0];
        if (first) {
          const link = carriedByBook(first) ? null : first.link;
          this.done.set(ticket, link);
          if (link) {
            later(); // lưới cuối không xin lại ngay sau lần đầu
            this.warm(link);
          }
        } else if (result.pending || result.unavailable) {
          later();
        } else {
          this.done.set(ticket, null); // chương kế không có nhạc
        }
      },
      later,
    ).finally(() => {
      if (this.asking === ticket) this.asking = null;
    });
  }
}

export class MusicBed {
  /** `warm`: xin máy chủ tải sẵn một bài ([ListenSource.musicWarm]); không có thì không tải sẵn. */
  constructor(private readonly createAudio: (src: string) => BedAudio = browserAudio, private readonly warm?: (link: string) => void) {}

  private cues: MusicCue[] = [];
  private gain = 0.1;
  private userVolume = 1;
  private playing = false;
  private current: Playing | null = null;
  private fading: BedAudio[] = [];
  // âm lượng bớt mỗi nhịp khi mờ đi: bài to và bài nhỏ cùng tắt trong FADE_SECONDS (SIBLING_FADE_SECONDS khi nối bài anh em)
  private fadeStep = new WeakMap<BedAudio, number>();
  // Phần tử đã [release]: lỗi muộn của nó không được tính là "bài hỏng".
  private released = new WeakSet<BedAudio>();
  private timer: ReturnType<typeof setInterval> | null = null;
  // Vé hẹn giờ vào bản lặp (một vòng một vé): tua, đổi bài, dừng thì huỷ.
  private loopTicket: ReturnType<typeof setTimeout> | null = null;
  // Phần tử lặp tạo sẵn cho vòng hiện tại (bước 0): chưa play, âm lượng 0, đứng ở loopStart. Tua, đổi bài, dừng thì nhả.
  private standby: { audio: BedAudio; owner: BedAudio; place: { at: number } } | null = null;
  private lastTime = 0;
  private listeners = new Set<(link: string | null) => void>();
  private loadListeners = new Set<(link: string, ok: boolean) => void>();
  private announced: string | null = null;
  // Bài không phát được (`link` của mốc) -> lúc được thử lại (Date.now()); tải được thì xoá.
  private failed = new Map<string, number>();
  // Phần tử đã phát ra tiếng thật (sự kiện `playing`): trước đó bài mới giữ âm lượng 0, bài cũ mờ như thường (PLAN_lx F1b).
  private sounded = new WeakSet<BedAudio>();
  // Bài đã xin tải sẵn trong phiên này (mỗi bài một lần; mốc tới nơi mà chưa có thì chính phần tử <audio> của nó tải và tự thử lại).
  private warmed = new Set<string>();

  /** Xin máy chủ tải sẵn bài `link` (một lần mỗi phiên). Chỉ bài danh mục (https): bài của người dùng không tải ở đâu cả. */
  warmLink(link: string): void {
    if (!this.warm || !link.startsWith("https://") || this.warmed.has(link)) return;
    this.warmed.add(link);
    this.warm(link);
  }

  /** Bài của mốc kế tiếp (khác bài đang kêu) tải sẵn trong lúc bài này chơi: sang mốc không phải chờ mạng (Android: MusicBed.kt prefetchNext). */
  private warmNext(sounding: MusicCue | null, seconds: number): void {
    const next = this.cues.find((cue) => cue.start > seconds && cue.link !== sounding?.link);
    if (next && !carriedByBook(next)) this.warmLink(next.link);
  }

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
    const playing = this.current;
    if (!playing) return;
    playing.goal = this.target();
    if (this.awaitingSound(playing)) playing.perTick = (playing.goal * STEP_MS) / 1000 / playing.fadeSeconds; // chưa có tiếng: giữ 0
    else playing.audio.volume = playing.goal;
  }

  /** Bài mới còn đang chờ tải (chưa có sự kiện `playing`, `readyState` < 4 - trình duyệt chưa ước tải kịp tới hết bài, hay bài đang tải dở chưa qua
   *  cổng [playsThrough] - đã qua thì readyState 3 là đủ): chưa được nhích âm lượng lên - bài cũ đứng ở mức đang có ([startFade]), thay vì bài mới
   *  vào rồi hụt giữa chừng hay "vào đột ngột" ở đủ mức ngay khi tải xong. */
  private awaitingSound(playing: Playing): boolean {
    const { audio } = playing;
    if (!playing.entering || typeof audio.readyState !== "number") return false;
    if (playing.gate === "wait") return true;
    return !(this.sounded.has(audio) && (audio.readyState >= 4 || (playing.gate === "open" && audio.readyState >= 3)));
  }

  /** Gọi mỗi khi thời gian giọng đọc đổi (`seeked` = người nghe vừa tua). `ended`: giọng dừng vì tự hết chương / hết cuốn chứ không phải
   *  người nghe - nhạc mờ ra như khi đổi đoạn thay vì tắt phụt cùng giọng. */
  sync(seconds: number, playing: boolean, seeked = false, ended = false): void {
    this.lastTime = seconds;
    this.playing = playing;
    if (!playing && ended) {
      // Giọng tự hết (cuối chương, sang chương kế hay hết cuốn): bài đang kêu mờ ra trong FADE_SECONDS, các bài đang mờ mờ nốt - không dừng
      // cùng giọng (bản Qt 0.4.152 rơi -30 -> -91 dB trong 6 ms, soát 01-11). Chương kế vào thì bài của nó mờ vào đè lên.
      if (this.current) this.switchTo(null, seconds);
      return;
    }
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
    // Bài đang tải dở: đồng hồ mờ canh hụt mỗi nhịp (đã tắt khi bài vào xong thì bật lại).
    if (playing && this.current && bufferedAhead(this.current.audio) !== null) this.startFade();
    // Chỉ bài đang kêu được chơi lại; bài đang mờ đi (đổi cuốn / chương lúc đã tạm dừng) thì chỉ dừng cùng giọng - chơi lại nó là mở một bài đã bỏ (soát a45).
    for (const audio of [this.current?.audio, ...this.fading]) {
      if (!audio) continue;
      if (playing && audio.paused && !audio.ended && audio === this.current?.audio && this.current.gate !== "wait") void audio.play().catch(() => undefined);
      // Luôn pause, kể cả phần tử đang `paused` (bài còn đang tải qua mseAudio giữ ý định phát: pause() mới huỷ nó, không thì tải xong nhạc tự kêu khi giọng đã dừng).
      if (!playing) audio.pause();
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
    this.cancelLoopTicket();
    this.cancelStandby();
    for (const audio of [this.current?.audio, ...this.fading]) if (audio) this.release(audio);
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
    if (this.released.has(audio)) return;
    this.failed.set(cue.link, Date.now() + RETRY_MS);
    if (this.current?.audio === audio) {
      this.cancelLoopTicket();
      this.cancelStandby();
    }
    this.release(audio);
    this.fading = this.fading.filter((other) => other !== audio);
    if (this.current?.audio === audio) {
      this.current = null;
      this.emitActive();
    }
    for (const listener of [...this.loadListeners]) listener(cue.link, false);
  }

  /** Phần tử <audio> đã hết dùng (mờ xong, bài hỏng, dừng): dừng RỒI bỏ nguồn và nạp lại. Chỉ `pause()` thì trình duyệt vẫn giữ kết nối tải bài của phần tử (đọc dở hay dừng giữa chừng),
   *  và nó tính vào 6 kết nối mỗi máy chủ: a56, bấm sang chương mới trong lúc hai bài của chương trước còn đang tải (25-46 giây mỗi bài lần đầu), bốn lượt xin clip + hai bài cũ + bài mới
   *  chiếm hết chỗ - clip tiêu đề đã có mà fetch() lấy file âm thanh phải chờ 2,6 giây trong trình duyệt. */
  private release(audio: BedAudio): void {
    audio.pause();
    this.released.add(audio);
    audio.dispose?.();
    audio.removeAttribute?.("src");
    audio.load?.();
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

  /** Lặp mờ chéo: phần tử đang kêu tới loopEnd - X thì một phần tử MỚI của chính bài vào từ loopStart, mờ chéo LOOP_CROSSFADE_SECONDS; phần
   *  tử cũ mờ đi rồi dừng. Vòng cuối của mốc `tail` (`finishTail`) và bài quá ngắn (lặp thường) thì không. Chưa tới hạn mà sắp tới (dưới 1,5 nhịp
   *  đồng bộ): hẹn giờ đúng lúc ([loopHandoffDelay]) thay vì chờ lần đồng bộ kế, vì `timeupdate` đến muộn tới 250 ms làm bản mới lệch pha với bản
   *  cũ suốt lúc mờ chéo (PLAN_loop §29-32). Vào muộn thì mở bản mới ở chỗ đã bù ([loopStartAt]). `fromTimer`: lần chạy do vé nổ. */
  private crossLoop(seconds: number, fromTimer = false): void {
    this.cancelLoopTicket();
    const playing = this.current;
    if (!playing || playing.final || seconds >= playing.cue.end || !(playing.audio.duration > 0)) {
      this.cancelStandby();
      return;
    }
    const bounds = loopBounds(playing.cue, playing.audio.duration);
    const at = playing.audio.currentTime;
    if (!loopDue(bounds, at) && !(fromTimer && !playing.audio.paused && at >= bounds.loopEnd - LOOP_CROSSFADE_SECONDS - LOOP_TIMER_SLACK_SECONDS)) {
      if (bounds.crossfade && bounds.loopEnd - LOOP_CROSSFADE_SECONDS - at < LOOP_STANDBY_SECONDS) this.prepareStandby(playing, bounds);
      else this.cancelStandby();
      // Vé nổ mà chưa tới hạn (bài đứng chờ tải): không hẹn lại, lần đồng bộ kế hẹn tiếp.
      if (!fromTimer && !playing.audio.paused) this.armLoopTicket(playing.audio, loopHandoffDelay(bounds, at, SYNC_TICK_SECONDS));
      return;
    }
    const old = playing.audio;
    this.fadeStep.set(old, (Math.max(old.volume, 0.01) * STEP_MS) / 1000 / LOOP_CROSSFADE_SECONDS);
    this.fading.push(old);
    const ready = this.standby?.owner === old ? this.standby : undefined;
    if (!ready) this.cancelStandby();
    this.standby = null; // phần tử sẵn (nếu có) thành bản mới: từ đây là của this.current
    this.current = { ...this.open(playing.cue, seconds, LOOP_CROSSFADE_SECONDS, loopStartAt(bounds, at), { old, bounds }, ready), early: playing.early };
    this.startFade();
  }

  /** Bước 0: tạo SẴN phần tử lặp của vòng hiện tại (một lần mỗi vòng) - đứng ở loopStart, âm lượng 0, chưa `play()`; tới hạn `crossLoop` chỉ còn phát nó. */
  private prepareStandby(playing: Playing, bounds: LoopBounds): void {
    if (this.standby?.owner === playing.audio) return;
    this.cancelStandby();
    const place = { at: bounds.loopStart };
    const audio = this.spawn(playing.cue, this.lastTime, place, { old: playing.audio, bounds });
    this.standby = { audio, owner: playing.audio, place };
  }

  /** Nhả phần tử lặp tạo sẵn (tua, đổi bài, dừng, chương mới, bài hỏng): lỗi muộn của nó không còn tính là bài hỏng ([drop] bỏ qua phần tử đã nhả). */
  private cancelStandby(): void {
    const standby = this.standby;
    if (!standby) return;
    this.standby = null;
    this.release(standby.audio);
  }

  private cancelLoopTicket(): void {
    if (this.loopTicket === null) return;
    globalThis.clearTimeout(this.loopTicket);
    this.loopTicket = null;
  }

  /** Hẹn một lần sau `delay` giây (null = chưa cần) để `audio` (bài đang kêu) vào bản lặp; vé nổ mà bài đã đổi thì thôi. */
  private armLoopTicket(audio: BedAudio, delay: number | null): void {
    if (delay === null) return;
    this.loopTicket = globalThis.setTimeout(() => {
      this.loopTicket = null;
      if (this.current?.audio === audio) this.crossLoop(this.lastTime, true);
    }, delay * 1000);
  }

  /** Sửa pha một lần cho bản lặp mới `audio` khi nó vừa có tiếng (bù độ trễ mở trình phát): bản mới còn gần như câm nên cú dời không nghe thấy.
   *  Bài cũ đã dừng hay đã mờ hết thì không còn gì để theo. */
  private fixHandoffDrift(audio: BedAudio, cue: MusicCue, handoff: { old: BedAudio; bounds: LoopBounds }): void {
    const { old, bounds } = handoff;
    if (this.released.has(audio) || this.released.has(old) || old.paused || !this.fading.includes(old)) return;
    if (audio.volume > LOOP_DRIFT_QUIET * this.target(cue)) return;
    const drift = loopDrift(bounds, old.currentTime, audio.currentTime);
    if (Math.abs(drift) > LOOP_DRIFT_TOLERANCE_SECONDS) audio.currentTime = Math.max(0, audio.currentTime + drift);
  }

  /** Đặt bài `audio` của mốc `cue` vào đúng chỗ ứng với giây `seconds` của chương (`alignedPosition`). Chưa biết độ dài bài thì
   *  chờ `loadedmetadata`. */
  private align(audio: BedAudio, cue: MusicCue, seconds: number): void {
    if (audio.duration > 0) audio.currentTime = alignedPosition(cue, seconds, loopBounds(cue, audio.duration));
  }

  /** Một phần tử <audio> của mốc `cue` với các hàm nghe, chưa `play()`, âm lượng 0. `place` (phần tử lặp): vào đúng chỗ ấy (loopStart + phần trễ, [loopStartAt]), không
   *  căn theo giây chương - đồng hồ bài lệch giọng vài phần giây thì căn lại có khi rơi về cuối vòng; `place.at` đổi được tới lúc `loadedmetadata` (vào muộn). `handoff`
   *  (phần tử lặp): bản cũ để sửa pha khi có tiếng ([fixHandoffDrift]). */
  private spawn(cue: MusicCue, seconds: number, place?: { at: number }, handoff?: { old: BedAudio; bounds: LoopBounds }): BedAudio {
    const audio = this.createAudio(cue.src);
    audio.loop = !loopBounds(cue, audio.duration).crossfade;
    audio.volume = 0;
    if (place) audio.currentTime = place.at; // chưa có metadata: trình duyệt nhớ làm chỗ bắt đầu
    audio.addEventListener("loadedmetadata", () => {
      this.failed.delete(cue.link);
      audio.loop = !loopBounds(cue, audio.duration).crossfade && !(this.current?.audio === audio && this.current.final);
      // Bài tải xong sau khi giọng đã chạy tiếp (hay vừa tua): theo giây mới nhất, không phải giây lúc tạo bài.
      if (!place) this.align(audio, cue, this.current?.audio === audio ? this.lastTime : seconds);
      else if (Math.abs(audio.currentTime - place.at) > 0.25) audio.currentTime = place.at;
      for (const listener of [...this.loadListeners]) listener(cue.link, true);
      if (this.current?.audio === audio && bufferedAhead(audio) !== null) this.startFade(); // tải dở: cổng [playsThrough] tạm dừng nó ngay ở chỗ vào
    }, { once: true });
    audio.addEventListener("error", () => {
      if (this.released.has(audio)) return;
      // Phần tử tạo sẵn hỏng trước khi dùng: bỏ nó, tới hạn tạo cái mới - không tính là bài hỏng.
      if (this.standby?.audio === audio) this.cancelStandby();
      else this.drop(cue, audio);
    }, { once: true });
    audio.addEventListener("playing", () => {
      this.sounded.add(audio);
      if (handoff) this.fixHandoffDrift(audio, cue, handoff);
      if (this.current?.audio === audio) this.startFade(); // phần tử đã chờ tiếng: bây giờ mới mờ vào
    }, { once: true });
    return audio;
  }

  /** Một phần tử <audio> mới của mốc `cue` (hay `ready`: phần tử lặp đã tạo sẵn ở [prepareStandby], vào muộn thì đặt lại tới `startAt`), mờ vào trong `fadeSeconds` giây. */
  private open(cue: MusicCue, seconds: number, fadeSeconds: number, startAt?: number, handoff?: { old: BedAudio; bounds: LoopBounds },
               ready?: { audio: BedAudio; place: { at: number } }): Playing {
    let audio: BedAudio;
    if (ready && startAt !== undefined) {
      audio = ready.audio;
      ready.place.at = startAt;
      if (Math.abs(audio.currentTime - startAt) > 0.001) audio.currentTime = startAt;
    } else {
      audio = this.spawn(cue, seconds, startAt === undefined ? undefined : { at: startAt }, handoff);
    }
    const goal = this.target(cue);
    if (this.playing) void audio.play().catch(() => undefined);
    return { cue, audio, goal, perTick: (goal * STEP_MS) / 1000 / fadeSeconds, entering: true, fadeSeconds };
  }

  private switchTo(cue: MusicCue | null, seconds: number, seeked = false): void {
    this.warmNext(cue, seconds);
    if (seeked || !(this.current && cue && this.current.cue.link === cue.link)) {
      this.cancelLoopTicket();
      this.cancelStandby();
    }
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
        const ahead = bufferedAhead(audio);
        if (ahead !== null) {
          // Còn tải dở: đo tốc độ, chờ cổng / canh hụt mỗi nhịp.
          const now = Date.now();
          const pace = (playing.pace ??= new DownloadPace());
          pace.add(now, audio.currentTime + ahead, audio.currentTime);
          // Chỉ cần tải kịp tới chỗ bài thôi kêu (tính lại mỗi nhịp: giọng chậm / khựng thì chỗ ấy dời theo).
          const end = Math.min(audio.duration, audio.currentTime + playEnd(this.cues, playing.cue) - this.lastTime);
          const through = playsThrough(audio.currentTime + ahead, audio.currentTime, end, pace.rate(now), pace.margin());
          if (this.playing) busy = true;
          if (playing.entering && playing.gate !== "open" && audio.volume <= 0) {
            // Chưa có tiếng: đứng yên ở chỗ vào (phát câm thì chỗ vào trôi đi 1 giây mỗi giây, tải chậm hơn 1x không bao giờ đuổi kịp). Sát chỗ thôi kêu
            // thì giữ im luôn ([MIN_ENTRY_SECONDS]).
            const enter = through && end - audio.currentTime >= MIN_ENTRY_SECONDS;
            playing.gate = enter ? "open" : "wait";
            if (!enter && !audio.paused) audio.pause();
            else if (enter && this.playing && audio.paused && !audio.ended) void audio.play().catch(() => undefined);
          } else if (!playing.starving && !audio.paused && audio.volume > 0 && ahead < UNDERRUN_LOW_SECONDS && !through) {
            playing.starving = true;
          }
        } else if (playing.gate === "wait") {
          playing.gate = "open"; // vừa tải trọn
          if (this.playing && audio.paused && !audio.ended) void audio.play().catch(() => undefined);
        }
        if (playing.starving) {
          audio.volume = Math.max(0, audio.volume - (Math.max(goal, 0.01) * STEP_MS) / 1000 / UNDERRUN_FADE_SECONDS);
          if (audio.volume <= 0) {
            // Đã im: tạm dừng tại chỗ, chờ cổng như bài mới, rồi mờ vào trong UNDERRUN_FADE_SECONDS.
            playing.starving = false;
            playing.entering = true;
            playing.gate = "wait";
            playing.fadeSeconds = UNDERRUN_FADE_SECONDS;
            playing.perTick = (goal * STEP_MS) / 1000 / UNDERRUN_FADE_SECONDS;
            audio.pause();
          }
          busy = true;
        } else if (audio.volume < goal && this.awaitingSound(playing)) {
          // Bài chưa có tiếng: giữ 0. Đang chạy mà chưa đủ dữ liệu thì canh tiếp; còn tạm dừng thì chờ `playing` gọi lại (khỏi giữ đồng hồ chạy không).
          if (!audio.paused) busy = true;
        } else {
          if (audio.volume < goal) audio.volume = Math.min(goal, audio.volume + move);
          else if (audio.volume > goal) audio.volume = Math.max(goal, audio.volume - move);
          if (Math.abs(audio.volume - goal) < 1e-4) playing.entering = false;
          else busy = true;
        }
      }
      // Bài mới còn chờ tải: bài cũ đứng ở mức đang có, không để cảnh câm suốt thời gian tải; bài mới có tiếng thì mờ tiếp.
      const holdOld = playing !== null && this.playing && this.awaitingSound(playing);
      this.fading = this.fading.filter((audio) => {
        // Bài cũ đang tải dở sắp hết phần đã tải (giữ chỗ quá chỗ thôi kêu của nó): thôi giữ, mờ hết trong UNDERRUN_FADE_SECONDS - mờ thường dài hơn
        // phần còn lại thì vẫn im phụt giữa chừng.
        const ahead = bufferedAhead(audio);
        const low = ahead !== null && ahead < UNDERRUN_LOW_SECONDS && !audio.paused;
        if (low) this.fadeStep.set(audio, Math.max(this.fadeStep.get(audio) ?? 0, (Math.max(audio.volume, 0.01) * STEP_MS) / 1000 / UNDERRUN_FADE_SECONDS));
        if (holdOld && !low && !audio.ended && !audio.paused) {
          busy = true;
          return true;
        }
        audio.volume = Math.max(0, audio.volume - (this.fadeStep.get(audio) ?? (0.1 * STEP_MS) / 1000 / FADE_SECONDS));
        if (audio.volume <= 0.001) {
          this.release(audio);
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
