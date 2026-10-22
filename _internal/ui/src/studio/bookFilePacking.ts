import { api } from "./api";

/** Bắt đầu xuất sách rồi theo việc nền; theo lại việc cũ thì không tạo lượt xuất mới. */
export async function packBookFile<T>(bookId: string, body: { target: string; series: boolean; single?: boolean }, follow: () => Promise<T>, attach = false): Promise<T> {
  if (!attach) await api(`/api/books/${bookId}/bookfile-job`, { method: "POST", body });
  return follow();
}
