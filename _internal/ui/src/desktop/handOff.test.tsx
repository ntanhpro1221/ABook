import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Soát a104: "Nghe trên máy này" chờ máy kia dừng xong (F4); "Phát trên…" mang hồ sơ đang nghe và báo loa / TV không có nhạc nền (F1, F3).
const h = vi.hoisted(() => ({
  listen: undefined as undefined | (() => Promise<void>),
  handOff: undefined as undefined | (() => void),
  api: vi.fn(),
  play: vi.fn(),
  error: vi.fn(),
  note: vi.fn(),
  data: undefined as unknown,
}));

vi.mock("react", async (original) => ({ ...(await original<typeof import("react")>()), useEffect: () => {}, useLayoutEffect: () => {} }));
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: h.data }),
  useQueryClient: () => ({ setQueryData: () => {}, invalidateQueries: vi.fn() }),
  useMutation: (options: any) => {
    const run = (input: unknown) =>
      Promise.resolve(options.mutationFn(input)).then(
        (result: unknown) => {
          options.onSuccess?.(result);
          return result;
        },
        (error: unknown) => {
          options.onError?.(error);
          throw error;
        },
      );
    return {
      mutate: (input: unknown, callbacks: any = {}) => void run(input).then((result) => callbacks.onSuccess?.(result), (error) => callbacks.onError?.(error)),
      mutateAsync: run,
    };
  },
}));
vi.mock("@/listen/player", () => ({
  usePlayer: () => ({
    play: h.play,
    pause: vi.fn(),
    resume: vi.fn(),
    close: vi.fn(),
    playing: true,
    track: { bookId: "book", bookTitle: "Sach", narrator: "", chapterId: 1, chapterTitle: "Chuong 1", recordId: "ho-so-b" },
  }),
}));
vi.mock("@/listen/source", () => ({
  useSource: () => ({ book: async () => ({ id: "book", chapters: [{ id: 1 }] }) }),
  useListenBook: () => ({ data: undefined }),
}));
vi.mock("@/listen/clock", () => ({ useClockReader: () => () => ({ time: 30 }) }));
vi.mock("@/listen/castMusic", () => ({ noteCastHasNoMusic: (...args: unknown[]) => h.note(...args) }));
vi.mock("@/listen/PlayerViews", () => ({ Back15: () => null, Forward15: () => null, RemoteSleepMenu: () => null }));
vi.mock("@/shared/BookCover", () => ({ BookCover: () => null }));
vi.mock("@/shared/ShortName", () => ({ ShortName: () => null }));
vi.mock("@/shared/ui", () => ({
  IconButton: (props: { label: string; onClick?: () => void }) => {
    if (props.label.startsWith("Phát trên")) h.handOff = props.onClick;
    return null;
  },
  Tooltip: ({ children }: any) => {
    if (children?.props?.["aria-label"] === "Nghe trên máy này") h.listen = children.props.onClick;
    return children;
  },
}));
vi.mock("@/studio/api", () => ({ api: (...args: unknown[]) => h.api(...args) }));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { error: h.error, loading: vi.fn(() => "t"), dismiss: vi.fn() }) }));

import { HandOffButton, RemoteBars } from "@/desktop/RemotePhone";

const tv = {
  device: "dev", name: "Google TV", kind: "tv", via: "cast", protocol: "gcast", bookId: "book", localBookId: "book", bookTitle: "Sach",
  chapterId: 1, chapterTitle: "Chuong 1", position: 30, duration: 300, playing: true, buffering: false, rate: 1, books: [], stream: true,
  acks: [], age: 0, known: true,
};

beforeEach(() => {
  h.listen = undefined;
  h.handOff = undefined;
  for (const mock of [h.play, h.error, h.note, h.api]) mock.mockReset();
  h.data = { receivedAt: Date.now(), phones: [tv] };
  vi.stubGlobal("window", { setTimeout: () => 0 });
});
afterEach(() => vi.unstubAllGlobals());

describe("Nghe trên máy này", () => {
  it("chỉ phát ở đây sau khi máy kia đã dừng", async () => {
    let finish!: (value: unknown) => void;
    h.api.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    renderToString(<RemoteBars />);
    expect(h.listen).toBeTypeOf("function");
    h.listen!();
    await Promise.resolve();
    expect(h.api).toHaveBeenCalledWith("/api/remote/dev", expect.objectContaining({ body: { action: "stop" } }));
    expect(h.play).not.toHaveBeenCalled(); // lệnh dừng chưa xong
    finish({ id: "ack" });
    await vi.waitFor(() => expect(h.play).toHaveBeenCalledTimes(1));
  });

  it("không phát ở đây khi máy kia không dừng được", async () => {
    h.api.mockRejectedValue(new Error("Google TV: không trả lời"));
    renderToString(<RemoteBars />);
    h.listen!();
    await vi.waitFor(() => expect(h.error).toHaveBeenCalledWith("Google TV: không trả lời")); // lời báo của lệnh, một lần
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(h.error).toHaveBeenCalledTimes(1);
    expect(h.play).not.toHaveBeenCalled();
  });
});

describe("Phát trên loa / TV", () => {
  it("mang hồ sơ đang nghe và báo loa, TV không có nhạc nền", () => {
    h.api.mockResolvedValue({ id: "ack" });
    renderToString(<HandOffButton />);
    expect(h.handOff).toBeTypeOf("function");
    h.handOff!();
    expect(h.api).toHaveBeenCalledWith(
      "/api/remote/dev",
      expect.objectContaining({ body: { action: "load", bookId: "book", chapterId: 1, seconds: 30, record: "ho-so-b" } }),
    );
    expect(h.note).toHaveBeenCalledWith(expect.anything(), "book");
  });
});
