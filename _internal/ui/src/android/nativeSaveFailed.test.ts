// Kiểm lệnh gốc; trình bày và Back của toast kiểm riêng trong layoutC11.dom.test.tsx.
vi.mock("@/shared/ToastDetails", () => ({ prepareToast: (args: unknown[]) => args }));
import { beforeEach, expect, it, vi } from "vitest";
import type { NativeState } from "./plugins";

const h = vi.hoisted(() => ({ getState: vi.fn(), addListener: vi.fn(), error: vi.fn() }));
vi.mock("./plugins", () => ({ EbookPlayer: h }));
vi.mock("./androidSource", () => ({ chapterFiles: new Map(), chapterTextEntry: vi.fn() }));
vi.mock("./notifications", () => ({ offerNotificationAccess: vi.fn() }));
vi.mock("sonner", () => ({ toast: { error: h.error } }));
import { NativeAudioEngine } from "./nativeEngine";

const base: NativeState = { bookId: "b", bookTitle: "Sách", chapterId: 1, chapterTitle: "Chương", playing: true, position: 12, duration: 100, buffering: false, rate: 1, sleep: { mode: "off" } };

beforeEach(() => h.error.mockReset());

it("lõi không lưu được chỗ nghe (bộ nhớ đầy) thì báo bạn đúng lời của lõi, một lần cho mỗi sự kiện", async () => {
  h.getState.mockResolvedValue(base);
  new NativeAudioEngine();
  await Promise.resolve();
  const receive = h.addListener.mock.calls.find(([name]) => name === "state")![1] as (state: NativeState) => void;
  receive({ ...base, kind: "tick", position: 13 });
  expect(h.error).not.toHaveBeenCalled();
  receive({ ...base, kind: "saveFailed", saveError: "Chưa lưu được chỗ bạn đang nghe - bộ nhớ trong máy có thể đã đầy." });
  expect(h.error).toHaveBeenCalledOnce();
  expect(h.error.mock.calls[0][1].description).toContain("bạn");
  // Các sự kiện sau mang saveError còn đó nhưng không phải sự kiện mới: không báo lại.
  receive({ ...base, kind: "tick", saveError: "Chưa lưu được chỗ bạn đang nghe - bộ nhớ trong máy có thể đã đầy." });
  expect(h.error).toHaveBeenCalledOnce();
});
