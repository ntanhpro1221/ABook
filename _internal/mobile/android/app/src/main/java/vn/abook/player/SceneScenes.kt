package vn.abook.player

import kotlin.math.ceil
import kotlin.math.max

/** Một đoạn nhạc của chương (music_scenes `_view` ở đường N0: không cảm xúc nên valence / arousal / tension / sd / confidence đều 0). */
class SceneScene(
    val chapterId: Int,
    val firstSegment: Int,
    val lastSegment: Int,
    /** Giây ƯỚC trong chương, làm tròn 3 số (`round(x, 3)` của Python). */
    val start: Double,
    val end: Double,
    /** "chapter_start", "heading", "separator", "time_jump", loại dấu hiệu ("subhead") hay "length". */
    val reason: String,
    val lines: Int,
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

    private class Draft(var first: Int, var last: Int, val reason: String, var seconds: Double)

    fun chapterScenes(chapterId: Int, input: List<SceneSegment>): List<SceneScene> {
        if (input.isEmpty()) return emptyList()
        val segments = SceneCues.withSceneBreaks(input)
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
