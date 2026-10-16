package vn.abook.player

import org.json.JSONObject
import java.security.MessageDigest
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/** Một bài của danh mục (mục trong `cells/<v>_<a>.json`, hay mảnh `tracks/<xx>.json`) - phần `music_select` đọc. */
class SceneTrack(
    val link: String,
    val valence: Double,
    val arousal: Double,
    /** null: danh mục cũ chưa có trục căng thẳng (bỏ trục ấy khỏi khoảng cách). */
    val tension: Double?,
    val style: String?,
    val family: String?,
    val background: Double?,
    val source: String?,
    val duration: Double?,
    /** Độ dài thật đo bởi danh mục (chỉ mảnh `tracks/`); ô `cells/` không có. */
    val seconds: Double? = null,
    val audibleStart: Double? = null,
    val audibleEnd: Double? = null,
) {
    companion object {
        private fun number(json: JSONObject, key: String): Double? =
            if (json.has(key) && !json.isNull(key)) (json.opt(key) as? Number)?.toDouble()?.takeIf { it.isFinite() } else null

        private fun text(json: JSONObject, key: String): String? =
            if (json.has(key) && !json.isNull(key)) (json.opt(key) as? String) else null

        /** Mục danh mục -> bài; thiếu `link` / `valence` / `arousal` thì null (Python sẽ văng KeyError ở `float(track["valence"])`: bài hỏng không dùng). */
        fun of(json: JSONObject): SceneTrack? {
            val link = text(json, "link")?.takeIf { it.isNotEmpty() } ?: return null
            return SceneTrack(
                link, number(json, "valence") ?: return null, number(json, "arousal") ?: return null, number(json, "tension"),
                text(json, "style"), text(json, "family"), number(json, "background"), text(json, "source"), number(json, "duration"),
                number(json, "seconds"), number(json, "audibleStart"), number(json, "audibleEnd"),
            )
        }
    }
}

class SceneSibling(val at: Double, val link: String)

/** Đoạn kèm bài đã chọn (`music_select.choose`): cùng tên trường với plan Python. */
class ChosenScene(val scene: SceneScene) {
    var key: String = ""
    var pinned = false
    /** null = im lặng (hay chưa có bài đủ gần). */
    var link: String? = null
    var distance: Double? = null
    var continued = false
    var silenced = false
    var pinUnavailable = false
    var stepDb: Double? = null
    var stopAt: Double? = null
    val siblings = ArrayList<SceneSibling>()
}

/** Lựa chọn của người nghe / cuốn cho một lượt chọn nhạc (`music_plan.read_overrides`); mặc định = sách chưa sửa gì. */
class SceneChoice(
    /** Mã sách: hoà điểm tất định theo `sha1("{bookKey}|{link}")`. Máy tính dùng mã sách của thư viện. */
    val bookKey: String,
    val family: String? = null,
    /** `taxonomy.genres[genre].styles` (null khi chưa chọn thể loại). */
    val genreStyles: Map<String, Double>? = null,
    val pins: Map<String, String> = emptyMap(),
    val banned: Set<String> = emptySet(),
    val silenced: Set<String> = emptySet(),
    /** Bài dùng được TRÊN MÁY NÀY không (null = bài nào cũng dùng được). */
    val available: ((String) -> Boolean)? = null,
    /** Thông tin bài ghim / bài không đi qua xếp hạng (null = không biết). */
    val trackInfo: ((String) -> SceneTrack?)? = null,
)

