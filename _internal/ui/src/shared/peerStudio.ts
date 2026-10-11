// "Mở Studio" của máy tính đã ghép ngay trong app máy này (webui/peer_studio.py, soát a27 lỗi 14): cùng giao diện, chỉ khác gốc API.
// Trang mang `?peer=<mã máy>`; mọi lời gọi `/api/...` và `/media/...` đi qua cầu nối của máy chủ máy này, nơi giữ mã thiết bị đã
// nhận lúc ghép - mã ấy không bao giờ xuống trang.

/** Mã máy (12 hex, như `/api/computers/<mã>`) trong chuỗi truy vấn của trang; "" khi trang là của chính máy này. */
export function peerOf(search: string): string {
  const value = new URLSearchParams(search).get("peer") ?? "";
  return /^[0-9a-f]{12}$/.test(value) ? value : "";
}

/** Đường đi của một lời gọi: qua cầu nối khi đang mở Studio của máy khác, nguyên vẹn khi không. */
export function throughPeer(path: string, peer: string): string {
  return peer ? `/api/peers/${peer}/studio${path}` : path;
}

/** Địa chỉ trang mở Studio của máy `peer` ở `hashPath` (vd "/studio/<mã cuốn>"): giữ các tham số khác của trang (mã phiên). */
export function peerPage(search: string, peer: string, hashPath = "/studio"): string {
  const params = new URLSearchParams(search);
  params.set("peer", peer);
  return `/?${params.toString()}#${hashPath}`;
}

/** Địa chỉ trang của chính máy này (bỏ `peer`), về Thư viện. */
export function homePage(search: string): string {
  const params = new URLSearchParams(search);
  params.delete("peer");
  const rest = params.toString();
  return `/${rest ? `?${rest}` : ""}#/`;
}

/** Tên sự kiện cửa sổ khi máy kia không trả lời (câu của máy chủ trong `detail`): thanh "Studio của <máy>" báo và tự nối lại. */
export const PEER_SILENT_EVENT = "abook-peer-silent";

/** Máy kia chưa cho dòng thiết bị của máy này "Điều khiển sản xuất" - cùng câu máy chủ trả (peer_studio.listen_only). */
export function listenOnlyLine(name: string): string {
  return `Chỉ nghe - bật quyền sửa ở ${name}: Cài đặt > Thiết bị`;
}

/** Máy cần bật quyền sửa cho trang chỉ nghe: máy tính đang mở qua app này (`peer`), không thì chính máy phục vụ trang (`machine` -
 *  Studio từ xa trong trình duyệt hay app điện thoại, remote_studio.forward). */
export function listenOnlyOwner(info: { peer?: { name: string }; machine?: string }): string {
  return info.peer?.name || info.machine || "máy tính";
}

/** Dòng ở thanh trên cùng khi đang mở Studio của máy khác: máy ấy không trả lời (câu của máy chủ), chỉ được nghe, hay bình thường. */
export function peerBarLine(name: string, { silent = "", listenOnly = false }: { silent?: string; listenOnly?: boolean } = {}): string {
  if (silent) return `${silent} - tự nối lại khi máy ấy trả lời`;
  return listenOnly ? listenOnlyLine(name) : `Đang mở Studio của ${name}`;
}
