package vn.abook.player

/**
 * Hạn chờ theo giờ thật của test JVM: một chỗ duy nhất, nhân với hệ số máy tải (Python: tests/timing.py, web: ui/src/testing/timeScale.ts).
 *
 * `ABOOK_TEST_TIME_SCALE` (mặc định 5) - máy chậm hơn nữa thì đặt cao hơn. Chỉ dùng cho HẠN CHỜ ("không quá N ms") và
 * cho cận trên của "xong ngay"; cận dưới ("đã chờ ít nhất N ms") không nhân. `blockedMs` là thời gian mà hành vi SAI sẽ mất:
 * hạn nhân hệ số bị chặn ở 80% con số ấy để nới hạn không biến thành test không bắt được lỗi nó canh.
 *
 * Test đo hiệu năng thật (ngưỡng cố định) đi qua [perf]: chỉ chạy khi đặt `ABOOK_PERF=1`, ngoài cổng thường.
 * Máy dò scripts/flaky_patterns.py cấm `System.currentTimeMillis() + N` / `nanoTime() - x < N` trần trong test.
 */
object TestTime {
    val scale: Double = System.getenv("ABOOK_TEST_TIME_SCALE")?.toDoubleOrNull()?.coerceAtLeast(1.0) ?: 5.0

    fun ms(limit: Long, blockedMs: Long? = null): Long {
        val bound = (limit * scale).toLong()
        return maxOf(limit, if (blockedMs == null) bound else minOf(bound, blockedMs * 8 / 10))
    }

    fun ms(limit: Int, blockedMs: Long? = null): Long = ms(limit.toLong(), blockedMs)

    fun nanos(limit: Long): Long = (limit * scale).toLong()

    fun seconds(limit: Long): Long = (limit * scale).toLong()

    fun seconds(limit: Double): Double = limit * scale

    /** Ngưỡng đo hiệu năng thật: bỏ qua trừ khi `ABOOK_PERF=1`. */
    fun perf(check: () -> Unit) {
        if (System.getenv("ABOOK_PERF") == "1") check()
    }
}
