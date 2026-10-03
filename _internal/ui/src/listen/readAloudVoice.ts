import { toast } from "sonner";
import { VOICE_CHANGED_EVENT, type ClipFetcher, type ClipOptions, type ReadAloudClip, type ReadAloudVoice } from "./readAloud";
import type { ListenSource } from "./source";

// Giọng đọc của "Nghe ngay": nhớ lựa chọn theo từng cuốn (+ một lựa chọn chung cho cuốn mới), chọn giọng mặc định, và bọc việc lấy clip với hai
// việc người nghe cần biết: giọng trực tuyến gửi chữ ra ngoài máy (nói một lần), và giọng ấy hỏng (mất mạng, khoá bị từ chối, hết hạn mức) thì
// rơi sang giọng kế - Edge rồi giọng của máy - mà không dừng.

const GLOBAL_KEY = "abook-readaloud-voice";
export const ONLINE_NOTICE = "Giọng trực tuyến gửi chữ của sách tới Microsoft để đọc.";
export const FALLBACK_NOTICE = "Không dùng được giọng trực tuyến - tạm đọc bằng giọng của máy.";
/** Sự kiện: người dùng vừa đổi khoá của giọng dùng khoá riêng (Cài đặt) - danh sách giọng phải hỏi lại. */
export const ONLINE_KEYS_CHANGED_EVENT = "abook:readaloud-online-keys";
/** Lý do mà giọng kế đỡ được: dịch vụ trực tuyến không với tới / không chạy, hay khoá của người dùng bị từ chối / hết hạn mức. Chữ không đọc
 *  được (`empty`) hay giọng không có (`voice`) thì không. */
const FALLBACK_REASONS = new Set(["offline", "timeout", "rejected", "service", "auth", "quota"]);
/** Tên nhà cung cấp của giọng dùng khoá riêng (abook/readaloud/byok.py, điện thoại OnlineVoices.kt). */
export const KEYED_PROVIDERS: Record<string, string> = { azure: "Azure Speech", google: "Google Cloud", fpt: "FPT.AI", viettel: "Viettel AI" };

/** Câu nói rõ chữ của sách đi đâu khi chọn giọng này (giọng dùng khoá: kèm việc có thể bị tính tiền vào tài khoản của người dùng). */
export function onlineNotice(voice: Pick<ReadAloudVoice, "provider" | "online">): string {
  const keyed = KEYED_PROVIDERS[voice.provider];
  if (keyed) return `Giọng ${keyed} gửi chữ của sách tới ${keyed} bằng khóa của bạn - có thể bị tính tiền vào tài khoản của bạn.`;
  return voice.online ? ONLINE_NOTICE : "";
}

function read(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* không nhớ được thì thôi */
  }
}

/** Giọng đã chọn cho cuốn này; chưa chọn thì giọng chung; chưa có gì thì "" (= mặc định của máy). */
export function chosenVoice(bookId: string): string {
  return read(`abook-readaloud-voice-${bookId}`) || read(GLOBAL_KEY);
}

/** Chọn giọng cho cuốn (và làm giọng chung cho cuốn khác chưa chọn); chương đang đọc đổi giọng từ đoạn kế. */
export function chooseVoice(bookId: string, voice: string): void {
  write(`abook-readaloud-voice-${bookId}`, voice);
  write(GLOBAL_KEY, voice);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(VOICE_CHANGED_EVENT, { detail: bookId }));
}

/** Người dùng bấm đổi giọng (giọng VieNeu không kịp nghe trên máy này): mọi cuốn đang chọn giọng có mã bắt đầu bằng `fromPrefix`, và lựa chọn
 *  chung, chuyển sang `voice`. Chỉ khi người dùng bấm - không bao giờ tự đổi. */
export function switchVoices(fromPrefix: string, voice: string): void {
  try {
    for (let index = localStorage.length - 1; index >= 0; index--) {
      const key = localStorage.key(index) ?? "";
      if (key.startsWith("abook-readaloud-voice-") && (localStorage.getItem(key) ?? "").startsWith(fromPrefix)) localStorage.setItem(key, voice);
    }
  } catch {
    /* không đọc được bộ nhớ: vẫn đổi lựa chọn chung */
  }
  write(GLOBAL_KEY, voice);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(VOICE_CHANGED_EVENT, { detail: "" }));
}

/** Giọng mặc định cho cuốn chưa chọn giọng riêng (Cài đặt → Giọng đọc); "" = mặc định của máy. */
export function defaultVoice(): string {
  return read(GLOBAL_KEY);
}

/** Đặt giọng mặc định từ Cài đặt: chỉ đổi giọng chung, cuốn đã chọn giọng riêng giữ nguyên (không báo trình phát đổi giọng giữa chừng). */
export function chooseDefaultVoice(voice: string): void {
  write(GLOBAL_KEY, voice);
}

/** Câu đọc thử ("Thử giọng" trong Cài đặt): ngắn, có dấu câu để nghe cả chỗ ngắt. */
export const SAMPLE_TEXT = "Xin chào, tôi sẽ đọc sách cho bạn nghe. Bạn thấy giọng này thế nào?";

/** Giọng dùng thật: giọng đã chọn nếu còn trong danh sách, không thì giọng mặc định, không thì giọng đầu tiên. */
export function resolveVoice(voices: ReadAloudVoice[], chosen: string): ReadAloudVoice | undefined {
  return voices.find((voice) => voice.id === chosen) ?? voices.find((voice) => voice.default) ?? voices[0];
}

let fellBack = false; // lời nhắn rơi sang giọng máy: một lần cho cả phiên, không mỗi chương một lần
const told = new Set<string>(); // lời nhắn của giọng dùng khoá: một lần mỗi (nhà cung cấp, lý do) cho cả phiên
const benched = new Map<string, string>(); // nhà cung cấp có khoá bị từ chối / hết hạn mức: các đoạn sau đi thẳng sang giọng kế

