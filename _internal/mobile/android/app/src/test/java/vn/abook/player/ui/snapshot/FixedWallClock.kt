package vn.abook.player.ui.snapshot

import org.junit.rules.ExternalResource
import vn.abook.player.ui.data.WallClock
import java.time.LocalDateTime
import java.time.ZoneId
import java.util.TimeZone

/**
 * Ghim [WallClock] cho một lớp test ảnh/test trạng thái: giờ giữa ngày, múi giờ cố định. Dữ liệu dựng "cách đây một giờ" lấy từ [nowMs]/[nowSeconds],
 * không từ System.currentTimeMillis - nếu không, nhóm "Hôm nay"/"Hôm qua" đổi theo lúc chạy (book_history_light đỏ quanh nửa đêm, clockfix174).
 * `tests/test_snapshot_wall_clock.py` chặn test ảnh đọc giờ thật.
 */
class FixedWallClock(at: LocalDateTime = NOON, val zone: TimeZone = TimeZone.getTimeZone(ZONE)) : ExternalResource() {
    val nowMs: Long = at.atZone(zone.toZoneId()).toInstant().toEpochMilli()
    val nowSeconds: Double get() = nowMs / 1000.0
    private var saved: Pair<() -> Long, () -> TimeZone>? = null

    override fun before() {
        saved = WallClock.nowMs to WallClock.zone
        WallClock.nowMs = { nowMs }
        WallClock.zone = { zone }
    }

    override fun after() {
        saved?.let { (now, zone) -> WallClock.nowMs = now; WallClock.zone = zone }
        saved = null
    }

    companion object {
        /** Thứ Bảy 24/10/2026 12:00: xa nửa đêm cả hai phía, dữ liệu "-1 giờ" hay "-7 ngày" không bao giờ đổi ngày khác cách dự định. */
        val NOON: LocalDateTime = LocalDateTime.of(2026, 10, 24, 12, 0)
        val ZONE: ZoneId = ZoneId.of("Asia/Ho_Chi_Minh")
    }
}
