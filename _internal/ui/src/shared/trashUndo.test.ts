import { beforeEach, describe, expect, it, vi } from "vitest";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
const api = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast }));
vi.mock("@/studio/api", () => ({ api }));

import { UNDO_SECONDS, UNDO_TOAST_MS, removedDescription, restoredNote, toastRemoved } from "./trashUndo";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("xoá sách có Hoàn tác", () => {
  it("nút Hoàn tác sống ngắn hơn hạn của máy chủ", () => {
    expect(UNDO_TOAST_MS).toBeLessThan(UNDO_SECONDS * 1000);
    expect(UNDO_TOAST_MS).toBe((UNDO_SECONDS - 2) * 1000);
  });

  it("lời báo nói đúng lúc nào cuốn vào Thùng rác", () => {
    expect(removedDescription("File gốc không bị đụng.", true)).toContain(`${UNDO_SECONDS} giây`);
    expect(removedDescription("", false)).toBe("Cuốn đã vào Thùng rác của Windows, khôi phục từ đó được.");
  });

  it("cuốn từng xếp hàng chờ thì lời khôi phục nói hàng chờ không tự xếp lại", () => {
    expect(restoredNote({ wasQueued: true })).toContain("hàng chờ");
    expect(restoredNote({ wasQueued: false })).toBeUndefined();
  });

  it("có mã hoàn tác thì toast có nút; bấm gọi đường hoàn tác rồi tải lại danh sách", async () => {
    api.mockResolvedValue({ ok: true, title: "Sách", wasQueued: true });
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá dự án “Sách”", title: "Sách", undo: "ab".repeat(16), note: "", onRestored: restored });
    const [message, options] = toast.success.mock.calls[0];
    expect(message).toBe("Đã xoá dự án “Sách”");
    expect(options.duration).toBe(UNDO_TOAST_MS);
    expect(options.action.label).toBe("Hoàn tác");

    options.action.onClick();
    await vi.waitFor(() => expect(restored).toHaveBeenCalledOnce());
    expect(api).toHaveBeenCalledWith(`/api/trash/${"ab".repeat(16)}/undo`, { method: "POST", body: {} });
    expect(toast.success).toHaveBeenLastCalledWith("Đã khôi phục “Sách”", { description: expect.stringContaining("hàng chờ") });
  });

  it("hoàn tác lỗi (quá hạn, trùng tên) thì báo lý do và không tải lại", async () => {
    api.mockRejectedValue(new Error("Đã có sách trùng tên ở đó"));
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "cd".repeat(16), note: "", onRestored: restored });
    toast.success.mock.calls[0][1].action.onClick();
    await vi.waitFor(() => expect(toast.error).toHaveBeenCalledWith("Chưa hoàn tác được", { description: "Đã có sách trùng tên ở đó" }));
    expect(restored).not.toHaveBeenCalled();
  });

  it("không có mã (khác ổ, vào Thùng rác ngay) thì không có nút", () => {
    toastRemoved({ message: "Đã xoá", title: "Sách", note: "", onRestored: () => undefined });
    const [, options] = toast.success.mock.calls[0];
    expect(options.action).toBeUndefined();
    expect(options.duration).toBeUndefined();
  });
});
