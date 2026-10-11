package vn.abook.player

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Độ khuếch đại một mốc nhạc nền - bản Kotlin của `music_plan.cue_gain_db` (abook/webui/music_plan.py), MỘT công thức cho
 * cả hai nền tảng: người nghe đổi mức nhạc của sách đã đóng gói thì `gainDb` từng mốc tính lại ở đây (BookEdits.applyMusic)
 * ra đúng con số người làm sách sẽ ghi. Hằng số phải giữ giống bên Python (BookEditsTest so với `gainDb` trong bộ ví dụ;
 * `VOICE_PLAYED_LUFS` và `SHORT_TERM_FLOOR_LU` thì MusicMixTest so với music_mix.json - chép tay vì sửa sách / hàng danh sách phát
 * chạy cả khi chưa có Context để đọc assets).
 */
object MusicGain {
    const val VOICE_LUFS = -20.0 // giọng mọi chương được chuẩn hoá về mức này (một kênh)
    /** Phát ra hai loa / tai nghe thì BS.1770 cộng hai kênh: +10 log10(2) LU. */
    val VOICE_PLAYED_LUFS = VOICE_LUFS + 10 * Math.log10(2.0)
    /** Đoạn to nhất của bài (p95 độ to ngắn hạn, `s95`) luôn dưới giọng ít nhất bấy nhiêu LU (MIX_QA 3.4). */
    const val SHORT_TERM_FLOOR_LU = 10.0
    const val DEFAULT_TRACK_LUFS = -16.6 // trung vị danh mục: bài chưa có `lufs`
    const val MASKING_CENTER = 0.30 // trung vị `speechBand`: bài lấn dải tiếng nói hơn mức này thì hạ thêm
    const val MASKING_SLOPE_DB = 8.0
    const val MASKING_LIMIT_DB = 6.0

    /** Thiếu `lufs` -> trung vị danh mục; thiếu `speechBand` -> không bù; có `s95` thì không quá VOICE_PLAYED_LUFS -
     *  SHORT_TERM_FLOOR_LU - s95. Kết quả <= 0, làm tròn 2 chữ số như `round(x, 2)`. */
    fun cueGainDb(levelDb: Double, lufs: Double?, speechBand: Double?, s95: Double? = null): Double {
        val loudness = lufs ?: DEFAULT_TRACK_LUFS
        val band = speechBand ?: MASKING_CENTER
        val masking = Math.max(-MASKING_LIMIT_DB, Math.min(MASKING_LIMIT_DB, MASKING_SLOPE_DB * (band - MASKING_CENTER)))
        var gain = VOICE_PLAYED_LUFS + levelDb - loudness - masking
        if (s95 != null) gain = Math.min(gain, VOICE_PLAYED_LUFS - SHORT_TERM_FLOOR_LU - s95)
        gain = Math.min(0.0, gain)
        return BigDecimal(gain).setScale(2, RoundingMode.HALF_EVEN).toDouble()
    }
}
