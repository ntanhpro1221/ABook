import type { ReadAloudVoice } from "./readAloud";

// Giọng trực tuyến gửi chữ của sách ra ngoài máy: hỏi MỘT lần, TRƯỚC khi đoạn đầu tiên được gửi (soát UX 03-10 - trước đây chỉ có một
// thông báo hiện ra sau khi chữ đã đi). "Nghe" (mặc định) là đồng ý và nhớ cho nhà cung cấp ấy, không hỏi lại; "Chọn giọng khác" mở danh sách
// giọng ngay trong hộp. Nhớ theo NHÀ CUNG CẤP (provider của giọng), không theo giọng: đồng ý gửi chữ cho Microsoft không phải đồng ý gửi cho
// dịch vụ khác. Máy tính và điện thoại dùng chung (trình phát hỏi trước khi bắt đầu phát chương chỉ có chữ - player.tsx).

const KEY = "abook-readaloud-online-ok";

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
}

/** Có phải hỏi trước khi đọc bằng giọng này không. */
export function needsOnlineConsent(voice: ReadAloudVoice | undefined): voice is ReadAloudVoice {
  return Boolean(voice?.online) && !onlineConsentGiven(voice!.provider);
}

/** Tên giọng như người nghe gọi: "Hoài My (Edge)" -> "Hoài My". */
export function spokenVoiceName(name: string): string {
  return name.replace(/\s*\([^)]*\)\s*$/, "").trim() || name;
}

/** Lời hỏi trong hộp. */
export function onlinePromptText(voice: Pick<ReadAloudVoice, "name" | "provider">): string {
  const company = COMPANIES[voice.provider];
  const name = spokenVoiceName(voice.name);
  return company
    ? `Giọng ${name} là giọng trực tuyến của ${company}: chữ của đoạn đang đọc được gửi tới ${company} để đọc.`
    : `Giọng ${name} là giọng trực tuyến: chữ của đoạn đang đọc được gửi tới dịch vụ ngoài để đọc.`;
}

// ---- hộp hỏi đang mở (một lúc một hộp) -------------------------------------------------------------------------

export interface ConsentRequest {
  voice: ReadAloudVoice;
  voices: ReadAloudVoice[];
  /** Mã giọng sẽ dùng (giọng đang hỏi, hay giọng khác vừa chọn trong hộp); null: người nghe đóng hộp - không phát. */
  answer: (voiceId: string | null) => void;
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

/** Hỏi người nghe; xong thì trả mã giọng sẽ đọc (đã nhớ đồng ý nếu giọng ấy trực tuyến), hay null nếu người nghe đóng hộp. Đang có hộp mở thì
 *  hộp cũ coi như bị đóng. */
export function askOnlineConsent(voice: ReadAloudVoice, voices: ReadAloudVoice[]): Promise<string | null> {
  current?.answer(null);
  return new Promise((resolve) => {
    const request: ConsentRequest = {
      voice,
      voices,
      answer: (voiceId) => {
        if (current !== request) return;
        const picked = voices.find((item) => item.id === voiceId);
        // Chọn một giọng trực tuyến trong danh sách ngay dưới lời hỏi cũng là đồng ý cho nhà cung cấp ấy.
        if (picked?.online) giveOnlineConsent(picked.provider);
        publish(null);
        resolve(picked ? picked.id : null);
      },
    };
    publish(request);
  });
}
