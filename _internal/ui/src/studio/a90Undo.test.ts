// Kiểm lệnh gốc; trình bày và Back của toast kiểm riêng trong layoutC11.dom.test.tsx.
vi.mock("@/shared/ToastDetails", () => ({ prepareToast: (args: unknown[]) => args }));
import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Soát a90 V2: hoàn tác một lần bấm ĐÃ GỬI sang máy giữ sách chỉ còn là lời nhờ máy ấy rút - thông báo phải nói đúng điều đó.

const h = vi.hoisted(() => ({ api: vi.fn(), success: vi.fn(), warning: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: h.success, warning: h.warning, error: h.error } }));
vi.mock("./api", () => ({ api: h.api }));
vi.mock("./data", () => ({ useCachedBook: () => undefined }));

import { undoAction, undoToast } from "./decisions";

async function click(action: { onClick: () => void }) {
  action.onClick();
  await vi.waitFor(() => expect(h.success.mock.calls.length + h.warning.mock.calls.length + h.error.mock.calls.length).toBeGreaterThan(0));
}

describe("hoàn tác một thay đổi đã gửi", () => {
  beforeEach(() => {
    h.api.mockReset();
    h.success.mockReset();
    h.warning.mockReset();
    h.error.mockReset();
  });

  it("nói đã nhờ máy giữ sách rút lại, không nói 'việc trở lại như trước'", async () => {
    h.api.mockResolvedValue({ undone: 1, restored: false, sent: true });
    await click(undoAction(new QueryClient(), "b1", "pronunciation", [{ surface: "Lucien", requestedAt: 5 }], "Việc trở lại như trước khi bấm."));
    const [title, options] = h.warning.mock.calls[0];
    expect(title).toBe("Đã nhờ máy giữ sách rút lại");
    expect(options.description).toContain("máy ấy");
    expect(options.description).not.toContain("trở lại như trước");
  });

  it("lần bấm chưa gửi vẫn là 'Đã hoàn tác' với lời cụ thể của người gọi", async () => {
    h.api.mockResolvedValue({ undone: 1, restored: false });
    await click(undoAction(new QueryClient(), "b1", "pronunciation", [{ surface: "Lucien", requestedAt: 5 }], "“Lucien” lại đọc như cũ."));
    expect(h.success.mock.calls[0]).toEqual(["Đã hoàn tác. “Lucien” lại đọc như cũ.", {}]);
  });

  it("một bước trong nhiều bước đã gửi thì cả lời báo nói thật", () => {
    expect(undoToast(true, true)[0]).toBe("Đã nhờ máy giữ sách rút lại");
    expect(undoToast(true, false)[0]).toContain("đọc lại theo cách cũ");
  });

  it("máy chủ từ chối (đã bị lần bấm sau thay) thì báo lỗi, không báo thành công", async () => {
    h.api.mockRejectedValue(new Error("Quyết định này đã được thay bằng một lựa chọn sau"));
    await click(undoAction(new QueryClient(), "b1", "pronunciation", [{ surface: "Lucien", requestedAt: 5 }]));
    expect(h.success).not.toHaveBeenCalled();
    expect(h.error.mock.calls[0][0]).toBe("Không hoàn tác được");
  });
});
