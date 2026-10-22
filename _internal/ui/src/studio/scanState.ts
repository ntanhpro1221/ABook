import type { ScanResult } from "./api";

/**
 * Kết quả quét nguồn của trình tạo sách, gắn với đúng danh sách nguồn đã quét (soát a92 V1): thêm / bớt file làm danh
 * sách đổi trước khi lượt quét mới xong, và kết quả cũ không được dùng cho nút Tạo hay payload. `result` rỗng = lượt quét
 * của danh sách ấy đã hỏng.
 */
export interface ScannedSources {
  key: string;
  result: ScanResult | null;
}

export const sourcesKey = (paths: readonly string[]) => paths.join("\n");

/** Kết quả đang giữ là của đúng danh sách nguồn hiện tại (hay chưa có nguồn nào thì không có gì để đợi). */
export function scanIsCurrent(scanned: ScannedSources | null, paths: readonly string[]): boolean {
  return paths.length === 0 ? true : scanned?.key === sourcesKey(paths);
}

/** Nút cuối trình tạo: chờ khi còn đọc nguồn (nói rõ), khoá khi thiếu tên sách hay máy không làm được. */
export function createGate({ title, reading, unfit }: { title: string; reading: boolean; unfit: boolean }): {
  disabled: boolean;
  reading: boolean;
  label: string | null;
} {
  return { disabled: reading || !title.trim() || unfit, reading, label: reading ? "Đang đọc nguồn…" : null };
}
