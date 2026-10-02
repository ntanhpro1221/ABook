package vn.abook.player

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Độ khuếch đại một mốc nhạc nền - bản Kotlin của `music_plan.cue_gain_db` (abook/webui/music_plan.py), MỘT công thức cho
 * cả hai nền tảng: người nghe đổi mức nhạc của sách đã đóng gói thì `gainDb` từng mốc tính lại ở đây (BookEdits.applyMusic)
 * ra đúng con số người làm sách sẽ ghi. Hằng số phải giữ giống bên Python (BookEditsTest so với `gainDb` trong bộ ví dụ).
 */
object MusicGain {
    const val VOICE_LUFS = -20.0 // giọng mọi chương được chuẩn hoá về mức này (một kênh)
    /** Phát ra hai loa / tai nghe thì BS.1770 cộng hai kênh: +10 log10(2) LU. */
    val VOICE_PLAYED_LUFS = VOICE_LUFS + 10 * Math.log10(2.0)
    const val DEFAULT_TRACK_LUFS = -16.6 // trung vị danh mục: bài chưa có `lufs`
    const val MASKING_CENTER = 0.30 // trung vị `speechBand`: bài lấn dải tiếng nói hơn mức này thì hạ thêm
    const val MASKING_SLOPE_DB = 8.0
    const val MASKING_LIMIT_DB = 6.0

    /** Thiếu `lufs` -> trung vị danh mục; thiếu `speechBand` -> không bù. Kết quả <= 0, làm tròn 2 chữ số như `round(x, 2)`. */
    fun cueGainDb(levelDb: Double, lufs: Double?, speechBand: Double?): Double {
        val loudness = lufs ?: DEFAULT_TRACK_LUFS
        val band = speechBand ?: MASKING_CENTER
        val masking = Math.max(-MASKING_LIMIT_DB, Math.min(MASKING_LIMIT_DB, MASKING_SLOPE_DB * (band - MASKING_CENTER)))
        val gain = Math.min(0.0, VOICE_PLAYED_LUFS + levelDb - loudness - masking)
        return BigDecimal(gain).setScale(2, RoundingMode.HALF_EVEN).toDouble()
    }
}
