import { api } from "@/studio/api";

export const AUTO_SLEEP_SAFETY = "Tự hẹn vì lâu không dùng máy";
export const AUTO_SLEEP_SCHEDULE = "Tự hẹn theo lịch đêm";
export const AUTO_SLEEP_CONTINUE = "Chạm để nghe tiếp";
export const NIGHT_IDLE_MS = 120_000;
export type AutoSleepReason = "safety" | "schedule";

/** The browser cannot observe input in other apps. Unknown OS evidence disables automatic timers. */
export function automaticSleepAllowed(osIdleMs: number | null, appIdleMs: number, requiredMs: number): boolean {
  return requiredMs > 0 && osIdleMs !== null && Number.isFinite(osIdleMs) && osIdleMs >= requiredMs && appIdleMs >= requiredMs;
}

/** Read only the OS running this browser, never the OS serving a remote Studio. */
export async function readLocalSystemIdleMs(): Promise<number | null> {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) return null;
  try {
    const result = await api<{ idleMs: number | null }>("/api/listener-activity", { signal: AbortSignal.timeout(1500) });
    return typeof result.idleMs === "number" && Number.isFinite(result.idleMs) && result.idleMs >= 0 ? result.idleMs : null;
  } catch { return null; }
}
