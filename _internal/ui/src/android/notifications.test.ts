import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { offerNotificationAccess, type NotificationApi } from "./notifications";

// Quyền thông báo (Android 13+): xin SAU khi đã có tiếng, và chỉ sau một câu nói vì sao - hộp hệ thống bật ngay lúc chọn giọng từng chặn lần nghe đầu (soát 03-10).
function memory(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => void data.set(key, value) };
}

function api(state: "granted" | "off"): NotificationApi & { asked: ReturnType<typeof vi.fn> } {
  const asked = vi.fn(async () => ({ state: "granted" as const }));
  return { notificationAccess: async () => ({ state }), requestNotificationAccess: asked, asked } as NotificationApi & { asked: ReturnType<typeof vi.fn> };
}

describe("offerNotificationAccess", () => {
  let notify: Mock<(message: string, allow: () => void) => void>;
  beforeEach(() => {
    notify = vi.fn<(message: string, allow: () => void) => void>();
  });

  it("explains first and never opens the system box by itself", async () => {
    const plugin = api("off");
    expect(await offerNotificationAccess(plugin, notify, memory())).toBe(true);
    expect(notify).toHaveBeenCalledTimes(1);
    const [message, allow] = notify.mock.calls[0];
    expect(message).toContain("khay thông báo");
    expect(plugin.asked).not.toHaveBeenCalled();
    allow();
    expect(plugin.asked).toHaveBeenCalledTimes(1);
  });

  it("asks only once ever, even if the listener ignored the sentence", async () => {
    const store = memory();
    await offerNotificationAccess(api("off"), notify, store);
    expect(await offerNotificationAccess(api("off"), notify, store)).toBe(false);
    expect(notify).toHaveBeenCalledTimes(1);
  });

  it("says nothing when the permission is already there or cannot be read", async () => {
    expect(await offerNotificationAccess(api("granted"), notify, memory())).toBe(false);
    const broken = { notificationAccess: async () => { throw new Error("không có"); }, requestNotificationAccess: vi.fn() } as unknown as NotificationApi;
    expect(await offerNotificationAccess(broken, notify, memory())).toBe(false);
    expect(notify).not.toHaveBeenCalled();
  });
});
