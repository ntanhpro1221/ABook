import { focusManager, QueryClient, QueryObserver } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PRODUCING_REFRESH_MS, producingRefetch } from "./liveRefresh";

// react-query chỉ đặt nhịp hỏi khi có "trình duyệt" - phải có trước khi nạp thư viện.
vi.hoisted(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), { location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" } });
});

vi.mock("./data", () => ({ useCachedBook: () => ({ data: undefined }) }));

// Soát a90 V4: hộp "Việc cần duyệt" và hàng đợi "Cần nghe lại" tự làm mới khi sách đang chạy - chỉ khi sách thật sự đang chạy và tab đang hiện.

type Book = Parameters<typeof producingRefetch>[0];
const running: Book = { running: true, starting: false, paused: null };

describe("làm mới theo nhịp khi sách đang chạy", () => {
  let client: QueryClient;
  let calls: number;

  beforeEach(() => {
    vi.useFakeTimers();
    client = new QueryClient();
    calls = 0;
  });
  afterEach(() => {
    vi.useRealTimers();
    focusManager.setFocused(undefined);
    client.clear();
  });

  function watch(book: Book) {
    const observer = new QueryObserver(client, {
      queryKey: ["work", "b1"],
      queryFn: async () => ({ items: [], round: ++calls }),
      refetchInterval: producingRefetch(book),
    });
    return observer.subscribe(() => undefined);
  }

  it("sách đang chạy: hỏi lại sau mỗi nhịp", async () => {
    const stop = watch(running);
    await vi.advanceTimersByTimeAsync(10);
    expect(calls).toBe(1);
    await vi.advanceTimersByTimeAsync(PRODUCING_REFRESH_MS * 2 + 10);
    expect(calls).toBe(3);
    stop();
  });

  it("sách đang bắt đầu cũng tính là đang chạy", async () => {
    const stop = watch({ running: false, starting: true, paused: null });
    await vi.advanceTimersByTimeAsync(PRODUCING_REFRESH_MS + 10);
    expect(calls).toBe(2);
    stop();
  });

  it.each([
    ["sách không chạy", { running: false, starting: false, paused: null }],
    ["sách đang tạm dừng (không có việc mới nào sinh ra)", { running: true, starting: false, paused: "listener" as const }],
    ["chưa biết sách", undefined],
  ])("%s: không hỏi theo nhịp", async (_name, book) => {
    const stop = watch(book as Book);
    await vi.advanceTimersByTimeAsync(PRODUCING_REFRESH_MS * 3);
    expect(calls).toBe(1);
    stop();
  });

  it("tab đang ẩn: không hỏi theo nhịp, hiện lại thì hỏi tiếp", async () => {
    focusManager.setFocused(false);
    const stop = watch(running);
    await vi.advanceTimersByTimeAsync(PRODUCING_REFRESH_MS * 3);
    expect(calls).toBe(1);
    focusManager.setFocused(true);
    await vi.advanceTimersByTimeAsync(PRODUCING_REFRESH_MS * 2);
    expect(calls).toBeGreaterThan(1);
    stop();
  });

  it("dữ liệu giống hệt thì giữ nguyên tham chiếu (danh sách không dựng lại, tiêu điểm và vị trí cuộn còn nguyên)", async () => {
    const same = { items: [{ key: "a" }] };
    const observer = new QueryObserver(client, {
      queryKey: ["work", "b2"],
      queryFn: async () => (calls++, { items: [{ key: "a" }] }),
      refetchInterval: producingRefetch(running),
    });
    const seen: unknown[] = [];
    const stop = observer.subscribe((result) => result.data && seen.push(result.data));
    await vi.advanceTimersByTimeAsync(PRODUCING_REFRESH_MS * 2 + 10);
    expect(calls).toBe(3);
    expect(new Set(seen).size).toBe(1);
    expect(same).toBeTruthy();
    stop();
  });
});
