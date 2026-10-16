package vn.abook.player

import kotlin.math.ceil
import kotlin.math.max

/**
 * Một đoạn nhạc của chương (music_scenes `_view`). Ở đường N0 không cảm xúc nên valence / arousal / tension / sd / confidence đều 0 và `moodSource` = "labels";
 * học sinh NN-lite ([SceneScenes.applyStudent]) đổi valence / arousal / tension và `moodSource` = "student" (confidence được nâng lên sàn `WEAK_MOOD` ở [SceneBook.chapterScenes]).
 */
data class SceneScene(
    val chapterId: Int,
    val firstSegment: Int,
    val lastSegment: Int,
    /** Giây ƯỚC trong chương, làm tròn 3 số (`round(x, 3)` của Python). */
    val start: Double,
    val end: Double,
    /** "chapter_start", "heading", "separator", "time_jump", loại dấu hiệu ("subhead") hay "length". */
    val reason: String,
    val lines: Int,
    val valence: Double = 0.0,
    val arousal: Double = 0.0,
    val tension: Double = 0.0,
    /** Độ lệch chuẩn các câu trong đoạn theo trục V / E / T (`sd`); N0 và học sinh đều 0. */
    val sdValence: Double = 0.0,
    val sdArousal: Double = 0.0,
    val sdTension: Double = 0.0,
    val confidence: Double = 0.0,
    val moodSource: String = "labels",
    /** Nền của mức chương khi học sinh không có đầu mức chương / khi chương chưa đủ P0 (đường nhãn câu): 0 ở N0. */
    val labelValence: Double = 0.0,
    val labelTension: Double = 0.0,
)

/**
 * Dựng đoạn của một chương - bản Kotlin của `music_scenes.chapter_scenes` ĐƯỜNG N0 (không nhãn cảm xúc, không giờ, không moods / ranh LLM / học sinh):
 * N0_CALLGRAPH.md mục 2.2. Ở N0 mọi câu trung tính nên điểm cảm xúc luôn (0, 0): nhánh `mood_shift` không bao giờ chạy, `_merge_short` hoà điểm
 * (lấy láng giềng ĐẦU: đoạn trước nếu có), `apply_chapter_level` / `apply_student` trả nguyên. Phần còn quyết định: ranh đoạn ([SceneCues.hardBreak]),
 * độ dài đoạn (giây ước theo số ký tự), gộp đoạn ngắn, chia đoạn dài.
 */
object SceneScenes {
    const val MIN_SCENE_SECONDS = 60.0
    const val MAX_SCENE_SECONDS = 180.0
    /** Chương chưa có audio: ước thời lượng đọc theo số ký tự (~15 ký tự/giây). */
    const val UNTIMED_SECONDS_PER_CHAR = 0.065

    /** `_durations` không giờ: `max(0.3, len(text) * 0.065)`, `len` đếm code point (không phải UTF-16). */
    fun durations(segments: List<SceneSegment>): List<Double> =
        segments.map { max(0.3, Py.len(it.text) * UNTIMED_SECONDS_PER_CHAR) }

    // Hằng số của `apply_student` (music_scenes.py): mức V của chương khi học sinh không có đầu mức chương; mức T khi chương không đủ P0 (đường nhãn câu); hệ số hình của học sinh.
    private const val CHAPTER_LEVEL_V_SLOPE = 1.876
    private const val CHAPTER_LEVEL_V_SHIFT = 0.068
    private const val CHAPTER_LEVEL_T_LABELS_SLOPE = 4.022
    private const val CHAPTER_LEVEL_T_LABELS_SHIFT = -0.056
    private const val STUDENT_SHAPE = 1.0

    /**
     * LVJ (Corpus research/music/SPEC_lvj_app.md; `music_scenes.LVJ_COEF`): mức chương chung V / E / T từ `chapterP` = (pV, pE, pT, q) của NN-lite, 5 hàng (pV, pE, pT, q, 1) x 3 cột (V, E, T).
     * Học trên 614 chương dev 16-21 (LLM_Train/music/runs/lvj_frozen.json sha256 7e67114f…). Hằng ĐÓNG BĂNG, không làm tròn, không chỉnh - muốn đổi phải đo lại.
     */
    val LVJ_COEF: Array<DoubleArray> = arrayOf(
        doubleArrayOf(0.6319019445430722, 0.2051738638237541, 0.9174568390927069), // pV
        doubleArrayOf(-0.03336188688214415, 1.2192877795096715, 0.024310404064604645), // pE
        doubleArrayOf(0.23150512513452876, -0.24328311641096767, 0.9916372911166209), // pT
        doubleArrayOf(0.7106786064598247, -0.2348117213659031, -0.8371668420209222), // q
        doubleArrayOf(-0.2581318606640798, -0.2223519284989122, 0.2591515637768544), // 1
    )

