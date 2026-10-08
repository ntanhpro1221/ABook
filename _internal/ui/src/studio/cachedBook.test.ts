import { QueryClient, QueryObserver, skipToken } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

// Soát UX a8: trang dự án chết ("Missing queryFn") sau khi chọn người nói ở thẻ vai phụ - lần làm mới ["book", id] chạy bằng
// tuỳ chọn của người quan sát gặp sau cùng. Người quan sát chỉ đọc đệm (useCachedBook) phải mang queryFn thật.
async function refreshWithReader(reader: QueryObserver["options"]["queryFn"], enabled: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let calls = 0;
  const page = new QueryObserver(client, { queryKey: ["book", "b1"], queryFn: async () => ({ calls: ++calls }) });
  const unsubscribePage = page.subscribe(() => undefined);
  await client.fetchQuery({ queryKey: ["book", "b1"], queryFn: async () => ({ calls: ++calls }) });
  const card = new QueryObserver(client, { queryKey: ["book", "b1"], queryFn: reader, enabled });
  const unsubscribeCard = card.subscribe(() => undefined);
  await client.invalidateQueries({ queryKey: ["book", "b1"] });
  const state = client.getQueryState(["book", "b1"]);
  unsubscribeCard();
  unsubscribePage();
  return state;
}

describe("đọc bản sách trong bộ nhớ đệm", () => {
  it("người quan sát skipToken làm lần làm mới hỏng (lỗi cũ)", async () => {
    const state = await refreshWithReader(skipToken, true);
    expect(String(state?.error)).toContain("Missing queryFn");
  });

  it("enabled: false với queryFn thật thì làm mới vẫn chạy", async () => {
    const state = await refreshWithReader(async () => ({ calls: -1 }), false);
    expect(state?.error).toBeNull();
    expect(state?.status).toBe("success");
  });
});
