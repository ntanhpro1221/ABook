import type { QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { toast } from "sonner";
import { EbookLibrary, type DownloadEvent } from "./plugins";

// Tiến độ tải sách, nghe ở CẤP APP chứ không ở màn "Tải sách": trước đây listener nằm trong màn ấy, rời màn giữa
// chừng là lỡ sự kiện "xong" - thư viện không làm mới (bìa/chương mới chỉ hiện sau ~30 giây hoặc mở lại app) và mất
// luôn thông báo "Đã tải xong" (27-09, thấy trên máy ảo khi cập nhật ảnh bìa).

let progress: Record<string, DownloadEvent> = {};
const listeners = new Set<() => void>();

function publish(event: DownloadEvent) {
  progress = { ...progress, [event.bookId]: event };
  listeners.forEach((listener) => listener());
}

export function useDownloadProgress(): Record<string, DownloadEvent> {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => progress,
  );
}

/** Gọi một lần khi app mở: theo dõi mọi lượt tải, làm mới thư viện khi xong. Trả về hàm gỡ. */
export function watchDownloads(client: QueryClient): () => void {
  const handle = EbookLibrary.addListener("download", (event) => {
    publish(event);
    if (event.finished) {
      toast.success("Đã tải xong", { description: "Sách đã có trong Thư viện, nghe được cả khi không có mạng." });
      void client.invalidateQueries({ queryKey: ["remote"] });
      void client.invalidateQueries({ queryKey: ["listen"] });
      void client.invalidateQueries({ queryKey: ["storage"] });
    }
    if (event.error) toast.error("Tải bị gián đoạn", { description: event.error });
  });
  return () => void handle.then((listener) => listener.remove());
}

/** Phần sửa gửi về máy tính xong (hay hỏng) ở nền: làm mới sách để dòng tình trạng và tên / bìa mới của máy tính hiện ra. */
export function watchEditsSync(client: QueryClient): () => void {
  const handle = EbookLibrary.addListener("editsSync", () => {
    void client.invalidateQueries({ queryKey: ["listen"] });
    void client.invalidateQueries({ queryKey: ["library"] });
  });
  return () => void handle.then((listener) => listener.remove());
}
