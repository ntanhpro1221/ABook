package vn.abook.player.ui.data

import java.util.TimeZone

/**
 * Giờ treo tường cho chữ nói theo ngày/giờ ("Hôm nay", "tối qua 23:41", "7 ngày qua", "13:57"). Sản phẩm luôn đọc giờ máy và múi giờ máy;
 * test ảnh/test trạng thái ghim cả hai (FixedWallClock ở src/test) để ảnh không đổi theo lúc chạy - trước đây "Hôm nay" thành "Hôm qua" quanh nửa đêm.
 * Chỉ dùng cho chữ hiển thị; hạn chờ, TTL cache, dấu thời gian ghi đĩa vẫn đọc đồng hồ thật như cũ.
 */
object WallClock {
    @Volatile var nowMs: () -> Long = System::currentTimeMillis
    @Volatile var zone: () -> TimeZone = TimeZone::getDefault
}
