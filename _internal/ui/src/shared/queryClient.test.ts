import { MutationObserver, onlineManager, QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";
import { createAppQueryClient } from "./queryClient";

// Soát a66 mục 1: mất Wi-Fi giữa phiên làm đứng mọi truy vấn chưa có cache (thẻ giọng, nút tải giọng, thanh tải 0 %),
// dù chúng chỉ gọi máy chủ cục bộ / plugin. Hai nền dùng chung createAppQueryClient.

const settle = <T,>(p: Promise<T>, ms = 200) =>
  Promise.race([p.then(() => "xong" as const), new Promise<"đứng">((r) => setTimeout(() => r("đứng"), ms))]);

afterEach(() => onlineManager.setOnline(true));

describe("truy vấn khi trình duyệt báo mất mạng", () => {
  it("vẫn chạy truy vấn và lệnh", async () => {
    onlineManager.setOnline(false);
    const client = createAppQueryClient();
    expect(await settle(client.fetchQuery({ queryKey: ["giọng"], queryFn: async () => 1 }))).toBe("xong");
    const m = new MutationObserver(client, { mutationFn: async () => 2 });
    expect(await settle(m.mutate())).toBe("xong");
  });

  it("đối chứng: mặc định của react-query thì đứng", async () => {
    onlineManager.setOnline(false);
    const client = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    expect(await settle(client.fetchQuery({ queryKey: ["giọng"], queryFn: async () => 1 }))).toBe("đứng");
  });
});
