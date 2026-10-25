import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), warning: vi.fn(), error: vi.fn(), dismiss: vi.fn() }));
const api = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast }));
vi.mock("@/studio/api", () => ({ api }));

import { UNDO_SECONDS, UNDO_TOAST_MS, restoredMessage, restoredNote, toastRemoved } from "./trashUndo";

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});
afterEach(() => { vi.runAllTimers(); vi.useRealTimers(); });

describe("xoá sách có Hoàn tác", () => {
  it("nút Hoàn tác sống ngắn hơn hạn của máy chủ", () => {
    expect(UNDO_TOAST_MS).toBeLessThan(UNDO_SECONDS * 1000);
    expect(UNDO_TOAST_MS).toBe((UNDO_SECONDS - 2) * 1000);
  });

  it("cuốn từng xếp hàng chờ thì lời khôi phục nói hàng chờ không tự xếp lại", () => {
    expect(restoredNote({ wasQueued: true })).toContain("hàng chờ");
    expect(restoredNote({ wasQueued: false })).toBeUndefined();
  });

  it("có mã hoàn tác thì toast có nút; bấm gọi đường hoàn tác rồi tải lại danh sách", async () => {
    api.mockResolvedValue({ ok: true, title: "Sách", wasQueued: true });
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá dự án “Sách”", title: "Sách", undo: "ab".repeat(16), onRestored: restored });
    const [message, options] = toast.success.mock.calls[0];
    expect(message).toBe("Đã xoá dự án “Sách”");
    expect(options.duration).toBe(UNDO_TOAST_MS);
    expect(options.action.label).toBe("Hoàn tác");

    options.action.onClick();
    await vi.waitFor(() => expect(restored).toHaveBeenCalledOnce());
    expect(api).toHaveBeenCalledWith(`/api/trash/${"ab".repeat(16)}/undo`, { method: "POST", body: {} });
    expect(toast.warning).toHaveBeenLastCalledWith("Đã khôi phục “Sách”", { description: expect.stringContaining("hàng chờ") });
  });

  it("hoàn tác lỗi (quá hạn, trùng tên) thì báo lý do và không tải lại", async () => {
    api.mockRejectedValue(new Error("Đã có sách trùng tên ở đó"));
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "cd".repeat(16), onRestored: restored });
    toast.success.mock.calls[0][1].action.onClick();
    await vi.waitFor(() => expect(toast.error).toHaveBeenCalledWith("Chưa hoàn tác được", { description: "Đã có sách trùng tên ở đó" }));
    expect(restored).not.toHaveBeenCalled();
  });

  it("thông báo xoá là MỘT dòng + nút Hoàn tác: không dòng mô tả", () => {
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "ab".repeat(16), onRestored: () => undefined });
    expect(toast.success.mock.calls[0][1].description).toBeUndefined();
    toastRemoved({ message: "Đã xoá", title: "Sách", onRestored: () => undefined });
    expect(toast.success.mock.calls.at(-1)![1]).toBeUndefined();
  });

  it("điện thoại: nút Hoàn tác gọi hàm restore của nơi gọi thay vì đường máy chủ", async () => {
    const restore = vi.fn().mockResolvedValue(undefined);
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "ef".repeat(16), restore, onRestored: restored });
    toast.success.mock.calls[0][1].action.onClick();
    await vi.waitFor(() => expect(restored).toHaveBeenCalledOnce());
    expect(restore).toHaveBeenCalledWith("ef".repeat(16));
    expect(api).not.toHaveBeenCalled();
    expect(toast.success).toHaveBeenLastCalledWith("Đã khôi phục “Sách”", {});
  });

  it("điện thoại: chỗ cũ bị chiếm / quá hạn thì báo lý do, không tải lại", async () => {
    const restore = vi.fn().mockRejectedValue(new Error("Cuốn này không còn để hoàn tác"));
    const restored = vi.fn();
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "ef".repeat(16), restore, onRestored: restored });
    toast.success.mock.calls[0][1].action.onClick();
    await vi.waitFor(() => expect(toast.error).toHaveBeenCalledWith("Chưa hoàn tác được", { description: "Cuốn này không còn để hoàn tác" }));
    expect(restored).not.toHaveBeenCalled();
  });

  it("không có mã (khác ổ, vào Thùng rác ngay) thì không có nút", () => {
    toastRemoved({ message: "Đã xoá", title: "Sách", onRestored: () => undefined });
    expect(toast.success).toHaveBeenCalledWith("Đã xoá");
  });
});

