import type { ReadAloudVoice } from "./readAloud";
import { KEYED_PROVIDERS } from "./readAloudVoice";

// Giọng trực tuyến gửi chữ của sách ra ngoài máy: hỏi MỘT lần, TRƯỚC khi đoạn đầu tiên được gửi (soát UX 03-10 - trước đây chỉ có một
// thông báo hiện ra sau khi chữ đã đi). "Nghe" (mặc định) là đồng ý và nhớ cho nhà cung cấp ấy, không hỏi lại; "Chọn giọng khác" mở danh sách
// giọng ngay trong hộp. Nhớ theo NHÀ CUNG CẤP (provider của giọng), không theo giọng: đồng ý gửi chữ cho Microsoft không phải đồng ý gửi cho
// dịch vụ khác. Máy tính và điện thoại dùng chung (trình phát hỏi trước khi bắt đầu phát chương chỉ có chữ - player.tsx).

const KEY = "abook-readaloud-online-ok";
/** Phát khi người nghe vừa đồng ý cho một nhà cung cấp: lõi Android cần biết để tự sang chương chữ (android/readAloud.ts). */
export const ONLINE_CONSENT_EVENT = "abook-readaloud-online-ok";

/** Tên công ty của các nhà cung cấp giọng trực tuyến đã biết (nhà cung cấp lạ: nói chung "dịch vụ ngoài"). */
const COMPANIES: Record<string, string> = { edge: "Microsoft" };

function agreed(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

/** Các nhà cung cấp người nghe đã đồng ý gửi chữ tới. */
export function onlineConsents(): string[] {
  return agreed();
}

/** Người nghe đã đồng ý gửi chữ cho nhà cung cấp này. */
export function onlineConsentGiven(provider: string): boolean {
  return agreed().includes(provider);
}

export function giveOnlineConsent(provider: string): void {
  const list = agreed();
  if (list.includes(provider)) return;
  try {
    localStorage.setItem(KEY, JSON.stringify([...list, provider]));
  } catch {
    /* không nhớ được thì lần sau hỏi lại */
  }
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(ONLINE_CONSENT_EVENT));
}

/** Có phải hỏi trước khi đọc bằng giọng này không. */
export function needsOnlineConsent(voice: ReadAloudVoice | undefined): voice is ReadAloudVoice {
  return Boolean(voice?.online) && !onlineConsentGiven(voice!.provider);
}

/** Tên giọng như người nghe gọi: "Hoài My (Edge)" -> "Hoài My". */
export function spokenVoiceName(name: string): string {
  return name.replace(/\s*\([^)]*\)\s*$/, "").trim() || name;
}

/** Chữ đi tới đâu khi đọc bằng giọng trực tuyến của nhà cung cấp này: "FPT.AI" (khoá của người nghe), "máy chủ Microsoft", hay "dịch vụ ngoài". */
export function onlineDestination(provider: string): string {
  const keyed = KEYED_PROVIDERS[provider];
  if (keyed) return keyed;
  const company = COMPANIES[provider];
  return company ? `máy chủ ${company}` : "dịch vụ ngoài";
}

/** Lời hỏi trong hộp. */
export function onlinePromptText(voice: Pick<ReadAloudVoice, "name" | "provider">): string {
  const name = spokenVoiceName(voice.name);
  const where = onlineDestination(voice.provider);
  if (KEYED_PROVIDERS[voice.provider]) return `Giọng ${name} dùng khoá ${where} của bạn: chữ của đoạn đang đọc được gửi tới ${where} để đọc, và dịch vụ có thể tính tiền vào tài khoản của bạn.`;
  // Người nghe biết giọng này là "Edge"; chữ đi tới đâu thì vẫn nói thật: máy chủ của công ty.
  return COMPANIES[voice.provider]
    ? `Giọng ${name} là giọng ${voice.provider === "edge" ? "Edge" : "trực tuyến"}: chữ của đoạn đang đọc được gửi tới ${where} để đọc.`
    : `Giọng ${name} là giọng trực tuyến: chữ của đoạn đang đọc được gửi tới ${where} để đọc.`;
}

