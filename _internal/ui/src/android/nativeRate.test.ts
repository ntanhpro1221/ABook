import { expect, it, vi } from "vitest";
import type { NativeState } from "./plugins";

const h = vi.hoisted(() => ({ getState: vi.fn(), addListener: vi.fn() }));
vi.mock("./plugins", () => ({ EbookPlayer: h }));
vi.mock("./androidSource", () => ({ chapterFiles: new Map(), chapterTextEntry: vi.fn() }));
vi.mock("./notifications", () => ({ offerNotificationAccess: vi.fn() }));
import { NativeAudioEngine } from "./nativeEngine";

const base: NativeState = { bookId: "b", bookTitle: "Sách", chapterId: 1, chapterTitle: "Chương", playing: true, position: 12, duration: 100, buffering: false, rate: 1, sleep: { mode: "off" } };

it("tốc độ do controller ngoài đổi (xe, đồng hồ) báo riêng sự kiện rate, không cần đổi chương; nút trong app thì không báo ngược", async () => {
  h.getState.mockResolvedValue(base);
  const engine = new NativeAudioEngine();
  await Promise.resolve();
  const receive = h.addListener.mock.calls.find(([name]) => name === "state")![1] as (state: NativeState) => void;
  const rate = vi.fn();
  const chapter = vi.fn();
  engine.on("rate", rate);
  engine.on("chapter", chapter);
  receive({ ...base, kind: "tick", position: 13 });
  receive({ ...base, kind: "rate", rate: 1.25 }); // chính app đặt (EbookPlayer.setRate)
  expect(rate).not.toHaveBeenCalled();
  receive({ ...base, kind: "rateChanged", rate: 1.5 }); // controller ngoài
  expect(rate).toHaveBeenCalledOnce();
  expect(engine.rate).toBe(1.5);
  expect(chapter).not.toHaveBeenCalled();
});
