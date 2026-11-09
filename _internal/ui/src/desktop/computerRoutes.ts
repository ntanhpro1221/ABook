import { S } from "../shared/strings.generated";
import { connectionRoute } from "@/shared/connectionRoute";
// Máy đã ghép đi đường nào (webui/remote_books.py): Wi-Fi ("192.168.1.20:47630"), Bluetooth ("bt:<địa chỉ>" - ghép bằng địa
// chỉ Bluetooth), hay Wi-Fi có Bluetooth dự phòng (trường `bt`). Phần chữ hiện cho người dùng nằm ở đây để thử được.

/** Thiết bị Bluetooth đã ghép trong Cài đặt Windows (GET /api/computers/bluetooth). */
export interface PairedDevice {
  name: string;
  address: string;
  kind: "phone" | "computer";
  /** Dịch vụ ABook tìm thấy qua SDP trên chính thiết bị này. */
  services: ("release" | "dev")[];
}

export interface RoutedComputer {
  host: string;
  port: number;
  connectedVia?: string;
  /** Địa chỉ Bluetooth dự phòng của máy ghép qua Wi-Fi (máy tự tìm theo tên, hay người dùng chọn). */
  bt?: string;
}

/** Máy ghép bằng địa chỉ Bluetooth (không có đường Wi-Fi). */
export function isBluetoothHost(host: string): boolean {
  return host.toLowerCase().startsWith("bt:");
}

/** Địa chỉ Bluetooth của máy ("AA:BB:..."), hay "" nếu máy chỉ có Wi-Fi. */
export function bluetoothAddress(computer: RoutedComputer): string {
  return (isBluetoothHost(computer.host) ? computer.host.slice(3) : computer.bt ?? "").toUpperCase();
}

/** Tên thiết bị đã ghép ở Windows cho địa chỉ ấy; không có thì chính địa chỉ. */
export function deviceName(devices: readonly PairedDevice[], address: string): string {
  return devices.find((device) => device.address.toUpperCase() === address.toUpperCase())?.name || address;
}

/** Nhãn đường vừa nối thành công, không đưa địa chỉ vào dòng trạng thái. */
export function routeLine(computer: RoutedComputer, _devices: readonly PairedDevice[]): string {
  return connectionRoute(computer.connectedVia);
}

export function deviceKindLabel(kind: PairedDevice["kind"]): string {
  return kind === "phone" ? S.s_dien_thoai_2f73f175 : S.s_may_tinh_8eafc226;
}

/** Đang chờ máy kia dậy (webui/remote_books.py `waking`): nối được tới máy mà ABook bên ấy chưa trả lời - điện thoại tắt màn
 *  hình thì hệ điều hành cho ABook "ngủ" tới vài phút. Giây kể từ 1970, như `lastSeen`. */
export interface Waking {
  since: number;
  until: number;
  via: "wifi" | "bluetooth";
}

/** Dòng trạng thái khi đang chờ: "Điện thoại đang ngủ - mở ABook trên điện thoại để trả lời ngay · chờ thêm tối đa 4 phút". */
export function wakingLine(computer: { kind?: "phone" | "computer"; waking?: Waking }, now: number = Date.now() / 1000): string {
  const left = Math.max(0, (computer.waking?.until ?? now) - now);
  const rest = left >= 90 ? S.s_0_phut_2596d212(Math.round(left / 60)) : S.s_0_giay_daac30d3(Math.max(1, Math.round(left)));
  const what =
    computer.kind === "computer"
      ? S.s_may_kia_chua_tra_loi_mo_abook_tren_may_ay_0c068d6a
      : S.s_dien_thoai_dang_ngu_mo_abook_tren_dien_tho_15b25e58;
  return S.s_0_cho_them_toi_da_1_3bde994a(what, rest);
}
