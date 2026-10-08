// Máy đã ghép đi đường nào (webui/remote_books.py): Wi-Fi ("192.168.1.20:47630"), Bluetooth ("bt:<địa chỉ>" - ghép bằng địa
// chỉ Bluetooth), hay Wi-Fi có Bluetooth dự phòng (trường `bt`). Phần chữ hiện cho người dùng nằm ở đây để thử được.

/** Thiết bị Bluetooth đã ghép trong Cài đặt Windows (GET /api/computers/bluetooth). */
export interface PairedDevice {
  name: string;
  address: string;
  kind: "phone" | "computer";
}

export interface RoutedComputer {
  host: string;
  port: number;
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

/** Dòng "đi đường nào" dưới tên máy: "Bluetooth · Galaxy của An", "192.168.1.20:47630", hay
 *  "192.168.1.20:47630 · dự phòng Bluetooth · Galaxy của An". */
export function routeLine(computer: RoutedComputer, devices: readonly PairedDevice[]): string {
  const address = bluetoothAddress(computer);
  if (isBluetoothHost(computer.host)) return `Bluetooth · ${deviceName(devices, address)}`;
  const wifi = `${computer.host}:${computer.port}`;
  return address ? `${wifi} · dự phòng Bluetooth · ${deviceName(devices, address)}` : wifi;
}

export function deviceKindLabel(kind: PairedDevice["kind"]): string {
  return kind === "phone" ? "điện thoại" : "máy tính";
}
