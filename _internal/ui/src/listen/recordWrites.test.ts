import { QueryClient } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { httpSource } from "@/desktop/httpSource";
import { ApiError, setApiTransport } from "@/studio/api";

const toasts = vi.hoisted(() => ({ error: vi.fn() }));
vi.mock("sonner", () => ({ toast: toasts }));

import { isRecordGone, RECORD_GONE_MESSAGE, reportWriteFailure, shownRecord } from "./recordWrites";

// Bốn việc ghi còn lại (a106): đi kèm mã hồ sơ của màn đã bấm; hồ sơ không còn thì báo một lần, rõ ràng.

afterEach(() => {
  setApiTransport(null);
  toasts.error.mockReset();
});

it("đánh dấu chương, đánh dấu cả cuốn, sửa và xoá dấu trang mang mã hồ sơ", async () => {
  const calls: { path: string; init?: { method?: string; body?: unknown } }[] = [];
  setApiTransport(async (path, init) => {
    calls.push({ path, init });
    return {};
  });
  await httpSource.setChapterDone("book", 3, true, "r-a");
  await httpSource.setFinished("book", true, "r-a");
  await httpSource.updateBookmark("book", "m1", "ghi chú", "r-a");
  await httpSource.deleteBookmark("book", "m1", "r-a");
  expect(calls[0]).toMatchObject({ path: "/api/listen/books/book/chapters/3/done", init: { method: "POST", body: { done: true, record: "r-a" } } });
  expect(calls[1]).toMatchObject({ path: "/api/listen/books/book/finished", init: { method: "POST", body: { finished: true, record: "r-a" } } });
  expect(calls[2]).toMatchObject({ path: "/api/listen/books/book/bookmarks/m1", init: { method: "PUT", body: { note: "ghi chú", record: "r-a" } } });
  expect(calls[3].path).toBe("/api/listen/books/book/bookmarks/m1?record=r-a");
  expect(calls[3].init?.method).toBe("DELETE");
});

it("không nói hồ sơ nào thì không gửi hồ sơ (máy chủ dùng hồ sơ đang dùng)", async () => {
  const calls: string[] = [];
  setApiTransport(async (path) => {
    calls.push(path);
    return {};
  });
  await httpSource.deleteBookmark("book", "m1");
  expect(calls).toEqual(["/api/listen/books/book/bookmarks/m1"]);
});

it("hồ sơ không còn: 409 của máy tính và lỗi cùng câu của điện thoại đều nhận ra, báo một thông báo", () => {
  expect(isRecordGone(new ApiError(409, RECORD_GONE_MESSAGE))).toBe(true);
  expect(isRecordGone(new Error(RECORD_GONE_MESSAGE))).toBe(true);
  expect(isRecordGone(new ApiError(500, "Máy gặp lỗi"))).toBe(false);
  reportWriteFailure(new ApiError(409, RECORD_GONE_MESSAGE), "Chưa đặt được dấu trang");
  expect(toasts.error).toHaveBeenCalledWith(RECORD_GONE_MESSAGE, { id: "record-gone" });
  toasts.error.mockReset();
  reportWriteFailure(new ApiError(500, "x"), "Chưa đặt được dấu trang");
  expect(toasts.error).toHaveBeenCalledWith("Chưa đặt được dấu trang");
});

it("hồ sơ của màn là hồ sơ đang hiện trong sách đã tải; chưa có sách hay nguồn không có hồ sơ thì để máy chủ chọn", () => {
  const client = new QueryClient();
  expect(shownRecord(client, "book")).toBeUndefined();
  client.setQueryData(["listen", "book", "book"], { id: "book", records: [{ id: "r-a", active: false }, { id: "r-b", active: true }] });
  expect(shownRecord(client, "book")).toBe("r-b");
  client.setQueryData(["listen", "book", "khac"], { id: "khac" });
  expect(shownRecord(client, "khac")).toBeUndefined();
});
