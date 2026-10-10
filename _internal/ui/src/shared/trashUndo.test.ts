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

  it("điện thoại: sau hạn là xoá hẳn (không có Thùng rác) và lời báo nói đúng như thế", () => {
    expect(removedDescription("", true, "gone")).toBe(`Hoàn tác được trong ${UNDO_SECONDS} giây; sau đó cuốn bị xoá hẳn khỏi điện thoại.`);
    expect(removedDescription("", false, "gone")).toBe("Cuốn đã bị xoá hẳn khỏi điện thoại.");
    expect(removedDescription("", true, "gone")).not.toContain("Thùng rác");
  });

  it("điện thoại: nút Hoàn tác gọi hàm restore của nơi gọi thay vì đường máy chủ", async () => {
    const restore = vi.fn().mockResolvedValue(undefined);
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "ef".repeat(16), note: "", to: "gone", restore, onRestored: restored });
    toast.success.mock.calls[0][1].action.onClick();
    await vi.waitFor(() => expect(restored).toHaveBeenCalledOnce());
    expect(restore).toHaveBeenCalledWith("ef".repeat(16));
    expect(api).not.toHaveBeenCalled();
    expect(toast.success).toHaveBeenLastCalledWith("Đã khôi phục “Sách”", { description: undefined });
  });

  it("điện thoại: chỗ cũ bị chiếm / quá hạn thì báo lý do, không tải lại", async () => {
    const restore = vi.fn().mockRejectedValue(new Error("Cuốn này không còn để hoàn tác"));
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "ef".repeat(16), note: "", to: "gone", restore, onRestored: restored });
    toast.success.mock.calls[0][1].action.onClick();
    await vi.waitFor(() => expect(toast.error).toHaveBeenCalledWith("Chưa hoàn tác được", { description: "Cuốn này không còn để hoàn tác" }));
    expect(restored).not.toHaveBeenCalled();
  });

  it("không có mã (khác ổ, vào Thùng rác ngay) thì không có nút", () => {
    toastRemoved({ message: "Đã xoá", title: "Sách", note: "", onRestored: () => undefined });
    const [, options] = toast.success.mock.calls[0];
    expect(options.action).toBeUndefined();
    expect(options.duration).toBeUndefined();
  });
});
