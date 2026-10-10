import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { optimistic } from "@/studio/decisions";

// Soát UX a23 B17: máy chủ tắt khi gán người nói - thông báo lỗi hiện, nhưng câu vẫn "Đã ghi Heidi - chờ áp dụng" vì bản sửa lạc
// quan không bao giờ được đặt lại.
describe("sửa lạc quan", () => {
  const key = ["casting", "b1", 3];
  const before = { lines: [{ stableId: "a", wish: null as null | { value: string } }] };

  it("đổi ngay rồi trở lại đúng bản trước khi không ghi được", () => {
    const client = new QueryClient();
    client.setQueryData(key, before);
    const context = optimistic<typeof before>(client, key, (data) => ({ lines: data.lines.map((line) => ({ ...line, wish: { value: "HEIDI" } })) }));
    expect(client.getQueryData<typeof before>(key)?.lines[0].wish).toEqual({ value: "HEIDI" });
    context.restore();
    expect(client.getQueryData(key)).toEqual(before);
  });

  it("chưa có bản nào trong bộ nhớ đệm thì không tạo gì", () => {
    const client = new QueryClient();
    optimistic(client, key, () => before).restore();
    expect(client.getQueryData(key)).toBeUndefined();
  });
});