it("ba lần xoá dùng một toast và hoàn tác cả ba mã, kể cả điện thoại", async () => {
  const restore = vi.fn().mockResolvedValue({ ok: true });
  const onRestored = vi.fn();
  for (const undo of ["one", "two", "three"]) toastRemoved({ message: "Đã xoá", title: undo, undo, restore, onRestored });
  const calls = toast.success.mock.calls.slice(0, 3);
  expect(new Set(calls.map(([, options]) => options.id)).size).toBe(1);
  expect(calls[0][1].id).toMatch(/^trash-undo-/);
  expect(calls[2][0]).toBe("Đã bỏ 3 cuốn");
  await calls[2][1].action.onClick();
  expect(restore.mock.calls.map(([token]) => token)).toEqual(["one", "two", "three"]);
  expect(onRestored).toHaveBeenCalledTimes(3);
});

it("mỗi mã giữ hạn riêng: thêm cuốn sau không kéo dài hạn cuốn trước", async () => {
  const restore = vi.fn().mockResolvedValue({ ok: true });
  const options = { message: "Đã xoá", title: "Sách", restore, onRestored: vi.fn() };
  toastRemoved({ ...options, undo: "old" });
  vi.advanceTimersByTime(20_000);
  toastRemoved({ ...options, undo: "new" });
  vi.advanceTimersByTime(8_000);
  const [, toastOptions] = toast.success.mock.calls.at(-1)!;
  await toastOptions.action.onClick();
  expect(restore.mock.calls.map(([token]) => token)).toEqual(["new"]);
});

it("một mã lỗi không ngăn các mã khác khôi phục và vẫn còn nút thử lại", async () => {
  const restore = vi.fn(async (token: string) => {
    if (token === "busy") throw new Error("Bạn hãy thử lại");
    return { ok: true };
  });
  const restored = vi.fn();
  for (const undo of ["busy", "good"]) toastRemoved({ message: "Đã xoá", title: undo, undo, restore, onRestored: restored });
  await toast.success.mock.calls.at(-1)![1].action.onClick();
  expect(restored).toHaveBeenCalledOnce();
  vi.advanceTimersByTime(0);
  restore.mockClear();
  await toast.success.mock.calls.at(-1)![1].action.onClick();
  expect(restore).toHaveBeenCalledWith("busy");
  expect(restore).toHaveBeenCalledTimes(1);
});

it("hoàn tác lỗi nhanh hiện lại nút dưới mã toast mới (Sonner gỡ toast vừa bấm theo mã cũ ~200 ms sau)", async () => {
  const restore = vi.fn().mockRejectedValue(new Error("Đã có sách trùng tên ở đó"));
  toastRemoved({ message: "Đã xoá", title: "Sách", undo: "fast", restore, onRestored: vi.fn() });
  const clicked = toast.success.mock.calls.at(-1)![1];
  await clicked.action.onClick();
  vi.advanceTimersByTime(0);
  const again = toast.success.mock.calls.at(-1)![1];
  expect(again.action.label).toBe("Hoàn tác");
  expect(again.id).not.toBe(clicked.id);
  // bỏ thêm một cuốn ngay sau cú bấm: cũng không dùng mã của toast đang bị gỡ
  toastRemoved({ message: "Đã xoá", title: "Khác", undo: "next", restore, onRestored: vi.fn() });
  expect(toast.success.mock.calls.at(-1)![1].id).not.toBe(clicked.id);
  toast.success.mock.calls.at(-1)![1].onDismiss();
});

it("gạt toast đi là không hoàn tác những cuốn ấy: lần bỏ sau không gộp và Hoàn tác không trả chúng về", async () => {
  const restore = vi.fn().mockResolvedValue({ ok: true });
  const options = { message: "Đã xoá", restore, onRestored: vi.fn() };
  toastRemoved({ ...options, title: "A", undo: "a" });
  toast.success.mock.calls.at(-1)![1].onDismiss();
  toastRemoved({ ...options, message: "Đã xoá “B”", title: "B", undo: "b" });
  const [message, shown] = toast.success.mock.calls.at(-1)!;
  expect(message).toBe("Đã xoá “B”");
  await shown.action.onClick();
  expect(restore.mock.calls.map(([token]) => token)).toEqual(["b"]);
});

it("toast cũ bị gỡ theo mã sau khi đã hiện toast mới thì không xoá các cuốn đang chờ", async () => {
  const restore = vi.fn().mockRejectedValue(new Error("Bạn hãy thử lại"));
  toastRemoved({ message: "Đã xoá", title: "A", undo: "keep", restore, onRestored: vi.fn() });
  const old = toast.success.mock.calls.at(-1)![1];
  await old.action.onClick();
  vi.advanceTimersByTime(0);
  old.onDismiss();
  restore.mockResolvedValue({ ok: true });
  await toast.success.mock.calls.at(-1)![1].action.onClick();
  expect(restore).toHaveBeenLastCalledWith("keep");
});

