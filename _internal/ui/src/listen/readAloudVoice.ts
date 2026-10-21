import { toast } from "sonner";
import { BOOK_STORAGE } from "@/shared/bookStorage";
import { VOICE_CHANGED_EVENT, isTransientClipError, type ClipFetcher, type ClipOptions, type ReadAloudClip, type ReadAloudVoice } from "./readAloud";
import type { ListenSource } from "./source";

// Giọng đọc của "Nghe ngay": nhớ lựa chọn theo từng cuốn (+ một lựa chọn chung cho cuốn mới), chọn giọng mặc định, và bọc việc lấy clip với hai
// việc người nghe cần biết: giọng trực tuyến gửi chữ ra ngoài máy (nói một lần), và giọng ấy hỏng (mất mạng, khoá bị từ chối, hết hạn mức) thì
// rơi sang giọng kế - Edge rồi giọng của máy - mà không dừng.

const GLOBAL_KEY = "abook-readaloud-voice";
/** Sự kiện: người dùng vừa đặt giọng mặc định (Cài đặt → Giọng đọc) - lõi điện thoại nhớ theo (android/readAloud.ts). */
export const DEFAULT_VOICE_EVENT = "abook:readaloud-default-voice";
export const ONLINE_NOTICE = "Giọng Edge gửi chữ của sách tới máy chủ Microsoft để đọc.";
export const FALLBACK_NOTICE = "Không dùng được giọng trực tuyến - tạm đọc bằng giọng của máy.";
/** Sự kiện: người dùng vừa đổi khoá của giọng dùng khoá riêng (Cài đặt) - danh sách giọng phải hỏi lại. */
export const ONLINE_KEYS_CHANGED_EVENT = "abook:readaloud-online-keys";
/** Lý do mà giọng kế đỡ được: dịch vụ trực tuyến không với tới / không chạy, hay khoá của người dùng bị từ chối / hết hạn mức. Chữ không đọc
 *  được (`empty`) hay giọng không có (`voice`) thì không. */
/** Mở đầu chung của thông báo mất mạng ở máy tính và điện thoại (ClipReader.NO_OFFLINE_LEAD): giao diện nhận ra thông báo này nhờ nó để đưa
 *  nút theo tình huống (“Đọc bằng …” nếu đã có giọng chạy trên máy, “Tải giọng VieNeu” nếu chưa) thay cho câu dài. */
export const NO_OFFLINE_LEAD = "Không có mạng - giọng ";
/** Câu ngắn khi mất mạng mà máy không có giọng nào đọc được khi không có mạng. `name`: tên giọng đang chọn. */
export function noOfflineMessage(name: string): string {
  return `${NO_OFFLINE_LEAD}${name} cần mạng.`;
}
/** Bản của lõi điện thoại (ClipReader.NO_OFFLINE_VOICE) chưa biết tên giọng: giao diện thay bằng `noOfflineMessage(tên)`. */
export const NO_OFFLINE_VOICE = "Không có mạng - giọng đang chọn cần mạng.";

export function isNoOfflineVoice(message: string): boolean {
  return message.startsWith(NO_OFFLINE_LEAD);
}

/** Giọng trực tuyến có mạng mà vẫn không đọc được (dịch vụ từ chối, trả lỗi, không phản hồi) và máy không có giọng nào đọc không cần mạng: câu ngắn
 *  nói tên giọng, giao diện đưa cùng đường ra như khi mất mạng. Bản của lõi điện thoại (ClipReader.NO_USABLE_VOICE) chưa kèm tên giọng. */
export function unusableVoiceMessage(name: string): string {
  return `Giọng ${name} đang không dùng được.`;
}
export const NO_USABLE_VOICE = "Giọng đang chọn đang không dùng được.";

/** Lời báo "giọng đang chọn không đọc được và máy không có giọng nào khác" (mất mạng hay giọng hỏng): giao diện đưa nút "Đọc bằng …" / "Tải giọng VieNeu". */
export function isVoiceStuck(message: string): boolean {
  return isNoOfflineVoice(message) || /^Giọng .+ đang không dùng được\.$/.test(message);
}

