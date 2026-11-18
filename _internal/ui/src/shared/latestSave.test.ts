// Soát sleeplast 18-11 (lỗi 1): đổi số liên tiếp gửi nhiều lần lưu, phản hồi muộn kéo mốc lùi về số cũ.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { latestSave } from "./latestSave";

/** Máy chủ giả: mỗi lần gửi là một lời hứa test tự trả lời (theo thứ tự nào cũng được). */
function server() {
  const calls: { value: number; answer: (saved: number) => void; fail: () => void }[] = [];
  const send = (value: number) => new Promise<number>((resolve, reject) => calls.push({ value, answer: resolve, fail: () => reject(new Error("500")) }));
  return { calls, send };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

it("đổi liền nhau: chỉ gửi một lần, bản cuối", async () => {
  const { calls, send } = server();
  const applied: number[] = [];
  const saver = latestSave(send, { apply: saved => applied.push(saved) });
  for (const value of [31, 32, 33, 34, 35]) { void saver.save(value); await vi.advanceTimersByTimeAsync(100); }
  expect(calls).toHaveLength(0);
  await vi.advanceTimersByTimeAsync(800);
  expect(calls.map(call => call.value)).toEqual([35]);
  calls[0].answer(35);
  await vi.runAllTimersAsync();
  expect(applied).toEqual([35]);
  expect(saver.pending).toBe(false);
});

it("phản hồi cũ về sau lần đổi mới: không áp, mốc cuối là lựa chọn cuối", async () => {
  const { calls, send } = server();
  const applied: number[] = [];
  const saver = latestSave(send, { apply: saved => applied.push(saved) });
  void saver.save(31);
  await vi.advanceTimersByTimeAsync(800);
  void saver.save(32);
  await vi.advanceTimersByTimeAsync(800);
  // Lần 31 còn bay: 32 chưa gửi chồng lên (máy chủ không nhận hai bản đua nhau).
  expect(calls.map(call => call.value)).toEqual([31]);
  const last = saver.save(33);
  calls[0].answer(31); // phản hồi của lần cũ về muộn
  await vi.advanceTimersByTimeAsync(0);
  expect(applied).toEqual([]);
  await vi.advanceTimersByTimeAsync(800);
  expect(calls.map(call => call.value)).toEqual([31, 33]);
  calls[1].answer(33);
  await last;
  expect(applied).toEqual([33]);
});

it("lần gửi trước hỏng, lần sau vẫn đi; lỗi không ném ra ngoài", async () => {
  const { calls, send } = server();
  const applied: number[] = [];
  const saver = latestSave(send, { apply: saved => applied.push(saved) });
  void saver.save(40);
  await vi.advanceTimersByTimeAsync(800);
  const last = saver.save(45);
  calls[0].fail();
  await vi.advanceTimersByTimeAsync(800);
  expect(calls.map(call => call.value)).toEqual([40, 45]);
  calls[1].fail();
  await expect(last).resolves.toBeUndefined();
  expect(applied).toEqual([]);
  expect(saver.pending).toBe(false);
});
