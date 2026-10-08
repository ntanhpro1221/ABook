// "Cho máy khác nghe thư viện này": máy OPPO, Xiaomi, Samsung... cho ABook "ngủ" khi nó ở nền (đo 08-10 trên ColorOS: ~30 giây sau
// khi rời màn hình), máy tính phải chờ tới vài phút. Không có cách công khai nào để app tự xin miễn - chỉ người dùng bật được,
// trong trang thông tin ứng dụng (LibraryPlugin.openAppSettings). Lời chỉ đường theo hãng (Build.MANUFACTURER).

/** Chỉ đường trong trang cài đặt mở ra, theo hãng máy. */
export function backgroundHelp(manufacturer: string | undefined): string {
  const maker = (manufacturer ?? "").trim().toLowerCase();
  if (["oppo", "realme", "oneplus"].includes(maker)) {
    return "Trong trang mở ra: Pin → bật “Cho phép hoạt động nền” và “Tự khởi chạy”.";
  }
  if (["xiaomi", "redmi", "poco"].includes(maker)) {
    return "Trong trang mở ra: Tiết kiệm pin → chọn “Không hạn chế”.";
  }
  if (maker === "samsung") {
    return "Trong trang mở ra: Pin → chọn “Không hạn chế”.";
  }
  return "Trong trang mở ra: Pin → chọn “Không hạn chế” hay “Cho phép chạy nền” (tên mục khác nhau tuỳ máy).";
}
