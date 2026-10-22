import { expect, it, vi } from "vitest";
import { OpenedInbox } from "./openedInbox";
it("chỉ mở sau khi nhận ở trang sẵn sàng, ACK lỗi thử lại mà không mở trùng", async () => {
  const open = vi.fn();
  const ack = vi.fn().mockRejectedValueOnce(new Error("network")).mockResolvedValue(undefined);
  const inbox = new OpenedInbox(open, ack);
  const event = { eventId: "1", id: "book" };
  await expect(inbox.receive(event)).rejects.toThrow();
  await inbox.receive(event);
  expect(open).toHaveBeenCalledTimes(1);
  expect(ack).toHaveBeenCalledTimes(2);
});
it("event và replay tới cùng lúc đều chờ mở xong mới ACK", async () => {
  let done!: () => void;
  const open = vi.fn(() => new Promise<void>((resolve) => { done = resolve; }));
  const ack = vi.fn().mockResolvedValue(undefined);
  const inbox = new OpenedInbox(open, ack);
  const first = inbox.receive({ eventId: "1" });
  const second = inbox.receive({ eventId: "1" });
  await Promise.resolve();
  expect(ack).not.toHaveBeenCalled();
  done(); await Promise.all([first, second]);
  expect(open).toHaveBeenCalledTimes(1);
  expect(ack).toHaveBeenCalled();
});
