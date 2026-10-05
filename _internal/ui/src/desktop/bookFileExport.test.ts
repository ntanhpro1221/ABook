import { describe, expect, it } from "vitest";
import { defaultExportFolder, exportWhereHint, packingText } from "./bookFileExport";

describe("defaultExportFolder", () => {
  it("joins with the separator the library path already uses", () => {
    expect(defaultExportFolder("D:\\Sách\\Thư viện")).toBe("D:\\Sách\\Thư viện\\Đã xuất");
    expect(defaultExportFolder("D:\\Sách\\")).toBe("D:\\Sách\\Đã xuất");
    expect(defaultExportFolder("/home/an/sach")).toBe("/home/an/sach/Đã xuất");
  });

  it("says nothing it does not know", () => {
    expect(defaultExportFolder(undefined)).toBeNull();
    expect(defaultExportFolder("")).toBeNull();
  });
});

describe("exportWhereHint", () => {
  it("tells the picker case and the fixed-folder case apart", () => {
    expect(exportWhereHint(true, "D:\\Sách")).toMatch(/chọn thư mục/);
    expect(exportWhereHint(false, "D:\\Sách")).toBe("Lưu vào D:\\Sách\\Đã xuất");
    expect(exportWhereHint(false, undefined)).toMatch(/Đã xuất/);
  });
});

describe("packingText", () => {
  it("changes as time passes", () => {
    expect(packingText(4, 0)).toBe("4 chương · đã 0:00");
    expect(packingText(4, 75)).toBe("4 chương · đã 1:15");
  });
});