/**
 * Chọn bài cho các đoạn - bản Kotlin của `music_select.choose` / `rank` / `score` / `z_distance` (N0_CALLGRAPH.md mục 3), main a41b70bc, mở rộng cho đoạn của học sinh NN-lite.
 *
 * Ở N0 mọi câu trung tính nên MỌI đoạn có cùng đích `(.15, -.55, tension 0)` (`CALM_TARGET` vì confidence 0 < `WEAK_MOOD`) và `scene_sigma` .35 ở cả ba trục
 * ([TARGET], [SIGMA]). Đoạn của học sinh ([SceneScenes.applyStudent], confidence = sàn `WEAK_MOOD`) có đích riêng V / E / T: [targetOf] / [sceneSigma] tính từ chính đoạn
 * (`target_of` / `scene_sigma`), `candidatesNear(v, a)` hỏi bài quanh đích ấy. Giữ nguyên MỌI cách hoà - thứ tự ô của `near` rồi thứ tự bài trong ô, sắp ổn định,
 * `min` lấy bài đứng trước, `_tiebreak` theo mã sách, phạt bài vừa dùng / bài ngắn / bài anh em, ghim, bỏ, im lặng, họ nhạc, thể loại.
 * Không có `keep` / `kept_siblings` (đó là cơ chế sửa MỘT đoạn của Studio): lượt chọn chạy liền từ đầu cuốn, hay từ chương bất kỳ với `recent` cho trước.
 * Số học làm đúng thứ tự phép tính của Python; `x ** 2` viết `x * x` (khác 1 ulp ở ~0,05% giá trị trên Windows nhờ pow của MSVC - vô hình sau `round(., 3)`).
 */
