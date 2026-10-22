import { expect, it, vi } from "vitest";
import type { ListenBook } from "@/listen/model";
import type { NativeState } from "./plugins";

const h = vi.hoisted(() => ({ updateMetadata: vi.fn(), getState: vi.fn(), addListener: vi.fn(), release: vi.fn(), pause: vi.fn() }));
vi.mock("./plugins", () => ({ EbookPlayer: h }));
vi.mock("./androidSource", () => ({ chapterFiles: new Map(), chapterTextEntry: vi.fn() }));
vi.mock("./notifications", () => ({ offerNotificationAccess: vi.fn() }));
import { NativeAudioEngine } from "./nativeEngine";

it("đổi tên cùng cuốn/cùng chương chỉ báo metadata (không phải sang chương) và chuyển nhãn xuống lõi", async () => {
  const old: NativeState = { bookId: "b", bookTitle: "Cũ", chapterId: 1, chapterTitle: "Chương cũ", playing: false, position: 12, duration: 100, buffering: false, rate: 1, sleep: { mode: "off" } };
  h.getState.mockResolvedValue(old);
  h.updateMetadata.mockResolvedValue({ ...old, bookTitle: "Mới", chapterTitle: "Chương mới" });
  const engine = new NativeAudioEngine();
  await Promise.resolve();
  const changed = vi.fn();
  const relabelled = vi.fn();
  engine.on("chapter", changed);
  engine.on("metadata", relabelled);
  const book = { id: "b", title: "Mới", narrator: "Giọng mới", chapters: [{ id: 1, fullTitle: "Chương mới" }] } as ListenBook;
  engine.updateMetadata(book);
  await Promise.resolve();
  expect(h.updateMetadata).toHaveBeenCalledWith({ bookId: "b", title: "Mới", narrator: "Giọng mới", chapters: [{ id: 1, title: "Chương mới" }] });
  expect(changed).not.toHaveBeenCalled();
  expect(relabelled).toHaveBeenCalledOnce();
  expect(engine.bookTitle).toBe("Mới");
  expect(engine.chapterTitle).toBe("Chương mới");
});

it("đóng sách (stop) báo lõi nhả bộ phát nhạc nền thay vì chỉ tạm dừng", () => {
  h.getState.mockResolvedValue({});
  h.release.mockResolvedValue({});
  new NativeAudioEngine().stop();
  expect(h.release).toHaveBeenCalledOnce();
  expect(h.pause).not.toHaveBeenCalled();
});
