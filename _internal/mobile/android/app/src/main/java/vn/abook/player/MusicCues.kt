package vn.abook.player

import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.pow

/**
 * Mốc nhạc của một chương trong mục `music` của book.json (music_plan.package) - phần thuần dữ liệu của [MusicBed], tách riêng để
 * test JVM chạy được (cùng quy tắc với ui/src/listen/musicBed.ts: `stepDbAt`, mục tiêu âm lượng).
 *
 * Mốc: `{start, end, track, gainDb, steps?, sibling?, tail?, audibleStart?, audibleEnd?, loopStart?, loopEnd?}`. `steps` = bước âm lượng trong cảnh
 * `[{at, db}]` (`at` = giây của chương, mức là `gainDb + db`); `sibling` = mốc nối bài anh em ở điểm kết bài trong cùng cảnh (mờ chéo dài hơn); `tail` = mốc kết
 * đúng ở điểm kết bài (bài anh em vào ngay sau, hay bài kết sớm): vòng cuối thôi lặp ([finalLoop]). Máy chủ tính hết, điện thoại
 * chỉ cộng.
 *
 * Lặp (mô hình chung với webui/music_mix.py, lô 2 mix-loop): `audibleStart` A / `audibleEnd` E = đoạn nghe được của bài (thiếu: 0
 * và độ dài thật). E - A >= 3X thì tới loopEnd - X một phần tử MỚI của bài vào từ loopStart, mờ chéo X giây - chu kỳ
 * P = loopEnd - loopStart - X; bài ngắn hơn lặp thường cả file ([loopBounds]). `loopStart` / `loopEnd` = điểm vòng của bài có đoạn kết
 * (danh mục, Corpus/research/music/PLAN_loop.md §10; thiếu hay không hợp lệ thì A / E): vòng cuối của mốc `tail` chơi qua loopEnd tới E.
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
        val loopStart: Double? = null,
        val loopEnd: Double? = null,
    )

    /** Vòng lặp của một bài (giây trong bài): phát trong [start, end), chu kỳ `period`; `crossfade` = lặp mờ chéo (không thì lặp thường
     *  cả file); phần tử lặp mở ở `loopEnd` - X và phát từ `loopStart` (không có điểm vòng: A và E). Chưa biết độ dài lẫn E: end =
     *  period = vô cùng (bài coi như không bao giờ hết). */
    data class Loop(
        val start: Double,
        val end: Double,
        val period: Double,
        val crossfade: Boolean,
        val loopStart: Double = start,
        val loopEnd: Double = end,
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
                cue.optBoolean("tail", false),
                finite(cue, "audibleStart"),
                finite(cue, "audibleEnd"),
                finite(cue, "loopStart"),
                finite(cue, "loopEnd"),
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
        val restart = cue.loopStart?.takeIf { it.isFinite() }
        val out = cue.loopEnd?.takeIf { it.isFinite() }?.let { if (total != null && it - x <= end) minOf(it, total) else it }
        if (restart != null && out != null && start <= restart && restart < out - x && out - x <= end && out - restart - x >= mix.loopMinPeriodSeconds) {
            return Loop(start, end, out - restart - x, true, restart, out)
        }
        return Loop(start, end, end - start - x, true)
    }

    /** Chỗ trong bài (giây) sau `t` >= 0 giây kể từ lúc bài vào từ A (`music_mix.loop_position`): vòng đầu A + t, sau đó
     *  loopStart + ((t - (loopStart - A)) mod P) - không có điểm vòng thì đúng A + (t mod P) như trước. */
    fun loopPosition(bounds: Loop, t: Double): Double {
        if (firstPass(bounds, t)) return bounds.start + t
        return bounds.loopStart + (t - (bounds.loopStart - bounds.start)) % bounds.period
    }

    /** `t` giây kể từ lúc bài vào từ A còn ở vòng đầu (chưa tới loopEnd - X lần nào): [loopPosition] là A + t. */
    fun firstPass(bounds: Loop, t: Double): Boolean =
        !bounds.period.isFinite() || (bounds.crossfade && t < bounds.loopEnd - mix.loopCrossfadeSeconds - bounds.start)

    /** Lúc mở các phần tử lặp và lúc nhạc hết của một mốc dài `length` giây mà bài vào từ A ở giây 0. */
    class Schedule(val opens: List<Double>, val end: Double)

    /** [Schedule] của mốc dài `length` (`music_mix.loop_schedule`): lượt j hết tự nhiên (tới E) ở (E - A) + j·P, phần tử kế mở trước đó
     *  E - loopEnd + X giây. Mốc `tail`: thôi ở lượt đầu tiên mà phần còn lại của mốc hơn chỗ bài hết chưa tới nửa chu kỳ (như
     *  [finalLoop]), nhạc hết ở E của vòng ấy. Lặp thường cả file không mở phần tử nào. */
    fun loopSchedule(bounds: Loop, length: Double, tail: Boolean = false): Schedule {
        var natural = bounds.end - bounds.start
        val lead = bounds.end - bounds.loopEnd + mix.loopCrossfadeSeconds
        val opens = ArrayList<Double>()
        if (tail) {
            while (natural.isFinite() && length - natural >= bounds.period / 2) {
                if (bounds.crossfade) opens.add(natural - lead)
                natural += bounds.period
            }
            return Schedule(opens, natural)
        }
        while (bounds.crossfade && natural - lead < length) {
            opens.add(natural - lead)
            natural += bounds.period
        }
        return Schedule(opens, length)
    }

    /** Chỗ trong bài (giây) ứng với giây `seconds` của chương ([loopPosition] từ đầu mốc) - vào giữa chương hay tua thì nhạc cũng ở
     *  giữa bài (ui/src/listen/musicBed.ts `alignedPosition`, soát a26 L8). */
    fun alignedPosition(cue: Cue, seconds: Double, bounds: Loop): Double =
        loopPosition(bounds, (seconds - cue.start).coerceAtLeast(0.0))

    /** [alignedPosition] tính bằng ms cho ExoPlayer (`durationMs` <= 0: chưa biết độ dài, null). */
    fun offsetMs(cue: Cue, seconds: Double, durationMs: Long): Long? =
        if (durationMs > 0) (alignedPosition(cue, seconds, loopBounds(cue, durationMs / 1000.0)) * 1000).toLong() else null

    /** Phần tử đang kêu ở `currentTime` (giây trong bài) đã tới loopEnd - X: lúc mở phần tử lặp mới từ loopStart. */
    fun loopDue(bounds: Loop, currentTime: Double): Boolean =
        bounds.crossfade && currentTime >= bounds.loopEnd - mix.loopCrossfadeSeconds

    /** Nhịp đồng bộ giọng của điện thoại (Playback gọi [MusicBed.sync] mỗi 500 ms): hẹn giờ vào bản lặp tính theo nhịp này ([loopHandoffDelay]). */
    const val SYNC_TICK_SECONDS = 0.5

    /** Còn dưới chừng này giây tới hạn vào bản lặp thì tạo SẴN bản lặp ([LoopHandoff]): đo thật máy tính, phần tử mới mất 53 ms (bài dài 601 ms) mới có tiếng. */
    const val LOOP_STANDBY_SECONDS = 3.0

    /** Lệch pha (giây) giữa bản lặp mới và bản cũ mà tai không nghe ra: dưới mức này không sửa pha ([loopDrift]). */
    const val LOOP_DRIFT_TOLERANCE_SECONDS = 0.02

    /** Bản mới còn nhỏ hơn tỷ lệ này của âm lượng đích thì dời nó không ai nghe thấy ([loopSettle]). */
    const val LOOP_DRIFT_QUIET = 0.1f

    /** Phần còn lại (giây, nhạc chạy 1x) tới lúc phải mở bản lặp (loopEnd - X) mà bài cũ đang ở `oldPos`, nếu nhỏ hơn 1,5 nhịp đồng bộ
     *  `tickSeconds` (lần đồng bộ kế có thể đến muộn hơn hạn nên phải hẹn giờ); 0 khi đã quá hạn; null khi chưa cần hẹn (hay bài không mờ chéo).
     *  Cùng ca số với ui/src/listen/musicBed.ts `loopHandoffDelay`. */
    fun loopHandoffDelay(bounds: Loop, oldPos: Double, tickSeconds: Double): Double? {
        if (!bounds.crossfade) return null
        val rem = bounds.loopEnd - mix.loopCrossfadeSeconds - oldPos
        if (rem <= 0) return 0.0
        return if (rem < 1.5 * tickSeconds) rem else null
    }

    /** Chỗ bản lặp mới phải vào khi bài cũ đang ở `oldPos`: loopStart cộng phần đã trễ so với hạn loopEnd - X (bù độ trễ của lần đồng bộ). */
    fun loopStartAt(bounds: Loop, oldPos: Double): Double =
        bounds.loopStart + maxOf(0.0, oldPos - (bounds.loopEnd - mix.loopCrossfadeSeconds))

    /** Bản mới đi chậm bao nhiêu giây so với bản cũ (dương = chậm): (cũ - (loopEnd - X)) - (mới - loopStart). Dời bản mới thêm đúng số này
     *  là hai bản cùng pha (bù độ trễ mở trình phát). */
    fun loopDrift(bounds: Loop, oldPos: Double, newPos: Double): Double =
        (oldPos - (bounds.loopEnd - mix.loopCrossfadeSeconds)) - (newPos - bounds.loopStart)

    /** Sửa pha một lần cho bản lặp mới vừa có tiếng: chỗ (giây trong bài) cần dời bản mới tới, hoặc null nếu không cần. Bài cũ đã dừng
     *  (`oldAlive` false) thì không còn gì để theo; bản mới đã to hơn [LOOP_DRIFT_QUIET] của `goal` thì dời sẽ nghe thấy. */
    fun loopSettle(bounds: Loop, oldPos: Double, newPos: Double, newVolume: Float, goal: Float, oldAlive: Boolean): Double? {
        if (!oldAlive || newVolume > LOOP_DRIFT_QUIET * goal) return null
        val drift = loopDrift(bounds, oldPos, newPos)
        return if (abs(drift) > LOOP_DRIFT_TOLERANCE_SECONDS) maxOf(0.0, newPos + drift) else null
    }

    /** Mốc `tail` đang ở vòng cuối (ui/src/listen/musicBed.ts `finalLoop`): phần còn lại của mốc hơn phần còn lại của bài (tới E)
     *  chưa tới nửa chu kỳ - không mở phần tử lặp nữa, bài chơi (qua loopEnd) tới E là hết. Chưa biết độ dài bài: chưa phải. */
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

    /** Tin `sync` đến sau khi sách `closed` đã đóng ([MusicBed.release]): của chính cuốn ấy mà giọng không chạy (tin "dừng" của lệnh tạm dừng) thì bỏ - không dựng lại trình phát nhạc. */
    fun staleAfterClose(closed: String, bookId: String, playing: Boolean): Boolean = closed.isNotEmpty() && bookId == closed && !playing

    /**
     * [toward] cho bài đang mờ VÀO: chưa có tiếng (`ready` = false: bài còn đang tải / đệm, nhất là nghe thẳng từ máy tính qua Wi-Fi) thì giữ nguyên
     * âm lượng - nếu cứ nhích thì mờ vào đã hết trước khi bài kêu, và nhạc nhảy thẳng tới mức khi tải xong. `ready` = trình phát đã có dữ liệu (Player.STATE_READY).
     */
    fun towardWhenReady(volume: Float, goal: Float, perTick: Float, ready: Boolean): Float =
        if (ready) toward(volume, goal, perTick) else volume
}