let known = new WeakMap<ListenSource, Promise<ReadAloudVoice[]>>();
if (typeof window !== "undefined") {
  window.addEventListener(ONLINE_KEYS_CHANGED_EVENT, () => {
    known = new WeakMap();
    benched.clear();
  });
}

/** Danh sách giọng của máy vừa đổi (tải xong giọng VieNeu): hỏi lại ở lần sau. */
export function forgetVoices(): void {
  known = new WeakMap();
}

/** Danh sách giọng của nguồn (nhớ cho cả phiên; lần hỏi hỏng thì hỏi lại lần sau). */
export function voicesOf(source: ListenSource): Promise<ReadAloudVoice[]> {
  if (!source.readAloudVoices) return Promise.resolve([]);
  let promise = known.get(source);
  if (!promise) {
    promise = source.readAloudVoices().catch(() => {
      known.delete(source);
      return [];
    });
    known.set(source, promise);
  }
  return promise;
}

/** Giọng đỡ khi `voice` hỏng, theo thứ tự: giọng dùng khoá -> giọng Edge mặc định -> giọng của máy; Edge -> giọng của máy. */
export function fallbackChain(voices: ReadAloudVoice[], voice: ReadAloudVoice): ReadAloudVoice[] {
  if (!voice.online) return [];
  const edges = voices.filter((item) => item.provider === "edge");
  const edge = edges.find((item) => item.default) ?? edges[0];
  const device = voices.find((item) => !item.online);
  return [voice.provider !== "edge" ? edge : undefined, device].filter((item): item is ReadAloudVoice => Boolean(item) && item!.id !== voice.id);
}

function fallbackNotice(failed: ReadAloudVoice, reason: string, next: ReadAloudVoice): string {
  const keyed = KEYED_PROVIDERS[failed.provider];
  const instead = next.online ? `giọng ${next.name}` : "giọng của máy";
  if (!keyed) return next.online ? `Không dùng được giọng trực tuyến - tạm đọc bằng ${instead}.` : FALLBACK_NOTICE;
  if (reason === "auth") return `Khóa ${keyed} không dùng được - tạm đọc bằng ${instead}. Kiểm tra lại khóa trong Cài đặt.`;
  if (reason === "quota") return `Khóa ${keyed} đã hết hạn mức - tạm đọc bằng ${instead}.`;
  return `Không dùng được giọng ${keyed} lúc này - tạm đọc bằng ${instead}.`;
}

/** Bộ lấy clip cho trình phát: giọng theo lựa chọn của người nghe; giọng trực tuyến hỏng (mạng, dịch vụ, khoá bị từ chối, hết hạn mức) thì
 *  đoạn ấy rơi sang giọng kế (`fallbackChain`) mà không dừng, mỗi chuyện nói một lần. Khoá bị từ chối / hết hạn mức: các đoạn sau đi thẳng sang
 *  giọng kế, không gọi lại vô ích. `notify`: chỗ hiện lời nhắn (mặc định toast). */
export function speechFetcher(source: ListenSource, bookId: string, notify: (message: string) => void = (message) => void toast(message, { duration: 8000 })): ClipFetcher {
  const fetchWith = async (voice: ReadAloudVoice, text: string, options?: ClipOptions): Promise<ReadAloudClip> => {
    const clip = await source.readAloudClip!(voice.id, text, options);
    return { ...clip, gainDb: voice.gainDb ?? clip.gainDb };
  };
  const tell = (failed: ReadAloudVoice, reason: string, next: ReadAloudVoice) => {
    if (!KEYED_PROVIDERS[failed.provider]) {
      if (fellBack) return;
      fellBack = true;
    } else {
      const kind = reason === "auth" || reason === "quota" ? reason : "network";
      if (told.has(`${failed.provider}:${kind}`)) return;
      told.add(`${failed.provider}:${kind}`);
    }
    notify(fallbackNotice(failed, reason, next));
  };
  return async (requested, text, options) => {
    if (!source.readAloudClip) throw new Error("Máy này chưa có giọng đọc.");
    const voices = await voicesOf(source);
    const voice = resolveVoice(voices, requested || chosenVoice(bookId));
    if (!voice) throw new Error("Máy này chưa có giọng đọc.");
    // Báo chữ đi đâu: hộp hỏi TRƯỚC lần đọc đầu (onlineConsent.ts, trình phát) - không nhắc lại ở đây sau khi chữ đã gửi.
    const chain = options?.cachedOnly ? [voice] : [voice, ...fallbackChain(voices, voice)];
    let failed: { voice: ReadAloudVoice; reason: string } | null = null;
    for (const [index, candidate] of chain.entries()) {
      const last = index === chain.length - 1;
      const benchedFor = benched.get(candidate.provider);
      if (benchedFor && !last) {
        failed = { voice: candidate, reason: benchedFor };
        continue;
      }
      if (failed) tell(failed.voice, failed.reason, candidate);
      try {
        return await fetchWith(candidate, text, options);
      } catch (error) {
        const why = (error as { reason?: string }).reason ?? "";
        if (!candidate.online || !FALLBACK_REASONS.has(why) || last) throw error;
        if (KEYED_PROVIDERS[candidate.provider] && (why === "auth" || why === "quota")) {
          benched.set(candidate.provider, why);
          if (why === "auth") known = new WeakMap(); // khoá bị từ chối: giọng ấy thôi hiện ở lần hỏi danh sách sau
        }
        failed = { voice: candidate, reason: why };
      }
    }
    throw new Error("Không có giọng nào đọc được đoạn này.");
  };
}
