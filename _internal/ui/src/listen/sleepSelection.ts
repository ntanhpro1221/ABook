import type { SleepRequest } from "./sleep";

export interface SleepSelection {
  request: SleepRequest;
  window?: string;
  retained?: boolean;
  disabledWindow?: string;
}

const key = (book: string, record?: string) => `abook.sleep-selection:${JSON.stringify([book, record ?? ""])}`;

export function saveSleepSelection(book: string, record: string | undefined, value: SleepSelection): void {
  localStorage.setItem(key(book, record), JSON.stringify(value));
}

/** Only the chosen mode is durable. A fresh player always starts with a full, paused cycle. */
export function readSleepSelection(book: string, record: string | undefined, window: string | null): SleepSelection {
  const off: SleepSelection = { request: { kind: "off" } };
  try {
    const value = JSON.parse(localStorage.getItem(key(book, record)) ?? "null") as SleepSelection | null;
    if (!value || (value.window !== undefined && value.window !== window)) return off;
    const r = value.request;
    if (r?.kind === "off") return { request: { kind: "off" }, disabledWindow: value.disabledWindow };
    if (r?.kind === "minutes" && Number.isInteger(r.minutes) && r.minutes >= 1 && r.minutes <= 240) return value;
    if (r?.kind === "chapter" && Number.isInteger(r.chapters ?? 1) && (r.chapters ?? 1) >= 1 && (r.chapters ?? 1) <= 10) return value;
  } catch { /* An unavailable or damaged preference never prevents playback. */ }
  return off;
}
