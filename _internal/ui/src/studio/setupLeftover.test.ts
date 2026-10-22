import { describe, expect, it } from "vitest";
import { leftoverLine } from "./setupLeftover";

// Soát a92 V2: lượt cài của lần mở app trước còn chạy ngầm - nói rõ cho người dùng, cho chờ hay dừng.

const at = (hour: number, minute: number) => new Date(2026, 9, 22, hour, minute).getTime() / 1000;

describe("leftoverLine", () => {
  it("tiến trình mồ côi của lần mở trước: nói giờ bắt đầu, cho chờ hoặc dừng lượt cũ", () => {
    const line = leftoverLine({ pid: 5, since: at(9, 5), what: "cài Studio", orphan: true, childPid: 7 });
    expect(line).toContain("09:05");
    expect(line).toContain("lần mở app trước");
    expect(line).toContain("Dừng lượt cũ");
  });
  it("cửa sổ ABook khác đang cài: bảo đóng nó hay chờ, không hứa dừng được", () => {
    const line = leftoverLine({ pid: 5, since: at(14, 30), what: "cài Studio", orphan: false, childPid: 0 });
    expect(line).toContain("cửa sổ ABook khác");
    expect(line).toContain("14:30");
    expect(line).not.toContain("Dừng lượt cũ");
  });
});
