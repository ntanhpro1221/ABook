package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import java.util.Calendar

/** Mức hẹn giờ người nghe đặt trong Cài đặt: bao lâu tiếng nhỏ dần trước khi dừng, và "Mỗi lần nghe thêm" hẹn lại bao nhiêu phút (khi hẹn theo chương hay vừa tự dừng). */
data class SleepOptions(val fadeSeconds: Int = 30, val extendMinutes: Int = 10)

/**
 * Chữ của hẹn giờ ngủ ngoài nhãn nút (web: listen/PlayerViews.tsx `SleepMenu`, `FadingNotice`, `SleepPicker`): đầu tấm, dòng ghi chú, lời báo sắp tắt.
 * Hàm thuần - thử trên JVM (SleepTextTest).
 */
object SleepText {
    /** Cách nghe thêm trên điện thoại: cú lắc (SleepTimer.kt) hay nút trên thông báo (web: extendGesture.ts, nhánh native). */
    const val GESTURE = S.s_lac_may_hoac_bam_nut_tren_thong_bao_b25ed723

    /** Hẹn giờ vừa tắt tiếng mà chưa quá chừng này thì tấm Hẹn giờ còn mời bật lại (web: 30 phút). */
    const val RECENT_STOP_MS = 30 * 60_000L

    /** Đầu khối đang hẹn: "hết chương" thì "Dừng khi", hẹn phút thì "Tắt sau". */
    fun heading(kind: SleepKind): String = if (kind == SleepKind.Chapter) S.s_dung_khi_f05a4cb5 else S.s_tat_sau_8d10e047

    /** Số lớn của khối đang hẹn khi hẹn theo chương (hẹn phút thì là đồng hồ). */
    const val CHAPTER_END = S.s_het_chuong_nay_8ccc288f

    /** Đầu lưới mức hẹn: đang hẹn thì "Đặt lại", chưa thì "Dừng phát sau". */
    fun gridHeading(active: Boolean): String = if (active) S.s_dat_lai_51a46825 else S.s_dung_phat_sau_41477737

    /** Số phút "Hẹn lại": hẹn phút thì đúng số người nghe đã chọn, hết chương thì "Mỗi lần nghe thêm" (`fallback`). MỘT hàm cho [vn.abook.player.SleepTimer.extend], nút thông báo và nhãn nút. Web: sleep.ts `sleepExtendMinutes`. */
    fun extendMinutes(minutesMode: Boolean, picked: Int, fallback: Int): Int = if (minutesMode && picked > 0) picked else fallback

    fun extendMinutes(sleep: PlayerSleep, options: SleepOptions): Int = extendMinutes(sleep.kind == SleepKind.Minutes, sleep.minutes, options.extendMinutes)

    /** Nhãn nút nghe thêm: đồng hồ về lại N phút, không cộng thêm (web: sleep.ts `sleepExtendLabel`). */
    fun extendLabel(minutes: Int): String = S.s_hen_lai_0_phut_d6009aba(minutes)

    /** Dòng ghi chú cuối tấm. `hadNight`: người nghe đã có một đêm được ghi lại thì nhắc thẻ "Tối qua". */
    fun note(options: SleepOptions, hadNight: Boolean): String =
        // Ghép từ các mảnh như web ghép quanh các giá trị (nhãn đối chiếu với web cắt đúng ở chỗ chèn giá trị).
        S.s_tieng_nho_dan_39149d9b + options.fadeSeconds + S.s_giay_truoc_khi_dung_luc_do_bd65541f + GESTURE + S.s_de_hen_lai_tu_dau_78b355e2 +
            if (hadNight) S.s_sang_hom_sau_the_toi_qua_giup_tim_lai_doan_9c2d2ff0 else ""

    /** Tắt tiếng chưa quá [RECENT_STOP_MS]: tấm Hẹn giờ mời bật lại. */
    fun recentlyStopped(sleep: PlayerSleep, nowMs: Long): Boolean =
        sleep.kind == SleepKind.Off && sleep.stoppedAtMs > 0 && nowMs - sleep.stoppedAtMs in 0 until RECENT_STOP_MS

    fun stoppedAt(stoppedAtMs: Long, zone: java.util.TimeZone = java.util.TimeZone.getDefault()): String {
        val at = Calendar.getInstance(zone).apply { timeInMillis = stoppedAtMs }
        val clock = "%02d:%02d".format(at.get(Calendar.HOUR_OF_DAY), at.get(Calendar.MINUTE))
        return S.s_hen_gio_da_tat_tieng_luc_5d5e4231 + clock + "."
    }

    fun restart(minutes: Int): String = S.s_bat_lai_0bad8bcf + minutes + S.s_phut_cf728a6a

    /** Đang trong đoạn nhỏ dần: đang hẹn, đang phát, và còn chưa tới `fadeSeconds` giây. */
    fun fading(sleep: PlayerSleep, remainingMs: Long, playing: Boolean, options: SleepOptions): Boolean =
        sleep.kind != SleepKind.Off && playing && remainingMs > 0 && remainingMs < options.fadeSeconds * 1000L &&
            (sleep.kind == SleepKind.Chapter || sleep.counting)

    fun fadingLine(minutes: Int): String = S.s_sap_tat_e76c49b1 + GESTURE + S.s_de_hen_lai_f1a3acdc + minutes + S.s_phut_cf728a6a

    const val UNTIL_CHAPTER_END = S.s_se_dung_khi_het_chuong_nay_9c1f8c30
}