class SceneChooser(
    private val choice: SceneChoice,
    private val candidatesNear: (Double, Double) -> List<SceneTrack>,
) {
    private val known = HashMap<String, SceneTrack?>()
    private val askedAvailable = HashMap<String, Boolean>()

    /** Bài đã gặp trong lượt chọn này (xếp hạng hay thông tin ghim) - độ dài / đoạn nghe được của nó cho vòng lặp; null = chưa biết. */
    fun trackOf(link: String): SceneTrack? = known[link]

    private fun usable(link: String?): Boolean {
        if (link == null || choice.available == null) return true
        return askedAvailable.getOrPut(link) { choice.available.invoke(link) }
    }

    private fun info(link: String): SceneTrack? {
        if (link !in known) known[link] = choice.trackInfo?.invoke(link)
        return known[link]
    }

    private fun ranked(
        scene: SceneScene, recent: List<String>, limit: Int, exclude: Set<String> = emptySet(),
    ): List<Pair<SceneTrack, Double>> {
        val found = rank(scene, recent, limit, exclude)
        for ((track, _) in found) if (track.link !in known) known[track.link] = track
        return found
    }

    /** `rank`: bài thay thế cho MỘT đoạn, tốt nhất trước. Mỗi mục: (bài, điểm đã `round(., 3)`). */
    fun rank(scene: SceneScene, recent: List<String>, limit: Int, exclude: Set<String> = emptySet()): List<Pair<SceneTrack, Double>> {
        val window = if (recent.size > RECENT_SCENES) recent.subList(recent.size - RECENT_SCENES, recent.size) else recent
        val ceiling = MAX_Z + (if (choice.family != null && choice.family.isNotEmpty()) FAMILY_PENALTY else 0.0)
        val ordered = ArrayList<Pair<Double, SceneTrack>>()
        val seen = HashSet<String>()
        val (valence, arousal) = targetOf(scene)
        val target = doubleArrayOf(valence, arousal, scene.tension)
        val sigma = sceneSigma(scene)
        for (track in candidatesNear(target[0], target[1])) {
            val link = track.link
            if (link.isEmpty() || link in seen || link in choice.banned || link in exclude) continue
            if (choice.available != null && !usable(link)) continue
            seen.add(link)
            if ((track.duration ?: 0.0).toLong() < MIN_TRACK_SECONDS || styleFit(track) <= 0.0) continue
            var value = score(track, target, sigma)
            value += tiebreak(choice.bookKey, link)
            if (value <= ceiling) { // ngưỡng im lặng chỉ tính khoảng cách + phạt; "vừa dùng" chỉ xếp hạng
                value += recentPenalty(link, window)
                ordered.add((value - EMOTION_WEIGHT * 0.0) to track)
            }
        }
        val sorted = ordered.sortedBy { it.first } // sắp ổn định: hoà giữ thứ tự gặp
        return sorted.take(limit).map { (value, track) -> track to Py.round(value, 3) }
    }

    private fun styleFit(track: SceneTrack): Double {
        val styles = choice.genreStyles
        if (styles.isNullOrEmpty()) return 1.0
        val style = track.style
        return if (!style.isNullOrEmpty()) (styles[style] ?: 0.0) else 0.5
    }

    private fun score(track: SceneTrack, target: DoubleArray, sigma: DoubleArray): Double {
        val distance = zDistance(track, target, sigma)
        var penalty = 0.0
        if (styleFit(track) < 1.0) penalty += STYLE_HALF_PENALTY
        val family = choice.family
        if (!family.isNullOrEmpty() && track.family != family) penalty += FAMILY_PENALTY
        val background = track.background
        if (background != null && track.source != "incompetech") penalty += FOREGROUND_PENALTY * (1.0 - background)
        return distance + penalty
    }

    /**
     * Lượt chọn cho các đoạn của MỘT hay nhiều chương liền nhau (theo thứ tự chương). `recent` = link các bài đã chơi ở các đoạn trước (cũ trước, mới
     * sau; cửa sổ [RECENT_SCENES]) - truyền vào để chọn tiếp một chương sau các chương trước; được cập nhật tại chỗ.
     */
    fun choose(scenes: List<SceneScene>, recent: MutableList<String> = ArrayList()): List<ChosenScene> {
        val tailMinSeconds = MusicCues.mix.tailMinSeconds
        val cueMergeGapSeconds = MusicCues.mix.cueMergeGapSeconds
        val heads = sceneHeads(scenes)
        val lengths = HashMap<Int, Double>()
        val runEnd = HashMap<Int, Double>()
        for ((index, head) in heads.withIndex()) {
            lengths[head] = (lengths[head] ?: 0.0) + seconds(scenes[index])
            runEnd[head] = max(runEnd[head] ?: Double.NEGATIVE_INFINITY, scenes[index].end)
        }

        val chosen = ArrayList<ChosenScene>()
        var used = HashSet<String>()
        var playing: String? = null
        var position = 0.0
        var headTension = 0.0
        var stopped = -1
        var ended: String? = null
        for ((index, scene) in scenes.withIndex()) {
            if (index == 0 || scene.chapterId != scenes[index - 1].chapterId) {
                used = HashSet(); playing = null; position = 0.0; stopped = -1; ended = null
            }
            val key = sceneKey(scene)
            val result = ChosenScene(scene).also { it.key = key }
            val pins = choice.pins
            val pinDown = key in pins && !usable(pins[key])
            val follows = heads[index] != index && playing != null
            if (key in pins && !pinDown) {
                result.link = pins[key]; result.pinned = true; result.distance = null
            } else if (key in choice.silenced) {
                result.link = null; result.distance = null; result.silenced = true
            } else if (heads[index] == stopped) {
                result.link = null; result.distance = null; result.continued = true
            } else if (follows) {
                result.link = playing; result.distance = null; result.continued = true
            } else {
                // Đầu cảnh: cùng cách xếp hạng với "Đổi bài", thêm phạt bài ngắn hơn cảnh; tránh bài đang chơi, bài vừa kết và bài ghim của đoạn kế.
                val want = min(lengths.getValue(heads[index]), SCENE_LENGTH_CAP)
                val ahead = if (index + 1 < scenes.size && heads[index + 1] == index + 1) scenes[index + 1] else null
                val after = if (ahead != null && ahead.chapterId == scene.chapterId) sceneKey(ahead) else null
                val avoid = HashSet<String>()
                playing?.let { avoid.add(it) }
                ended?.let { avoid.add(it) }
                if (after != null) pins[after]?.takeIf { it.isNotEmpty() }?.let { avoid.add(it) }
                var options = if (avoid.isNotEmpty()) ranked(scene, recent, HEAD_CANDIDATES, avoid) else emptyList()
                if (options.isEmpty()) options = ranked(scene, recent, HEAD_CANDIDATES)
                var best: Pair<SceneTrack, Double>? = null
                var bestKey = 0.0
                for (option in options) {
                    val rankKey = option.second + SHORT_TRACK_PENALTY * shortfall(option.first, want)
                    if (best == null || rankKey < bestKey) { best = option; bestKey = rankKey }
                }
                result.link = best?.first?.link
                result.distance = best?.second
            }
            if (pinDown) result.pinUnavailable = true
            val link = result.link
            val carried = link != null && link == playing
            if (result.continued) {
                // Ở N0 tension của mọi đoạn là 0 nên bước âm lượng luôn 0; đoạn của học sinh nhích theo tension của nó so với đầu cảnh.
                result.stepDb = max(-STEP_MAX_DB, min(STEP_MAX_DB, STEP_DB_PER_TENSION * (scene.tension - headTension)))
            } else {
                if (link != playing) { playing = link; position = 0.0 }
                ended = null
                headTension = scene.tension
            }
            // Bài chạy qua mảnh này theo đồng hồ chương: hết một vòng thì nối bài anh em, không có thì lặp.
            val start = scene.start
            val gap = if (index > 0) start - scenes[index - 1].end else 0.0
            if (carried && gap >= cueMergeGapSeconds) position = 0.0
            val clock = if (carried && 0.0 < gap && gap < cueMergeGapSeconds) start - gap else start
            val length = seconds(scene) + start - clock
            var elapsed = 0.0
            while (playing != null && length - elapsed > 1e-9) {
                val (trackSeconds, period) = loop(playing)
                val step = min(length - elapsed, trackSeconds - position)
                position += step
                elapsed += step
                if (position < trackSeconds - 1e-9) continue
                val now = clock + elapsed
                if (runEnd.getValue(heads[index]) - now < tailMinSeconds) {
                    result.stopAt = Py.round(now, 3)
                    ended = playing
                    playing = null
                    stopped = heads[index]
                    break
                }
                val exclude = HashSet(used)
                exclude.add(playing)
                val sibling = sibling(info(playing), ranked(scene, recent, SIBLING_CANDIDATES, exclude))
                position = if (sibling != null) 0.0 else trackSeconds - period // lặp: phần tử mới đã chơi X giây (lặp thường: 0)
                if (sibling != null) {
                    playing = sibling
                    used.add(sibling)
                    result.siblings.add(SceneSibling(Py.round(max(start, now), 3), sibling))
                }
            }
            if (link != null) {
                used.add(link)
                // Đoạn kề chọn trúng bài đang chơi: chơi tiếp, không phải bài "mới".
                if (recent.isEmpty() || recent.last() != link) recent.add(link)
            }
            chosen.add(result)
        }
        holdSteps(chosen)
        return chosen
    }

    /** (giây từ A tới E, chu kỳ lặp) của bài theo đoạn nghe được (`music_mix.loop_bounds`); chưa biết độ dài thì bài không bao giờ hết. */
    private fun loop(link: String): Pair<Double, Double> {
        val track = info(link)
        val bounds = MusicTimeline.loopBounds(
            MusicTimeline.TrackInfo(track?.seconds?.takeIf { it != 0.0 } ?: track?.duration, track?.audibleStart, track?.audibleEnd),
        )
        return (bounds.end - bounds.start) to bounds.period
    }

    companion object {
        const val MAX_Z = 2.0
        const val TAU = 0.1
        const val SCENE_SD_DEFAULT = 0.25
        const val TRACK_SD_DEFAULT = 0.2
        const val UNCERTAIN_SD = 0.35
        const val EMOTION_WEIGHT = 0.0
        const val RECENT_SCENES = 100
        const val MIN_TRACK_SECONDS = 60
        const val WEAK_MOOD = 0.2
        const val SIBLING_Z = 0.8
        const val SHORT_TRACK_PENALTY = 1.0
        const val SCENE_LENGTH_CAP = 900.0
        const val HEAD_CANDIDATES = 30
        const val SIBLING_CANDIDATES = 50
        const val STEP_DB_PER_TENSION = 6.0
        const val STEP_MAX_DB = 3.0
        const val STEP_HOLD_SECONDS = 40.0

        // AXIS_WEIGHTS theo thứ tự khoá của Python: arousal, tension, valence (thứ tự CỘNG là valence, arousal, tension - xem [zDistance]).
        private const val W_AROUSAL = 1.0
        private const val W_TENSION = 0.8
        private const val W_VALENCE = 0.6

        val PENALTY_UNIT: Double = sqrt(SCENE_SD_DEFAULT * SCENE_SD_DEFAULT + TRACK_SD_DEFAULT * TRACK_SD_DEFAULT + TAU * TAU)
        val STYLE_HALF_PENALTY: Double = 0.3 / PENALTY_UNIT
        val FAMILY_PENALTY: Double = 0.35 / PENALTY_UNIT
        val FOREGROUND_PENALTY: Double = 0.25 / PENALTY_UNIT
        val RECENT_PENALTY: Double = 0.3 / PENALTY_UNIT

        private const val CALM_VALENCE = 0.15
        private const val CALM_AROUSAL = -0.55

        /** `target_of`: điểm (valence, arousal) cần tìm nhạc; đoạn không có không khí rõ (confidence < `WEAK_MOOD`) thì kéo về nền êm nhẹ. */
        fun targetOf(scene: SceneScene): Pair<Double, Double> {
            if (scene.confidence >= WEAK_MOOD) return scene.valence to scene.arousal
            val weight = scene.confidence / WEAK_MOOD
            return (weight * scene.valence + (1 - weight) * CALM_VALENCE) to (weight * scene.arousal + (1 - weight) * CALM_AROUSAL)
        }

        /** `scene_sigma`: độ không chắc của đoạn trên (valence, arousal, tension) = `hypot(sd trục, UNCERTAIN_SD * (1 - confidence))`. */
        fun sceneSigma(scene: SceneScene): DoubleArray {
            val extra = UNCERTAIN_SD * (1.0 - max(0.0, min(1.0, scene.confidence)))
            return doubleArrayOf(Math.hypot(scene.sdValence, extra), Math.hypot(scene.sdArousal, extra), Math.hypot(scene.sdTension, extra))
        }

        private val CALM_SCENE = SceneScene(0, 0, 0, 0.0, 0.0, "", 0)

        /** `(*target_of(scene), tension)` của đoạn N0 (confidence 0, tension 0). */
        val TARGET: DoubleArray = targetOf(CALM_SCENE).let { doubleArrayOf(it.first, it.second, 0.0) }

        /** `scene_sigma` của đoạn N0: `hypot(sd = 0, UNCERTAIN_SD * (1 - 0))`. */
        val SIGMA: DoubleArray = sceneSigma(CALM_SCENE)

        /** `z_distance`: khoảng cách đoạn - bài trên ba trục chia độ không chắc; cộng theo thứ tự valence, arousal, tension. */
        fun zDistance(track: SceneTrack, target: DoubleArray, sigma: DoubleArray? = null): Double {
            val s = sigma ?: doubleArrayOf(SCENE_SD_DEFAULT, SCENE_SD_DEFAULT, SCENE_SD_DEFAULT)
            var total = 0.0
            var diff = track.valence - target[0]
            total += W_VALENCE * (diff * diff) / (s[0] * s[0] + TRACK_SD_DEFAULT * TRACK_SD_DEFAULT + TAU * TAU)
            diff = track.arousal - target[1]
            total += W_AROUSAL * (diff * diff) / (s[1] * s[1] + TRACK_SD_DEFAULT * TRACK_SD_DEFAULT + TAU * TAU)
            val tension = track.tension
            if (target.size > 2 && tension != null) {
                diff = tension - target[2]
                total += W_TENSION * (diff * diff) / (s[2] * s[2] + TRACK_SD_DEFAULT * TRACK_SD_DEFAULT + TAU * TAU)
            }
            return sqrt(total)
        }

        /** `_tiebreak`: hoà điểm tất định theo mã sách. */
        fun tiebreak(bookKey: String, link: String): Double {
            val digest = MessageDigest.getInstance("SHA-1").digest("$bookKey|$link".toByteArray(Charsets.UTF_8))
            val first = digest.take(4).fold(0L) { acc, byte -> (acc shl 8) or (byte.toLong() and 0xFF) }
            return first.toDouble() / 4294967295.0 * 1e-3
        }

        /** `recent_penalty`: bài đã dùng trong cửa sổ bị phạt RECENT_PENALTY x (1 + vị trí lần dùng gần nhất / độ dài cửa sổ). */
        fun recentPenalty(link: String, recent: List<String>): Double {
            for (index in recent.indices.reversed()) {
                if (recent[index] == link) return RECENT_PENALTY * (1.0 + (index + 1).toDouble() / recent.size)
            }
            return 0.0
        }

        fun sceneKey(scene: SceneScene): String = "${scene.chapterId}:${scene.firstSegment}"

        /** `scene_heads`: vị trí đoạn ĐẦU CẢNH của từng đoạn (mảnh "length" thuộc cảnh của đoạn trước, cùng chương). */
        fun sceneHeads(scenes: List<SceneScene>): List<Int> {
            val heads = ArrayList<Int>(scenes.size)
            for ((index, scene) in scenes.withIndex()) {
                val sameChapter = index > 0 && scene.chapterId == scenes[index - 1].chapterId
                heads.add(if (sameChapter && scene.reason == "length") heads[index - 1] else index)
            }
            return heads
        }

        private fun seconds(scene: SceneScene): Double = max(0.0, scene.end - scene.start)

        /** `_shortfall`: phần cảnh (độ dài `want`) mà bài không phủ nổi trong một vòng. */
        private fun shortfall(track: SceneTrack, want: Double): Double {
            if (want <= 0) return 0.0
            val duration = track.duration ?: 0.0
            val length = if (duration != 0.0) duration else want
            return max(0.0, 1.0 - length / want)
        }

        /** `_sibling`: bài anh em của bài đang chơi - bài đầu tiên (theo xếp hạng cho mảnh này) cách bài ấy không quá SIBLING_Z. */
        private fun sibling(current: SceneTrack?, candidates: List<Pair<SceneTrack, Double>>): String? {
            if (current == null) return null
            val target = doubleArrayOf(current.valence, current.arousal, current.tension ?: 0.0)
            return candidates.firstOrNull { zDistance(it.first, target) <= SIBLING_Z }?.first?.link
        }

        /** `_hold_steps`: bước âm lượng cách bước trước (trong cùng cảnh) chưa đủ STEP_HOLD_SECONDS thì giữ mức trước; đầu cảnh về 0. */
        private fun holdSteps(chosen: List<ChosenScene>) {
            var lastAt = Double.NEGATIVE_INFINITY
            var lastDb = 0.0
            for (scene in chosen) {
                val start = scene.scene.start
                if (!scene.continued) { lastAt = start; lastDb = 0.0; continue }
                val db = scene.stepDb ?: 0.0
                if (start - lastAt < STEP_HOLD_SECONDS) scene.stepDb = lastDb
                else if (db != lastDb) { lastAt = start; lastDb = db }
                scene.stepDb = Py.round(scene.stepDb ?: 0.0, 2)
            }
        }
    }
}
