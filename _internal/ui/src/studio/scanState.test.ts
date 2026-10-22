import { describe, expect, it } from "vitest";
import type { ScanResult } from "./api";
import { createGate, scanIsCurrent, sourcesKey, type ScannedSources } from "./scanState";

// Soát a92 V1: kết quả quét gắn với đúng danh sách nguồn; nguồn đổi thì kết quả cũ không dùng cho nút Tạo / payload.

const result = { files: [{ path: "old/1.txt" }], totals: { words: 1, chapters: 1, audioSeconds: 1 }, skipped: [], missing: [] } as unknown as ScanResult;
const scanned = (paths: string[]): ScannedSources => ({ key: sourcesKey(paths), result });

describe("scanIsCurrent", () => {
  it("chỉ đúng khi kết quả quét của chính danh sách nguồn hiện tại", () => {
    expect(scanIsCurrent(scanned(["old/1.txt"]), ["old/1.txt"])).toBe(true);
    expect(scanIsCurrent(scanned(["old/1.txt"]), ["old/1.txt", "new/2.txt"])).toBe(false);
    expect(scanIsCurrent(scanned(["old/1.txt"]), ["new/2.txt", "old/1.txt"])).toBe(false);
  });
  it("chưa có nguồn thì không có gì để đợi; có nguồn mà chưa quét thì chưa đúng", () => {
    expect(scanIsCurrent(null, [])).toBe(true);
    expect(scanIsCurrent(null, ["a"])).toBe(false);
  });
});

describe("createGate", () => {
  const ready = { title: "Sách", reading: false, unfit: false };
  it("đang đọc nguồn: nút Tạo chờ và nói rõ", () => {
    const gate = createGate({ ...ready, reading: true });
    expect(gate.disabled).toBe(true);
    expect(gate.reading).toBe(true);
    expect(gate.label).toBe("Đang đọc nguồn…");
  });
  it("đọc xong, có tên sách: bấm được", () => {
    expect(createGate(ready).disabled).toBe(false);
    expect(createGate({ ...ready, title: "  " }).disabled).toBe(true);
    expect(createGate({ ...ready, unfit: true }).disabled).toBe(true);
  });
});
