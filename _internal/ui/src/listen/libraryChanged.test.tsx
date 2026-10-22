import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";

// Thư viện lấy lại khi nguồn báo đổi (soát a101 F2): điện thoại trả sách đã tải ngay, sách nghe thẳng về sau.
const h = vi.hoisted(() => ({ effects: [] as { run: () => unknown; deps: unknown[] }[] }));
vi.mock("react", async (original) => {
  const react = await original<typeof import("react")>();
  return { ...react, useEffect: (run: () => unknown, deps: unknown[] = []) => h.effects.push({ run, deps }) };
});
import { SourceProvider, useListenLibrary, type ListenSource } from "./source";

beforeEach(() => {
  h.effects = [];
});

it("nguồn báo đổi thì truy vấn thư viện bị đánh dấu cũ; rời trang thì thôi nghe", () => {
  let listener: (() => void) | undefined;
  const stop = vi.fn();
  const source = {
    kind: "android",
    library: async () => [],
    libraryChanged: (next: () => void) => {
      listener = next;
      return stop;
    },
  } as unknown as ListenSource;
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  function Probe() {
    useListenLibrary();
    return null;
  }
  renderToString(
    <QueryClientProvider client={client}>
      <SourceProvider source={source}>
        <Probe />
      </SourceProvider>
    </QueryClientProvider>,
  );
  const cleanups = h.effects.map((effect) => effect.run());
  expect(listener).toBeTypeOf("function");
  listener!();
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["listen", "library"] });
  cleanups.forEach((cleanup) => typeof cleanup === "function" && cleanup());
  expect(stop).toHaveBeenCalled();
});

it("nguồn không có libraryChanged (máy tính): không đăng ký gì", () => {
  const source = { kind: "desktop", library: async () => [] } as unknown as ListenSource;
  function Probe() {
    useListenLibrary();
    return null;
  }
  renderToString(
    <QueryClientProvider client={new QueryClient()}>
      <SourceProvider source={source}>
        <Probe />
      </SourceProvider>
    </QueryClientProvider>,
  );
  expect(() => h.effects.forEach((effect) => effect.run())).not.toThrow();
});