    /** `music_scenes.lvj_level`: (L_V, L_E, L_T) = clip(LVJ_COEF^T . [chapterP, 1]), từng trục về [-1, 1]. */
    fun lvjLevel(chapterP: DoubleArray): DoubleArray {
        val row = doubleArrayOf(chapterP[0], chapterP[1], chapterP[2], chapterP[3], 1.0)
        return DoubleArray(3) { column ->
            var sum = 0.0
            for (index in 0 until 5) sum += row[index] * LVJ_COEF[index][column]
            max(-1.0, minOf(1.0, sum))
        }
    }

    /**
     * `music_scenes._shift_to_level`: dời trung bình theo giây (`end - start`) của valence / arousal / tension về `level` (L_V, L_E, L_T) trên giá trị ĐÃ làm tròn của bước student,
     * giữ hình trong chương: `round(clip(out - TB(out) + L), 3)`.
     */
    fun shiftToLevel(scenes: List<SceneScene>, level: DoubleArray): List<SceneScene> {
        val weights = scenes.map { max(0.0, it.end - it.start) }
        var total = 0.0
        for (weight in weights) total += weight
        if (total <= 0) return scenes

        fun shift(values: List<Double>, target: Double): List<Double> {
            var sum = 0.0
            for (index in values.indices) sum += weights[index] * values[index]
            val mean = sum / total
            return values.map { Py.round(max(-1.0, minOf(1.0, it - mean + target)), 3) }
        }

        val valence = shift(scenes.map { it.valence }, level[0])
        val arousal = shift(scenes.map { it.arousal }, level[1])
        val tension = shift(scenes.map { it.tension }, level[2])
        return scenes.mapIndexed { index, scene -> scene.copy(valence = valence[index], arousal = arousal[index], tension = tension[index]) }
    }

    /** `_chapter_p`: `chapterP` (4 số hữu hạn, cùng giá trị ở mọi đoạn) khi MỌI mục có; không thì null (LVJ không chạy: Studio, mục cũ). */
    private fun chapterP(items: List<StudentItem>): DoubleArray? {
        val rows = items.map { it.chapterP ?: return null }
        if (rows.isEmpty() || rows.any { row -> row.size != 4 || row.any { !it.isFinite() } }) return null
        return rows[0]
    }

    /**
     * `music_scenes.apply_student` cho các đoạn của MỘT chương: mức chương như CL (mức V ưu tiên `chapterV` của học sinh), HÌNH trong chương do học sinh đoán:
     * valence = clip(L_V + k (dV - TB(dV))), arousal = clip(TB(arousal) + k (dE - TB(dE))), tension = clip(L_T + k (dT - TB(dT))), k = [STUDENT_SHAPE], TB = trung bình
     * theo giây của đoạn, `round(., 3)`. Điện thoại chỉ có đoạn đường nhãn (không LLM: `moodSource` luôn "labels"), nên mức T luôn theo nhãn (`CHAPTER_LEVEL_T_LABELS`).
     * Khi MỌI mục có `chapterP`, thêm bước LVJ ở cuối ([lvjLevel] + [shiftToLevel]): mức chương V / E / T dời về LVJ_COEF.
     * null (người gọi đi đường N0) khi không có mục cho MỌI đoạn của chương.
     */
    fun applyStudent(scenes: List<SceneScene>, items: List<StudentItem>?): List<SceneScene>? {
        if (scenes.isEmpty() || items.isNullOrEmpty()) return null
        val weights = scenes.map { max(0.0, it.end - it.start) }
        var total = 0.0
        for (weight in weights) total += weight
        if (total <= 0) return null
        val byKey = HashMap<Triple<Int, Int, Int>, StudentItem>()
        for (item in items) byKey[Triple(item.chapterId, item.firstSegment, item.lastSegment)] = item // trùng khoá: mục sau thắng (dict của Python)
        val matched = scenes.map { byKey[Triple(it.chapterId, it.firstSegment, it.lastSegment)] ?: return null }
        val chapterV = chapterLevelV(matched)

        fun mean(values: List<Double>): Double {
            var sum = 0.0
            for (index in values.indices) sum += weights[index] * values[index]
            return sum / total
        }

        fun clip(value: Double): Double = max(-1.0, minOf(1.0, value))

        val levelV = if (chapterV != null) clip(chapterV) else clip(CHAPTER_LEVEL_V_SLOPE * mean(scenes.map { it.labelValence }) + CHAPTER_LEVEL_V_SHIFT)
        val levelT = clip(CHAPTER_LEVEL_T_LABELS_SLOPE * mean(scenes.map { it.labelTension }) + CHAPTER_LEVEL_T_LABELS_SHIFT)
        val levelE = mean(scenes.map { it.arousal })
        val meanDv = mean(matched.map { it.dV })
        val meanDe = mean(matched.map { it.dE })
        val meanDt = mean(matched.map { it.dT })
        val student = scenes.mapIndexed { index, scene ->
            val item = matched[index]
            scene.copy(
                moodSource = "student",
                valence = Py.round(clip(levelV + STUDENT_SHAPE * (item.dV - meanDv)), 3),
                arousal = Py.round(clip(levelE + STUDENT_SHAPE * (item.dE - meanDe)), 3),
                tension = Py.round(clip(levelT + STUDENT_SHAPE * (item.dT - meanDt)), 3),
            )
        }
        val p = chapterP(matched) ?: return student
        return shiftToLevel(student, lvjLevel(p)) // LVJ: bước cuối, chỉ khi MỌI mục có chapterP (`music_scenes._apply_lvj`)
    }

