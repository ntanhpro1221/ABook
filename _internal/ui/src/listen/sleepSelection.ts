import type { SleepRequest } from "./sleep";

export interface SleepSelection {
  request: SleepRequest;
  window?: string;
  retained?: boolean;
  disabledWindow?: string;
}

const key = (book: string, record?: string) => `abook.sleep-selection:${JSON.stringify([book, record ?? ""])}`;
const disabledNight = "abook.sleep-disabled-window";

export function saveSleepSelection(book: string, record: string | undefined, value: SleepSelection): void {
  const { disabledWindow, ...selection } = value;
  if (disabledWindow !== undefined) localStorage.setItem(disabledNight, disabledWindow);
  localStorage.setItem(key(book, record), JSON.stringify(selection));
}

/** Only the chosen mode is durable. A fresh player always starts with a full, paused cycle. */
export function readSleepSelection(book: string, record: string | undefined, window: string | null): SleepSelection {
  const off: SleepSelection = { request: { kind: "off" } };
  try {
    off.disabledWindow = localStorage.getItem(disabledNight) ?? "";
    const value = JSON.parse(localStorage.getItem(key(book, record)) ?? "null") as SleepSelection | null;
    if (!value || (value.window !== undefined && value.window !== window)) return off;
    const r = value.request;
    if (r?.kind === "off") return off;
    if (r?.kind === "minutes" && Number.isInteger(r.minutes) && r.minutes >= 1 && r.minutes <= 240) return { ...value, disabledWindow: off.disabledWindow };
    if (r?.kind === "chapter" && Number.isInteger(r.chapters ?? 1) && (r.chapters ?? 1) >= 1 && (r.chapters ?? 1) <= 10) return { ...value, disabledWindow: off.disabledWindow };
  } catch { /* An unavailable or damaged preference never prevents playback. */ }
  return off;
}
