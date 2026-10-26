import { expect, it } from "vitest";
import { singleRecordActions } from "./BookScreen";
import type { ListenBook } from "./model";

// Cuốn chỉ có một hồ sơ (gần như mọi người) không có nút "Hồ sơ nghe:": đổi tên / xoá hồ sơ ấy phải có ở menu "Tuỳ chọn khác" (soát a105 F9).

const book = (names: string[]) =>
  ({ id: "sach", records: names.map((name, index) => ({ id: `r-${index}`, name, active: index === 0 })) }) as unknown as ListenBook;

it("một hồ sơ: menu có Đổi tên và Xoá hồ sơ, cùng hộp thoại với nút hồ sơ nghe", () => {
  const actions = singleRecordActions(book(["Mặc định"]));
  const byKey = Object.fromEntries(actions.map((action) => [action.key, action]));
  expect(byKey.rename.label).toBe("Đổi tên hồ sơ");
  expect(byKey.rename.dialog).toEqual({ kind: "rename", name: "Mặc định" });
  expect(byKey.delete.label).toBe("Xoá hồ sơ");
  expect(byKey.delete.dialog).toEqual({ kind: "delete", name: "Mặc định" });
  expect(byKey.delete.danger).toBe(true);
  expect(actions.map((action) => action.key)).toEqual(["create", "move", "rename", "delete"]);
});

it("nhiều hồ sơ hay chưa có hồ sơ: để nút hồ sơ nghe lo, menu này không thêm gì", () => {
  expect(singleRecordActions(book(["A", "B"]))).toEqual([]);
  expect(singleRecordActions(book([]))).toEqual([]);
  expect(singleRecordActions({ id: "sach" } as ListenBook)).toEqual([]);
});
