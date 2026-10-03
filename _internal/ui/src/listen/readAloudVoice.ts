import { toast } from "sonner";
import { VOICE_CHANGED_EVENT, type ClipFetcher, type ClipOptions, type ReadAloudClip, type ReadAloudVoice } from "./readAloud";
import type { ListenSource } from "./source";

// Giọng đọc của "Nghe ngay": nhớ lựa chọn theo từng cuốn (+ một lựa chọn chung cho cuốn mới), chọn giọng mặc định, và bọc việc lấy clip với hai
// việc người nghe cần biết: giọng trực tuyến gửi chữ ra ngoài máy (nói một lần), và mất mạng thì rơi sang giọng của máy mà không dừng.

const GLOBAL_KEY = "abook-readaloud-voice";
const NOTICE_KEY = "abook-readaloud-online-notice";
export const ONLINE_NOTICE = "Giọng trực tuyến gửi chữ của sách tới Microsoft để đọc.";
export const FALLBACK_NOTICE = "Không dùng được giọng trực tuyến - tạm đọc bằng giọng của máy.";
/** Lý do mà giọng của máy đỡ được: dịch vụ trực tuyến không với tới / không chạy. Chữ không đọc được (`empty`) hay giọng không có (`voice`) thì không. */
const FALLBACK_REASONS = new Set(["offline", "timeout", "rejected", "service"]);

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

/** Giọng dùng thật: giọng đã chọn nếu còn trong danh sách, không thì giọng mặc định, không thì giọng đầu tiên. */
export function resolveVoice(voices: ReadAloudVoice[], chosen: string): ReadAloudVoice | undefined {
  return voices.find((voice) => voice.id === chosen) ?? voices.find((voice) => voice.default) ?? voices[0];
}

let fellBack = false; // lời nhắn rơi sang giọng máy: một lần cho cả phiên, không mỗi chương một lần

let known = new WeakMap<ListenSource, Promise<ReadAloudVoice[]>>();

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

/** Bộ lấy clip cho trình phát: giọng theo lựa chọn của người nghe; giọng trực tuyến hỏng vì mạng thì rơi sang giọng của máy cho đúng clip ấy
 *  (không dừng), nói một lần. `notify`: chỗ hiện lời nhắn (mặc định toast). */
export function speechFetcher(source: ListenSource, bookId: string, notify: (message: string) => void = (message) => void toast(message, { duration: 8000 })): ClipFetcher {
  const fetchWith = async (voice: ReadAloudVoice, text: string, options?: ClipOptions): Promise<ReadAloudClip> => {
    const clip = await source.readAloudClip!(voice.id, text, options);
    return { ...clip, gainDb: voice.gainDb ?? clip.gainDb };
  };
  return async (requested, text, options) => {
    if (!source.readAloudClip) throw new Error("Máy này chưa có giọng đọc.");
    const voices = await voicesOf(source);
    const voice = resolveVoice(voices, requested || chosenVoice(bookId));
    if (!voice) throw new Error("Máy này chưa có giọng đọc.");
    if (voice.online && !options?.cachedOnly && read(NOTICE_KEY) !== "1") {
      write(NOTICE_KEY, "1");
      notify(ONLINE_NOTICE);
    }
    try {
      return await fetchWith(voice, text, options);
    } catch (error) {
      const reason = (error as { reason?: string }).reason ?? "";
      const device = voices.find((item) => !item.online);
      if (!voice.online || options?.cachedOnly || !device || !FALLBACK_REASONS.has(reason)) throw error;
      if (!fellBack) {
        fellBack = true;
        notify(FALLBACK_NOTICE);
      }
      return fetchWith(device, text, options);
    }
  };
}
