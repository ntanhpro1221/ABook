import { beforeEach, expect, it, vi } from "vitest";
import type { NativeEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import type { Track } from "./player";

// Hook gọi thẳng như hàm: mỗi lần `render()` là một lần dựng lại cùng component (ref giữ nguyên, effect chạy khi deps đổi).
const h = vi.hoisted(() => ({ book: undefined as unknown, refs: [] as { current: unknown }[], deps: [] as (readonly unknown[] | undefined)[], cursor: 0 }));
vi.mock("react", async (original) => ({
  ...await original<typeof import("react")>(),
  useRef: (initial: unknown) => (h.refs[h.cursor++] ??= { current: initial }),
  useCallback: (fn: unknown) => fn,
  useEffect: (run: () => void, deps: readonly unknown[]) => {
    const slot = h.cursor++;
    const before = h.deps[slot];
    if (!before || deps.some((dep, index) => dep !== before[index])) run();
    h.deps[slot] = deps;
  },
}));
vi.mock("./source", () => ({ useListenBook: () => ({ data: h.book }) }));
import { useTrackMetadata } from "./trackMetadata";

const chapters = [1, 2].map((id) => ({ id, title: `Chương ${id}`, fullTitle: `Chương ${id}`, available: true, duration: 100 })) as ListenChapter[];
const book = { id: "b", title: "Sách", narrator: "Giọng", chapters } as ListenBook;
const track: Track = { bookId: "b", bookTitle: "Sách", bookCover: null, narrator: "Giọng", chapterId: 1, chapterTitle: "Chương 1" };

beforeEach(() => {
  h.refs = []; h.deps = [];
});

function setup() {
  const native = { native: true, updateMetadata: vi.fn() } as unknown as NativeEngine & { updateMetadata: ReturnType<typeof vi.fn> };
  const refs = { current: { track, queue: chapters, book: { id: "b", title: "Sách" } as { id: string; title: string } | null } };
  const setTrack = vi.fn();
  const setQueue = vi.fn();
  const render = () => {
    h.cursor = 0;
    return useTrackMetadata(track, refs, setTrack, setQueue, native);
  };
  return { native, refs, render };
}

it("điện thoại: mở sách vừa nạp không gửi lại nhãn cả cuốn xuống lõi, chỉ gửi khi sách thật sự đổi", () => {
  const { native, render } = setup();
  h.book = undefined;
  render()(book, chapters); // player.tsx: ngay trước loadQueue
  h.book = { ...book, chapters: chapters.map((chapter) => ({ ...chapter })) }; // câu trả lời của máy chủ: cùng nội dung, đối tượng mới
  render();
  expect(native.updateMetadata).not.toHaveBeenCalled();
  h.book = { ...book, chapters: [chapters[0], { ...chapters[1], fullTitle: "Chương 2 mới" }] };
  render();
  expect(native.updateMetadata).toHaveBeenCalledOnce();
  h.book = { ...(h.book as ListenBook) }; // hỏi lại định kỳ, không đổi gì
  render();
  expect(native.updateMetadata).toHaveBeenCalledOnce();
  h.book = { ...(h.book as ListenBook), cover: { url: "/bia.png", color: "#000" } };
  render();
  expect(native.updateMetadata).toHaveBeenCalledTimes(2);
});

it("cuốn trong refs khác cuốn của dữ liệu thì không bị đổi tên", () => {
  const { refs, render } = setup();
  refs.current.book = { id: "khác", title: "Cuốn khác" };
  h.book = { ...book, title: "Tên mới" };
  render();
  expect(refs.current.book.title).toBe("Cuốn khác");
});
