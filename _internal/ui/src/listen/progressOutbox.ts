import type { ReadingAnchor } from "./readingAnchor";

export interface ProgressSnapshot {
  bookId: string;
  chapterId: number;
  seconds: number;
  duration: number;
  record?: string;
  anchor?: ReadingAnchor;
  savedAt?: number;
  sessionId?: string;
  revision?: number;
}
type Pending = ProgressSnapshot & { receipt: string };
type Storage = Pick<globalThis.Storage, "getItem" | "setItem">;
const KEY = "abook:pending-progress";
const keyOf = (spot: ProgressSnapshot) => `${spot.bookId}:${spot.record ?? ""}`;

/** Bản chờ sống qua reload; chỉ ACK đúng bản mới được gỡ. Mỗi hồ sơ gửi tuần tự. */
export class ProgressOutbox {
  private pending: Record<string, Pending> = {};
  private running = new Map<string, Promise<void>>();
  constructor(
    private send: (spot: ProgressSnapshot, keepalive: boolean) => Promise<unknown>,
    private storage: Storage | undefined = (() => { try { return globalThis.localStorage; } catch { return undefined; } })(),
    private ack: (spot: ProgressSnapshot) => void = () => undefined,
  ) {
    try {
      const saved = JSON.parse(storage?.getItem(KEY) ?? "{}");
      if (saved && typeof saved === "object" && !Array.isArray(saved)) {
        for (const [key, spot] of Object.entries(saved)) {
          if (spot && typeof spot === "object" && typeof (spot as Pending).bookId === "string" && typeof (spot as Pending).receipt === "string") this.pending[key] = spot as Pending;
        }
      }
    } catch { /* Kho trình duyệt chưa sẵn sàng. */ }
  }
  private persist() {
    try { this.storage?.setItem(KEY, JSON.stringify(this.pending)); } catch { /* Vẫn giữ bản chờ trong phiên hiện tại. */ }
  }
  put(spot: ProgressSnapshot, keepalive = false): Promise<void> {
    const pending = { ...spot, receipt: crypto.randomUUID() };
    this.pending[keyOf(spot)] = pending;
    this.persist();
    return this.deliver(pending, keepalive);
  }
  private deliver(spot: Pending, keepalive: boolean): Promise<void> {
    const key = keyOf(spot);
    // Khi đóng trang, không đợi POST thường đang mắc mạng: bản mới có revision cao hơn.
    const task = (keepalive ? Promise.resolve() : this.running.get(key) ?? Promise.resolve()).catch(() => undefined).then(async () => {
      try {
        await this.send(spot, keepalive);
      } catch (error) {
        if ((error as { status?: number })?.status === 409 && this.pending[key]?.receipt === spot.receipt) {
          delete this.pending[key];
          this.persist();
        }
        throw error;
      }
      if (this.pending[key]?.receipt === spot.receipt) {
        delete this.pending[key];
        this.persist();
      }
      this.ack(spot);
    });
    this.running.set(key, task);
    void task.finally(() => { if (this.running.get(key) === task) this.running.delete(key); }).catch(() => undefined);
    return task;
  }
  async flush(keepalive = false): Promise<void> {
    await Promise.all(Object.values(this.pending).filter((spot) => keepalive || !this.running.has(keyOf(spot))).map((spot) => this.deliver(spot, keepalive)));
  }
}