/** Giọng chạy trên máy (đã tải: VieNeu, Supertonic…; không kể giọng của máy, nó đã tự đỡ) để đổi sang khi mất mạng; cùng giới với giọng đang chọn nếu có. */
export function localVoiceFor(voices: ReadAloudVoice[], current: ReadAloudVoice | undefined): ReadAloudVoice | undefined {
  const local = voices.filter((voice) => !voice.online && voice.provider !== "device");
  return local.find((voice) => current?.gender && voice.gender === current.gender) ?? local[0];
}

const FALLBACK_REASONS = new Set(["offline", "timeout", "rejected", "service", "auth", "quota"]);
/** Giọng trực tuyến có mạng mà hỏng: dịch vụ từ chối (Microsoft đổi giao thức...), trả lỗi, không phản hồi. */
const TROUBLE_REASONS = new Set(["timeout", "rejected", "service"]);
/** Nhà cung cấp vừa hỏng kiểu ấy thì nghỉ chừng này rồi mới thử lại (không để mỗi đoạn, mỗi lần mở sách đập thêm 4 kết nối + thử lại). */
const TROUBLE_MS = 5 * 60_000;
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

const stampKey = (bookId: string) => BOOK_STORAGE.readAloudVoiceAt + bookId;
const voiceKey = (bookId: string) => BOOK_STORAGE.readAloudVoice + bookId;

// Nơi nhận lựa chọn giọng riêng của cuốn để ghi vào hồ sơ nghe (trình phát đăng ký - source.setVoice): máy kia đọc tiếp bằng đúng giọng ấy.
let voiceSink: ((bookId: string, voice: string) => void) | null = null;

/** Đăng ký nơi nhận lựa chọn giọng (một nơi một lúc); trả hàm gỡ. */
export function onVoiceChosen(sink: (bookId: string, voice: string) => void): () => void {
  voiceSink = sink;
  return () => {
    if (voiceSink === sink) voiceSink = null;
  };
}

/** Giọng riêng của cuốn đến từ máy kia qua hồ sơ nghe (`voice`/`voiceAt`, soát a68 lỗi 8): chọn sau lựa chọn ở máy này thì nhận - trừ khi máy này
 *  không có giọng ấy (giọng trên máy chưa tải, khoá nhà cung cấp chưa nhập): giữ giọng của máy này, không báo lỗi. True khi đã nhận. */
export function adoptSyncedVoice(bookId: string, state: { voice?: string; voiceAt?: number } | undefined, available: readonly { id: string }[] | null | undefined): boolean {
  const voice = state?.voice;
  const at = state?.voiceAt ?? 0;
  if (typeof voice !== "string" || !at || at <= Number(read(stampKey(bookId)) || 0)) return false;
  if (voice && !available?.some((item) => item.id === voice)) return false;
  write(voiceKey(bookId), voice);
  write(stampKey(bookId), String(at));
  troubled.clear();
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(VOICE_CHANGED_EVENT, { detail: bookId }));
  return true;
}

/** Giọng đã chọn cho cuốn này; chưa chọn thì giọng chung; chưa có gì thì "" (= mặc định của máy). */
export function chosenVoice(bookId: string): string {
  return read(voiceKey(bookId)) || read(GLOBAL_KEY);
}

/** Chọn giọng cho RIÊNG cuốn này (menu Giọng đọc của trình phát, lời báo, hộp hỏi đồng ý); chương đang đọc đổi giọng từ đoạn kế. Giọng mặc định
 *  của các cuốn khác giữ nguyên - chỉ Cài đặt đổi nó (soát a67: đổi giọng một cuốn lặng lẽ đổi luôn giọng mặc định). */
export function chooseVoice(bookId: string, voice: string): void {
  write(voiceKey(bookId), voice);
  write(stampKey(bookId), String(Date.now() / 1000));
  voiceSink?.(bookId, voice);
  troubled.clear();
  // Lần chọn đầu tiên (chưa có giọng mặc định): cũng làm giọng mặc định, để cuốn thứ hai không bắt người mới chọn lại từ đầu.
  const first = !read(GLOBAL_KEY);
  if (first) write(GLOBAL_KEY, voice);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(VOICE_CHANGED_EVENT, { detail: bookId }));
    if (first) window.dispatchEvent(new CustomEvent(DEFAULT_VOICE_EVENT));
  }
}

