import { QueryClient } from "@tanstack/react-query";
import { afterEach, expect, it } from "vitest";
import { httpSource } from "@/desktop/httpSource";
import { ApiError, setApiTransport } from "@/studio/api";

import { isRecordGone, RECORD_GONE_MESSAGE, shownRecord } from "./recordWrites";

// Việc ghi của người nghe (a106): đi kèm mã hồ sơ của màn đã bấm; hồ sơ không còn thì nhận ra rõ ràng.

afterEach(() => {
  setApiTransport(null);
});

it("đánh dấu chương, đánh dấu cả cuốn mang mã hồ sơ", async () => {
  const calls: { path: string; init?: { method?: string; body?: unknown } }[] = [];
  setApiTransport(async (path, init) => {
    calls.push({ path, init });
    return {};
  });
  await httpSource.setChapterDone("book", 3, true, "r-a");
  await httpSource.setFinished("book", true, "r-a");
  expect(calls[0]).toMatchObject({ path: "/api/listen/books/book/chapters/3/done", init: { method: "POST", body: { done: true, record: "r-a" } } });
  expect(calls[1]).toMatchObject({ path: "/api/listen/books/book/finished", init: { method: "POST", body: { finished: true, record: "r-a" } } });
});

it("hồ sơ không còn: 409 của máy tính và lỗi cùng câu của điện thoại đều nhận ra", () => {
  expect(isRecordGone(new ApiError(409, RECORD_GONE_MESSAGE))).toBe(true);
  expect(isRecordGone(new Error(RECORD_GONE_MESSAGE))).toBe(true);
  expect(isRecordGone(new ApiError(500, "Máy gặp lỗi"))).toBe(false);
});

it("hồ sơ của màn là hồ sơ đang hiện trong sách đã tải; chưa có sách hay nguồn không có hồ sơ thì để máy chủ chọn", () => {
  const client = new QueryClient();
  expect(shownRecord(client, "book")).toBeUndefined();
  client.setQueryData(["listen", "book", "book"], { id: "book", records: [{ id: "r-a", active: false }, { id: "r-b", active: true }] });
  expect(shownRecord(client, "book")).toBe("r-b");
  client.setQueryData(["listen", "book", "khac"], { id: "khac" });
  expect(shownRecord(client, "khac")).toBeUndefined();
});
