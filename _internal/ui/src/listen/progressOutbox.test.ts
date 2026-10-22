import { expect, it, vi } from "vitest";
import { ProgressOutbox } from "./progressOutbox";

function storage() {
  const data = new Map<string, string>();
  return { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => { data.set(key, value); } };
}
const spot = { bookId: "a", chapterId: 1, seconds: 30, duration: 100 };
it("giữ bản chờ sau lỗi 503 và gửi lại sau khi dựng lại trang", async () => {
  const disk = storage();
  const failed = vi.fn().mockRejectedValue(new Error("503"));
  const queue = new ProgressOutbox(failed, disk);
  await expect(queue.put(spot)).rejects.toThrow("503");
  const send = vi.fn().mockResolvedValue(undefined);
  await new ProgressOutbox(send, disk).flush();
  expect(send).toHaveBeenCalledWith(expect.objectContaining(spot), false);
  send.mockClear();
  await new ProgressOutbox(send, disk).flush();
  expect(send).not.toHaveBeenCalled();
});
it("ACK cũ không gỡ chỗ mới còn chờ", async () => {
  let ack!: () => void;
  const send = vi.fn().mockImplementationOnce(() => new Promise<void>((done) => { ack = done; })).mockRejectedValue(new Error("503"));
  const disk = storage();
  const queue = new ProgressOutbox(send, disk);
  const first = queue.put(spot);
  await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(1));
  const second = queue.put({ ...spot, seconds: 60 });
  ack();
  await first;
  await expect(second).rejects.toThrow();
  const retry = vi.fn().mockResolvedValue(undefined);
  await new ProgressOutbox(retry, disk).flush();
  expect(retry).toHaveBeenCalledWith(expect.objectContaining({ seconds: 60 }), false);
});
