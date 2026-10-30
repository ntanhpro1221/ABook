package vn.abook.benchmark

import androidx.benchmark.macro.MacrobenchmarkScope

/**
 * Chạm / kéo bằng `input` của shell theo TỈ LỆ màn hình. Lý do: trên ColorOS (OPPO CPH2121) UiAutomator trong tiến trình đo không thấy cửa sổ của app
 * (currentPackageName luôn là launcher, mọi `By.res` rỗng) dù `uiautomator dump` từ shell thấy đủ. Tỉ lệ lấy từ bố cục thật ở 1080x2400; điền ở một chỗ
 * này để mọi kịch bản dùng chung. Thời gian chờ là số cố định (không có cây để hỏi), đủ dài hơn mọi chuyển cảnh (<= 400 ms).
 */
internal object Spot {
    val tabLibrary = 0.167f to 0.955f
    val tabStudio = 0.5f to 0.955f
    val tabSettings = 0.833f to 0.955f
    val firstBook = 0.19f to 0.335f
    val miniOpen = 0.44f to 0.88f
    val collapse = 0.122f to 0.080f
    val modeListen = 0.369f to 0.081f
    val modeRead = 0.633f to 0.081f
    val speed = 0.167f to 0.945f
    val sleep = 0.389f to 0.945f
    const val SEEK_Y = 0.728f
    const val SEEK_LEFT = 0.07f
    const val SEEK_RIGHT = 0.93f
}

internal fun MacrobenchmarkScope.tap(spot: Pair<Float, Float>, settleMs: Long = 700) {
    device.executeShellCommand("input tap ${(spot.first * device.displayWidth).toInt()} ${(spot.second * device.displayHeight).toInt()}")
    Thread.sleep(settleMs)
}

internal fun MacrobenchmarkScope.back(settleMs: Long = 700) {
    device.executeShellCommand("input keyevent KEYCODE_BACK")
    Thread.sleep(settleMs)
}

/** Kéo từ (x0,y0) tới (x1,y1) trong [ms] mili giây; toạ độ theo tỉ lệ. */
internal fun MacrobenchmarkScope.swipe(x0: Float, y0: Float, x1: Float, y1: Float, ms: Int, settleMs: Long = 300) {
    val w = device.displayWidth
    val h = device.displayHeight
    device.executeShellCommand("input swipe ${(x0 * w).toInt()} ${(y0 * h).toInt()} ${(x1 * w).toInt()} ${(y1 * h).toInt()} $ms")
    Thread.sleep(settleMs)
}
