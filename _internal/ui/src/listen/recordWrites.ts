import { S } from "../shared/strings.generated";
import type { QueryClient } from "@tanstack/react-query";
import type { ListenBook } from "./model";

// Việc ghi của người nghe (đánh dấu chương, đánh dấu cả cuốn) mang MÃ HỒ SƠ của màn đã bấm. Hồ sơ ấy đã bị xoá hay chuyển sang
// cuốn khác trong lúc đó (cửa sổ khác, máy kia) thì máy chủ từ chối (máy tính: 409; điện thoại: lỗi cùng câu) - không ghi sang người khác.

export const RECORD_GONE_MESSAGE = S.s_ho_so_nghe_nay_da_bi_xoa_hoac_chuyen_sang_310a9a7d;

/** Hồ sơ mà màn của `bookId` đang hiện (đúng thứ người dùng nhìn khi bấm); chưa tải sách hay nguồn không có hồ sơ: undefined (máy chủ dùng hồ sơ đang dùng). */
export function shownRecord(client: QueryClient, bookId: string): string | undefined {
  return client.getQueryData<ListenBook>(["listen", "book", bookId])?.records?.find((record) => record.active)?.id;
}

/** Lời từ chối "hồ sơ không còn" (khác với mọi lỗi ghi thường). */
export function isRecordGone(error: unknown): boolean {
  const failure = error as { status?: number; message?: string } | null;
  return failure?.status === 409 || /^Hồ sơ nghe này/.test(failure?.message ?? "");
}
