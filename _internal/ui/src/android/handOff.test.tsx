import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Soát a104 trên điện thoại: "Nghe ở đây" chờ loa / TV dừng xong (F4); "Phát trên…" báo loa / TV không có nhạc nền (F3).
const h = vi.hoisted(() => ({
  listen: undefined as undefined | (() => void),
  handOff: undefined as undefined | (() => void),
  command: vi.fn(),
  play: vi.fn(),
  error: vi.fn(),
  note: vi.fn(),
  data: undefined as unknown,
  track: undefined as unknown,
  playing: true,
}));

// Nút thường (không qua IconButton) không có chỗ để bấm khi chỉ render ra chuỗi: lấy onClick của nó lúc dựng.
vi.mock("react/jsx-dev-runtime", async (original) => {
  const real = await original<typeof import("react/jsx-dev-runtime")>();
  return {
    ...real,
    jsxDEV: (type: unknown, props: any, ...rest: unknown[]) => {
      if (type === "button" && props?.children === "Nghe ở đây") h.listen = props.onClick;
      return (real.jsxDEV as any)(type, props, ...rest);
    },
  };
});
vi.mock("react", async (original) => ({ ...(await original<typeof import("react")>()), useEffect: () => {}, useLayoutEffect: () => {} }));
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: h.data }),
  useQueryClient: () => ({ setQueryData: () => {}, invalidateQueries: vi.fn() }),
  useMutation: (options: any) => ({
    mutateAsync: (input: unknown) =>
      Promise.resolve(options.mutationFn(input)).then(
        (result: unknown) => result,
        (error: unknown) => {
          options.onError?.(error);
          throw error;
        },
      ),
    mutate: () => {},
  }),
}));
vi.mock("@/listen/player", () => ({
  usePlayer: () => ({
    play: h.play,
    pause: vi.fn(),
    playing: h.playing,
    track: h.track,
  }),
}));
vi.mock("@/listen/source", () => ({ useSource: () => ({ book: async () => ({ id: "book", chapters: [{ id: 1 }] }) }) }));
vi.mock("@/listen/clock", () => ({ useClockReader: () => () => ({ time: 30 }) }));
vi.mock("@/listen/castMusic", () => ({ noteCastHasNoMusic: (...args: unknown[]) => h.note(...args) }));
vi.mock("@/listen/PlayerViews", () => ({ Back15: () => null, Forward15: () => null, RemoteSleepMenu: () => null }));
vi.mock("@/shared/ui", () => ({
  IconButton: (props: { label: string; onClick?: () => void }) => {
    if (props.label.startsWith("Phát trên")) h.handOff = props.onClick;
    return null;
  },
}));
vi.mock("./plugins", () => ({
  EbookLibrary: { remoteCommand: (...args: unknown[]) => h.command(...args), remotePlayers: vi.fn(), scanPlayers: vi.fn() },
}));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { error: h.error, loading: vi.fn(() => "t"), dismiss: vi.fn() }) }));

import { PhoneHandOffButton, RemotePlayerBars } from "@/android/RemotePlayers";

const tv = {
  device: "dlna:dev", name: "Google TV", kind: "tv", via: "cast", protocol: "gcast", localBookId: "book", known: true, acks: [], age: 0,
  state: { bookId: "book", bookTitle: "Sach", chapterId: 1, chapterTitle: "Chuong 1", position: 30, duration: 300, playing: true, buffering: false, rate: 1 },
};

beforeEach(() => {
  h.listen = undefined;
  h.handOff = undefined;
  for (const mock of [h.command, h.play, h.error, h.note]) mock.mockReset();
  h.data = { receivedAt: Date.now(), players: [tv] };
  h.track = { bookId: "book", bookTitle: "Sach", narrator: "", chapterId: 1, chapterTitle: "Chuong 1" };
  h.playing = true;
  vi.stubGlobal("document", { visibilityState: "visible", addEventListener: () => {}, removeEventListener: () => {} });
  vi.stubGlobal("window", { setTimeout: () => 0 });
});
afterEach(() => vi.unstubAllGlobals());

describe("Nghe ở đây", () => {
  it("chỉ phát ở điện thoại sau khi loa / TV đã dừng", async () => {
    let finish!: (value: unknown) => void;
    h.command.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    h.track = undefined; // điện thoại chưa phát gì: thanh "Đang phát trên Google TV" hiện
    h.playing = false;
    renderToString(<RemotePlayerBars />);
    expect(h.listen).toBeTypeOf("function");
    h.listen!();
    await Promise.resolve();
    expect(h.command).toHaveBeenCalledWith({ device: "dlna:dev", command: { action: "stop" } });
    expect(h.play).not.toHaveBeenCalled(); // lệnh dừng chưa xong
    finish({ id: "ack" });
    await vi.waitFor(() => expect(h.play).toHaveBeenCalledTimes(1));
  });

  it("không phát khi loa / TV không dừng được", async () => {
    h.command.mockRejectedValue(new Error("Google TV: không trả lời"));
    h.track = undefined;
    h.playing = false;
    renderToString(<RemotePlayerBars />);
    h.listen!();
    await vi.waitFor(() => expect(h.error).toHaveBeenCalledWith("Google TV: không trả lời"));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(h.error).toHaveBeenCalledTimes(1);
    expect(h.play).not.toHaveBeenCalled();
  });
});

describe("Phát trên loa / TV", () => {
  it("báo loa, TV không có nhạc nền của cuốn", () => {
    h.command.mockResolvedValue({ id: "ack" });
    renderToString(<PhoneHandOffButton />);
    expect(h.handOff).toBeTypeOf("function");
    h.handOff!();
    expect(h.command).toHaveBeenCalledWith({ device: "dlna:dev", command: { action: "load", bookId: "book", chapterId: 1, seconds: 30 } });
    expect(h.note).toHaveBeenCalledWith(expect.anything(), "book");
  });
});
