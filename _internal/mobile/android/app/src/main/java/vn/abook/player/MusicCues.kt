package vn.abook.player

import org.json.JSONObject
import kotlin.math.pow

/**
 * Mốc nhạc của một chương trong mục `music` của book.json (music_plan.package) - phần thuần dữ liệu của [MusicBed], tách riêng để
 * test JVM chạy được (cùng quy tắc với ui/src/listen/musicBed.ts: `stepDbAt`, mục tiêu âm lượng).
 *
 * Mốc: `{start, end, track, gainDb, steps?, sibling?}`. `steps` = bước âm lượng trong cảnh `[{at, db}]` (`at` = giây của chương,
 * mức là `gainDb + db`); `sibling` = mốc nối bài anh em ở điểm kết bài trong cùng cảnh (mờ chéo dài hơn). Máy chủ tính hết, điện
 * thoại chỉ cộng.
 */
object MusicCues {
    const val FADE_MS = 2000L
    const val SIBLING_FADE_MS = 6000L
    const val STEP_RAMP_MS = 4000L

    // Bài danh mục luôn .mp3; bài người dùng nhập ("Nhạc của tôi") giữ định dạng của file (music_plan.TRACK_EXTENSIONS).
    private val TRACK = Regex("music/[0-9a-f]{40}\\.(?:mp3|m4a|ogg|opus|flac|wav)")

    class Step(val at: Double, val db: Double)

    /** `gainDb`: độ khuếch đại máy chủ đã tính cho bài này (music_plan.cue_gain_db, ghi sẵn vào mốc khi đóng gói); null = sách
     *  xuất bởi bản cũ -> mức chung `levelDb` của cuốn. Máy điện thoại không tự tính lại, chỉ áp con số. */
    data class Cue(
        val start: Double,
        val end: Double,
        val track: String,
        val gainDb: Double?,
        val steps: List<Step> = emptyList(),
        val sibling: Boolean = false,
    )

    /** Các mốc của chương `chapterId` trong `music`; mốc hỏng (bài không có trong `tracks`, tên sai) bị bỏ, bước hỏng bị bỏ. */
    fun of(music: JSONObject?, chapterId: Int?): List<Cue> {
        val tracks = music?.optJSONObject("tracks") ?: return emptyList()
        val list = music.optJSONObject("chapters")?.optJSONArray(chapterId?.toString() ?: return emptyList())
            ?: return emptyList()
        return (0 until list.length()).mapNotNull { index ->
            val cue = list.optJSONObject(index) ?: return@mapNotNull null
            val track = cue.optString("track")
            if (!TRACK.matches(track) || !tracks.has(track)) null
            else Cue(
                cue.optDouble("start", 0.0), cue.optDouble("end", 0.0), track,
                if (cue.has("gainDb")) cue.optDouble("gainDb").takeIf { it.isFinite() } else null,
                stepsOf(cue),
                cue.optBoolean("sibling", false),
            )
        }
    }

    /** Mốc tại giây `seconds`; mốc của bài đang hỏng ([MusicFailures]) tính như khoảng không nhạc - tới hạn thử lại thì lại là mốc. */
    fun at(cues: List<Cue>, seconds: Double, failures: MusicFailures): Cue? =
        cues.firstOrNull { seconds >= it.start && seconds < it.end }?.takeUnless { failures.isFailed(it.track) }

    private fun stepsOf(cue: JSONObject): List<Step> {
        val list = cue.optJSONArray("steps") ?: return emptyList()
        return (0 until list.length()).mapNotNull { index ->
            val step = list.optJSONObject(index) ?: return@mapNotNull null
            val at = step.optDouble("at")
            val db = step.optDouble("db")
            if (at.isFinite() && db.isFinite()) Step(at, db) else null
        }.sortedBy { it.at }
    }

    /** Mức bước (dB) của mốc tại giây `seconds` của chương: bước cuối cùng đã tới, chưa tới bước nào thì 0. */
    fun stepDbAt(cue: Cue, seconds: Double): Double {
        var db = 0.0
        for (step in cue.steps) {
            if (seconds < step.at) break
            db = step.db
        }
        return db
    }

    /** Âm lượng mục tiêu tại giây `seconds`: gainDb của mốc cộng bước đang hiệu lực (<= 0 dB, ExoPlayer tối đa 1); mốc không có
     *  gainDb thì `fallback` (mức chung của cuốn) nhân bước. */
    fun targetGain(cue: Cue, seconds: Double, fallback: Float): Float {
        val step = stepDbAt(cue, seconds)
        return cue.gainDb?.let { 10.0.pow(minOf(0.0, it + step) / 20.0).toFloat() }
            ?: minOf(1f, fallback * 10.0.pow(step / 20.0).toFloat())
    }

    /** Một nhịp dịch âm lượng `volume` về phía `goal`, mỗi nhịp tối đa `perTick`. */
    fun toward(volume: Float, goal: Float, perTick: Float): Float {
        val move = maxOf(perTick, 1e-5f)
        return if (volume < goal) minOf(goal, volume + move) else maxOf(goal, volume - move)
    }
}