/** Người dùng bấm đổi giọng (giọng VieNeu không kịp nghe trên máy này): mọi cuốn đang chọn giọng có mã bắt đầu bằng `fromPrefix`, và lựa chọn
 *  chung, chuyển sang `voice`. Chỉ khi người dùng bấm - không bao giờ tự đổi. */
export function switchVoices(fromPrefix: string, voice: string): void {
  try {
    for (let index = localStorage.length - 1; index >= 0; index--) {
      const key = localStorage.key(index) ?? "";
      if (key.startsWith(BOOK_STORAGE.readAloudVoice) && (localStorage.getItem(key) ?? "").startsWith(fromPrefix)) localStorage.setItem(key, voice);
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
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(DEFAULT_VOICE_EVENT));
}

/** Câu đọc thử ("Thử giọng" trong Cài đặt): ngắn, có dấu câu để nghe cả chỗ ngắt. */
export const SAMPLE_TEXT = "Xin chào, tôi sẽ đọc sách cho bạn nghe. Bạn thấy giọng này thế nào?";

/** Giọng VieNeu kể chuyện TRUNG TÍNH của từng bản (mô-đun tải riêng), theo thứ tự ưu tiên - giọng cho người nghe chưa chọn gì. Không bao giờ lấy
 *  giọng đầu danh sách: ở cả hai bản đó là "Adam bựa" / "Adam" (giọng nam có cá tính, không hợp một lời kể đầu tiên - soát a66: tải Nano xong mọi
 *  cuốn chưa chọn lặng lẽ thành Adam).
 *  - Turbo, chọn từ danh sách giọng của Studio (abook/voice_catalog.py): "Phạm Tuyên" là giọng dẫn truyện mặc định của Studio cho giọng nam (Nam ·
 *    Bắc · Tự nhiên, giọng chuẩn ít vùng miền nhất), "Ngọc Linh" là giọng dẫn truyện mặc định cho giọng nữ (Nữ · Bắc · Kể chuyện), "Thanh Bình"
 *    (Nam · Bắc · Kể chuyện) là giọng kể chuyện chủ sách đã chỉnh trầm xuống cho êm.
 *  - Nano không có giọng nào ở trên: "Ái Hân" (nữ) - cùng giới với giọng mặc định trước khi tải (Edge Hoài My) nên người nghe không thấy đổi giới,
 *    là giọng app đã mời khi mất mạng ("Đọc bằng Ái Hân", localVoiceFor) và giọng đo tốc độ đọc của Nano (abook/readaloud/prepare.py); rồi "Mỹ
 *    Duyên" (nữ, chủ sách giữ nguyên tốc độ khi chấm giọng Studio), "Đức Trí" (nam, giọng dẫn truyện chủ sách chọn ở Studio).
 *  Cùng danh sách ở bản Android (readaloud/NarratorVoice.kt); bộ ví dụ chung tests/fixtures/default_voice. */
export const NARRATOR_VOICES: Record<string, readonly string[]> = {
  turbo: ["Phạm Tuyên", "Ngọc Linh", "Thanh Bình"],
  nano: ["Ái Hân", "Mỹ Duyên", "Đức Trí"],
};

/** Giọng VieNeu mặc định trong `voices` (mã "vieneu:<bản>/<tên>"): giọng ưu tiên của bản ấy, xét theo bậc (bậc 1 của mọi bản rồi mới tới bậc 2;
 *  cùng bậc thì giọng đứng trước trong danh sách); không có thì giọng VieNeu đầu tiên cùng giới `gender` (giới của giọng đang dùng khi chưa có
 *  giọng trên máy - giọng mặc định của máy); không biết giới mới lấy giọng VieNeu đầu danh sách. */
export function narratorVoice(voices: ReadAloudVoice[], gender?: string): ReadAloudVoice | undefined {
  const local = voices.filter((voice) => voice.provider === "vieneu");
  const tierOf = (voice: ReadAloudVoice) => voice.id.slice(voice.id.indexOf(":") + 1, voice.id.indexOf("/"));
  const nameOf = (voice: ReadAloudVoice) => voice.id.slice(voice.id.indexOf("/") + 1).normalize("NFC");
  const ranks = Math.max(0, ...Object.values(NARRATOR_VOICES).map((list) => list.length));
  for (let rank = 0; rank < ranks; rank++) {
    const found = local.find((voice) => NARRATOR_VOICES[tierOf(voice)]?.[rank]?.normalize("NFC") === nameOf(voice));
    if (found) return found;
  }
  return local.find((voice) => gender && voice.gender === gender) ?? local[0];
}

/** Giọng dùng thật: giọng đã chọn nếu còn trong danh sách, không thì giọng mặc định, không thì giọng đầu tiên. Người nghe CHƯA tự chọn giọng nào mà máy đã có
 *  giọng VieNeu thì mặc định là giọng kể chuyện trung tính của VieNeu (`narratorVoice`; đọc ngay trên máy, chữ không rời máy) chứ không phải giọng Edge gửi chữ tới Microsoft (soát UX a15). */
export function resolveVoice(voices: ReadAloudVoice[], chosen: string): ReadAloudVoice | undefined {
  const exact = voices.find((voice) => voice.id === chosen);
  if (exact) return exact;
  const fallback = voices.find((voice) => voice.default) ?? voices[0];
  const local = chosen ? undefined : narratorVoice(voices, fallback?.gender);
  return local ?? fallback;
}

/** Giọng chạy trên máy này (VieNeu, Supertonic, giọng của máy) hay trực tuyến: trình phát xin clip của giọng trên máy lần lượt ([SpeechTrack.serial]); chưa biết giọng thì
 *  như trực tuyến (xin song song, cách cũ). */
export function runsOnThisMachine(voice: Pick<ReadAloudVoice, "online"> | undefined): boolean {
  return voice !== undefined && !voice.online;
}

/** Giọng đang đọc cuốn này, viết cho người nghe thấy ở Thư viện: "Đức Trí (VieNeu)", "Hoài My (Edge)"; giọng của máy (hay chưa biết) thì "Giọng đọc của máy" (như Cài đặt). */
export function voiceCaption(voice: ReadAloudVoice | undefined): string {
  if (!voice || voice.provider === "device") return "Giọng đọc của máy";
  if (/\([^)]*\)\s*$/.test(voice.name)) return voice.name;
  const maker = voice.provider === "edge" ? "Edge" : voice.provider === "vieneu" ? "VieNeu" : voice.provider === "supertonic" ? "Supertonic" : KEYED_PROVIDERS[voice.provider];
  return maker ? `${voice.name} (${maker})` : voice.name;
}

