import type { ScannedFile } from "@/studio/api";
import { formatNumber } from "@/shared/format";

// Cách trình tạo sách trình bày kết quả quét: trang phụ của file sách (chưa tích sẵn, cùng luật với Nghe ngay) và số đếm ước tính.

/** Trang phụ (bìa, bản quyền, mục lục, mục rất ngắn) trong kết quả quét, theo thứ tự trong sách. */
export function matterFiles(files: readonly ScannedFile[]): ScannedFile[] {
  return files.filter((file) => file.matter);
}

/** Đường dẫn các trang phụ mà người dùng CHƯA tích lại (`keep` = những trang họ đã tích): chúng không vào sách. */
export function unpickedMatter(files: readonly ScannedFile[], keep: readonly string[]): string[] {
  const kept = new Set(keep);
  return files.filter((file) => file.matter && !kept.has(file.path)).map((file) => file.path);
}

/** Mọi chương không vào sách: chương người dùng bỏ tay, và trang phụ chưa tích lại. */
export function allExcluded(files: readonly ScannedFile[], excluded: readonly string[], keep: readonly string[]): string[] {
  return [...new Set([...excluded, ...unpickedMatter(files, keep)])];
}

/** Tích / bỏ tích một trang phụ: tích thì ra khỏi danh sách bỏ tay luôn (bấm "Bỏ chương" rồi tích lại là có lại). */
export function keepMatter(
  state: { keepMatter?: string[]; excluded: string[] },
  path: string,
  on: boolean,
): { keepMatter: string[]; excluded: string[] } {
  const keep = (state.keepMatter ?? []).filter((item) => item !== path);
  return on
    ? { keepMatter: [...keep, path], excluded: state.excluded.filter((item) => item !== path) }
    : { keepMatter: keep, excluded: state.excluded };
}

/** Số ước tính của file dài (chỉ đọc phần đầu để đếm): đặt "~" trước số. */
export function approx(value: number, estimated?: boolean): string {
  return `${estimated ? "~" : ""}${formatNumber(value)}`;
}
