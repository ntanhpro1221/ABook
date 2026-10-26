// @vitest-environment happy-dom
// Bấm nghe cuốn A rồi cuốn B ngay sau: máy chủ trả sách B trước, sách A sau - phải phát B (cuốn bấm sau cùng), không phải A.
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import type { ListenBook } from "./model";

const state = vi.hoisted(() => ({ book: vi.fn(), play: vi.fn() }));
vi.mock("./source", async (original) => ({ ...(await original<typeof import("./source")>()), useSource: () => ({ kind: "desktop", book: state.book }) }));
vi.mock("./player", async (original) => ({ ...(await original<typeof import("./player")>()), usePlayer: () => ({ track: null, play: state.play, resume: vi.fn() }) }));
import { usePlayListenBook } from "./LibraryScreen";

const chapter = { id: 1, index: 0, title: "Chương 1", fullTitle: "Chương 1", subtitle: "", duration: 60, available: true };
const full = (id: string) => ({ id, title: id, chapters: [chapter], state: { chapters: {} }, progress: { heardSeconds: 0, totalSeconds: 60, fraction: 0, chaptersDone: 0, finished: false } }) as unknown as ListenBook;
const row = (id: string) => ({ id, title: id }) as unknown as ListenBook;

it("lời đáp về muộn của cuốn bấm trước không phát đè cuốn bấm sau", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const waiting = new Map<string, (book: ListenBook) => void>();
  state.book.mockImplementation((id: string) => new Promise((resolve) => waiting.set(id, resolve)));
  let playBook: ReturnType<typeof usePlayListenBook> | undefined;
  function Probe() {
    playBook = usePlayListenBook();
    return null;
  }
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(() => root.render(<Probe />));
  const first = playBook!(row("A"));
  const second = playBook!(row("B"));
  waiting.get("B")!(full("B"));
  await second;
  waiting.get("A")!(full("A"));
  await first;
  expect(state.play).toHaveBeenCalledTimes(1);
  expect(state.play.mock.calls[0][0].id).toBe("B");
  await act(() => root.unmount());
});