/** Tên giọng đang đọc cuốn `bookId` (giọng đã chọn cho cuốn, không thì mặc định của máy); "" khi máy chưa báo giọng nào. */
export function bookVoiceCaption(voices: ReadAloudVoice[] | undefined, bookId: string): string {
  return voices?.length ? voiceCaption(resolveVoice(voices, chosenVoice(bookId))) : "";
}

let fellBack = false; // lời nhắn rơi sang giọng máy: một lần cho cả phiên, không mỗi chương một lần
const told = new Set<string>(); // lời nhắn của giọng dùng khoá: một lần mỗi (nhà cung cấp, lý do) cho cả phiên
const benched = new Map<string, string>(); // nhà cung cấp có khoá bị từ chối / hết hạn mức: các đoạn sau đi thẳng sang giọng kế
const troubled = new Map<string, { reason: string; until: number }>(); // nhà cung cấp (không dùng khoá) vừa từ chối / lỗi / không phản hồi: nghỉ TROUBLE_MS

let known = new WeakMap<ListenSource, Promise<ReadAloudVoice[]>>();
if (typeof window !== "undefined") {
  window.addEventListener(ONLINE_KEYS_CHANGED_EVENT, () => {
    known = new WeakMap();
    benched.clear();
    troubled.clear();
  });
}

/** Người nghe bấm "Thử lại" (hay đổi giọng): quên các giọng đã bị cho là hỏng, lần đọc kế gọi lại dịch vụ thật. */
export function forgetVoiceTrouble(): void {
  troubled.clear();
}

