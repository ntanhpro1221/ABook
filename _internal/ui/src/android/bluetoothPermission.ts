// Quyền "Thiết bị ở gần" (Bluetooth) của màn "Tải sách": nói vì sao cần TRƯỚC khi Android hỏi, và khi người dùng đã từ chối hẳn (hộp xin của
// Android không hiện nữa) thì chỉ đường tới Cài đặt thay vì một lời báo lỗi lặp lại mỗi lần bấm (soát a66: ngõ cụt).

/** Trạng thái quyền như Capacitor báo (LibraryPlugin.bluetoothPermission). */
export type BluetoothPermission = "granted" | "prompt" | "prompt-with-rationale" | "denied";

/** Việc kế tiếp khi người dùng bấm "Kết nối qua Bluetooth": có quyền thì tìm máy luôn; chưa có thì giải thích rồi mới xin; từ chối hẳn thì Cài đặt. */
export function bluetoothStep(state: BluetoothPermission): "go" | "explain" | "settings" {
  if (state === "granted") return "go";
  return state === "denied" ? "settings" : "explain";
}

export const BLUETOOTH_REASON =
  "Để thấy máy tính đã ghép Bluetooth với điện thoại này và nhận sách qua đó, ABook cần quyền “Thiết bị ở gần”. ABook không dò hay kết nối thiết bị nào khác.";

export const BLUETOOTH_DENIED =
  "Quyền “Thiết bị ở gần” của ABook đang tắt. Mở Cài đặt → Quyền → Thiết bị ở gần → Cho phép, rồi quay lại bấm Kết nối qua Bluetooth.";
