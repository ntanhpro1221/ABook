package vn.abook.player.ui.nowplaying

import java.util.Calendar

/** Mức hẹn giờ người nghe đặt trong Cài đặt: bao lâu tiếng nhỏ dần trước khi dừng, và "Mỗi lần nghe thêm" hẹn lại bao nhiêu phút (khi hẹn theo chương hay vừa tự dừng). */
data class SleepOptions(val fadeSeconds: Int = 30, val extendMinutes: Int = 10)

/**
 * Chữ của hẹn giờ ngủ ngoài nhãn nút (web: listen/PlayerViews.tsx `SleepMenu`, `FadingNotice`, `SleepPicker`): đầu tấm, dòng ghi chú, lời báo sắp tắt.
 * Hàm thuần - thử trên JVM (SleepTextTest).
 */
object SleepText {
    /** Cách nghe thêm trên điện thoại: cú lắc (SleepTimer.kt) hay nút trên thông báo (web: extendGesture.ts, nhánh native). */
    const val GESTURE = "lắc máy hoặc bấm nút trên thông báo"

    /** Hẹn giờ vừa tắt tiếng mà chưa quá chừng này thì tấm Hẹn giờ còn mời bật lại (web: 30 phút). */
    const val RECENT_STOP_MS = 30 * 60_000L

    /** Đầu khối đang hẹn: "hết chương" thì "Dừng khi", hẹn phút thì "Tắt sau". */
    fun heading(kind: SleepKind): String = if (kind == SleepKind.Chapter) "Dừng khi" else "Tắt sau"

    /** Số lớn của khối đang hẹn khi hẹn theo chương (hẹn phút thì là đồng hồ). */
    const val CHAPTER_END = "hết chương này"

    /** Đầu lưới mức hẹn: đang hẹn thì "Đặt lại", chưa thì "Dừng phát sau". */
    fun gridHeading(active: Boolean): String = if (active) "Đặt lại" else "Dừng phát sau"

    /** Số phút "Hẹn lại": hẹn phút thì đúng số người nghe đã chọn (`picked` = 0: không ai chọn, như lưới an toàn ngủ quên), hết chương thì "Mỗi lần nghe thêm" (`fallback`). MỘT hàm cho [vn.abook.player.SleepTimer.extend], nút thông báo và nhãn nút. Web: sleep.ts `sleepExtendMinutes`. */
    fun extendMinutes(minutesMode: Boolean, picked: Int, fallback: Int): Int = if (minutesMode && picked > 0) picked else fallback

    fun extendMinutes(sleep: PlayerSleep, options: SleepOptions): Int = extendMinutes(sleep.kind == SleepKind.Minutes, sleep.minutes, options.extendMinutes)

    /** Nhãn nút nghe thêm: đồng hồ về lại N phút, không cộng thêm (web: sleep.ts `sleepExtendLabel`). */
    fun extendLabel(minutes: Int): String = "Hẹn lại $minutes phút"

    /** Dòng ghi chú cuối tấm. `hadNight`: người nghe đã có một đêm được ghi lại thì nhắc thẻ "Tối qua". */
    fun note(options: SleepOptions, hadNight: Boolean): String =
        // Ghép từ các mảnh như web ghép quanh các giá trị (nhãn đối chiếu với web cắt đúng ở chỗ chèn giá trị).
        "Tiếng nhỏ dần " + options.fadeSeconds + " giây trước khi dừng. Lúc đó " + GESTURE + " để hẹn lại từ đầu." +
            if (hadNight) " Sáng hôm sau, thẻ “Tối qua” giúp tìm lại đoạn còn nhớ." else ""

    /** Tắt tiếng chưa quá [RECENT_STOP_MS]: tấm Hẹn giờ mời bật lại. */
    fun recentlyStopped(sleep: PlayerSleep, nowMs: Long): Boolean =
        sleep.kind == SleepKind.Off && sleep.stoppedAtMs > 0 && nowMs - sleep.stoppedAtMs in 0 until RECENT_STOP_MS

    fun stoppedAt(stoppedAtMs: Long, zone: java.util.TimeZone = java.util.TimeZone.getDefault()): String {
        val at = Calendar.getInstance(zone).apply { timeInMillis = stoppedAtMs }
        val clock = "%02d:%02d".format(at.get(Calendar.HOUR_OF_DAY), at.get(Calendar.MINUTE))
        return "Hẹn giờ đã tắt tiếng lúc " + clock + "."
    }

    fun restart(minutes: Int): String = "Bật lại " + minutes + " phút"

    /** Đang trong đoạn nhỏ dần: đang hẹn, đang phát, và còn chưa tới `fadeSeconds` giây. */
    fun fading(sleep: PlayerSleep, remainingMs: Long, playing: Boolean, options: SleepOptions): Boolean =
        sleep.kind != SleepKind.Off && playing && remainingMs > 0 && remainingMs < options.fadeSeconds * 1000L &&
            (sleep.kind == SleepKind.Chapter || sleep.counting)

    fun fadingLine(minutes: Int): String = "Sắp tắt · " + GESTURE + " để hẹn lại " + minutes + " phút"

    const val UNTIL_CHAPTER_END = "Sẽ dừng khi hết chương này."
}
