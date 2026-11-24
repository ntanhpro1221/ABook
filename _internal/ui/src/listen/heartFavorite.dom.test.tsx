// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { httpSource } from "@/desktop/httpSource";
import { setApiTransport } from "@/studio/api";
import { FavoriteButton } from "./FavoriteButton";
import { inFilter } from "./LibraryScreen";
import type { ListenBook, ListeningState } from "./model";
import { SourceProvider, type ListenSource } from "./source";

// Thả tim cho sách (heart): nút ở trang sách / Đang nghe ghi vào hồ sơ nghe qua API, nhãn trợ năng theo trạng thái, bộ lọc "Yêu thích".

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  setApiTransport(null);
  vi.restoreAllMocks();
});

function book(id: string, state: Partial<ListeningState> = {}, progress: Partial<ListenBook["progress"]> = {}): ListenBook {
  return {
    id, title: id, narrator: "", duration: 100, chaptersTotal: 1, chaptersAvailable: 1, complete: true, producing: false, updatedAt: null,
    state: { chapters: {}, ...state },
    progress: { heardSeconds: 0, totalSeconds: 100, fraction: 0, chaptersDone: 0, finished: false, ...progress },
  };
}

it("API ghi tim mang mã hồ sơ của màn đã bấm", async () => {
  const calls: { path: string; init?: { method?: string; body?: unknown } }[] = [];
  setApiTransport(async (path, init) => {
    calls.push({ path, init });
    return { favorite: true };
  });
  await httpSource.setFavorite("book", true, "r-a");
  expect(calls[0]).toMatchObject({ path: "/api/listen/books/book/favorite", init: { method: "POST", body: { favorite: true, record: "r-a" } } });
});

it("bộ lọc Yêu thích theo tim, độc lập với tình trạng nghe", () => {
  const loved = book("a", { favorite: true }, { finished: true });
  const plain = book("b");
  expect(inFilter(loved, "favorite")).toBe(true);
  expect(inFilter(loved, "finished")).toBe(true);
  expect(inFilter(plain, "favorite")).toBe(false);
  expect(inFilter(book("c", { favorite: false }), "favorite")).toBe(false);
  expect(inFilter(plain, "all")).toBe(true);
});

it("chạm tim đổi trạng thái: viền -> tô đầy, nhãn Yêu thích -> Bỏ yêu thích, kết quả máy chủ vào bộ đệm sách và thư viện", async () => {
  const setFavorite = vi.fn(async (_id: string, favorite: boolean) => ({ chapters: {}, favorite, favoriteAt: 5 }) as ListeningState);
  const source = { kind: "desktop", setFavorite, library: async () => [book("b1")], book: async () => book("b1") } as unknown as ListenSource;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["listen", "book", "b1"], book("b1"));
  client.setQueryData(["listen", "library"], [book("b1"), book("b2")]);
  function Probe() {
    const current = client.getQueryData<ListenBook>(["listen", "book", "b1"]);
    return <FavoriteButton bookId="b1" on={Boolean(current?.state.favorite)} />;
  }
  const render = async () => act(async () => root.render(<QueryClientProvider client={client}><SourceProvider source={source}><Probe /></SourceProvider></QueryClientProvider>));
  await render();
  const button = () => host.querySelector<HTMLButtonElement>("[data-favorite]")!;
  expect(button().getAttribute("aria-label")).toBe("Yêu thích");
  expect(button().dataset.favorite).toBe("off");
  expect(button().querySelector("svg")!.getAttribute("fill")).toBe("none");
  expect(button().textContent).toBe("Yêu thích");
  await act(async () => button().click());
  expect(setFavorite).toHaveBeenCalledWith("b1", true, undefined);
  await render();
  expect(client.getQueryData<ListenBook>(["listen", "book", "b1"])!.state.favorite).toBe(true);
  expect(client.getQueryData<ListenBook[]>(["listen", "library"])!.map((item) => Boolean(item.state.favorite))).toEqual([true, false]);
  expect(button().dataset.favorite).toBe("on");
  expect(button().getAttribute("aria-label")).toBe("Bỏ yêu thích");
  expect(button().querySelector("svg")!.getAttribute("fill")).toBe("currentColor");
  expect(button().className).toContain("text-accent-text");
  await act(async () => button().click());
  expect(setFavorite).toHaveBeenLastCalledWith("b1", false, undefined);
});