    /** `_chapter_level_v`: `chapterV` (cùng giá trị ở mọi đoạn) khi MỌI mục có và hữu hạn; không thì null (mức V về nhãn câu). */
    private fun chapterLevelV(items: List<StudentItem>): Double? {
        val levels = items.map { it.chapterV ?: return null }
        return levels.firstOrNull()?.takeIf { levels.all { level -> level.isFinite() } }
    }

    private class Draft(var first: Int, var last: Int, val reason: String, var seconds: Double)

    /** `boundaries`: ranh giới tính sẵn ngoài chương theo nguồn ({"lite": {id: "mood_shift"}} của LB, [NnLite.sceneBounds]); xem [SceneCues.withSceneBreaks]. */
    fun chapterScenes(chapterId: Int, input: List<SceneSegment>, boundaries: Map<String, Map<Int, String>> = emptyMap()): List<SceneScene> {
        if (input.isEmpty()) return emptyList()
        val segments = SceneCues.withSceneBreaks(input, boundaries)
        val seconds = durations(segments)
        val timeline = ArrayList<Double>(segments.size)
        var clock = 0.0
        for (length in seconds) {
            timeline.add(clock)
            clock += length
        }

        val scenes = ArrayList<Draft>()
        var current = Draft(0, 0, "chapter_start", 0.0)
        for (index in segments.indices) {
            val reason = if (index > 0) SceneCues.hardBreak(segments[index], segments[index - 1]) else null
            if (!reason.isNullOrEmpty() && current.seconds > 0) {
                scenes.add(current)
                current = Draft(index, index, reason, 0.0)
            }
            current.seconds += seconds[index]
            current.last = index
        }
        scenes.add(current)
        return splitLong(mergeShort(scenes), seconds).map { scene ->
            SceneScene(
                chapterId, segments[scene.first].id, segments[scene.last].id,
                Py.round(timeline[scene.first], 3), Py.round(timeline[scene.last] + seconds[scene.last], 3),
                scene.reason, scene.last - scene.first + 1,
            )
        }
    }

    /**
     * `_merge_short`: đoạn ngắn hơn MIN_SCENE_SECONDS gộp vào đoạn kề; điểm cảm xúc luôn hoà (0, 0) nên láng giềng đầu danh sách thắng:
     * `index - 1` nếu có, không thì `index + 1`. Gộp vào đoạn trước thì đoạn trước giữ `reason`; gộp với đoạn sau (đoạn đầu) thì đoạn đang xét giữ.
     * Lặp lại từ đầu sau mỗi lần gộp. Giây cộng dồn theo đúng thứ tự (đoạn trước + đoạn sau).
     */
    private fun mergeShort(scenes: List<Draft>): List<Draft> {
        val merged = ArrayList(scenes)
        var changed = true
        while (changed && merged.size > 1) {
            changed = false
            for (index in merged.indices) {
                val scene = merged[index]
                if (scene.seconds >= MIN_SCENE_SECONDS) continue
                val target = if (index - 1 >= 0) index - 1 else index + 1
                val keep: Draft
                val drop: Draft
                if (target < index) { keep = merged[target]; drop = scene } else { keep = scene; drop = merged[target] }
                keep.seconds += drop.seconds
                val first = minOf(keep.first, drop.first)
                val last = max(keep.last, drop.last)
                keep.first = first
                keep.last = last
                merged.removeAt(if (drop === scene) index else target)
                changed = true
                break
            }
        }
        return merged
    }

    /**
     * `_split_long`: đoạn dài hơn MAX_SCENE_SECONDS chia `ceil(tổng / 180)` phần đều theo giây, cắt ở câu đầu tiên làm đồng hồ >= tổng / số phần;
     * mảnh sau mảnh đầu có `reason` = "length". `tổng` cộng lần lượt từng câu (sum() của Python 3.11, không bù sai số).
     */
    private fun splitLong(scenes: List<Draft>, seconds: List<Double>): List<Draft> {
        val out = ArrayList<Draft>()
        for (scene in scenes) {
            val first = scene.first
            val last = scene.last
            var total = 0.0
            for (index in first..last) total += seconds[index]
            val parts = ceil(total / MAX_SCENE_SECONDS).toInt()
            if (parts <= 1) {
                out.add(scene)
                continue
            }
            val target = total / parts
            var start = first
            var piece = 0.0
            for (index in first..last) {
                piece += seconds[index]
                if (piece >= target && index < last) {
                    out.add(Draft(start, index, if (start == first) scene.reason else "length", 0.0))
                    start = index + 1
                    piece = 0.0
                }
            }
            if (start <= last) out.add(Draft(start, last, if (start == first) scene.reason else "length", 0.0))
        }
        return out
    }
}
