package vn.abook.player

import org.json.JSONObject
import kotlin.math.pow

/**
 * Mốc nhạc của một chương trong mục `music` của book.json (music_plan.package) - phần thuần dữ liệu của [MusicBed], tách riêng để
 * test JVM chạy được (cùng quy tắc với ui/src/listen/musicBed.ts: `stepDbAt`, mục tiêu âm lượng).
 *
 * Mốc: `{start, end, track, gainDb, steps?, sibling?, tail?, audibleStart?, audibleEnd?}`. `steps` = bước âm lượng trong cảnh
 * `[{at, db}]` (`at` = giây của chương, mức là `gainDb + db`); `sibling` = mốc nối bài anh em ở điểm kết bài trong cùng cảnh (mờ chéo dài hơn); `tail` = mốc kết
 * đúng ở điểm kết bài (bài anh em vào ngay sau, hay bài kết sớm): vòng cuối thôi lặp ([finalLoop]). Máy chủ tính hết, điện thoại
 * chỉ cộng.
 *
 * Lặp (mô hình chung với webui/music_mix.py, lô 2 mix-loop): `audibleStart` A / `audibleEnd` E = đoạn nghe được của bài (thiếu: 0
 * và độ dài thật). E - A >= 3X thì tới E - X một phần tử MỚI của bài vào từ A, mờ chéo X giây - chu kỳ P = E - A - X; bài ngắn hơn
 * lặp thường cả file ([loopBounds]).
 */
object MusicCues {
    /** Nhịp trượt âm lượng của [MusicBed]. */
    const val TICK_MS = 50L

    /** Hằng số trộn (music_mix.json): [MusicBed.init] nạp từ assets, test JVM nạp từ file. */
    lateinit var mix: MusicMix

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
        val tail: Boolean = false,
        val audibleStart: Double? = null,
        val audibleEnd: Double? = null,
    )

    /** Vòng lặp của một bài (giây trong bài): phát trong [start, end), chu kỳ `period`; `crossfade` = lặp mờ chéo (không thì lặp thường
     *  cả file). Chưa biết độ dài lẫn E: end = period = vô cùng (bài coi như không bao giờ hết). */
    data class Loop(val start: Double, val end: Double, val period: Double, val crossfade: Boolean)

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
                cue.optBoolean("tail", false),
                finite(cue, "audibleStart"),
                finite(cue, "audibleEnd"),
            )
        }
    }

    /** Mốc tại giây `seconds`; mốc của bài đang hỏng ([MusicFailures]) tính như khoảng không nhạc - tới hạn thử lại thì lại là mốc. */
    fun at(cues: List<Cue>, seconds: Double, failures: MusicFailures): Cue? =
        cues.firstOrNull { seconds >= it.start && seconds < it.end }?.takeUnless { failures.isFailed(it.track) }

    private fun finite(cue: JSONObject, key: String): Double? =
        if (cue.has(key)) cue.optDouble(key).takeIf { it.isFinite() } else null

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

    /** Vòng lặp của bài của mốc `cue`, độ dài thật `durationSeconds` (NaN / <= 0: chưa biết) - music_mix.loop_bounds. */
    fun loopBounds(cue: Cue, durationSeconds: Double): Loop {
        val total = durationSeconds.takeIf { it.isFinite() && it > 0 }
        val start = maxOf(0.0, cue.audibleStart ?: 0.0)
        var end = cue.audibleEnd?.takeIf { it > 0 } ?: total ?: return Loop(0.0, Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY, false)
        if (total != null) end = minOf(end, total)
        val x = mix.loopCrossfadeSeconds
        if (end - start < 3 * x) {
            val whole = total ?: end
            return Loop(0.0, whole, whole, false)
        }
        return Loop(start, end, end - start - x, true)
    }

    /** Chỗ trong bài (giây) ứng với giây `seconds` của chương: A + ((giây - đầu mốc) mod P) - vào giữa chương hay tua thì nhạc cũng
     *  ở giữa bài (ui/src/listen/musicBed.ts `alignedPosition`, soát a26 L8). */
    fun alignedPosition(cue: Cue, seconds: Double, bounds: Loop): Double {
        val offset = (seconds - cue.start).coerceAtLeast(0.0)
        return bounds.start + if (bounds.period.isFinite()) offset % bounds.period else offset
    }

    /** [alignedPosition] tính bằng ms cho ExoPlayer (`durationMs` <= 0: chưa biết độ dài, null). */
    fun offsetMs(cue: Cue, seconds: Double, durationMs: Long): Long? =
        if (durationMs > 0) (alignedPosition(cue, seconds, loopBounds(cue, durationMs / 1000.0)) * 1000).toLong() else null

    /** Phần tử đang kêu ở `currentTime` (giây trong bài) đã tới E - X: lúc mở phần tử lặp mới từ A. */
    fun loopDue(bounds: Loop, currentTime: Double): Boolean =
        bounds.crossfade && currentTime >= bounds.end - mix.loopCrossfadeSeconds

    /** Mốc `tail` đang ở vòng cuối (ui/src/listen/musicBed.ts `finalLoop`): phần còn lại của mốc hơn phần còn lại của bài (tới E)
     *  chưa tới nửa chu kỳ - không mở phần tử lặp nữa, bài chơi tới E là hết. Chưa biết độ dài bài: chưa phải. */
    fun finalLoop(cue: Cue, seconds: Double, currentTime: Double, bounds: Loop): Boolean =
        cue.tail && bounds.end.isFinite() && cue.end - seconds - (bounds.end - currentTime) < bounds.period / 2

    /** Bài đã hết: chơi tới E (phần sau là im) hay `ended`. */
    fun finished(bounds: Loop, currentTime: Double, ended: Boolean): Boolean = ended || currentTime >= bounds.end

    /** Nối bài anh em: bài cũ mờ ra trong siblingFadeSeconds, hay trong phần còn lại thật của nó (tới E) nếu ngắn hơn - không bao
     *  giờ bị cắt khi còn kêu (MIX_QA 3.5). */
    fun siblingFadeSeconds(bounds: Loop, currentTime: Double): Double =
        maxOf(TICK_MS / 1000.0, minOf(mix.siblingFadeMs / 1000.0, bounds.end - currentTime))

    /** Bài đang kêu (`playingTrack`) chơi tiếp cho mốc `next` không: cùng bài, cùng chương. Sang chương mới thì như web (player.tsx
     *  xoá mốc cũ khi đổi chương): bài cũ mờ ra, mốc đầu chương mới mở lại bài ở chỗ căn - kể cả khi cùng bài. */
    fun continues(playingTrack: String?, next: Cue?, newChapter: Boolean): Boolean =
        !newChapter && next != null && next.track == playingTrack

    /** Mốc kế bắt đầu đúng ở cuối mốc `cue` (bài anh em): bài của `cue` kết sớm hơn mốc thì mốc này vào ngay; null = sau `cue` là
     *  quãng lặng (bài kết sớm ở `stopAt`). */
    fun nextAfter(cues: List<Cue>, cue: Cue): Cue? = cues.firstOrNull { it.start == cue.end }

    /** Một nhịp dịch âm lượng `volume` về phía `goal`, mỗi nhịp tối đa `perTick`. */
    fun toward(volume: Float, goal: Float, perTick: Float): Float {
        val move = maxOf(perTick, 1e-5f)
        return if (volume < goal) minOf(goal, volume + move) else maxOf(goal, volume - move)
    }
}
