// @vitest-environment happy-dom
// Tab Studio trên điện thoại mở lại: danh sách máy tính đã có thì hiện ngay, hỏi lại ở nền - không nháy khung chờ (useStudioComputersQuery).
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { QueryClientProvider } from "@tanstack/react-query";
import { createAppQueryClient } from "@/shared/queryClient";

const library = vi.hoisted(() => ({
  connection: vi.fn(async () => ({ host: "pc" })),
  peerLibraries: vi.fn(async () => ({ peers: [] })),
  studioComputers: vi.fn(async () => ({ computers: [{ key: "", name: "Máy nhà" }] })),
}));
vi.mock("./plugins", () => ({ EbookLibrary: library, EbookPlayer: {}, ReadAloud: {} }));

import { useStudioComputersQuery } from "./StudioOpen";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root | undefined;
afterEach(() => { act(() => root?.unmount()); root = undefined; document.body.innerHTML = ""; vi.useRealTimers(); });

const seen: boolean[] = [];
function Probe() {
  const query = useStudioComputersQuery();
  seen.push(query.isLoading);
  return <span>{query.data?.computers.length ?? "chờ"}</span>;
}

const flush = () => act(async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); await new Promise((r) => setTimeout(r, 0)); });

it("mở tab lần hai: không có nhịp nào ở trạng thái chờ, vẫn hỏi lại máy tính sau khi kết nối trả lời", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  const client = createAppQueryClient();
  const host = document.body.appendChild(document.createElement("div"));
  const mount = () => act(() => { root = createRoot(host); root.render(<QueryClientProvider client={client}><Probe /></QueryClientProvider>); });

  mount();
  await flush();
  expect(host.textContent).toBe("1");
  act(() => root?.unmount());

  // Mở lại sau vài giây; vỏ app đã hỏi lại kết nối trước khi tab Studio dựng (lượt trả lời mới có sẵn ngay nhịp đầu).
  vi.setSystemTime(Date.now() + 5000);
  await act(() => client.refetchQueries({ queryKey: ["connection"] }));
  seen.length = 0;
  const before = library.studioComputers.mock.calls.length;
  mount();
  expect(host.textContent).toBe("1");
  await flush();
  expect(seen).not.toContain(true);
  expect(host.textContent).toBe("1");
  expect(library.studioComputers.mock.calls.length).toBeGreaterThan(before);
});
