import { toast } from "@/shared/toast";

const KEY = "abook-data-notices-seen";
const shown = new Set<string>();

/** Persisted native recovery messages survive process death; show each once per browser when possible. */
export function showDataNotices(messages: string[] = []): void {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    if (Array.isArray(saved)) for (const text of saved) if (typeof text === "string") shown.add(text);
  } catch { /* still show when storage is unavailable */ }
  for (const text of messages) if (typeof text === "string" && !shown.has(text)) {
    toast.warning(text, { duration: 15_000 });
    shown.add(text);
  }
  try { localStorage.setItem(KEY, JSON.stringify([...shown])); } catch { /* native keeps the messages */ }
}