it("chỗ cũ đã có cuốn cùng tên: lời khôi phục nói tên mới của cuốn", async () => {
  expect(restoredMessage("Sách", { title: "Sách (2)", renamed: true })).toBe("Đã khôi phục “Sách” vào thư mục “Sách (2)”");
  expect(restoredMessage("Sách", { title: "Sách", renamed: false })).toBe("Đã khôi phục “Sách”");
  expect(restoredNote({ renamed: true, wasQueued: true })).toBe("Thư viện có hai cuốn trùng tên. Chưa xếp lại hàng chờ làm sách.");
  api.mockResolvedValue({ ok: true, title: "Sách (2)", renamed: true });
  const restored = vi.fn();
  toastRemoved({ message: "Đã xoá", title: "Sách", undo: "12".repeat(16), onRestored: restored });
  await toast.success.mock.calls.at(-1)![1].action.onClick();
  expect(toast.warning).toHaveBeenCalledWith("Đã khôi phục “Sách” vào thư mục “Sách (2)”", { description: "Thư viện có hai cuốn trùng tên." });
});

it("hoàn tác nhiều cuốn lần lượt, cũ trước: cuốn sau chỉ bắt đầu khi cuốn trước xong", async () => {
  const waiting = new Map<string, () => void>();
  const restore = vi.fn((token: string) => new Promise((resolve) => waiting.set(token, () => resolve({ ok: true }))));
  const onRestored = vi.fn();
  for (const undo of ["cu", "moi"]) toastRemoved({ message: "Đã xoá", title: undo, undo, restore, onRestored });
  const clicked = toast.success.mock.calls.at(-1)![1].action.onClick();
  await vi.waitFor(() => expect(restore).toHaveBeenCalledOnce());
  expect(restore).toHaveBeenLastCalledWith("cu");
  waiting.get("cu")!();
  await vi.waitFor(() => expect(restore).toHaveBeenCalledTimes(2));
  expect(restore).toHaveBeenLastCalledWith("moi");
  waiting.get("moi")!();
  await clicked;
  expect(onRestored).toHaveBeenCalledTimes(2);
});

it("cuốn về dưới mã mới thì những gì máy này nhớ theo mã sách đi theo; chưa chuyển được thì lời báo nói", async () => {
  const store = new Map([["abook-reading-old", '{"chapterId":3}'], ["abook-readaloud-voice-old", "edge:vi-VN-NamMinhNeural"]]);
  (globalThis as unknown as { localStorage: Storage }).localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  } as Storage;
  try {
    const restore = vi.fn().mockResolvedValue({ ok: true, title: "Sách (2)", renamed: true, oldId: "old", newId: "new" });
    toastRemoved({ message: "Đã xoá", title: "Sách", undo: "doi-ma", restore, onRestored: vi.fn() });
    await toast.success.mock.calls.at(-1)![1].action.onClick();
    expect(Object.fromEntries(store)).toEqual({ "abook-reading-new": '{"chapterId":3}', "abook-readaloud-voice-new": "edge:vi-VN-NamMinhNeural" });
  } finally {
    delete (globalThis as { localStorage?: Storage }).localStorage;
  }
  expect(restoredNote({ renamed: true, dataLeft: true })).toContain("Chưa mang theo chỗ nghe");
});

it("gạt toast hay hết mục thì lần bỏ kế hiện dưới mã mới (Sonner còn giữ toast đang thoát)", () => {
  const options = { message: "Đã xoá", restore: vi.fn(), onRestored: vi.fn() };
  toastRemoved({ ...options, title: "A", undo: "gat" });
  const swiped = toast.success.mock.calls.at(-1)![1];
  swiped.onDismiss();
  toastRemoved({ ...options, title: "B", undo: "sau-gat" });
  const next = toast.success.mock.calls.at(-1)![1];
  expect(next.id).not.toBe(swiped.id);

  vi.advanceTimersByTime(UNDO_TOAST_MS); // hết hạn: hết mục, toast được gỡ
  expect(toast.dismiss).toHaveBeenLastCalledWith(next.id);
  toastRemoved({ ...options, title: "C", undo: "sau-het" });
  expect(toast.success.mock.calls.at(-1)![1].id).not.toBe(next.id);
});
