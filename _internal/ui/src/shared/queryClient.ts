import { QueryClient } from "@tanstack/react-query";

/** QueryClient chung của hai nền.
 *
 * Mọi truy vấn của app gọi máy chủ cục bộ (máy tính) hay plugin native (điện thoại), không cần Internet.
 * Mặc định react-query ('online') TẠM DỪNG mọi truy vấn chưa có cache khi trình duyệt báo mất mạng: thẻ giọng
 * trong Cài đặt biến mất, nút "Tải giọng" không hiện, thanh tải đứng 0 % dù lõi đã báo lỗi. 'always' cho
 * chúng chạy như thường; việc nào thật sự cần mạng tự báo lỗi của nó. */
export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 1000, networkMode: "always" },
      mutations: { networkMode: "always" },
    },
  });
}
