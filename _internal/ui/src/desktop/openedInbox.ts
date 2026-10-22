/** eval có thể tới trước React. Replay từ host chỉ gỡ sau khi trang xử lý xong và ACK. */
export class OpenedInbox<T extends { eventId?: string }> {
  private seen = new Set<string>();
  private opening = new Map<string, Promise<unknown>>();
  constructor(private open: (event: T) => unknown, private ack: (eventId: string) => Promise<unknown>) {}
  async receive(event: T): Promise<void> {
    if (!event.eventId) { this.open(event); return; } // cửa sổ Qt cũ
    if (!this.seen.has(event.eventId)) {
      const id = event.eventId;
      if (!this.opening.has(id)) this.opening.set(id, Promise.resolve().then(() => this.open(event)));
      try { await this.opening.get(id); this.seen.add(id); }
      finally { this.opening.delete(id); }
    }
    await this.ack(event.eventId);
  }
}