function troubleOf(provider: string): string | undefined {
  const found = troubled.get(provider);
  if (!found) return undefined;
  if (found.until <= Date.now()) {
    troubled.delete(provider);
    return undefined;
  }
  return found.reason;
}

/** Danh sách giọng của máy vừa đổi (tải xong giọng VieNeu): hỏi lại ở lần sau. */
export function forgetVoices(): void {
  known = new WeakMap();
  troubled.clear();
}

const watching = new Set<string>();

/** Mô-đun giọng trên máy `key` đang tải / tự đo: hỏi `poll()` (true = còn đang làm) mỗi `everyMs` cho tới khi xong rồi quên danh sách giọng
 *  (`forgetVoices`) và gọi `done()` - sống cả phiên, không theo thẻ trong Cài đặt: rời Cài đặt giữa lúc tải thì trình phát vẫn thấy giọng mới
 *  ngay khi tải xong (soát a69: chỉ còn Edge tới lúc mở lại app). Một mô-đun một vòng hỏi; hỏi hỏng thì hỏi tiếp, thưa hơn. */
export function watchVoiceModule(key: string, poll: () => Promise<boolean>, done: () => void, everyMs = 1000): void {
  if (watching.has(key)) return;
  watching.add(key);
  const tick = async () => {
    let working: boolean;
    try {
      working = await poll();
    } catch {
      setTimeout(() => void tick(), everyMs * 5);
      return;
    }
    if (working) {
      setTimeout(() => void tick(), everyMs);
      return;
    }
    watching.delete(key);
    forgetVoices();
    done();
  };
  setTimeout(() => void tick(), everyMs);
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
    const clip = await source.readAloudClip!(voice.id, text, { ...options, bookId });
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
      // Lần hỏi mới (đoạn đã hết lần thử lại, hay người nghe vừa tới đoạn ấy): quên lệnh nghỉ của giọng này, gọi dịch vụ thật - nó có thể đã khoẻ lại từ lâu.
      if (options?.fresh && !KEYED_PROVIDERS[candidate.provider]) troubled.delete(candidate.provider);
      const troubleNow = troubleOf(candidate.provider);
      const benchedFor = benched.get(candidate.provider) ?? troubleNow;
      if (benchedFor && !last) {
        failed = { voice: candidate, reason: benchedFor };
        continue;
      }
      const shortName = voice.name.replace(/\s*\([^)]*\)\s*$/, "").trim() || voice.name;
      // Giọng này vừa hỏng và không còn giọng nào đọc không cần mạng: nói ngay, không gọi lại dịch vụ ở mỗi đoạn.
      if (last && troubleNow && !options?.cachedOnly && chain.every((item) => item.online)) {
        throw Object.assign(new Error(unusableVoiceMessage(shortName)), { reason: troubleNow, final: true });
      }
      if (failed) tell(failed.voice, failed.reason, candidate);
      try {
        return await fetchWith(candidate, text, options);
      } catch (error) {
        // Bộ máy sẽ tự thử lại lỗi thoáng qua này (Edge cắt lượt / bận / chậm): chưa vội coi giọng là hỏng, cho nghỉ 5 phút hay rơi sang giọng khác - ném lỗi gốc lên, lần thử cuối
        // (`willRetry` tắt) mới xử lý như dưới đây.
        if (options?.willRetry && !(options.retryBefore !== undefined && Date.now() >= options.retryBefore) && candidate.online && !options.cachedOnly && isTransientClipError(error)) throw error;
        const why = (error as { reason?: string }).reason ?? "";
        if (candidate.online && TROUBLE_REASONS.has(why) && !KEYED_PROVIDERS[candidate.provider] && !options?.cachedOnly) {
          troubled.set(candidate.provider, { reason: why, until: Date.now() + TROUBLE_MS });
        }
        if (last && !options?.cachedOnly && chain.every((item) => item.online)) {
          if (why === "offline") throw Object.assign(new Error(noOfflineMessage(shortName)), { reason: "offline", final: true });
          if (TROUBLE_REASONS.has(why)) throw Object.assign(new Error(unusableVoiceMessage(shortName)), { reason: why, final: true });
        }
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
