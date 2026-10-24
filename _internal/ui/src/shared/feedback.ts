// Phản hồi giác quan của giao diện (DESIGN.md 5.3 âm thanh, 5.4 rung): MỘT chỗ cho mọi tiếng chạm và mọi cú rung.
// Tiếng tự tổng hợp bằng Web Audio (không file thu âm), cùng một âm sắc "đồng thau gõ nhẹ", ngắn <= 250 ms, ~ -24 dB. Tiếng tự im khi sách
// đang phát - trừ báo hẹn giờ ngủ sắp tắt. Rung chỉ trên điện thoại: android/main.tsx nối `haptic` tới EbookPlayer.haptic (Haptics.kt chọn
// hằng số cũ hơn khi máy chưa có). Máy tính không rung. Chỉ gọi cho việc NGƯỜI DÙNG vừa làm; không cho tiến độ chạy, sự kiện nền, tự cuộn,
// hẹn giờ ngủ tắt.

export type FeedbackKind = "tap" | "toggle" | "tick" | "confirm" | "done" | "sleepWarn" | "reject" | "longPress" | "playPause";

/** Tên hằng số HapticFeedbackConstants mà lõi native hiểu (Haptics.kt). */
export type HapticEffect = "CONTEXT_CLICK" | "CLOCK_TICK" | "SEGMENT_TICK" | "LONG_PRESS" | "CONFIRM" | "REJECT" | "GESTURE_THRESHOLD_ACTIVATE";

/** Bảng 5.4. null = không rung (hẹn giờ ngủ: người nghe có thể đã ngủ). */
export const HAPTICS: Readonly<Record<FeedbackKind, HapticEffect | null>> = {
  tap: "CONTEXT_CLICK",
  toggle: "SEGMENT_TICK",
  tick: "CLOCK_TICK",
  confirm: "CONFIRM",
  done: "CONFIRM",
  sleepWarn: null,
  reject: "REJECT",
  longPress: "LONG_PRESS",
  playPause: "CONTEXT_CLICK",
};

interface Note {
  /** Hz */
  pitch: number;
  /** giây kể từ lúc bấm */
  at: number;
  /** giây tới khi tắt hẳn */
  length: number;
  /** dB so với mức đầy */
  level: number;
}

const C6 = 1046.5;
const E6 = 1318.5;
const G6 = 1568;
const A3 = 220;

/** Bảng 5.3. null = không tiếng: nút thường, phát/dừng (lời đọc tự báo), chạm giữ, lỗi (chữ + rung thay tiếng). */
export const SOUNDS: Readonly<Record<FeedbackKind, readonly Note[] | null>> = {
  tap: null,
  toggle: [{ pitch: G6, at: 0, length: 0.06, level: -30 }],
  tick: [{ pitch: E6, at: 0, length: 0.04, level: -32 }],
  confirm: [
    { pitch: C6, at: 0, length: 0.12, level: -24 },
    { pitch: E6, at: 0.09, length: 0.16, level: -24 },
  ],
  done: [
    { pitch: C6, at: 0, length: 0.1, level: -24 },
    { pitch: E6, at: 0.08, length: 0.1, level: -24 },
    { pitch: G6, at: 0.16, length: 0.09, level: -24 },
  ],
  sleepWarn: [{ pitch: A3, at: 0, length: 0.25, level: -22 }],
  reject: null,
  longPress: null,
  playPause: null,
};

/** Dòng mô tả công tắc "Âm thanh chạm" (Cài đặt > Giao diện, cả hai nền tảng). */
export const TOUCH_SOUNDS_HINT = "Tiếng khẽ khi bạn chọn. Im khi đang nghe.";

interface FeedbackOptions {
  /** Cài đặt > Giao diện > "Âm thanh chạm" (mặc định bật). */
  sounds: boolean;
  /** Cài đặt > Giao diện > "Rung" (mặc định bật; chỉ điện thoại). */
  haptics: boolean;
  /** Cầu xuống lõi native; null trên máy tính. */
  haptic: ((effect: HapticEffect) => unknown) | null;
}

const options: FeedbackOptions = { sounds: true, haptics: true, haptic: null };
let bookPlaying = false;
let audio: AudioContext | null = null;
let timbre: PeriodicWave | null = null;

export function configureFeedback(next: Partial<FeedbackOptions>): void {
  Object.assign(options, next);
}

/** Trình phát báo sách đang phát / đã dừng (listen/player.tsx): đang phát thì tiếng chạm im. */
export function setBookPlaying(playing: boolean): void {
  bookPlaying = playing;
}

/** Bọc một việc người dùng bấm: phản hồi trước, rồi làm việc ấy (onClick={withFeedback("playPause", toggle)}). */
export function withFeedback<A extends unknown[]>(kind: FeedbackKind, action: (...args: A) => unknown): (...args: A) => void {
  return (...args) => {
    feedback(kind);
    action(...args);
  };
}

export function feedback(kind: FeedbackKind): void {
  const effect = HAPTICS[kind];
  if (effect && options.haptics && options.haptic) {
    try {
      void Promise.resolve(options.haptic(effect)).catch(() => undefined);
    } catch {
      /* lõi native không trả lời: bỏ qua cú rung */
    }
  }
  const notes = SOUNDS[kind];
  if (notes && options.sounds && (!bookPlaying || kind === "sleepWarn")) play(notes);
}

function context(): AudioContext | null {
  if (audio) return audio;
  const scope = globalThis as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
  const Context = scope.AudioContext ?? scope.webkitAudioContext;
  if (!Context) return null;
  try {
    audio = new Context();
  } catch {
    return null;
  }
  // Âm sắc "đồng thau gõ nhẹ": cơ bản + vài hoạ âm giảm dần (bậc 2-3 đậm như kèn đồng, bậc cao rất nhẹ cho khỏi chói).
  const harmonics = [0, 1, 0.55, 0.35, 0.18, 0.08];
  timbre = audio.createPeriodicWave(new Float32Array(harmonics.length), new Float32Array(harmonics));
  return audio;
}

function play(notes: readonly Note[]): void {
  const ctx = context();
  if (!ctx) return;
  if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);
  const start = ctx.currentTime + 0.005;
  for (const note of notes) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    if (timbre) osc.setPeriodicWave(timbre);
    osc.frequency.value = note.pitch;
    const at = start + note.at;
    const peak = 10 ** (note.level / 20);
    // Gõ: lên trong 4 ms, tắt theo hàm mũ - không đuôi kéo dài, không nảy.
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(peak, at + 0.004);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + note.length);
    osc.connect(gain).connect(ctx.destination);
    osc.start(at);
    osc.stop(at + note.length + 0.02);
  }
}

/** Kéo thanh tua qua một mốc (mỗi `step` giây, hay chạm đầu / cuối chương) - lúc rung "tích" (5.4 CLOCK_TICK). Chỉ gọi khi đang kéo. */
export function crossedSeekMark(from: number, to: number, duration: number, step: number): boolean {
  if (from === to) return false;
  const edge = (value: number) => value <= 0 || (duration > 0 && value >= duration);
  if (edge(to)) return !edge(from);
  return Math.floor(from / step) !== Math.floor(to / step);
}

/** Chỉ cho bài thử: về trạng thái đầu. */
export function resetFeedbackForTest(): void {
  Object.assign(options, { sounds: true, haptics: true, haptic: null });
  bookPlaying = false;
  audio = null;
  timbre = null;
}
