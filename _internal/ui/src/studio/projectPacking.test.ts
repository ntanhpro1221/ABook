import { describe, expect, it } from "vitest";
import { packError, packView } from "./projectPacking";

describe("packView", () => {
  it("chưa có tiến độ: dòng chung, thanh chạy không biết trước", () => {
    expect(packView(null)).toEqual({ title: "Đang đóng gói…", fraction: null });
    expect(packView({ state: "running", phase: "prepare" })).toEqual({ title: "Đang đóng gói…", fraction: null });
  });

  it("gom chương: nói số chương, thanh nằm trong phần của pha", () => {
    const view = packView({ state: "running", phase: "listen", done: 100, total: 400 });
    expect(view.title).toBe("Đang đóng gói (100/400 chương)…");
    expect(view.fraction).toBeGreaterThan(0.02);
    expect(view.fraction).toBeLessThan(0.38);
  });

  it("băm rồi ghi: nói dung lượng, thanh chỉ tăng qua các pha", () => {
    const hashing = packView({ state: "running", phase: "hash", done: 50 * 1024 ** 2, total: 200 * 1024 ** 2 });
    const writing = packView({ state: "running", phase: "write", done: 0, total: 200 * 1024 ** 2 });
    expect(hashing.title).toContain("50");
    expect(hashing.title).toContain("200");
    expect(writing.fraction).toBeGreaterThan(hashing.fraction ?? 1);
    expect(packView({ state: "running", phase: "write", done: 200 * 1024 ** 2, total: 200 * 1024 ** 2 }).fraction).toBeCloseTo(1);
  });

  it("đã quá tổng thì không vượt 100%", () => {
    expect(packView({ state: "running", phase: "write", done: 9, total: 3 }).fraction).toBeLessThanOrEqual(1);
  });
});

describe("packError", () => {
  it("ổ đầy và file bị khoá: lời cho người nghe, nguyên văn ở Chi tiết", () => {
    expect(packError("[Errno 28] No space left on device").summary).toContain("hết chỗ");
    const locked = packError("[WinError 32] The process cannot access the file because it is being used by another process");
    expect(locked.summary).toContain("thư mục khác");
    expect(locked.detail).toContain("WinError 32");
  });

  it("lời tiếng Việt của máy chủ giữ nguyên; lỗi lạ nói chung chung", () => {
    expect(packError("Dự án đang chạy. Đóng gói khi nó đã chạy xong hoặc đã dừng.")).toEqual({
      summary: "Dự án đang chạy. Đóng gói khi nó đã chạy xong hoặc đã dừng.",
      detail: "",
    });
    expect(packError("KeyError: 'x'")).toEqual({ summary: "Chưa gói được dự án.", detail: "KeyError: 'x'" });
  });
});
