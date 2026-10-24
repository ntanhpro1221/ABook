// Đồng hồ giả của phòng trưng bày: mọi trang mở ra lúc 21:15 thứ Bảy 24-10-2026 (giờ Việt Nam), rồi chạy theo thời gian thật từ đó -
// "x phút trước" giống nhau ở mọi lần chụp, mà bộ hẹn giờ / đếm lùi của app vẫn chạy đúng nhịp. Mục trưng bày đổi được giờ (`?clock=`).

export const NOW_MS = Date.UTC(2026, 9, 24, 14, 15, 0);
export const NOW_SECONDS = Math.floor(NOW_MS / 1000);

let installed = false;

/** Thay `Date` toàn cục: `new Date()` / `Date.now()` bắt đầu ở `start` (ms). Ngày tạo bằng tham số giữ nguyên. */
export function installClock(start = NOW_MS): void {
  if (installed) return;
  installed = true;
  const RealDate = Date;
  const offset = start - RealDate.now();
  const now = () => RealDate.now() + offset;
  class GalleryDate extends RealDate {
    constructor(...args: unknown[]) {
      if (args.length === 0) super(now());
      else super(...(args as [string | number | Date]));
    }
    static now(): number {
      return now();
    }
  }
  globalThis.Date = GalleryDate as DateConstructor;
}
