import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { setApiTransport, type ApiInit } from "@/studio/api";
import type { ListeningRecord } from "./model";
import { SourceProvider, useListenMutations, type ListenSource } from "./source";

// "Chuyển sang cuốn khác…" của hồ sơ nghe: máy tính gọi POST /api/listen/books/<mã>/records/<hồ sơ>/move {book}; trang sách làm mới
// cả cuốn cũ lẫn cuốn nhận hồ sơ.

afterEach(() => setApiTransport(null));

describe("chuyển hồ sơ nghe", () => {
  it("máy tính gửi đúng lệnh của máy chủ", async () => {
    const calls: [string, ApiInit | undefined][] = [];
    setApiTransport(async (path, init) => {
      calls.push([path, init]);
      return { records: [] };
    });
    const { httpSource } = await import("@/desktop/httpSource");
    expect(await httpSource.records!.move("sach-cu", "r-0123456789abcdef", "sach-moi")).toEqual([]);
    expect(calls).toEqual([["/api/listen/books/sach-cu/records/r-0123456789abcdef/move", { method: "POST", body: { book: "sach-moi" } }]]);
  });

  it("lệnh chuyển làm mới cuốn cũ, cuốn nhận và thư viện", async () => {
    const moved: string[][] = [];
    const left: ListeningRecord[] = [];
    const source = {
      records: {
        create: async () => [],
        activate: async () => [],
        rename: async () => [],
        remove: async () => [],
        move: async (bookId: string, recordId: string, toBook: string) => {
          moved.push([bookId, recordId, toBook]);
          return left;
        },
      },
    } as unknown as ListenSource;
    const client = new QueryClient();
    const stale: string[] = [];
    const invalidate = client.invalidateQueries.bind(client);
    client.invalidateQueries = ((filters?: { queryKey?: readonly unknown[] }) => {
      stale.push(JSON.stringify(filters?.queryKey));
      return invalidate(filters);
    }) as typeof client.invalidateQueries;
    let mutations: ReturnType<typeof useListenMutations> | null = null;
    function Capture() {
      mutations = useListenMutations("sach-cu");
      return null;
    }
    renderToString(
      <QueryClientProvider client={client}>
        <SourceProvider source={source}>
          <Capture />
        </SourceProvider>
      </QueryClientProvider>,
    );

    expect(await mutations!.moveRecord.mutateAsync({ recordId: "r-0123456789abcdef", toBook: "sach-moi" })).toBe(left);

    expect(moved).toEqual([["sach-cu", "r-0123456789abcdef", "sach-moi"]]);
    expect(stale).toEqual(expect.arrayContaining([
      JSON.stringify(["listen", "book", "sach-cu"]),
      JSON.stringify(["listen", "book", "sach-moi"]),
      JSON.stringify(["listen", "library"]),
    ]));
  });
});