/** Lời trong bước "Chọn giọng đọc": đúng với danh sách đang hiện - chỉ nói "không gửi chữ" khi trong đó có giọng chạy trên máy,
 *  còn giọng trực tuyến thì nói rõ chữ được gửi tới đâu (cùng lời với hộp hỏi). `current`: giọng đang được hỏi. */
export function chooseVoiceText(voices: readonly Pick<ReadAloudVoice, "online">[], current: Pick<ReadAloudVoice, "name" | "provider">): string {
  const hasLocal = voices.some((item) => !item.online);
  const hasOnline = voices.some((item) => item.online);
  const local = "Giọng của máy đọc ngay trên máy này, không gửi chữ đi đâu.";
  if (!hasOnline) return local;
  return hasLocal ? `${local} ${onlinePromptText(current)}` : onlinePromptText(current);
}

// ---- hộp hỏi đang mở (một lúc một hộp) -------------------------------------------------------------------------

export interface ConsentRequest {
  voice: ReadAloudVoice;
  voices: ReadAloudVoice[];
  /** Mã giọng sẽ dùng (giọng đang hỏi, hay giọng vừa chọn trong hộp); null: người nghe đóng hộp - không phát. `chosen`: người nghe chọn giọng ấy
   *  trong danh sách "Chọn giọng khác" (kể cả chọn lại đúng giọng đang hỏi) - khác "Nghe", là lựa chọn giọng cho cuốn. */
  answer: (voiceId: string | null, chosen?: boolean) => void;
}

/** Trả lời của hộp hỏi: giọng sẽ đọc + người nghe có tự chọn nó trong danh sách không (trình phát nhớ lựa chọn ấy cho cuốn). */
export interface ConsentAnswer {
  voice: string;
  chosen: boolean;
}

let current: ConsentRequest | null = null;
const listeners = new Set<() => void>();

function publish(next: ConsentRequest | null) {
  current = next;
  listeners.forEach((listener) => listener());
}

export function subscribeConsent(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function pendingConsent(): ConsentRequest | null {
  return current;
}

/** Hỏi người nghe; xong thì trả giọng sẽ đọc (đã nhớ đồng ý nếu giọng ấy trực tuyến), hay null nếu người nghe đóng hộp. Đang có hộp mở thì
 *  hộp cũ coi như bị đóng. */
export function askOnlineConsent(voice: ReadAloudVoice, voices: ReadAloudVoice[]): Promise<ConsentAnswer | null> {
  current?.answer(null);
  return new Promise((resolve) => {
    const request: ConsentRequest = {
      voice,
      voices,
      answer: (voiceId, chosen = false) => {
        if (current !== request) return;
        const picked = voices.find((item) => item.id === voiceId);
        // Chọn một giọng trực tuyến trong danh sách ngay dưới lời hỏi cũng là đồng ý cho nhà cung cấp ấy.
        if (picked?.online) giveOnlineConsent(picked.provider);
        publish(null);
        resolve(picked ? { voice: picked.id, chosen } : null);
      },
    };
    publish(request);
  });
}

/** Chọn `voice` từ menu "Giọng đọc" LÚC ĐANG NGHE: giọng trực tuyến chưa được đồng ý thì hỏi TRƯỚC (đổi giọng đã làm đoạn kế gửi đi ngay - soát a79 lỗi 2). Trả mã giọng sẽ
 *  dùng (giọng vừa bấm, hay giọng người nghe chọn lại trong hộp), hay null nếu người nghe đóng hộp - khi đó không đổi gì. */
export async function pickVoiceWithConsent(voice: ReadAloudVoice, voices: ReadAloudVoice[]): Promise<string | null> {
  if (!voice.online || onlineConsentGiven(voice.provider)) return voice.id;
  const picked = await askOnlineConsent(voice, voices);
  return picked ? picked.voice : null;
}
